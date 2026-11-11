#!/usr/bin/env python3
"""Inspect recovered tables/calibrations and propose late-1998 control runs.

Produces diagnostic evidence only: it does not configure Geant4, apply detector
calibrations, alter run policy, or claim a validated charged-particle sample.
"""
import argparse
from collections import Counter
import csv
import hashlib
import io
import json
from pathlib import Path
import sys

# Like the transport launcher, this command runs directly from a source checkout.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from legacy_tables import read_channel_matrix
from legacy_calibration import read_1998_calibration
from calibration.run_quality import load_run_quality

ROOT = Path(__file__).resolve().parents[2]
OBSERVABLES = ('Dedx_track', 'Eclusc_track', 'Tof_trf', 'De_trf')


def sha256(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(chunk)
    return result.hexdigest()


def inspect_control(path):
    import numpy as np
    import uproot

    path = Path(path).resolve()
    initial = path.stat()
    digest = sha256(path)
    counts = Counter()
    with uproot.open(path) as handle:
        tree = handle['h70']
        missing = sorted(set(OBSERVABLES) - set(tree.keys()))
        for arrays in tree.iterate(['Idrun'], step_size='32 MB', library='np'):
            runs = arrays['Idrun']
            if runs.ndim != 1 or not np.all(np.isfinite(runs) & (runs > 0) & (runs == np.floor(runs))):
                raise ValueError(f'Invalid run identities in {path}')
            values, occurrences = np.unique(runs, return_counts=True)
            counts.update({int(run): int(count) for run, count in zip(values, occurrences)})
        identity = str(handle.file.uuid)
        entries = tree.num_entries
    final = path.stat()
    if (initial.st_size, initial.st_mtime_ns) != (final.st_size, final.st_mtime_ns):
        raise ValueError(f'Control ROOT changed during inspection: {path}')
    return {'path': str(path), 'sha256': digest, 'root_uuid': identity, 'tree': 'h70',
            'entries': entries, 'events_by_run': dict(sorted(counts.items())),
            'missing_branches': missing,
            'status': 'missing_observables' if missing else 'observables_present_unvalidated'}


def propose_controls(events_by_run, calibrated_runs, excluded_runs):
    eligible = sorted(run for run, count in events_by_run.items()
                      if count > 0 and run in calibrated_runs and run not in excluded_runs)
    return {'status': 'proposed_unvalidated' if len(eligible) >= 2 else 'needs_independent_runs',
            'tuning_runs': eligible[::2], 'validation_runs': eligible[1::2],
            'selection': 'sorted eligible run IDs alternated; no particle cuts or tuning performed',
            'limits': 'Presence only; purity, trigger and detector response remain unvalidated.'}


def write_inspection(data_dir, catalog, policy_path, control_roots, output):
    output, data_dir, catalog = Path(output), Path(data_dir), Path(catalog)
    if output.exists():
        raise FileExistsError(f'Output exists; refusing overwrite: {output}')
    matrix_path = data_dir / 'inp_laggen/channel.mat'
    table = read_channel_matrix(matrix_path)
    catalog_bytes = catalog.read_bytes()
    rows = [row for row in csv.DictReader(io.StringIO(catalog_bytes.decode('utf-8')))
            if row['source_period'] == '1998_uv']
    runs = [int(row['run_number']) for row in rows]
    if (not rows or len(set(runs)) != len(runs)
            or any(row['target'] != 'P' or row['beam_type'] != 'UV' for row in rows)):
        raise ValueError('Expected unique 1998_uv proton/UV runs in catalog')
    policy = load_run_quality(policy_path)
    excluded = {row['run'] for row in policy['excluded_runs']}
    calibration_records, ready = [], set()
    for run in sorted(runs):
        try:
            constants = read_1998_calibration(data_dir, run)
        except ValueError as error:
            calibration_records.append({'run': run, 'status': 'invalid_or_missing', 'error': str(error)})
            continue
        ready.add(run)
        calibration_records.append({
            'run': run, 'status': constants['status'], 'sources': constants['sources'],
            'bgo_source_range': [min(constants['bgo_source_constants']), max(constants['bgo_source_constants'])],
            'bgo_pedestal_range': [min(constants['bgo_pedestal_by_readout']), max(constants['bgo_pedestal_by_readout'])],
            'strip_edge': constants['strip_edge'], 'excluded_by_existing_policy': run in excluded,
        })
    controls, counts, seen_hashes = [], Counter(), set()
    for path in control_roots:
        control = inspect_control(path)
        if control['sha256'] in seen_hashes:
            raise ValueError('Duplicate control ROOT content')
        seen_hashes.add(control['sha256'])
        controls.append(control)
        if not control['missing_branches']:
            counts.update(control['events_by_run'])
    report = {
        'schema_version': 1, 'status': 'structural_inspection_only',
        'data_dir': str(data_dir.resolve()), 'period': '1998_uv', 'target': 'P',
        'target_active_length_cm': None, 'target_length_status': 'awaiting_owner',
        'catalog_sha256': hashlib.sha256(catalog_bytes).hexdigest(),
        'run_quality_sha256': policy['sha256'],
        'table': {'path': str(matrix_path.resolve()), 'sha256': table.source_sha256,
                  'channels': 64, 'ignored_channel': table.ignored_channel,
                  'energies_W_GeV': table.energies_gev, 'angles_cm_degrees': list(range(0, 181, 10)),
                  'interpolation': 'linear_between_explicit_energy_labels_no_extrapolation',
                  'physical_source_validation': 'pending', 'units_and_branching': 'not_certified'},
        'calibration_runs': calibration_records, 'calibration_passed': len(ready), 'catalog_runs': len(runs),
        'control_files': controls, 'control_proposal': propose_controls(counts, ready, excluded),
        'limits': ['Per-run constants are parsed, not applied to simulated deposits.',
                   'Shared databases, BGO linearity, trigger, dead channels and build options still need validation.',
                   'No efficiency, absolute normalization, PID performance or production campaign certified.'],
    }
    output.mkdir(parents=True, exist_ok=False)
    (output / 'inspection.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, required=True)
    parser.add_argument('--catalog', type=Path, default=ROOT / 'config/support/run_manifest.csv')
    parser.add_argument('--run-quality', type=Path, default=ROOT / 'config/support/run_quality_exclusions.json')
    parser.add_argument('--control-root', type=Path, action='append', default=[])
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    report = write_inspection(args.data_dir, args.catalog, args.run_quality, args.control_root, args.output_dir)
    print(f"Calibration structure: {report['calibration_passed']}/{report['catalog_runs']}; "
          f"controls: {report['control_proposal']['status']}; {args.output_dir / 'inspection.json'}")
    return 0 if report['calibration_passed'] == report['catalog_runs'] else 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError) as error:
        print(f'ERROR: {error}', file=sys.stderr)
        sys.exit(1)
