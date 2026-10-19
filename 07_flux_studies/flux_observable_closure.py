"""Offline paired sensitivity of the existing Sigma extraction to masked flux.

Native-strip predictions copy bins directly; legacy predictions use independent
calibration axes. Recovered scenarios share events. The without-recovery control
removes every masked run from both selected events and exposure strata.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import replace
import csv
import json
import time
from pathlib import Path

import numpy as np

from calibration.run_manifest import validate_manifest
from graal_common.physics.beam_profiles import get_beam_profile
from observable_extraction.beam_asymmetry import _extract_sample
from observable_extraction.calibration.flux_v2 import load_exposures
from observable_extraction.core.binning import PAIR_NAMES, pair_mass_edges, phi_edges_rad
from observable_extraction.io.reconstructed_events import (
    read_reconstructed, read_run_universe, select_sigma_events,
)

DEFAULT_METHODS = ('linear', 'extra_trees_hybrid', 'kernel_ridge_hybrid')
SUPPORTED_METHODS = (*DEFAULT_METHODS, 'mlp_hybrid', 'cnn1d_hybrid', 'cnn_hybrid')
_STATE_FIELDS = {'POL1': 'flux_vertical', 'POL2': 'flux_horizontal', 'BREM': 'flux_brem'}


def project_to_strip_axis(values, common_edges, strip_edges):
    """Integrate common-bin densities on independently known native strip bins.

    Common-grid tails outside the target axis are reported explicitly. The
    common domain must contain the whole native axis; extrapolation is forbidden.
    """
    values, common_edges, strip_edges = [np.asarray(x, dtype=float)
                                        for x in (values, common_edges, strip_edges)]
    if (values.ndim != 1 or common_edges.shape != (len(values) + 1,)
            or strip_edges.ndim != 1 or len(strip_edges) < 2
            or any(not np.all(np.isfinite(x)) for x in (values, common_edges, strip_edges))
            or np.any(values < 0) or np.any(np.diff(common_edges) <= 0)
            or np.any(np.diff(strip_edges) <= 0)):
        raise ValueError('invalid common histogram or native strip axis')
    if strip_edges[0] < common_edges[0] or strip_edges[-1] > common_edges[-1]:
        raise ValueError('common grid does not cover native strip axis; extrapolation forbidden')
    cumulative = np.interp(strip_edges, common_edges, np.r_[0., np.cumsum(values)])
    projected = np.diff(cumulative)
    return projected, dict(common_integral=float(values.sum()),
                           projected_integral=float(projected.sum()),
                           outside_strip_axis_integral=float(values.sum() - projected.sum()))


def load_known_axes(flux_path, targets):
    """Read held-out target axes from the original calibrated ROOT, never donors."""
    import uproot
    axes = {}
    with uproot.open(flux_path) as source:
        keys = defaultdict(list)
        for key in source.keys(recursive=False):
            keys[key.rsplit(';', 1)[0]].append(key)
        for run, state in sorted(targets):
            name = f'run{run}_{state}'
            if len(keys[name]) != 1:
                raise ValueError(f'missing or duplicate independent target axis: {name}')
            histogram = source[keys[name][0]]
            try:
                values, edges = histogram.to_numpy(flow=False)
            except (ValueError, AttributeError) as exc:
                raise ValueError(f'invalid independent target axis: {name}') from exc
            if (len(values) != 128 or np.asarray(edges).shape != (129,)
                    or not np.all(np.isfinite(edges)) or np.any(np.diff(edges) <= 0)):
                raise ValueError(f'invalid independent target axis: {name}')
            axes[(run, state)] = np.asarray(edges, dtype=float)
    return axes


def replace_masked_exposures(native, projected):
    """Replace exactly requested flux components without changing any stratum."""
    by_run = defaultdict(dict)
    for (run, state), values in projected.items():
        if state not in _STATE_FIELDS:
            raise ValueError(f'unknown state {state}')
        if not any(key[0] == run for key in native):
            raise ValueError(f'no native exposure for requested run {run}')
        values = np.asarray(values, dtype=float)
        if values.ndim != 1 or np.any(~np.isfinite(values)) or np.any(values < 0):
            raise ValueError(f'invalid projected flux for run {run}/{state}')
        by_run[run][_STATE_FIELDS[state]] = values
    result = dict(native)
    for key, exposure in native.items():
        replacements = {}
        for field, values in by_run.get(key[0], {}).items():
            if key[1] > len(values):
                raise ValueError(f'projected axis lacks native strip {key}')
            replacements[field] = float(values[key[1] - 1])
        if replacements:
            # FluxExposure rejects zero POL1/POL2: do not silently drop a stratum.
            result[key] = replace(exposure, **replacements)
    return result


def _point_key(output):
    p = output.point
    return output.estimator, p.pair, p.energy_bin, p.mass_bin


def _point_record(output):
    p = output.point
    return dict(sigma=p.sigma, stat_low=p.stat_low, stat_high=p.stat_high,
                energy_low_gev=p.energy_low_gev, energy_high_gev=p.energy_high_gev,
                mass_low_gev=p.mass_low_gev, mass_high_gev=p.mass_high_gev,
                converged=bool(p.diagnostics.converged))


def _comparison(reference, candidate, scenario, reference_name, keys, matched_all):
    rows = []
    for key in keys:
        a, b = reference.get(key), candidate.get(key)
        row = dict(scenario=scenario, reference=reference_name, estimator=key[0],
                   pair=key[1], energy_bin=key[2], mass_bin=key[3],
                   matched_all_scenarios=key in matched_all)
        if a is None or b is None:
            row.update(status='missing_fit', missing_reference=a is None, missing_scenario=b is None,
                       delta_sigma=None, delta_over_nominal_stat=None)
        else:
            delta = b['sigma'] - a['sigma']
            nominal_stat = .5 * (a['stat_low'] + a['stat_high'])
            row.update(status='matched', reference_sigma=a['sigma'], scenario_sigma=b['sigma'],
                       nominal_stat=nominal_stat, delta_sigma=delta,
                       delta_over_nominal_stat=delta / nominal_stat if nominal_stat > 0 else None)
        rows.append(row)
    return rows


def run_observable_closure(predictions, *, common_edges_by_period=None, flux_path,
                           manifest_path, reco_paths, output_dir,
                           methods=DEFAULT_METHODS, workers=1, representation='common_energy',
                           flux_replicas=None, flux_replica_count=None, run_quality_path=None):
    """Compare fixed-grid observables with masked flux and optional replicas.

    ``representation='native_strip'`` copies the 128 bins directly and adds a
    control removing all masked runs from both events and exposures. Legacy
    common-energy projection remains the default. ``flux_replicas`` maps method
    to period to synchronized replica payloads keyed by ``(run, state)``. Pass
    ``flux_replica_count`` to retain absent replicas in the failure denominator;
    otherwise the largest supplied list defines the requested count.

    Replica covariance is estimated on common complete fits at the oracle's
    estimable points. Bias and coverage remain unvalidated without independent
    repeated trials. Nothing here authorizes production adoption.
    """
    if representation not in ('common_energy', 'native_strip'):
        raise ValueError('unsupported flux representation')
    if representation == 'common_energy' and common_edges_by_period is None:
        raise ValueError('common_energy representation requires common_edges_by_period')
    flux_replicas = {} if flux_replicas is None else flux_replicas
    if flux_replica_count is None:
        flux_replica_count = max((len(replicas) for periods in flux_replicas.values()
                                  for replicas in periods.values()), default=0)
    if isinstance(flux_replica_count, bool) or not isinstance(flux_replica_count, int) or flux_replica_count < 0:
        raise ValueError('flux_replica_count must be a nonnegative integer')
    methods = tuple(methods)
    if not methods or len(set(methods)) != len(methods) or any(m not in SUPPORTED_METHODS for m in methods):
        raise ValueError('closure methods must be distinct supported methods')
    from calibration.run_quality import load_run_quality
    quality = load_run_quality(run_quality_path)
    excluded_runs = {r['run'] for r in quality['excluded_runs']}
    records = validate_manifest(Path(manifest_path))
    manifest = {r.run_number: r for r in records}
    selected = defaultdict(dict)
    truth = {}
    for row in predictions:
        if row['role'] != 'test':
            raise ValueError('observable closure accepts only masked test predictions')
        run, state, period = int(row['run']), row['state'], row['period']
        if run in excluded_runs:
            raise ValueError(f'quality-excluded run cannot supply closure truth: {run}')
        if state not in _STATE_FIELDS:
            raise ValueError(f'unknown prediction state {state}')
        if run not in manifest or manifest[run].source_period != period or manifest[run].target != 'P':
            raise ValueError(f'prediction does not match proton manifest: {run}/{period}')
        key = (period, run, state)
        current_truth = np.asarray(row['truth'], dtype=float)
        if current_truth.shape != (128,):
            raise ValueError('closure requires 128-bin common-grid predictions')
        if key in truth and not np.array_equal(truth[key], current_truth):
            raise ValueError(f'inconsistent held-out truth: {key}')
        truth[key] = current_truth
        method = row['method']
        if method not in methods:
            continue
        if method in selected[key]:
            raise ValueError(f'duplicate prediction: {key}/{method}')
        selected[key][method] = np.asarray(row['estimate'], dtype=float)
    period_targets = defaultdict(set)
    for period, run, state in truth:
        period_targets[period].add((run, state))
    report = dict(status='diagnostic_only', representation=representation, phi_bins=12, estimator='both',
                  run_quality=quality,
                  flux_path=str(Path(flux_path)), manifest_path=str(Path(manifest_path)),
                  sample='raw_bdt', vector_mode='raw', periods=[],
                  scenario_definition='All requested test run/states replaced together within each period; other native flux retained.',
                  statistic_label='Paired sensitivity deltaSigma / reference statistical error; not independent significance.',
                  uncertainty=dict(paired_event_selection=True, paired_bootstrap=False,
                                   flux_covariance='unvalidated', coverage='unvalidated'),
                  production_gate=dict(adopted=False, status='not_adopted',
                                       reasons=['development periods only', 'flux covariance and coverage unvalidated',
                                                'independent bias and coverage evidence unavailable']),
                  brem_caveat='BREM-only replacements do not alter central Sigma in these ratio/likelihood estimators; this does not validate BREM-dependent background or uncertainty corrections.')
    cache = {}
    for period, targets in sorted(period_targets.items()):
        profile_names = {manifest[run].beam_type.lower() for run, _ in targets}
        if len(profile_names) != 1:
            raise ValueError(f'mixed profiles in period {period}')
        profile_name = profile_names.pop()
        profile = get_beam_profile(profile_name)
        if profile_name not in reco_paths:
            raise ValueError(f'missing reconstruction path for profile {profile_name}')
        if profile_name not in cache:
            path = Path(reco_paths[profile_name])
            universe, cutflow = read_run_universe(path)
            unknown = set(universe) - manifest.keys()
            if unknown:
                raise ValueError(f'reconstruction universe has unknown runs: {sorted(unknown)}')
            if any(manifest[r].target != profile.target or manifest[r].beam_type != profile.beam_type for r in universe):
                raise ValueError(f'reconstruction universe disagrees with profile {profile_name}')
            events = read_reconstructed(path, 'reco_eta_pi0_bdt', vector_mode='raw')
            if not set(map(int, np.unique(events.run_number))) <= set(universe):
                raise ValueError('selected events fall outside inclusive reconstruction universe')
            universe = set(universe) - excluded_runs
            events = events.take(~np.isin(events.run_number, sorted(excluded_runs)))
            audit = {}
            native = load_exposures(Path(flux_path), manifest_path=Path(manifest_path),
                                    run_numbers=universe, target=profile.target, beam_type=profile.beam_type,
                                    polarization_model=profile.polarization,
                                    energy_range=profile.energy_range_gev, audit=audit, allow_empty=True)
            cache[profile_name] = (events, native, universe, audit)
        events, all_native, universe, audit = cache[profile_name]
        period_runs = {r for r in universe if manifest[r].source_period == period}
        native = {key: value for key, value in all_native.items() if key[0] in period_runs}
        period_events = events.take(np.isin(events.run_number, sorted(period_runs)))
        # Select once from native availability. No scenario may alter this object.
        selected_events = select_sigma_events(period_events, native,
                                               energy_range=profile.energy_range_gev, drop_missing=True)
        energy_edges = np.asarray(profile.energy_edges_gev)
        keys = [(estimator, pair, e, m) for estimator in ('ratio', 'likelihood')
                for pair in PAIR_NAMES for e in range(len(energy_edges) - 1)
                for m in range(len(pair_mass_edges(pair)) - 1)]
        expected = len(keys)
        entry = dict(period=period, profile=profile_name, reco_path=str(reco_paths[profile_name]),
                     run_universe=sorted(period_runs), exposed_runs=sorted({key[0] for key in native}),
                     native_strata=len(native), input_events=len(period_events), selected_events=len(selected_events),
                     target_states=[dict(run=run, state=state) for run, state in sorted(targets)],
                     target_selected_events=int(np.isin(selected_events.run_number, [r for r, _ in targets]).sum()),
                     brem_only=all(state == 'BREM' for _, state in targets),
                     energy_edges_gev=energy_edges.tolist(), expected_points_per_scenario=expected,
                     flux_audit={str(run): audit.get(str(run)) for run in sorted(period_runs)},
                     scenarios={}, comparisons=[], comparison_summaries=[])
        scenario_points = {}
        axes_error = None
        try:
            axes = {} if representation == 'native_strip' else load_known_axes(flux_path, targets)
            common_edges = (np.arange(129, dtype=float) if representation == 'native_strip'
                            else np.asarray(common_edges_by_period[period], dtype=float))
            if common_edges.shape != (129,):
                raise ValueError('closure requires 129 common-grid edges')
            if not np.all(np.isfinite(common_edges)) or np.any(np.diff(common_edges) <= 0):
                raise ValueError('invalid common-grid edges')
            if representation != 'native_strip':
                entry['common_energy_edges_gev'] = common_edges.tolist()
        except (ValueError, KeyError) as exc:
            axes_error = str(exc)
        scenarios = ('native_truth', 'roundtrip_truth', *methods)
        if representation == 'native_strip':
            scenarios += ('without_recovery',)
        for scenario in scenarios:
            projections = []
            try:
                exposures, scenario_events = native, selected_events
                if scenario == 'without_recovery':
                    masked_runs = {run for run, _ in targets}
                    exposures = {key: value for key, value in native.items() if key[0] not in masked_runs}
                    scenario_events = selected_events.take(~np.isin(selected_events.run_number, sorted(masked_runs)))
                elif scenario != 'native_truth':
                    if axes_error:
                        raise ValueError(axes_error)
                    projected = {}
                    for run, state in sorted(targets):
                        key = (period, run, state)
                        if scenario == 'roundtrip_truth':
                            values = truth[key]
                        else:
                            if scenario not in selected[key]:
                                raise ValueError(f'missing prediction: {run}/{state}/{scenario}')
                            values = selected[key][scenario]
                        if values.shape != (128,):
                            raise ValueError(f'invalid prediction shape: {run}/{state}/{scenario}')
                        if representation == 'native_strip':
                            projected[(run, state)] = _native_values(values)
                            projections.append(dict(run=run, state=state, mode='native_strip_copy',
                                                    projected_integral=float(values.sum())))
                            continue
                        if (run, state) not in axes:
                            raise ValueError(f'missing independent target axis: {run}/{state}')
                        projected[(run, state)], projection_audit = project_to_strip_axis(values, common_edges, axes[(run, state)])
                        projections.append(dict(run=run, state=state,
                                                native_axis_low_gev=float(axes[(run, state)][0]),
                                                native_axis_high_gev=float(axes[(run, state)][-1]),
                                                **projection_audit))
                    exposures = replace_masked_exposures(native, projected)
            except ValueError as exc:
                scenario_points[scenario] = {}
                entry['scenarios'][scenario] = dict(status='invalid_projection', reason=str(exc),
                                                    estimable_points=0, missing_points=expected,
                                                    projections=projections, points=[])
                continue
            started = time.perf_counter()
            bundle = _extract_sample(sample_name='raw_bdt', events=scenario_events, exposures=exposures,
                                     estimator='both', retain_ratio_objects=False, energy_edges=energy_edges,
                                     phi_edges=phi_edges_rad(12), best_binning=False, workers=workers)
            fitted = {_point_key(output): _point_record(output) for output in bundle.points
                      if _valid_fit(output)}
            scenario_points[scenario] = fitted
            entry['scenarios'][scenario] = dict(status='estimable' if fitted else 'not_estimable',
                                                estimable_points=len(fitted), missing_points=expected - len(fitted),
                                                selected_events=len(scenario_events), native_strata=len(exposures),
                                                extraction_seconds=time.perf_counter() - started,
                                                projections=projections,
                                                points=[dict(estimator=k[0], pair=k[1], energy_bin=k[2], mass_bin=k[3], **v)
                                                        for k, v in sorted(fitted.items())])
        matched_all = set.intersection(*(set(points) for points in scenario_points.values()))
        entry['matched_all_scenarios_points'] = len(matched_all)
        comparisons = [('native_truth', 'roundtrip_truth')]
        comparisons += [(ref, method) for method in methods for ref in ('native_truth', 'roundtrip_truth')]
        if representation == 'native_strip':
            comparisons += [('native_truth', 'without_recovery')]
        for reference, scenario in comparisons:
            entry['comparisons'].extend(_comparison(scenario_points[reference], scenario_points[scenario],
                                                     scenario, reference, keys, matched_all))
        for reference, scenario in comparisons:
            for estimator in ('ratio', 'likelihood'):
                rows = [r for r in entry['comparisons'] if r['reference'] == reference
                        and r['scenario'] == scenario and r['estimator'] == estimator]
                matched = [r for r in rows if r['status'] == 'matched']
                deltas = [r['delta_sigma'] for r in matched]
                sensitivity = [abs(r['delta_over_nominal_stat']) for r in matched
                               if r['delta_over_nominal_stat'] is not None]
                entry['comparison_summaries'].append(dict(
                    reference=reference, scenario=scenario, estimator=estimator,
                    expected_points=len(rows), matched_points=len(matched),
                    missing_points=len(rows) - len(matched),
                    mean_delta_sigma=float(np.mean(deltas)) if deltas else None,
                    max_abs_delta_sigma=max(map(abs, deltas)) if deltas else None,
                    max_abs_delta_over_nominal_stat=max(sensitivity) if sensitivity else None))
        if representation == 'native_strip':
            _add_recovery_uncertainty(entry, scenario_points, methods, flux_replicas,
                                      flux_replica_count, native, targets, selected_events,
                                      energy_edges, workers, keys)
        report['periods'].append(entry)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / 'observable_closure.json').write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    _write_comparison_csv(report, output_dir / 'observable_closure.csv')
    _plot_closure(report, output_dir / 'observable_closure.pdf')
    if representation == 'native_strip':
        _plot_recovery(report, output_dir / 'recovery_precision.pdf')
        rows = [dict(period=period['period'], **row) for period in report['periods']
                for row in period['recovery_precision']]
        with (output_dir / 'recovery_precision.csv').open('w', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]) if rows else ['period', 'method', 'status'])
            writer.writeheader()
            writer.writerows(rows)
    return report


def _write_comparison_csv(report, path):
    rows = [dict(period=p['period'], **row) for p in report['periods'] for row in p['comparisons']]
    if not rows:
        path.write_text('period,scenario,reference,status,delta_sigma\n')
        return
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _plot_closure(report, path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages
    with PdfPages(path) as pdf:
        if not report['periods']:
            fig, ax = plt.subplots(figsize=(8, 3))
            ax.text(.5, .5, 'No selected test predictions: closure not estimable', ha='center')
            ax.axis('off')
            pdf.savefig(fig)
            plt.close(fig)
        for period in report['periods']:
            fig, axes = plt.subplots(2, 1, figsize=(10, 7), constrained_layout=True)
            for ax, estimator in zip(axes, ('ratio', 'likelihood')):
                for scenario in period['scenarios']:
                    if scenario == 'native_truth':
                        continue
                    reference = ('native_truth' if scenario in ('roundtrip_truth', 'without_recovery')
                                 or report.get('representation') == 'native_strip' else 'roundtrip_truth')
                    rows = [r for r in period['comparisons'] if r['scenario'] == scenario
                            and r['reference'] == reference and r['estimator'] == estimator]
                    present = [(i, r['delta_over_nominal_stat']) for i, r in enumerate(rows)
                               if r['status'] == 'matched' and r['delta_over_nominal_stat'] is not None]
                    ax.plot([x for x, _ in present], [y for _, y in present], '.',
                            label=f'{scenario}: {len(present)}/{len(rows)} matched')
                ax.axhline(0., color='black', lw=.7)
                ax.set(title=estimator, ylabel='ΔΣ / reference stat. error', xlabel='Fixed pair / energy / mass grid index')
                ax.legend(fontsize=7)
            fig.suptitle(f"{period['period']} — paired sensitivity, not significance\n"
                         'Native truth is the fixed statistical-error reference. Coverage unvalidated.')
            pdf.savefig(fig)
            plt.close(fig)


def _native_values(values):
    values = np.asarray(values, dtype=float)
    if values.shape != (128,) or not np.all(np.isfinite(values)) or np.any(values < 0):
        raise ValueError('native strip flux must contain 128 finite nonnegative values')
    return values.copy()


def _stat_error(point):
    return .5 * (point['stat_low'] + point['stat_high'])


def _key_record(key):
    return dict(estimator=key[0], pair=key[1], energy_bin=key[2], mass_bin=key[3])


def _add_recovery_uncertainty(entry, scenario_points, methods, replicas_by_method,
                              requested, native, targets, events, energy_edges, workers, keys):
    """Propagate whole-spectrum replicas through the frozen observable extraction.

    Covariance uses the same complete replica indices at every oracle-estimable
    point. Failed replicas remain in the requested denominator. This finite
    ensemble is diagnostic: neither it nor bins within one period constitute
    independent repeated-experiment evidence for mean bias or coverage.
    """
    oracle = scenario_points['native_truth']
    without = scenario_points['without_recovery']
    covariance_keys = sorted(oracle)
    entry['flux_replica_results'] = {}
    entry['recovery_precision'] = []
    representation_rows = [row for row in entry['comparisons']
                           if row['reference'] == 'native_truth' and row['scenario'] == 'roundtrip_truth']
    shifts = [abs(row['delta_over_nominal_stat']) for row in representation_rows
              if row.get('delta_over_nominal_stat') is not None]
    representation_complete = bool(oracle) and all(
        scenario_points['roundtrip_truth'].get(key) is not None for key in oracle)
    entry['acceptance'] = dict(
        representation=dict(budget_sigma_stat=.05, evaluable_points=len(shifts),
                            status=('passed' if max(shifts, default=0.) <= .05 else 'failed')
                            if representation_complete and shifts else 'unvalidated'),
        bias=dict(budget_sigma_stat=.10, status='unvalidated',
                  reason='One paired period fit cannot estimate independent mean bias and its uncertainty.'),
        flux=dict(budget_sigma_stat=.30, status='unvalidated',
                  reason='Replica spread is diagnostic; residual coverage has not been independently calibrated.'),
        coverage=dict(nominal_levels=[.68, .95], status='unvalidated',
                      reason='No independent repeated-experiment coverage trials.'),
        adopted=False)
    for method in methods:
        supplied = replicas_by_method.get(method, {}).get(entry['period'], [])
        if len(supplied) > requested:
            raise ValueError('flux_replica_count is smaller than supplied replica count')
        fits, audits, complete_values, complete_indices = [], [], [], []
        for index in range(requested):
            fitted = {}
            audit = dict(index=index, status='failed', estimable_points=0,
                         missing_points=len(keys), reused_native_fit=False)
            started = time.perf_counter()
            try:
                if index >= len(supplied) or not isinstance(supplied[index], dict):
                    raise ValueError('missing replica payload')
                payload = supplied[index]
                if set(payload) != targets:
                    raise ValueError('replica must supply exactly every masked run/state')
                replacements = {key: _native_values(value) for key, value in payload.items()}
                exposures = replace_masked_exposures(native, replacements)
                # Both fixed estimators depend only on polarized flux. Validate
                # BREM replacements first, then reuse the same mathematical fit.
                if all(state == 'BREM' for _, state in targets):
                    fitted = oracle
                    audit['reused_native_fit'] = True
                    audit['reuse_reason'] = 'Only BREM changed; fixed ratio/likelihood estimators use polarized flux.'
                else:
                    bundle = _extract_sample(sample_name='raw_bdt', events=events, exposures=exposures,
                                             estimator='both', retain_ratio_objects=False,
                                             energy_edges=energy_edges, phi_edges=phi_edges_rad(12),
                                             best_binning=False, workers=workers)
                    fitted = {_point_key(output): _point_record(output) for output in bundle.points
                              if _valid_fit(output)}
                complete = bool(covariance_keys) and all(key in fitted for key in covariance_keys)
                audit.update(status='complete' if complete else 'incomplete_fit',
                             estimable_points=len(fitted), missing_points=len(keys) - len(fitted))
                if complete:
                    complete_indices.append(index)
                    complete_values.append([fitted[key]['sigma'] for key in covariance_keys])
            except (ValueError, TypeError, RuntimeError, FloatingPointError) as exc:
                audit['reason'] = str(exc)
            audit['extraction_seconds'] = time.perf_counter() - started
            fits.append(fitted)
            audits.append(audit)
            if (index + 1) % 8 == 0 or index + 1 == requested:
                seconds = sum(item['extraction_seconds'] for item in audits)
                print(f"{entry['period']} {method}: observable replicas {index + 1}/{requested}, "
                      f'{len(complete_indices)} complete, {seconds:.1f}s', flush=True)
        complete_count = len(complete_values)
        covariance = (np.atleast_2d(np.cov(np.asarray(complete_values), rowvar=False, ddof=1))
                      if complete_count >= 2 else None)
        spread = {} if covariance is None else dict(zip(covariance_keys, np.sqrt(np.maximum(0., np.diag(covariance)))))
        # Use the same jointly complete replicas as the covariance. These are
        # conditional reconstruction intervals, not repeated-experiment coverage.
        quantiles = (np.quantile(np.asarray(complete_values), [.16, .84, .025, .975], axis=0)
                     if complete_count >= 2 else None)
        intervals = {} if quantiles is None else dict(zip(covariance_keys, quantiles.T))
        summary = dict(requested_replicas=requested, complete_replicas=complete_count,
                       failed_replicas=requested - complete_count,
                       failure_fraction=(requested - complete_count) / requested if requested else None,
                       complete_replica_indices=complete_indices,
                       covariance_points=[_key_record(key) for key in covariance_keys],
                       covariance=None if covariance is None else covariance.tolist(),
                       covariance_status='diagnostic_estimate' if covariance is not None else 'unvalidated',
                       covariance_denominator=complete_count, replicas=audits,
                       covariance_scope='Within-period oracle-estimable points, common complete replica fits only.',
                       coverage='unvalidated', bias='unvalidated', coverage_diagnostics={})
        entry['flux_replica_results'][method] = summary
        model = scenario_points[method]
        for key in keys:
            reference, recovered, baseline = oracle.get(key), model.get(key), without.get(key)
            flux_std = float(spread[key]) if key in spread else None
            stat = _stat_error(recovered) if recovered else None
            oracle_stat = _stat_error(reference) if reference else None
            baseline_stat = _stat_error(baseline) if baseline else None
            total = float(np.hypot(stat, flux_std)) if stat is not None and flux_std is not None else None
            bias = recovered['sigma'] - reference['sigma'] if recovered and reference else None
            rmse = float(np.hypot(total, bias)) if total is not None and bias is not None else None
            row = dict(method=method, **_key_record(key),
                       status='matched' if recovered and reference and baseline else 'missing_fit',
                       missing_oracle=reference is None, missing_recovered=recovered is None,
                       missing_without_recovery=baseline is None,
                       stat_error=stat, oracle_stat_error=oracle_stat,
                       without_recovery_stat_error=baseline_stat,
                       flux_std=flux_std, total_error=total,
                       total_error_definition='conditional stat+flux diagnostic: sqrt(recovered_stat^2 + flux_std^2); excludes bias and is not complete systematic uncertainty',
                       precision_ratio=(total / baseline_stat if total is not None and baseline_stat and baseline_stat > 0 else None),
                       precision_ratio_definition='conditional stat+flux diagnostic / without-recovery statistical error; below 1 does not establish benefit',
                       paired_rmse_proxy=rmse,
                       paired_rmse_proxy_definition='sqrt(recovered_stat^2 + flux_std^2 + paired_oracle_shift^2); descriptive proxy, not validated mean bias or its uncertainty',
                       rmse_ratio=rmse / baseline_stat if rmse is not None and baseline_stat and baseline_stat > 0 else None,
                       benefit_status='unvalidated',
                       bias_sigma=bias,
                       bias_over_oracle_stat=bias / oracle_stat if bias is not None and oracle_stat and oracle_stat > 0 else None,
                       bias_estimate_uncertainty=None, bias_validation='unvalidated', coverage='unvalidated',
                       flux_over_oracle_stat=flux_std / oracle_stat if flux_std is not None and oracle_stat and oracle_stat > 0 else None,
                       replica_successes=sum(key in fit for fit in fits),
                       replica_failures=sum(key not in fit for fit in fits),
                       requested_replicas=requested,
                       uncertainty_status='diagnostic_estimate' if flux_std is not None else 'unvalidated')
            bounds = intervals.get(key)
            for level, indices in ((68, (0, 1)), (95, (2, 3))):
                low, high = (None, None) if bounds is None else (float(bounds[indices[0]]), float(bounds[indices[1]]))
                row[f'replica_lower{level}'] = low
                row[f'replica_upper{level}'] = high
                row[f'oracle_in_replica_interval{level}'] = (
                    bool(low <= reference['sigma'] <= high) if low is not None and reference else None)
            row['replica_interval_count'] = complete_count
            row['replica_interval_status'] = 'conditional_reconstruction_diagnostic' if bounds is not None else 'unvalidated'
            ratio = row['flux_over_oracle_stat']
            row['flux_budget_diagnostic'] = ('within_budget' if ratio <= .30 else 'exceeds_budget') if ratio is not None else 'unvalidated'
            entry['recovery_precision'].append(row)
        for estimator in ('ratio', 'likelihood'):
            rows = [row for row in entry['recovery_precision']
                    if row['method'] == method and row['estimator'] == estimator]
            evaluable = [row for row in rows if row['oracle_in_replica_interval68'] is not None]
            diagnostic = dict(status='conditional_reconstruction_diagnostic' if evaluable else 'unvalidated',
                              expected_points=len(rows), evaluable_points=len(evaluable),
                              missing_points=len(rows) - len(evaluable),
                              complete_replicas=complete_count, requested_replicas=requested,
                              caveat='Observable points are correlated; this fraction is not independent binomial coverage certification. Conditional on fixed selected events and successful complete fits; finite replica quantiles are diagnostic.')
            for level in (68, 95):
                covered = sum(row[f'oracle_in_replica_interval{level}'] for row in evaluable)
                diagnostic[f'covered{level}_points'] = covered
                diagnostic[f'coverage{level}_fraction'] = covered / len(evaluable) if evaluable else None
            summary['coverage_diagnostics'][estimator] = diagnostic


def _valid_fit(output):
    p = output.point
    return (p.diagnostics.converged and np.all(np.isfinite([p.sigma, p.stat_low, p.stat_high]))
            and p.stat_low >= 0 and p.stat_high >= 0)


def _plot_recovery(report, path):
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages
    with PdfPages(path) as pdf:
        for period in report['periods']:
            fig, axes = plt.subplots(2, 1, figsize=(11, 7), constrained_layout=True)
            for method in period['flux_replica_results']:
                rows = [row for row in period['recovery_precision'] if row['method'] == method]
                for ax, field in zip(axes, ('precision_ratio', 'flux_over_oracle_stat')):
                    present = [(i, row[field]) for i, row in enumerate(rows) if row[field] is not None]
                    ax.plot([x for x, _ in present], [y for _, y in present], '.',
                            label=f'{method}: {len(present)}/{len(rows)} points')
                    ax.legend(fontsize=7)
            axes[0].axhline(1., color='black', lw=.8)
            axes[0].set(ylabel='Conditional stat+flux / without-recovery stat.', xlabel='Fixed observable point index')
            axes[1].axhline(.30, color='black', lw=.8)
            axes[1].set(ylabel='Flux std. / fixed oracle stat.', xlabel='Fixed observable point index')
            fig.suptitle(f"{period['period']} — diagnostic precision; bias and coverage unvalidated")
            pdf.savefig(fig)
            plt.close(fig)
            for method, uncertainty in period['flux_replica_results'].items():
                if uncertainty['covariance'] is None:
                    continue
                matrix = np.asarray(uncertainty['covariance'])
                fig, ax = plt.subplots(figsize=(8, 6), constrained_layout=True)
                magnitude = max(float(np.abs(matrix).max()), 1e-20)
                im = ax.imshow(matrix, cmap='coolwarm', vmin=-magnitude, vmax=magnitude)
                fig.colorbar(im, ax=ax, label='Covariance of Sigma from flux replicas')
                ax.set(title=f"{period['period']} / {method}: {uncertainty['complete_replicas']}/{uncertainty['requested_replicas']} complete replicas",
                       xlabel='Oracle-estimable point index', ylabel='Oracle-estimable point index')
                pdf.savefig(fig)
                plt.close(fig)
