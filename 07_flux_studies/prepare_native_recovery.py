"""Prepare complete-campaign counts, frozen quality decisions and recovery masks."""
from __future__ import annotations

import argparse
from collections import defaultdict
from copy import deepcopy
from pathlib import Path

from calibration.calibration_qa import sha256_file
from calibration.run_manifest import validate_manifest
from calibration.run_quality import DEFAULT_RUN_QUALITY_PATH, diagnose_flux_per_event, load_run_quality
from flux_studies.audit_flux import audit_flux
from flux_studies.calibrated_data import count_h80, load_calibrated_dataset
from flux_studies.realistic_gaps import gap_inventory, realistic_split
from flux_studies.reporting import publish_output, write_csv, write_json


def campaign_quality(records, base, sources):
    """Freeze factor-100 decisions for this campaign without altering base policy.

    Previously excluded runs remain excluded. Fresh evidence replaces their old
    evidence only when they again violate the factor-100 criterion. Manual
    exclusions retain their original decision basis.
    """
    findings = diagnose_flux_per_event(records)
    policy = deepcopy({k: v for k, v in base.items() if k not in ('path', 'sha256')})
    policy['evidence_sources'].update(sources)
    by_run = {r['run']: r for r in policy['excluded_runs']}
    groups = defaultdict(list)
    for finding in findings:
        groups[finding['run']].append(finding)
    for run, evidence in groups.items():
        if run in by_run and by_run[run]['decision_basis'] != 'flux_per_event_factor_100':
            continue
        by_run[run] = dict(run=run, period=evidence[0]['period'],
            reason='Full-campaign flux/event outside [0.01, 100] times period/state median; all states excluded and treated as missing for experimental reconstruction.',
            decision_basis='flux_per_event_factor_100',
            evidence=[{k: v for k, v in row.items() if k not in ('run', 'period')} for row in evidence])
    policy['excluded_runs'] = [by_run[r] for r in sorted(by_run)]
    return policy, findings


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--raw-flux', type=Path, required=True)
    parser.add_argument('--calibrated-flux', type=Path, required=True)
    parser.add_argument('--h80-dir', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--seed', type=int, default=142)
    args = parser.parse_args(argv)
    manifest = validate_manifest(args.manifest)
    periods = sorted({r.source_period for r in manifest if r.target == 'P'})
    paths = [args.h80_dir / f'pre_analisi_{period}.root' for period in periods]
    absent = [str(p) for p in paths if not p.is_file()]
    if absent:
        parser.error(f'complete proton campaign is missing h80 files: {absent}')
    inputs = [args.manifest, args.raw_flux, args.calibrated_flux, DEFAULT_RUN_QUALITY_PATH, *paths]
    print(f'Preparing {len(paths)} proton periods; verifying full input hashes...', flush=True)
    with publish_output(args.output_dir, inputs) as directory:
        counts, sources = {}, []
        for path in paths:
            print(f'Counting all h80 entries: {path.name}', flush=True)
            local, provenance = count_h80([path])
            if counts.keys() & local.keys() or {s['uuid'] for s in sources} & {s['uuid'] for s in provenance}:
                raise ValueError(f'duplicate run/state coverage or h80 identity: {path}')
            counts.update(local)
            sources.extend(provenance)
        write_json(directory / 'h80_counts.json', dict(sources=sources,
                   counts=[dict(run=r, state=s, count=n) for (r, s), n in sorted(counts.items())]))
        data = load_calibrated_dataset(args.manifest, args.calibrated_flux, counts, representation='native_strip')
        evidence_sources = {str(p.resolve()): sha256_file(p) for p in
                            (args.manifest, args.calibrated_flux, DEFAULT_RUN_QUALITY_PATH)}
        evidence_sources[str((args.output_dir / 'h80_counts.json').resolve())] = sha256_file(directory / 'h80_counts.json')
        policy, findings = campaign_quality(data['diagnostic_records'], data['run_quality'], evidence_sources)
        quality_path = directory / 'run_quality_exclusions.json'
        write_json(quality_path, policy)
        load_run_quality(quality_path)
        data = load_calibrated_dataset(args.manifest, args.calibrated_flux, counts,
                                      representation='native_strip', run_quality_path=quality_path)
        excluded = {r['run'] for r in policy['excluded_runs']}
        recover = {r['run'] for r in policy['excluded_runs'] if r['decision_basis'] == 'flux_per_event_factor_100'}
        # A previous manual exclusion can also newly satisfy the factor-100 rule.
        recover.update(r['run'] for r in findings)
        audit = audit_flux(manifest=args.manifest, raw_flux=args.raw_flux, calibrated_flux=args.calibrated_flux)
        inventory = gap_inventory(manifest, audit, counts, data['records'], excluded_runs=excluded, recover_runs=recover)
        design = realistic_split(data['records'], inventory['patterns'], seed=args.seed)
        write_json(directory / 'gap_inventory.json', inventory)
        write_json(directory / 'realistic_design.json', design)
        write_json(directory / 'factor100_findings.json', findings)
        write_csv(directory / 'missing_states.csv', inventory['missing'])
        write_json(directory / 'preparation.json', dict(periods=periods, inclusive_events=sum(counts.values()),
                   clean_runs=len({r['run'] for r in data['records']}), clean_spectra=len(data['records']),
                   excluded_runs=sorted(excluded), recover_quality_runs=sorted(recover),
                   current_factor100_runs=sorted({r['run'] for r in findings}),
                   test_masks=len(design['test_masks']), inventory=inventory['summary'],
                   status='prepared_experimental_not_adopted',
                   comparison_caveat='Full current h80 excludes no-tagger events; local pilot used historical h80. Compare convention and period effects separately.'))
        print(f"Clean spectra: {len(data['records'])}; quality recovery runs: {sorted(recover)}; test masks: {len(design['test_masks'])}", flush=True)
    print(f'Published {args.output_dir}', flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
