"""Count potential recovery from frozen diagnostics; never authorize flux adoption."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path

from calibration.run_quality import DEFAULT_RUN_QUALITY_PATH, load_run_quality
from flux_studies.reporting import publish_output, write_csv, write_json
from graal_common.physics.beam_profiles import BEAM_PROFILES, get_beam_profile

STATES = ('POL1', 'POL2', 'BREM')
METHOD = 'extra_trees_hybrid'


def _unique(rows):
    result = {}
    for row in rows:
        key = row['run'], row['state']
        if key in result or row['state'] not in STATES:
            raise ValueError(f'duplicate or invalid run/state: {key}')
        result[key] = row
    return result


def recovery_budget(missing, support, counts, reconstructed, *, excluded_runs):
    """A run is potential only if every missing state has measured support.

    This is a support-based upper bound. Production acceptance needs independent
    validation and is deliberately not inferred from a diagnostic support flag.
    Counts cover all states of each run because the exposure loader discards an
    incomplete triplet in full. Known states restored with the run count once.
    """
    counts = _unique(counts)
    support = _unique(r for r in support if r['method'] == METHOD)
    reco = _unique(reconstructed)
    missing = _unique(missing)
    for key, row in counts.items():
        if type(row['count']) is not int or row['count'] < 0:
            raise ValueError(f'invalid h80 count: {key}')
    for key, row in reco.items():
        if row['h80_count'] != counts.get(key, {}).get('count', 0):
            raise ValueError(f'reconstruction/h80 count mismatch: {key}')
        if not 0 <= row['reconstructed_energy_window'] <= row['reconstructed'] <= row['h80_count']:
            raise ValueError(f'invalid reconstructed count: {key}')
    groups = defaultdict(list)
    for key, row in missing.items():
        if row['run'] in excluded_runs:
            continue
        if row.get('missing_reason', 'missing_calibrated') != 'missing_calibrated':
            raise ValueError(f'non-genuine missing state outside exclusion policy: {key}')
        if row['count'] != counts.get(key, {}).get('count', 0):
            raise ValueError(f'inventory/h80 count mismatch: {key}')
        groups[row['period'], row['run']].append(row)
    runs = []
    for (period, run), rows in sorted(groups.items()):
        supported = [r['state'] for r in rows
                     if r['status'] == 'candidate' and support.get((run, r['state']), {}).get('supported') is True]
        potential = len(supported) == len(rows)
        blockers = {b for r in rows for b in support.get((run, r['state']), {}).get('blockers', [])}
        if not potential:
            blockers.add('unsupported_missing_states')
        h80 = {s: counts.get((run, s), {}).get('count', 0) for s in STATES}
        if any(h80[s] and (run, s) not in reco for s in STATES):
            raise ValueError(f'missing reconstruction cutflow for run {run}')
        nreco = {s: reco.get((run, s), {}).get('reconstructed', 0) for s in STATES}
        window = {s: reco.get((run, s), {}).get('reconstructed_energy_window', 0) for s in STATES}
        runs.append(dict(period=period, run=run, missing_states=sorted(r['state'] for r in rows),
                         supported_missing_states=sorted(supported), potential=potential,
                         production_accepted=False, blockers=sorted(blockers),
                         h80_events=sum(h80.values()),
                         h80_missing_state_events=sum(h80[r['state']] for r in rows),
                         reconstructed_events=sum(nreco.values()),
                         sigma_events_energy_window=window['POL1'] + window['POL2'],
                         brem_events_energy_window=window['BREM']))

    def summarize(rows):
        potential = [r for r in rows if r['potential']]
        return dict(missing_runs=len(rows), missing_states=sum(len(r['missing_states']) for r in rows),
                    supported_missing_states=sum(len(r['supported_missing_states']) for r in rows),
                    potential_runs=len(potential), production_accepted_runs=0, production_accepted_events=0,
                    **{'potential_' + name: sum(r[name] for r in potential)
                       for name in ('h80_events', 'h80_missing_state_events', 'reconstructed_events',
                                    'sigma_events_energy_window', 'brem_events_energy_window')})
    return dict(method=METHOD, excluded_runs=sorted(excluded_runs),
                status='support_based_potential_only_not_production_accepted',
                acceptance_required=['independent_confirmation', 'calibrated_flux_uncertainty_and_coverage',
                                     'validated_missing_state_energy_axis', 'observable_bias_and_precision_check'],
                summary=summarize(runs),
                by_period={p: summarize([r for r in runs if r['period'] == p])
                           for p in sorted({r['period'] for r in runs})}, runs=runs)


def read_reconstructed_counts(paths):
    """Count tree entries and verify them against inclusive production cutflows."""
    import numpy as np
    import uproot
    result = []
    for path in paths:
        with uproot.open(path) as source:
            meta = json.loads(source['reconstruction_provenance'].member('fTitle'))
            low, high = get_beam_profile(meta['beam_profile']).energy_range_gev
            arrays = source[meta['output_tree']].arrays(['RunNumber', 'Polarization', 'beam'])
            run = np.asarray(arrays['RunNumber'])
            pol = np.asarray(arrays['Polarization'])
            energy = np.asarray(arrays['beam']['fE'])
            total = Counter(zip(run.tolist(), pol.tolist()))
            window = (energy >= low) & (energy <= high)
            selected = Counter(zip(run[window].tolist(), pol[window].tolist()))
            seen = set()
            for row in meta['counts_by_run_state']:
                key = row['run'], row['polarization']
                if key in seen or row.get('written', 0) != total.get(key, 0):
                    raise ValueError(f'duplicate or inconsistent reconstruction cutflow: {path}: {key}')
                seen.add(key)
                if key[1] not in (0, 1, 2):
                    raise ValueError(f'unknown polarization: {key}')
                # Full production h80 skips no-tagger entries before writing.
                result.append(dict(run=key[0], state={0: 'BREM', 1: 'POL1', 2: 'POL2'}[key[1]],
                                   h80_count=row['raw_input'] - row.get('skipped_no_tagger', 0),
                                   reconstructed=total.get(key, 0),
                                   reconstructed_energy_window=selected.get(key, 0)))
            if total.keys() - seen:
                raise ValueError(f'reconstructed events missing from cutflow: {path}')
    _unique(result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--study', type=Path, required=True, help='Contains prepared/ and realistic/')
    parser.add_argument('--reco', type=Path, nargs='+', required=True)
    parser.add_argument('--run-quality', type=Path, default=DEFAULT_RUN_QUALITY_PATH)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args(argv)
    inventory = args.study / 'prepared/gap_inventory.json'
    counts = args.study / 'prepared/h80_counts.json'
    support = args.study / 'realistic/candidate_support.json'
    with publish_output(args.output_dir, [inventory, counts, support, args.run_quality, *args.reco]) as output:
        policy = load_run_quality(args.run_quality)
        reconstructed = read_reconstructed_counts(args.reco)
        result = recovery_budget(json.loads(inventory.read_text())['missing'],
                                 json.loads(support.read_text()), json.loads(counts.read_text())['counts'],
                                 reconstructed, excluded_runs={r['run'] for r in policy['excluded_runs']})
        result['run_quality'] = policy
        result['energy_windows_gev'] = {name: p.energy_range_gev for name, p in BEAM_PROFILES.items()}
        result['event_definition'] = (
            'h80: all full-production entries with tagger, no channel selection; '
            'reconstructed: eta pi0 entries after production selection; sigma: POL1/POL2 '
            'within the UV/VIS profile energy window, before flux/strip acceptance and final observable binning. '
            'These are potential event counts, not fitted signal yields or accepted recovery.')
        write_json(output / 'reconstructed_counts.json', reconstructed)
        write_json(output / 'recovery_budget.json', result)
        write_csv(output / 'recovery_runs.csv', result['runs'])
        print(json.dumps(result['summary'], indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
