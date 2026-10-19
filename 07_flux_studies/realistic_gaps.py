"""Inventory missing calibrated states and mask analogous measured run sequences."""
from collections import Counter, defaultdict
import numpy as np

from flux_studies.neighbor_validation import neighbor_example

STATES = ('POL1', 'POL2', 'BREM')


def gap_inventory(manifest, audit, counts, records, *, excluded_runs, recover_runs=()):
    recover_runs = set(recover_runs)
    if not recover_runs <= set(excluded_runs):
        raise ValueError('recovered quality runs must be excluded from measured references')
    records = [r for r in records if r['run'] not in excluded_runs]
    periods = defaultdict(list)
    for row in manifest:
        if row.target == 'P':
            periods[row.source_period].append(row)
    entries = {(r['run_number'], r['state']): r for r in audit['rows']}
    missing, patterns, unsupported = [], [], []
    for period, period_rows in sorted(periods.items()):
        period_rows.sort(key=lambda r: r.run_number)
        incomplete = []
        for position, row in enumerate(period_rows):
            recovering = row.run_number in recover_runs
            absent = [state for state in STATES if recovering or not entries[(row.run_number, state)]['calibrated_keys']]
            if not absent:
                continue
            states = []
            for state in absent:
                target = dict(run=row.run_number, period=period, state=state,
                              group=(period, row.target, row.beam_type, state),
                              position=position * 15., count=counts.get((row.run_number, state), 0))
                example = neighbor_example(target, records) if target['count'] > 0 else None
                status = ('quality_excluded' if row.run_number in excluded_runs and not recovering else
                          'missing_h80_count' if target['count'] <= 0 else
                          'no_two_sided_donors' if example is None else 'candidate')
                result = {**target, 'status': status,
                          'missing_reason': 'quality_excluded_as_missing' if recovering else 'missing_calibrated',
                          'donors': example['donors'] if example else [],
                          'gap': example['gap'] if example else None,
                          'raw_problems': [p for p in entries[(row.run_number, state)]['problems']
                                           if p != 'missing_calibrated'],
                          'production_status': 'not_adopted'}
                missing.append(result)
                states.append(result)
            incomplete.append(dict(position=position, run=row.run_number, states=states))
        chunks = []
        for row in incomplete:
            if not chunks or row['position'] != chunks[-1][-1]['position'] + 1:
                chunks.append([])
            chunks[-1].append(row)
        supported_windows = {}
        run_positions = {r.run_number: i for i, r in enumerate(period_rows)}
        for chunk in chunks:
            pattern = dict(period=period, runs=[r['run'] for r in chunk],
                           positions=[r['position'] for r in chunk],
                           masks=[[s['state'] for s in r['states']] for r in chunk])
            statuses = sorted({s['status'] for r in chunk for s in r['states']})
            if statuses == ['candidate']:
                left = min(run_positions[s['donors'][0]] for r in chunk for s in r['states'])
                right = max(run_positions[s['donors'][1]] for r in chunk for s in r['states'])
                window = supported_windows.setdefault((left, right), {})
                for r in chunk:
                    window[r['run']] = [s['state'] for s in r['states']]
            else:
                unsupported.append({**pattern, 'reasons': statuses})
        for (left, right), masks in sorted(supported_windows.items()):
            window_runs = [period_rows[i].run_number for i in range(left + 1, right)]
            patterns.append(dict(period=period, runs=window_runs,
                                 positions=list(range(left + 1, right)),
                                 masks=[masks.get(run, []) for run in window_runs],
                                 donors=[period_rows[left].run_number, period_rows[right].run_number]))
    return dict(missing=missing, patterns=patterns, unsupported_patterns=unsupported,
                summary=dict(missing_states=len(missing), missing_runs=len({r['run'] for r in missing}),
                             statuses=dict(Counter(r['status'] for r in missing)),
                             supported_patterns=len(patterns)))


def realistic_split(records, patterns, *, seed=42):
    """Place real missing-state patterns on clean, contiguous runs, keeping brackets.

    Whole runs are hidden from fits regardless of state mask. Immediate clean
    bracketing runs remain train, so adjacent artificial gaps cannot merge.
    Position is manifest ordinal times the assumed 15 minutes, not run arithmetic.
    """
    rng = np.random.default_rng(seed)
    by_period = defaultdict(dict)
    for row in records:
        by_period[row['period']][row['run']] = row['position']
    plan, placements, test_masks, unsupported = {}, [], [], []
    for period, coordinates in sorted(by_period.items()):
        available_patterns = [p for p in patterns if p['period'] == period]
        runs = sorted(coordinates, key=coordinates.get)
        roles = dict.fromkeys(runs, 'train')
        blocks = {run: i for i, run in enumerate(runs)}
        plan[period] = []
        if not available_patterns:
            unsupported.append(dict(period=period, reason='no_supported_real_gap_pattern'))
        else:
            by_position = {int(round(pos / 15)): run for run, pos in coordinates.items()}
            reserved = set()
            block = len(runs)
            quota = max(1, len(runs) // 5)
            for role in ('test', 'validation'):
                selected_count = 0
                # Cycle observed patterns, preserving their empirical multiplicity.
                choices = [available_patterns[i] for i in rng.permutation(len(available_patterns))]
                while selected_count < quota:
                    progressed = False
                    for pattern in choices:
                        size = len(pattern['masks'])
                        starts = []
                        for start in sorted(by_position):
                            positions = range(start, start + size)
                            if not all(pos in by_position for pos in range(start - 1, start + size + 1)):
                                continue
                            hidden = [by_position[pos] for pos in positions]
                            boundary = [by_position[start - 1], by_position[start + size]]
                            if (any(roles[r] != 'train' or r in reserved for r in hidden)
                                    or any(roles[r] != 'train' for r in boundary)):
                                continue
                            starts.append(start)
                        if not starts:
                            continue
                        start = int(rng.choice(starts))
                        hidden = [by_position[pos] for pos in range(start, start + size)]
                        reserved.update((by_position[start - 1], by_position[start + size]))
                        for run in hidden:
                            roles[run], blocks[run] = role, block
                        placements.append(dict(period=period, role=role, block=block, runs=hidden,
                                               masks=pattern['masks'], source_runs=pattern['runs']))
                        if role == 'test':
                            test_masks.extend(dict(period=period, run=run, state=state)
                                              for run, states in zip(hidden, pattern['masks'], strict=True)
                                              for state in states)
                        block += 1
                        selected_count += len(hidden)
                        progressed = True
                        if selected_count >= quota:
                            break
                    if not progressed:
                        break
                if selected_count < quota:
                    unsupported.append(dict(period=period, role=role,
                                            reason='insufficient_separated_clean_windows',
                                            requested_runs=quota, placed_runs=selected_count))
        plan[period] = [dict(run=r, role=roles[r], block=blocks[r]) for r in runs]
    return dict(split_plan=plan, placements=placements, test_masks=test_masks,
                unsupported=unsupported, seed=seed,
                interpretation='development; whole-run masking, scored states follow supported real gaps')
