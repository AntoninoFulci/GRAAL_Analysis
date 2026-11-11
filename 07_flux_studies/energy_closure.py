"""Paired A/B/C/D extraction for an explicitly declared energy recovery study.

Inputs are genuine run/strip exposures, already projected with independent
axes. No common-grid index is ever interpreted as a detector strip here.
"""
from dataclasses import fields
import math

import numpy as np

from calibration.run_quality import load_run_quality
from observable_extraction.core.models import FluxExposure, FitNotEstimableError
from observable_extraction.extraction import extract_sample
from observable_extraction.core.binning import PAIR_NAMES, pair_mass_edges, phi_edges_rad
from observable_extraction.io.reconstructed_events import EventArrays, select_sigma_events
from flux_studies.flux_observable_closure import _point_key, _point_record, _valid_fit, _comparison


def _resample(events, indices):
    return EventArrays(**{field.name: None if getattr(events, field.name) is None
                          else getattr(events, field.name)[indices] for field in fields(events)})


def _extract(events, exposures, energy_edges, workers):
    bundle = extract_sample(sample_name='raw_bdt', events=events, exposures=exposures,
                            estimator='both', retain_ratio_objects=False,
                            energy_edges=energy_edges, phi_edges=phi_edges_rad(12),
                            best_binning=False, workers=workers)
    result = {}
    for output in bundle.points:
        if _valid_fit(output):
            record = _point_record(output)
            record['ratio_used_fallback'] = bool(output.point.diagnostics.used_fallback)
            record['p_value'] = float(output.point.diagnostics.p_value)
            result[_point_key(output)] = record
    return result


def _same_measured_value(left, right):
    if isinstance(left, (float, int)) and isinstance(right, (float, int)):
        # ROOT's low + width/2 and NumPy's (low + high)/2 differ at roundoff.
        return math.isclose(left, right, rel_tol=8 * np.finfo(float).eps, abs_tol=0.)
    return left == right


def _validate_exposures(exposures, reference=None, *, active_masks=()):
    """Only declared masked states may change on an identical strip universe."""
    for key, item in exposures.items():
        if not isinstance(item, FluxExposure) or key != (item.run_number, item.xstrip):
            raise ValueError(f"exposure key conflicts with run/strip identity: {key}")
    if reference is None:
        return
    if set(exposures) != set(reference):
        raise ValueError('projected strata differ from matched measured strata')
    fields_by_state = dict(POL1=('flux_vertical', 'polarization_vertical'),
                           POL2=('flux_horizontal', 'polarization_horizontal'),
                           BREM=('flux_brem', 'brem_status'))
    for key, item in exposures.items():
        original = reference[key]
        for state, names in fields_by_state.items():
            if (key[0], state) not in active_masks and any(
                    not _same_measured_value(getattr(item, name), getattr(original, name)) for name in names):
                raise ValueError(f"unmasked {state} changed at run/strip {key}")
        if (not any((key[0], state) in active_masks for state in ('POL1', 'POL2'))
                and not _same_measured_value(item.energy_gev, original.energy_gev)):
            raise ValueError(f"unmasked polarized energy changed at run/strip {key}")


def compare_energy_scenarios(events, native, recovered, roundtrip, *, masked_states,
                             accepted_runs, energy_edges, workers=1, event_replicas=0,
                             flux_replicas=None, seed=0, point_universe=None, run_quality=None):
    """Extract measured baseline A, recovered B, matched C and representation D.

    Poisson event resampling uses identical event multiplicities for all four
    scenarios, including A's shared events. The optional flux replica sequence
    contains complete B exposure maps at matching replica indices; missing maps
    remain failures. Combined event/flux replicas do not assume independence or
    add the same residual variance twice. They are not a complete systematic
    error budget: measured-reference and other systematic errors remain explicit.
    """
    energy_edges = np.asarray(energy_edges, dtype=float)
    if (energy_edges.ndim != 1 or len(energy_edges) < 2
            or not np.all(np.isfinite(energy_edges)) or np.any(np.diff(energy_edges) <= 0)):
        raise ValueError('invalid analysis energy edges')
    if (isinstance(event_replicas, bool) or not isinstance(event_replicas, int)
            or event_replicas < 0 or seed < 0):
        raise ValueError('invalid replica count or seed')
    if flux_replicas is not None and len(flux_replicas) > event_replicas:
        raise ValueError('flux replicas exceed declared synchronized replica count')
    quality = load_run_quality() if run_quality is None else run_quality
    excluded = {row['run'] for row in quality['excluded_runs']}
    accepted_runs = set(accepted_runs)
    if accepted_runs & excluded:
        raise ValueError('accepted runs violate run-quality policy')
    native = {k: v for k, v in native.items() if k[0] not in excluded}
    recovered = {k: v for k, v in recovered.items() if k[0] not in excluded}
    roundtrip = {k: v for k, v in roundtrip.items() if k[0] not in excluded}
    masked_states = set(masked_states)
    if any(state not in ('POL1', 'POL2', 'BREM') for _, state in masked_states):
        raise ValueError('unknown masked state')
    masked_runs = {run for run, _ in masked_states}
    if not set(accepted_runs) <= masked_runs:
        raise ValueError('accepted runs must belong to mask')
    if not set(accepted_runs) <= {key[0] for key in native}:
        raise ValueError('accepted masked runs lack measured reference exposure')
    active_masks = {(run, state) for run, state in masked_states if run in accepted_runs}
    for run, state in active_masks:
        if state == 'BREM' and any(not exposure.has_measured_brem
                                  for key, exposure in native.items() if key[0] == run):
            raise ValueError(f'accepted BREM mask lacks valid measured BREM truth: run {run}')
    pol_masked = {run for run, state in masked_states if state != 'BREM'}
    rejected_pol = pol_masked - set(accepted_runs)
    paired_native = {key: value for key, value in native.items() if key[0] not in rejected_pol}
    baseline = {key: value for key, value in native.items() if key[0] not in pol_masked}
    selected = select_sigma_events(events, native,
        energy_range=(float(energy_edges[0]), float(energy_edges[-1])), drop_missing=True,
        run_quality=quality)
    paired = selected.take(~np.isin(selected.run_number, sorted(rejected_pol)))
    baseline_events = paired.take(~np.isin(paired.run_number, sorted(pol_masked)))
    maps = dict(A=baseline, B={k: v for k, v in recovered.items() if k[0] not in rejected_pol},
                C=paired_native, D={k: v for k, v in roundtrip.items() if k[0] not in rejected_pol})
    expected_keys = [(estimator, pair, energy, mass)
        for estimator in ('ratio', 'likelihood') for pair in sorted(PAIR_NAMES)
        for energy in range(len(energy_edges) - 1)
        for mass in range(len(pair_mass_edges(pair)) - 1)]
    if point_universe is not None:
        requested = [tuple(key) for key in point_universe]
        if not requested or len(set(requested)) != len(requested) or not set(requested) <= set(expected_keys):
            raise ValueError('invalid frozen comparison point universe')
        expected_keys = requested
    expected = len(expected_keys)
    result = dict(status='diagnostic_only', expected_points=expected,
        point_universe=[list(key) for key in expected_keys],
        masked_states=[dict(run=r, state=s) for r, s in sorted(masked_states)],
        accepted_runs=sorted(accepted_runs), rejected_pol_runs=sorted(rejected_pol),
        counts=dict(unique_selected_events=len(selected), baseline_pol_events=len(baseline_events),
                    paired_pol_events=len(paired),
                    recovered_pol_events=int(np.isin(paired.run_number,
                        sorted(pol_masked & set(accepted_runs))).sum())),
        scenarios={}, comparisons=[], quality_excluded_runs=sorted(excluded), production_adopted=False)
    points = {}
    for name, exposures in maps.items():
        scenario_events = baseline_events if name == 'A' else paired
        try:
            _validate_exposures(exposures, paired_native if name in ('B', 'D') else None,
                                active_masks=active_masks)
            fitted = _extract(scenario_events, exposures, energy_edges, workers)
            points[name] = {k: v for k, v in fitted.items() if k in expected_keys}
        except (ValueError, FitNotEstimableError) as exc:
            points[name] = {}
            result['scenarios'][name] = dict(
                status='not_estimable' if isinstance(exc, FitNotEstimableError) else 'invalid_exposures',
                reason=str(exc),
                estimable_points=0, missing_points=expected, selected_events=len(scenario_events), points=[])
            continue
        result['scenarios'][name] = dict(status='estimable' if points[name] else 'not_estimable',
            selected_events=len(scenario_events), strata=len(exposures),
            estimable_points=len(points[name]), missing_points=expected - len(points[name]),
            points=[dict(key=list(k), **v) for k, v in sorted(points[name].items())])
    matched = set.intersection(*(set(p) for p in points.values()))
    comparisons = [('C', 'B'), ('C', 'D'), ('D', 'B'), ('A', 'B')]
    for reference, scenario in comparisons:
        rows = _comparison(points[reference], points[scenario], scenario, reference, expected_keys, matched)
        for row, key in zip(rows, expected_keys, strict=True):
            a, b = points[reference].get(key), points[scenario].get(key)
            row['ratio_function_changed'] = (a['ratio_used_fallback'] != b['ratio_used_fallback']
                if a and b and key[0] == 'ratio' else None)
        result['comparisons'].extend(rows)

    rng = np.random.default_rng(seed)
    replicas = []
    for index in range(event_replicas):
        indices = np.repeat(np.arange(len(paired)), rng.poisson(1., len(paired)))
        sampled = _resample(paired, indices)
        sampled_baseline = sampled.take(~np.isin(sampled.run_number, sorted(pol_masked)))
        row, failures = {}, {}
        for name, exposures in maps.items():
            if result['scenarios'][name]['status'] == 'invalid_exposures':
                row[name] = {}
                failures[name] = result['scenarios'][name]['reason']
                continue
            if name == 'B' and flux_replicas is not None:
                payload = flux_replicas[index] if index < len(flux_replicas) else None
                exposures = ({k: v for k, v in payload.items() if k[0] not in rejected_pol | excluded}
                             if payload is not None else {})
            try:
                _validate_exposures(exposures, paired_native if name in ('B', 'D') else None,
                                    active_masks=active_masks)
                fitted = _extract(sampled_baseline if name == 'A' else sampled,
                                  exposures, energy_edges, workers)
                row[name] = {key: value for key, value in fitted.items() if key in expected_keys}
            except (ValueError, FitNotEstimableError) as exc:
                row[name] = {}
                failures[name] = str(exc)
        row['_failures'] = failures
        replicas.append(row)
    result['uncertainty'] = _summarize_replicas(replicas, comparisons, expected_keys,
        event_replicas=event_replicas, seed=seed, flux_propagated=flux_replicas is not None)
    proposed = result['counts']['recovered_pol_events']
    result['counts']['proposed_recovered_pol_events'] = proposed
    if result['scenarios']['B']['status'] == 'invalid_exposures':
        result['counts']['recovered_pol_events'] = 0
    return result


def _summarize_replicas(replicas, comparisons, expected_keys, *, event_replicas, seed, flux_propagated):
    uncertainty = dict(requested_replicas=event_replicas, seed=seed,
        paired_event_bootstrap=bool(event_replicas), flux_propagated=flux_propagated,
        combination='joint synchronized event/flux replicas; no quadrature addition',
        measured_reference_uncertainty='not supplied', other_systematics='not supplied',
        total_uncertainty_available=False, paired={}, scenario_replicas=[])
    uncertainty['scenario_replicas'] = [dict(index=i, failures=row['_failures'],
        scenarios={name: [dict(key=list(k), **v) for k, v in sorted(p.items())]
        for name, p in row.items() if name != '_failures'}) for i, row in enumerate(replicas)]
    for reference, scenario in comparisons:
        matrix = np.full((event_replicas, len(expected_keys)), np.nan)
        switches = np.zeros(len(expected_keys), dtype=int)
        for i, row in enumerate(replicas):
            for j, key in enumerate(expected_keys):
                a, b = row[reference].get(key), row[scenario].get(key)
                if a is not None and b is not None:
                    matrix[i, j] = b['sigma'] - a['sigma']
                    switches[j] += int(key[0] == 'ratio' and
                        a['ratio_used_fallback'] != b['ratio_used_fallback'])
        complete = np.all(np.isfinite(matrix), axis=1)
        rows = []
        for j, key in enumerate(expected_keys):
            values = matrix[np.isfinite(matrix[:, j]), j]
            rows.append(dict(key=list(key), successful=len(values), failed=event_replicas - len(values),
                mean_shift=float(np.mean(values)) if len(values) else None,
                shift_std=float(np.std(values, ddof=1)) if len(values) >= 2 else None,
                ratio_function_changes=int(switches[j])))
        uncertainty['paired'][f'{scenario}-{reference}'] = dict(requested=event_replicas,
            complete_replicas=int(complete.sum()), complete_replica_indices=np.flatnonzero(complete).tolist(),
            covariance=np.atleast_2d(np.cov(matrix[complete], rowvar=False)).tolist()
                if complete.sum() >= 2 else None, points=rows)
    return uncertainty


def _application_map(native, candidate):
    """Real missing-state recovery preserves every existing measured POL pair."""
    _validate_exposures(candidate)
    if not set(native) <= set(candidate):
        raise ValueError('recovered exposures remove existing measured strata')
    missing_brem = {(key[0], 'BREM') for key, item in native.items() if item.brem_status == 'missing'}
    _validate_exposures({key: candidate[key] for key in native}, native, active_masks=missing_brem)
    for key, item in native.items():
        if item.brem_status != 'missing' and (
                candidate[key].brem_status != item.brem_status
                or not _same_measured_value(candidate[key].flux_brem, item.flux_brem)):
            raise ValueError(f'existing measured BREM or defective status changed: {key}')
        if item.brem_status == 'missing' and candidate[key].brem_status not in ('missing', 'estimated'):
            raise ValueError(f'recovered BREM cannot become a measured control: {key}')


def compare_recovered_sample(events, native, recovered, *, energy_edges, flux_replicas=None,
                             event_replicas=0, seed=0, run_quality=None, point_universe=None,
                             workers=1):
    """Compare A/B on real missing flux; shifts measure stability, never bias.

    B selects event rows once using the recovered exposure universe; A is its
    subset with measured polarized exposure. Event Poisson multiplicities are
    synchronized, including shared A/B events, and aligned B flux maps carry
    the predictive dependence prepared upstream. There is no measured oracle
    for the recovered states and no complete systematic error budget.
    """
    edges = np.asarray(energy_edges, dtype=float)
    if (edges.ndim != 1 or len(edges) < 2 or not np.isfinite(edges).all()
            or np.any(np.diff(edges) <= 0)):
        raise ValueError('invalid analysis energy edges')
    if (isinstance(event_replicas, bool) or not isinstance(event_replicas, int)
            or event_replicas < 0 or seed < 0):
        raise ValueError('invalid replica count or seed')
    if flux_replicas is not None and len(flux_replicas) > event_replicas:
        raise ValueError('flux replicas exceed declared synchronized replica count')
    quality = load_run_quality() if run_quality is None else run_quality
    excluded = {row['run'] for row in quality['excluded_runs']}
    native = {key: value for key, value in native.items() if key[0] not in excluded}
    recovered = {key: value for key, value in recovered.items() if key[0] not in excluded}
    _validate_exposures(native)
    _application_map(native, recovered)
    selected = select_sigma_events(events, recovered,
        energy_range=(float(edges[0]), float(edges[-1])), drop_missing=True, run_quality=quality)

    def baseline_subset(sample):
        return sample.take(np.array([(int(run), int(strip)) in native
            for run, strip in zip(sample.run_number, sample.xstrip, strict=True)], dtype=bool))

    baseline = baseline_subset(selected)
    keys = [(estimator, pair, energy, mass)
        for estimator in ('ratio', 'likelihood') for pair in sorted(PAIR_NAMES)
        for energy in range(len(edges) - 1) for mass in range(len(pair_mass_edges(pair)) - 1)]
    if point_universe is not None:
        requested = [tuple(key) for key in point_universe]
        if not requested or len(set(requested)) != len(requested) or not set(requested) <= set(keys):
            raise ValueError('invalid frozen comparison point universe')
        keys = requested
    result = dict(status='diagnostic_only', interpretation='benefit_and_stability_not_bias',
        production_adopted=False, measured_oracle_available=False,
        expected_points=len(keys), point_universe=[list(key) for key in keys],
        quality_excluded_runs=sorted(excluded),
        counts=dict(unique_selected_events=len(selected), before_events=len(baseline),
                    after_events=len(selected), recovered_events=len(selected) - len(baseline)),
        scenarios={}, comparisons=[], precision=[])
    maps, central = dict(A=native, B=recovered), {}
    for name, mapping in maps.items():
        sample = baseline if name == 'A' else selected
        try:
            fitted = _extract(sample, mapping, edges, workers)
            central[name] = {key: value for key, value in fitted.items() if key in keys}
            status, reason = ('estimable' if central[name] else 'not_estimable'), None
        except (ValueError, FitNotEstimableError) as exc:
            central[name], status, reason = {}, 'not_estimable', str(exc)
        result['scenarios'][name] = dict(status=status, reason=reason, selected_events=len(sample),
            strata=len(mapping), estimable_points=len(central[name]),
            missing_points=len(keys) - len(central[name]),
            points=[dict(key=list(key), **value) for key, value in sorted(central[name].items())])
    matched = set(central['A']) & set(central['B'])
    result['comparisons'] = _comparison(central['A'], central['B'], 'B', 'A', keys, matched)
    for row, key in zip(result['comparisons'], keys, strict=True):
        a, b = central['A'].get(key), central['B'].get(key)
        row['ratio_function_changed'] = (a['ratio_used_fallback'] != b['ratio_used_fallback']
            if a and b and key[0] == 'ratio' else None)

    rng, replicas = np.random.default_rng(seed), []
    for index in range(event_replicas):
        sampled = _resample(selected, np.repeat(np.arange(len(selected)), rng.poisson(1., len(selected))))
        sampled_baseline = baseline_subset(sampled)
        row = {'_failures': {}}
        for name, mapping in maps.items():
            try:
                if name == 'B' and flux_replicas is not None:
                    payload = flux_replicas[index] if index < len(flux_replicas) else None
                    if payload is None:
                        raise ValueError('missing synchronized flux replica')
                    mapping = {key: value for key, value in payload.items() if key[0] not in excluded}
                    if set(mapping) != set(recovered):
                        raise ValueError('replica strata differ from central recovered strata')
                    _application_map(native, mapping)
                    for key, item in mapping.items():
                        original = recovered[key]
                        if any(not _same_measured_value(getattr(item, field), getattr(original, field))
                               for field in ('energy_gev', 'polarization_vertical', 'polarization_horizontal')):
                            raise ValueError(f'flux replica changes fixed calibration at {key}')
                        if (item.brem_status != original.brem_status
                                or (original.has_measured_brem
                                    and not _same_measured_value(item.flux_brem, original.flux_brem))):
                            raise ValueError(f'flux replica changes measured BREM or availability at {key}')
                fitted = _extract(sampled_baseline if name == 'A' else sampled, mapping, edges, workers)
                row[name] = {key: value for key, value in fitted.items() if key in keys}
            except (ValueError, FitNotEstimableError) as exc:
                row[name] = {}
                row['_failures'][name] = str(exc)
        replicas.append(row)
    result['uncertainty'] = _summarize_replicas(replicas, [('A', 'B')], keys,
        event_replicas=event_replicas, seed=seed, flux_propagated=flux_replicas is not None)
    for key in keys:
        a, b = central['A'].get(key), central['B'].get(key)
        stat_a = .5 * (a['stat_low'] + a['stat_high']) if a else None
        stat_b = .5 * (b['stat_low'] + b['stat_high']) if b else None
        aligned = [(row['A'][key]['sigma'], row['B'][key]['sigma']) for row in replicas
                   if key in row['A'] and key in row['B']]
        std_a, std_b = (map(float, np.std(aligned, axis=0, ddof=1))
                        if len(aligned) >= 2 else (None, None))
        result['precision'].append(dict(key=list(key), stat_A=stat_a, stat_B=stat_b,
            stat_ratio_B_over_A=stat_b / stat_a if stat_a and stat_b is not None else None,
            successful_paired_replicas=len(aligned), failed_paired_replicas=event_replicas - len(aligned),
            joint_replica_std_A=std_a, joint_replica_std_B=std_b,
            joint_replica_std_ratio_B_over_A=std_b / std_a if std_a and std_b is not None else None,
            total_uncertainty_available=False))
    return result
