"""Explicit offline common-energy recovery campaign; never a workflow default.

Run ``python -m flux_studies.energy_campaign --help``. Input JSON identifies the
actual cohort and resources. Publication is exclusive and authenticates every
declared input before and after computation. No production flux is overwritten.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from calibration.calibration_qa import sha256_file
from calibration.run_manifest import validate_manifest
from flux_studies.calibrated_data import count_h80, load_calibrated_dataset
from flux_studies.energy_recovery import load_independent_axes, map_energy_to_strips
from flux_studies.reporting import publish_output, write_json
from graal_common.physics.beam_profiles import get_beam_profile
from observable_extraction.calibration.energy_exposures import build_projected_exposures
from observable_extraction.calibration.flux_v2 import load_exposures
from observable_extraction.io.reconstructed_events import read_reconstructed, read_run_universe, select_sigma_events


def input_paths(config):
    inputs = config['inputs']
    paths = [inputs[k] for k in ('manifest', 'calibrated_flux', 'run_quality')]
    paths += list(inputs['h80']) + list(inputs['reco'].values())
    paths += [inputs[k] for k in ('counts_cache', 'axes_product', 'axes_provenance') if inputs.get(k)]
    return list(dict.fromkeys(str(Path(p).resolve(strict=True)) for p in paths))


def load_campaign(config):
    """Load state inventory using exact declared h80 and reconstruction cohort."""
    inputs, cohort = config['inputs'], config['cohort_runs']
    if (not cohort or len(cohort) != len(set(cohort))
            or any(type(r) is not int or r <= 0 for r in cohort)):
        raise ValueError('cohort_runs must be distinct positive run IDs')
    if not inputs['h80'] or len(set(map(str, inputs['h80']))) != len(inputs['h80']):
        raise ValueError('declare distinct inclusive h80 paths')
    hashes = {p: sha256_file(p) for p in input_paths(config)}
    if 'input_sha256' in config and hashes != config['input_sha256']:
        raise ValueError('campaign input identity differs from frozen input_sha256')
    manifest = {r.run_number: r for r in validate_manifest(Path(inputs['manifest']))}
    if not set(cohort) <= manifest.keys() or any(manifest[r].target != 'P' for r in cohort):
        raise ValueError('cohort must contain only declared proton manifest runs')
    if inputs.get('counts_cache'):
        from flux_studies.study_native_recovery import load_cached_counts
        counts, sources = load_cached_counts(inputs['counts_cache'], expected_paths=inputs['h80'],
                                             checkout=Path.cwd(), require_content=True)
    else:
        counts, sources = count_h80(inputs['h80'])
    axes = {}
    if bool(inputs.get('axes_product')) != bool(inputs.get('axes_provenance')):
        raise ValueError('independent axes require both product and provenance')
    if inputs.get('axes_product'):
        axes = load_independent_axes(inputs['axes_product'], inputs['axes_provenance'],
                                     manifest=inputs['manifest'], h80_paths=inputs['h80'])
    dataset = load_calibrated_dataset(inputs['manifest'], inputs['calibrated_flux'], counts,
        edges=config['energy_edges'], state_wise=True, independent_axes=axes,
        run_quality_path=inputs['run_quality'], count_sources=sources)
    # Inventory retains the complete P manifest. Training sees the declared cohort.
    dataset['records'] = [r for r in dataset['records'] if r['run'] in cohort]
    if {p: sha256_file(p) for p in hashes} != hashes:
        raise ValueError('campaign input identity changed during load')
    return dict(config=config, dataset=dataset, axes=axes, manifest=manifest,
                input_sha256=hashes, sources=sources)


def measured_states(dataset, runs):
    """Keep defective present states explicit; never turn them into absences."""
    excluded = {r['run'] for r in dataset['run_quality']['excluded_runs']}
    lookup = {(r['run'], r['state']): r for r in dataset['diagnostic_records']}
    result = {}
    for item in dataset['inventory']:
        key = item['run'], item['state']
        if key[0] not in runs or key[0] in excluded or item['measurement_status'] == 'missing_histogram':
            continue
        if item['measurement_status'] == 'measured_valid' and key in lookup:
            row = lookup[key]
            result[key] = dict(values=row['native_values'], calibration_edges=row['calibration_edges'])
        else:
            result[key] = dict(status=item['measurement_status'])
    return result


def _profile_inputs(campaign, runs):
    config, manifest = campaign['config'], campaign['manifest']
    excluded = {r['run'] for r in campaign['dataset']['run_quality']['excluded_runs']}
    loaded = {}
    seen = set()
    for name, path in config['inputs']['reco'].items():
        profile = get_beam_profile(name)
        universe, cutflow = read_run_universe(Path(path))
        if (set(universe) - manifest.keys() or any(manifest[r].target != profile.target
                or manifest[r].beam_type != profile.beam_type for r in universe)):
            raise ValueError('reconstruction universe conflicts with manifest/profile')
        if seen & set(universe):
            raise ValueError('duplicate reconstruction run universe')
        seen.update(universe)
        from reconstruction.runtime.provenance import validate_energy_domain
        import ROOT
        source = ROOT.TFile.Open(str(path), 'READ')
        if not source or source.IsZombie():
            raise ValueError(f'cannot validate reconstructed energy domain: {path}')
        try:
            record = source.Get('reconstruction_provenance')
            metadata = json.loads(record.GetTitle()) if record else {}
            validate_energy_domain(metadata, name, profile.energy_range_gev,
                                   requires_bdt=True, allow_legacy=False)
            identity = dict(path=str(Path(path).resolve()), uuid=str(source.GetUUID().AsString()),
                            tree='reco_eta_pi0_bdt', provenance=metadata)
        finally:
            source.Close()
        events = read_reconstructed(Path(path), 'reco_eta_pi0_bdt')
        if not set(map(int, np.unique(events.run_number))) <= set(universe):
            raise ValueError('selected events outside inclusive reconstruction universe')
        selected_runs = (set(universe) & set(runs)) - excluded
        events = events.take(np.isin(events.run_number, sorted(selected_runs)))
        audit = {}
        native = load_exposures(Path(config['inputs']['calibrated_flux']),
            manifest_path=Path(config['inputs']['manifest']), run_numbers=selected_runs,
            target=profile.target, beam_type=profile.beam_type,
            polarization_model=profile.polarization, energy_range=profile.energy_range_gev,
            run_quality=campaign['dataset']['run_quality'], audit=audit, allow_empty=True) if selected_runs else {}
        loaded[name] = dict(profile=profile, events=events, native=native, audit=audit,
                            cutflow=cutflow, runs=selected_runs, input_identity=identity)
    return loaded


def baseline_report(campaign, *, runs=None, profiles=None):
    dataset, config = campaign['dataset'], campaign['config']
    cohort = set(config['cohort_runs']) if runs is None else set(runs) & set(config['cohort_runs'])
    excluded = {r['run'] for r in dataset['run_quality']['excluded_runs']}
    valid = {(r['run'], r['state']) for r in dataset['inventory']
             if r['measurement_status'] == 'measured_valid' and r['run'] not in excluded}
    paired = {r for r in cohort if all((r, s) in valid for s in ('POL1', 'POL2'))}
    status = {(r['run'], r['state']): r['measurement_status'] for r in dataset['inventory']}
    no_brem = {r for r in paired if status[r, 'BREM'] == 'missing_histogram'}
    defective_brem = {r for r in paired if (r, 'BREM') not in valid and r not in no_brem}
    result = dict(production_adopted=False, input_sha256=campaign['input_sha256'],
        input_audit=dataset['input_audit'], cohort_runs=sorted(cohort),
        position_assumption=dataset['position_assumption'],
        counts=dict(measured_pol_pair_runs=sorted(paired),
                    measured_pol_without_brem_runs=sorted(no_brem), selected_events=None,
                    measured_pol_defective_brem_runs=sorted(defective_brem),
                    recovered_without_ml_events=None, recovered_ml_events=0), profiles={})
    if config['inputs']['reco']:
        total, gained, absent, defective = 0, 0, 0, 0
        for name, loaded in (profiles if profiles is not None else _profile_inputs(campaign, cohort)).items():
            selected = select_sigma_events(loaded['events'], loaded['native'],
                energy_range=loaded['profile'].energy_range_gev, drop_missing=True,
                run_quality=dataset['run_quality'])
            # The historical triplet baseline required a valid measured BREM at
            # each stratum. Count event rows once, never fitted signal yields.
            measured_keys = {k for k, e in loaded['native'].items() if e.brem_status == 'measured_valid'}
            prior = np.array([(int(r), int(s)) in measured_keys
                for r, s in zip(selected.run_number, selected.xstrip, strict=True)], dtype=bool)
            total += len(selected)
            gained += int((~prior).sum())
            absent += int(np.isin(selected.run_number, sorted(no_brem)).sum())
            defective += int(np.isin(selected.run_number, sorted(defective_brem)).sum())
            result['profiles'][name] = dict(input_selected_events=len(loaded['events']),
                before_events=int(prior.sum()), after_events=len(selected),
                recovered_without_ml_events=int((~prior).sum()), cutflow=loaded['cutflow'],
                flux_audit=loaded['audit'], input_identity=loaded['input_identity'])
        result['counts'].update(selected_events=total, recovered_without_ml_events=gained,
            recovered_missing_brem_events=absent, recovered_defective_brem_events=defective)
    return result


def run_inventory(config, output):
    with publish_output(output, input_paths(config)) as directory:
        campaign = load_campaign(config)
        result = baseline_report(campaign)
        write_json(directory / 'inventory.json', campaign['dataset']['inventory'])
        write_json(directory / 'baseline.json', result)
        write_json(directory / 'campaign.json', {**config, 'input_sha256': campaign['input_sha256']})
    return result


def run_baseline(config, output):
    """Compare the complete-triplet measured sample with valid POL-only data."""
    from flux_studies.energy_closure import compare_recovered_sample
    if not config['inputs']['reco']:
        raise ValueError('baseline extraction requires declared reconstructed inputs')
    with publish_output(output, input_paths(config)) as directory:
        campaign = load_campaign(config)
        profiles = _profile_inputs(campaign, set(config['cohort_runs']))
        report = baseline_report(campaign, profiles=profiles)
        report['sigma'] = {}
        for name, loaded in profiles.items():
            before = {k: e for k, e in loaded['native'].items() if e.brem_status == 'measured_valid'}
            report['sigma'][name] = compare_recovered_sample(loaded['events'], before, loaded['native'],
                energy_edges=loaded['profile'].energy_edges_gev, flux_replicas=None,
                event_replicas=0, seed=0, run_quality=campaign['dataset']['run_quality'])
        report['comparison_kind'] = 'measured POL admission only; no ML validation'
        write_json(directory / 'baseline.json', report)
        write_json(directory / 'inventory.json', campaign['dataset']['inventory'])
        write_json(directory / 'campaign.json', {**config, 'input_sha256': campaign['input_sha256']})
    return report


def _project(campaign, predictions, accepted_runs, *, truth=False):
    projected, failures = {}, []
    for row in predictions:
        if row['method'] != 'extra_trees_hybrid' or row['run'] not in accepted_runs:
            continue
        key = row['run'], row['state']
        if key in projected:
            raise ValueError(f'duplicate projected target: {key}')
        try:
            axis = campaign['axes'][key]
            values = row['truth'] if truth else row['estimate']
            if values is None:
                raise ValueError('unavailable energy estimate')
            projected[key] = map_energy_to_strips(values, campaign['config']['energy_edges'], axis)
        except (KeyError, ValueError) as exc:
            failures.append(dict(run=key[0], state=key[1], reason=str(exc)))
    return projected, failures


def original_axis_control(native, measured, predictions, energy_edges):
    """Evaluation-only rebinning control on measured axes, never model features."""
    from flux_studies.flux_observable_closure import project_to_strip_axis, replace_masked_exposures
    projected, audit = {}, []
    for row in predictions:
        if row['method'] != 'extra_trees_hybrid':
            continue
        key = row['run'], row['state']
        if key in projected:
            raise ValueError('duplicate representation control target')
        projected[key], transfer = project_to_strip_axis(row['truth'], energy_edges,
                                                          measured[key]['calibration_edges'])
        audit.append(dict(run=key[0], state=key[1], **transfer))
    return replace_masked_exposures(native, projected), audit


def accepted_uncertainty(uncertainty, decision):
    """Select the accepted policy cohort, preserving aligned failed replicas."""
    accepted = {(r['run'], r['state']) for r in decision['state_decisions'] if r['accepted']
                and r['run'] in decision['accepted_runs']}
    indices = [i for i, key in enumerate(uncertainty['keys'])
               if key['method'] == 'extra_trees_hybrid' and (key['run'], key['state']) in accepted]
    remap = {old: new for new, old in enumerate(indices)}
    result = dict(uncertainty, keys=[uncertainty['keys'][i] for i in indices],
                  draws=np.asarray(uncertainty['draws'])[:, indices])
    result['bootstrap_audit'] = [dict(row, targets=[dict(target,
        prediction_index=remap[target['prediction_index']]) for target in row['targets']
        if target['prediction_index'] in remap]) for row in uncertainty['bootstrap_audit']]
    return result


def _closure_reports(campaign, study, uncertainty, decision, phase):
    from flux_studies.energy_closure import compare_energy_scenarios
    config, dataset = campaign['config'], campaign['dataset']
    role = 'final' if phase == 'verification' else 'development'
    allowed_roles = {'final'} if role == 'final' else {'train', 'calibration', 'development'}
    runs = {a['run'] for a in config['assignments'] if a['role'] in allowed_roles}
    accepted = set(decision['accepted_runs'])
    accepted_states = {(r['run'], r['state']) for r in decision['state_decisions'] if r['accepted']}
    predictions = [p for p in study['predictions'] if p['role'] == role]
    selected = [p for p in predictions if (p['run'], p['state']) in accepted_states]
    projected, failures = _project(campaign, selected, accepted)
    roundtrip, truth_failures = _project(campaign, selected, accepted, truth=True)
    reports = []
    for loaded in _profile_inputs(campaign, runs).values():
        profile = loaded['profile']
        for period in sorted({campaign['manifest'][r].source_period for r in loaded['runs']}):
            period_runs = {r for r in loaded['runs'] if campaign['manifest'][r].source_period == period}
            masks = {(p['run'], p['state']) for p in predictions if p['run'] in period_runs}
            native = {k: e for k, e in loaded['native'].items() if k[0] in period_runs}
            events = loaded['events'].take(np.isin(loaded['events'].run_number, sorted(period_runs)))
            measured = measured_states(dataset, period_runs)
            kwargs = dict(polarization_model=profile.polarization,
                          energy_range=profile.energy_range_gev, replace_measured=True)
            def overlay(payload, failed):
                if any(item['run'] in period_runs for item in failed):
                    return {}, {'failure': 'projection unavailable; hidden truth never substituted'}
                return build_projected_exposures(measured,
                    {key: value for key, value in payload.items() if key[0] in period_runs}, **kwargs)
            recovered, audit = overlay(projected, failures)
            converted, roundtrip_audit = overlay(roundtrip, truth_failures)
            replicas = []
            for index in range(config['replicas']):
                replica_predictions = []
                for key, values in zip(uncertainty['keys'], uncertainty['draws'][index], strict=True):
                    if (key['run'], key['state']) in accepted_states and key['run'] in period_runs:
                        replica_predictions.append({**key, 'estimate': values})
                payload, failed = _project(campaign, replica_predictions, accepted)
                # An omitted entire target is a failed replica, not measured truth.
                required = {key for key in projected if key[0] in period_runs}
                replica, _ = overlay(payload, failed)
                replicas.append(replica if not failed and required <= payload.keys() else None)
            universe = [tuple(p[1:]) for p in config.get('point_universe', []) if p[0] == period]
            report = compare_energy_scenarios(events, native, recovered, converted,
                masked_states=masks, accepted_runs=accepted & {r for r, _ in masks},
                energy_edges=profile.energy_edges_gev, workers=1,
                event_replicas=config['replicas'], flux_replicas=replicas, seed=config['seed'],
                point_universe=universe or None, run_quality=dataset['run_quality'])
            report.update(period=period, projection_audit=audit, roundtrip_audit=roundtrip_audit,
                          projection_failures=failures, representation_failures=truth_failures)
            # Keep independent-axis changes distinct from the common-grid effect.
            # Original target axes are read only here, after model and decisions.
            from flux_studies.energy_closure import _extract
            from flux_studies.flux_observable_closure import _comparison
            local_predictions = [p for p in selected if p['run'] in period_runs and p['run'] in accepted]
            rejected_pol = {r for r, s in masks if s != 'BREM'} - accepted
            matched_native = {k: v for k, v in native.items() if k[0] not in rejected_pol}
            matched_events = select_sigma_events(events, matched_native,
                energy_range=profile.energy_range_gev, drop_missing=True, run_quality=dataset['run_quality'])
            try:
                original, control_audit = original_axis_control(matched_native, measured,
                    local_predictions, config['energy_edges'])
                points = _extract(matched_events, original, profile.energy_edges_gev, 1)
                original_points = {k: v for k, v in points.items() if list(k) in report['point_universe']}
                references = {name: {tuple(p['key']): {k: v for k, v in p.items() if k != 'key'}
                    for p in report['scenarios'][name]['points']} for name in ('C', 'D')}
                keys = [tuple(k) for k in report['point_universe']]
                report['axis_diagnostics'] = dict(status='evaluated', projections=control_audit,
                    points=[dict(key=list(k), **p) for k, p in original_points.items()],
                    comparisons=_comparison(references['C'], original_points, 'original_axis_roundtrip', 'C', keys, set())
                        + _comparison(original_points, references['D'], 'D', 'original_axis_roundtrip', keys, set()))
            except (ValueError, KeyError) as exc:
                report['axis_diagnostics'] = dict(status='unavailable', reason=str(exc),
                                                  missing_points=report['expected_points'])
            reports.append(report)
    return reports


def run_study(config, output, *, phase='development', protocol_sha256=None):
    """Develop or verify one explicitly specified mask/rule, retaining all failures."""
    from flux_studies.energy_validation import (evaluate_energy, calibrate_energy_uncertainty,
                                               energy_replicas, grouped_energy_coverage)
    from flux_studies.energy_protocol import decide_energy_runs, qualify_energy
    if phase not in ('development', 'verification'):
        raise ValueError('unknown study phase')
    if phase == 'verification' and (not protocol_sha256 or not config.get('parameters')):
        raise ValueError('verification requires a frozen protocol and parameters')
    if not config['inputs']['reco']:
        raise ValueError('study requires explicit reconstructed UV/VIS inputs')
    with publish_output(output, input_paths(config)) as directory:
        campaign = load_campaign(config)
        roles = {a['run']: a['role'] for a in config['assignments']}
        role = 'final' if phase == 'verification' else 'development'
        masks = [m for m in config['masks'] if roles[m[0]] in ('calibration', role)]
        parameters = ({tuple(f['group']): f['parameters'] for f in config['parameters']}
                      if config.get('parameters') else None)
        study = evaluate_energy(campaign['dataset']['records'], assignments=config['assignments'],
                                 masks=masks, seed=config['seed'], parameters=parameters,
                                 n_bins=len(config['energy_edges']) - 1)
        calibration = calibrate_energy_uncertainty(study, min_groups=config['min_groups'])
        uncertainty = energy_replicas(campaign['dataset']['records'], study, calibration,
            roles=(role,), n_replicas=config['replicas'], seed=config['seed'], min_groups=config['min_groups'])
        coverage_all = grouped_energy_coverage(study, uncertainty, min_groups=config['min_groups'],
                                               n_resamples=config['coverage_resamples'], seed=config['seed'])
        predictions = [p for p in study['predictions'] if p['role'] == role]
        decisions = decide_energy_runs(predictions, uncertainty, campaign['dataset'], campaign['axes'],
            config['rule'], config['normalization_domains'], masked_states=masks)
        coverage = grouped_energy_coverage(study, accepted_uncertainty(uncertainty, decisions),
            min_groups=config['min_groups'], n_resamples=config['coverage_resamples'], seed=config['seed'])
        closure = _closure_reports(campaign, study, uncertainty, decisions, phase)
        domains = [dict(d, period=d['group'][0], state=d['group'][-1]) for d in coverage['domains']
                   if d['method'] == 'extra_trees_hybrid']
        qualification = qualify_energy(closure, domains, config['limits'],
            point_universe=config.get('point_universe'), systematics=config.get('systematics'))
        report = dict(phase=phase, protocol_sha256=protocol_sha256,
            qualification=qualification, decisions=decisions, closure=closure,
            coverage=domains, production_adopted=False,
            input_sha256=campaign['input_sha256'], baseline=baseline_report(campaign,
                runs={a['run'] for a in config['assignments'] if
                      (a['role'] == 'final' if phase == 'verification' else a['role'] != 'final')}))
        write_json(directory / 'report.json', report)
        write_json(directory / 'inventory.json', campaign['dataset']['inventory'])
        write_json(directory / 'study.json', study)
        write_json(directory / 'uncertainty.json', uncertainty)
        write_json(directory / 'calibration.json', calibration)
        write_json(directory / 'all_mask_coverage.json', coverage_all)
        write_json(directory / 'development_config.json', {**config,
            'input_sha256': campaign['input_sha256'], 'parameters': study['fits']})
    return report


def run_application(protocol_path, verification_path, output):
    """Publish candidates only after the frozen procedure qualified its domain.

    This is an explicit experimental extraction. It never installs a recovered
    file into the production workflow or overwrites calibrated measurements.
    """
    from flux_studies.energy_protocol import load_protocol, load_verified_result, qualify_energy, decide_energy_runs
    from flux_studies.energy_validation import (evaluate_energy, predict_energy,
        calibrate_energy_uncertainty, energy_replicas)
    frozen = load_protocol(protocol_path)
    config = frozen['config']
    verification = load_verified_result(protocol_path, verification_path)
    qualification = qualify_energy(verification['closure'], verification['coverage'], config['limits'],
        point_universe=config['point_universe'], systematics=config['systematics'])
    if qualification['status'] != 'qualified':
        raise ValueError('frozen verification has not qualified recovery')
    paths = input_paths(config) + [str(protocol_path), str(verification_path)]
    with publish_output(output, paths) as directory:
        campaign = load_campaign(config)
        dataset = campaign['dataset']
        parameters = {tuple(f['group']): f['parameters'] for f in config['parameters']}
        roles = {a['run']: a['role'] for a in config['assignments']}
        verified_domains = {tuple(d) for d in qualification.get('qualified_domains', [])}
        targets, unsupported = [], []
        for row in dataset['inventory']:
            if row['run'] not in config['cohort_runs'] or row['measurement_status'] != 'missing_histogram':
                continue
            if (row['period'], row['state']) not in verified_domains:
                unsupported.append(dict(run=row['run'], state=row['state'], period=row['period'],
                                         accepted=False, reasons=['domain_not_qualified']))
                continue
            record = campaign['manifest'][row['run']]
            targets.append(dict(run=row['run'], state=row['state'], period=row['period'],
                position=row['position'], count=row['count'] or 0,
                group=(record.source_period, record.target, record.beam_type, row['state']),
                quality_excluded='run_quality' in row['reasons']))
        target_runs = {row['run'] for row in targets}
        fitting_records = [r for r in dataset['records'] if r['run'] not in target_runs]
        known = evaluate_energy(fitting_records, assignments=config['assignments'],
            masks=[m for m in config['masks'] if roles[m[0]] == 'calibration' and m[0] not in target_runs],
            seed=config['seed'], parameters=parameters, n_bins=len(config['energy_edges']) - 1)
        calibration = calibrate_energy_uncertainty(known, min_groups=config['min_groups'])
        study = predict_energy(fitting_records, targets, assignments=config['assignments'],
                                seed=config['seed'], parameters=parameters,
                                n_bins=len(config['energy_edges']) - 1)
        uncertainty = energy_replicas(fitting_records, study, calibration,
            roles=tuple(set(roles.values())), n_replicas=config['replicas'],
            seed=config['seed'], min_groups=config['min_groups'])
        normalization = [d for d in config['normalization_domains']
                          if (d['period'], d['state']) in verified_domains]
        decisions = decide_energy_runs(study['predictions'], uncertainty, dataset, campaign['axes'],
                                        config['rule'], normalization)
        decisions['state_decisions'].extend(unsupported)
        accepted_states = {(r['run'], r['state']) for r in decisions['state_decisions'] if r['accepted']}
        selected = [p for p in study['predictions'] if (p['run'], p['state']) in accepted_states]
        projected, failures = _project(campaign, selected, set(decisions['accepted_runs']))
        # Products without adequate independent axes remain energetic candidates.
        write_json(directory / 'energy_candidates.json', dict(representation='integrated_bin_flux',
            energy_unit='GeV', flux_unit='calibrated_flux_integral', edges=config['energy_edges'],
            predictions=study['predictions'], decisions=decisions, projection_failures=failures,
            protocol_sha256=frozen['sha256'], production_adopted=False))
        write_json(directory / 'uncertainty.json', uncertainty)
        write_json(directory / 'calibration.json', calibration)
        summaries = {}
        from flux_studies.energy_closure import compare_recovered_sample
        for name, loaded in _profile_inputs(campaign, set(config['cohort_runs'])).items():
            local = {key: value for key, value in projected.items() if key[0] in loaded['runs']}
            recovered, audit = build_projected_exposures(measured_states(dataset, loaded['runs']), local,
                polarization_model=loaded['profile'].polarization,
                energy_range=loaded['profile'].energy_range_gev)
            replicas = []
            for index in range(config['replicas']):
                replica_predictions = [{**key, 'estimate': values} for key, values in
                    zip(uncertainty['keys'], uncertainty['draws'][index], strict=True)
                    if (key['run'], key['state']) in accepted_states and key['run'] in loaded['runs']]
                payload, failed = _project(campaign, replica_predictions, set(decisions['accepted_runs']))
                if failed or not set(local) <= payload.keys():
                    replicas.append(None)
                else:
                    replica, _ = build_projected_exposures(measured_states(dataset, loaded['runs']), payload,
                        polarization_model=loaded['profile'].polarization,
                        energy_range=loaded['profile'].energy_range_gev)
                    replicas.append(replica)
            summaries[name] = compare_recovered_sample(loaded['events'], loaded['native'], recovered,
                energy_edges=loaded['profile'].energy_edges_gev, flux_replicas=replicas,
                event_replicas=config['replicas'], seed=config['seed'], run_quality=dataset['run_quality'])
            summaries[name]['projection_audit'] = audit
        report = dict(protocol_sha256=frozen['sha256'], verification_sha256=sha256_file(verification_path),
            decisions=decisions, comparisons=summaries, production_adopted=False,
            caveat='Real missing flux has no measured oracle; final comparison is benefit and stability only.')
        write_json(directory / 'report.json', report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('inventory', 'baseline', 'develop', 'freeze', 'verify', 'apply'))
    parser.add_argument('--config', type=Path, help='explicit campaign JSON for inventory/develop/freeze')
    parser.add_argument('--protocol', type=Path, help='frozen protocol for verify/apply')
    parser.add_argument('--verification', type=Path, help='verification report required for apply')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    if Path('results_test').resolve() not in args.output.resolve().parents:
        parser.error('--output must be inside an explicit results_test/<campaign>/ root')
    if args.action in ('inventory', 'baseline', 'develop', 'freeze'):
        if args.config is None:
            parser.error('--config is required')
        config = json.loads(args.config.read_text())
        if args.action == 'inventory':
            run_inventory(config, args.output)
        elif args.action == 'baseline':
            run_baseline(config, args.output)
        elif args.action == 'develop':
            run_study(config, args.output)
        else:
            from flux_studies.energy_protocol import freeze_protocol
            identities = {p: sha256_file(p) for p in input_paths(config)}
            if 'input_sha256' in config and config['input_sha256'] != identities:
                raise ValueError('cannot rebind developed parameters to changed input identities')
            config['input_sha256'] = identities
            freeze_protocol(config, args.output)
    else:
        if args.protocol is None:
            parser.error('--protocol is required')
        from flux_studies.energy_protocol import load_protocol, claim_final, complete_verification
        frozen = load_protocol(args.protocol)
        if args.action == 'verify':
            if args.output.exists():
                parser.error('verification output already exists')
            claim_final(args.protocol)
            run_study(frozen['config'], args.output, phase='verification', protocol_sha256=frozen['sha256'])
            complete_verification(args.protocol, args.output / 'report.json')
        else:
            if args.verification is None:
                parser.error('--verification is required')
            run_application(args.protocol, args.verification, args.output)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
