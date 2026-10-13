"""Reproduce the plan-05 VIS background audit without changing production.

Run: python3 -m scripts.audit_bdt_backgrounds --output results/<new>/backgrounds
Existing MC is read only. Models below are diagnostic, never production bundles.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, replace
import hashlib
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
import uproot
from xgboost import XGBClassifier

from bdt_training.beam_spectrum import BeamSpectrum, reweight
from bdt_training.dataset.channel_weights import channel_yield, compute_shares
from bdt_training.dataset.mc_samples import (
    _extract_E_theta, _load_4vec, load_photons, shuffle_photons,
)
from bdt_training.photon_loss import LossParams, p_loss, sample_surviving_photons
from bdt_training.training.stage1_training import _find_best_threshold
from graal_common.physics.channels import CHANNELS, ETA_PI0_HYP, M_PROTON
from graal_common.physics.pairing import best_pairing_indices, pair_masses
from graal_common.stage1.features import compute_stage1_features, feature_names


def exact_four_probability(survival: np.ndarray) -> np.ndarray:
    """Poisson-binomial P(N_observed=4), with independent photon efficiencies."""
    distribution = np.zeros((len(survival), 5))
    distribution[:, 0] = 1
    for probability in survival.T:
        previous = distribution.copy()
        distribution *= 1 - probability[:, None]
        distribution[:, 1:] += previous[:, :-1] * probability[:, None]
    return distribution[:, 4]


def paired_efficiency(a, b, weights):
    """Weighted paired difference; fixed weights, event sampling uncertainty."""
    total = float(weights.sum())
    if total <= 0:
        return None
    delta = np.asarray(a, float) - np.asarray(b, float)
    mean = float(np.dot(weights, delta) / total)
    return dict(difference=mean, standard_error=float(
        np.sqrt(np.sum(weights**2 * (delta - mean)**2)) / total))


def signed_mass(vectors):
    square = vectors[..., 3]**2 - np.sum(vectors[..., :3]**2, axis=-1)
    return np.sign(square) * np.sqrt(np.abs(square))


def identity(path):
    path = Path(path)
    with path.open('rb') as stream:
        hasher = hashlib.sha256()
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            hasher.update(chunk)
        digest = hasher.hexdigest()
    return dict(path=str(path.resolve()), bytes=path.stat().st_size, sha256=digest)


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def summary(values):
    return dict(mean=float(values.mean()), rms=float(np.sqrt(np.mean(values**2))),
                q01_q50_q99=np.quantile(values, [.01, .5, .99], axis=0).tolist())


def observable_selection(photons, beam, X):
    heavy_idx, light_idx = best_pairing_indices(pair_masses(photons), ETA_PI0_HYP)
    rows = np.arange(len(photons))[:, None]
    heavy = photons[rows, heavy_idx].sum(axis=1)
    light = photons[rows, light_idx].sum(axis=1)
    missing = beam + [0, 0, 0, M_PROTON] - heavy - light
    selected = ((X[:, 8] < 10) & (heavy[:, 3] <= beam[:, 3])
                & (light[:, 3] <= beam[:, 3])
                & (np.abs(signed_mass(missing) - M_PROTON) < .06))
    return selected, heavy, light


def audit_channel(path, channel, spectrum, seed, cap):
    """Audit all rows; a fixed per-channel subset supports diagnostic training."""
    rng = np.random.default_rng(seed)
    with uproot.open(path) as root:
        tree = root['mc']
        photons = load_photons(tree, channel)
        beam, proton = (_load_4vec(tree, name) for name in ('beam', 'proton'))
        n = len(beam)
        multiplicity = (np.unique(tree['n_true_gamma'].array(library='np')).tolist()
                        if 'n_true_gamma' in tree else [photons.shape[1]])
        true_residual = None
        true_eta_phi = None
        if 'beam_true' in tree:
            true_photons = np.stack([_load_4vec(tree, name + '_true')
                                    for name in channel.photon_branches], axis=1)
            true_residual = np.max(np.abs(
                _load_4vec(tree, 'beam_true') + [0, 0, 0, M_PROTON]
                - _load_4vec(tree, 'proton_true') - true_photons.sum(axis=1)), axis=0).tolist()
            eta = true_photons[:, :2].sum(axis=1)
            true_eta_phi = np.arctan2(eta[:, 1], eta[:, 0])
        energies, theta = _extract_E_theta(photons)
        params = LossParams()
        exact = exact_four_probability(1 - p_loss(energies, theta, params))
        observed, mask = sample_surviving_photons(photons, energies, theta, rng, params)
        residual = beam + [0, 0, 0, M_PROTON] - proton - photons.sum(axis=1)
        decay_pair_masses = signed_mass(photons[:, 0::2] + photons[:, 1::2])
        record = dict(input=identity(path), entries=n, n_photons=photons.shape[1],
                      n_true_gamma_values=multiplicity, threshold_gev=channel.production_threshold_gev,
                      sigma_ref_ub=channel.sigma_ref_ub, e_ref_gev=channel.e_ref_gev,
                      signal_br_ratio=channel.signal_br_ratio,
                      smeared_decay_pair_masses=summary(decay_pair_masses),
                      smeared_four_momentum_residual=summary(residual),
                      truth_max_abs_four_momentum_residual=true_residual,
                      truth_status='available' if true_residual else 'not stored; smeared closure is not truth closure',
                      analytic_p_four=float(exact.mean()), sampled_four=int(mask.sum()),
                      sampled_p_four=float(mask.mean()),
                      sampling_standard_error=float(np.sqrt(np.sum(exact*(1-exact))) / n))
        if channel.name == 'eta_via_3pi0':
            record['smeared_six_gamma_mass'] = summary(signed_mass(photons.sum(axis=1)))
        if channel.name == 'eta_pi0_via_3pi0':
            record['smeared_eta_six_gamma_mass'] = summary(signed_mass(photons[:, :6].sum(axis=1)))
        del photons, energies, theta, exact, residual
        observed = shuffle_photons(observed, rng)
        X = compute_stage1_features(observed, proton[mask], beam[mask], ETA_PI0_HYP)
        selected, heavy, light = observable_selection(observed, beam[mask], X)
        # Preserve current production semantics in baseline; compare proposal-based
        # weights explicitly, without adopting them in production.
        energy = beam[mask, 3]
        current_w = reweight(energy, spectrum)
        proposal_w = reweight(beam[:, 3], spectrum)[mask]
        current_y = channel_yield(channel, energy, current_w, n)
        proposal_y = channel_yield(channel, energy, proposal_w, n)
        record.update(no_fit_selected=int(selected.sum()), zero_weight=int((current_w == 0).sum()),
                      current_y_unit=current_y.y_unit, proposal_y_unit=proposal_y.y_unit,
                      current_y_sigma=current_y.y_sigma, proposal_y_sigma=proposal_y.y_sigma)
        kept = np.sort(np.random.default_rng(seed+1000).choice(len(X), min(cap, len(X)), replace=False))
        row_ids = np.flatnonzero(mask)[kept]
        # Separate RNG, assigned once: removing a channel never changes other splits.
        split_u = np.random.default_rng(seed+2000).random(len(kept))
        split = np.where(split_u < .6, 0, np.where(split_u < .8, 1, 2))
        phi = np.arctan2(heavy[:, 1], heavy[:, 0])
        data = dict(X=X[kept], beam_E=energy[kept], w=current_w[kept],
                    proposal_w=proposal_w[kept], row_ids=row_ids, split=split,
                    selected=selected[kept], mass_eta=signed_mass(heavy)[kept],
                    mass_pi0=signed_mass(light)[kept], phi=phi[kept],
                    truth_phi=(true_eta_phi[mask][kept] if true_eta_phi is not None else phi[kept]))
    return record, data, replace(current_y, is_signal=channel.name == 'eta_pi0'), replace(
        proposal_y, is_signal=channel.name == 'eta_pi0')


def weights_for(samples, shares, field='w'):
    return {name: data[field] * shares[name] / data[field].sum()
            for name, data in samples.items() if name in shares}


def efficiency(mask, weights):
    return float(np.dot(mask, weights) / weights.sum()) if weights.sum() > 0 else None


def histograms(data, selected, weights):
    result = {}
    for field, edges in (
        ('mass_eta', np.linspace(0, .9, 31)), ('mass_pi0', np.linspace(0, .4, 31)),
        ('beam_E', np.linspace(.9313, 1.1, 18)), ('phi', np.linspace(-np.pi, np.pi, 17))):
        result[field] = dict(edges=edges.tolist(),
                            before=np.histogram(data[field], edges, weights=weights)[0].tolist(),
                            after=np.histogram(data[field][selected], edges, weights=weights[selected])[0].tolist(),
                            outside_count=int(((data[field] < edges[0]) | (data[field] > edges[-1])).sum()))
    return result


def injection(samples, accepted, weights, seed, trials=200, events=2000):
    """Conditional MC moment toy, not the production ratio/likelihood estimator.

    Inject Sigma=.3 in signal truth eta phi; backgrounds Sigma=0. Resample the
    same held-out identities for all variants; assign polarization states with
    P=0.6. No assumption of independent ablations. Known-fraction correction
    is an oracle diagnostic, not a measured contamination correction.
    """
    names = list(samples)
    probabilities = np.concatenate([weights[name][samples[name]['split'] == 2] for name in names])
    probabilities /= probabilities.sum()
    phi = np.concatenate([samples[name]['phi'][samples[name]['split'] == 2] for name in names])
    truth_phi = np.concatenate([samples[name]['truth_phi'][samples[name]['split'] == 2] for name in names])
    signal = np.concatenate([np.full(int((samples[name]['split'] == 2).sum()), name == 'eta_pi0') for name in names])
    gates = {variant: np.concatenate([masks[name] for name in names]) for variant, masks in accepted.items()}
    fractions = {variant: float(np.sum(probabilities * gate * signal) / np.sum(probabilities * gate))
                 for variant, gate in gates.items() if np.sum(probabilities * gate) > 0}
    rng = np.random.default_rng(seed)
    draws = {variant: [] for variant in gates}
    for _ in range(trials):
        rows = rng.choice(len(phi), events, p=probabilities)
        plus = rng.random(events) < (1 - .6 * .3 * signal[rows] * np.cos(2*truth_phi[rows])) / 2
        moments = -2 * np.where(plus, 1., -1.) * np.cos(2*phi[rows]) / .6
        for variant, gate in gates.items():
            values = moments[gate[rows]]
            if len(values) < 2:
                draws[variant].append([None, None])
                continue
            draws[variant].append([float(values.mean()), float(values.std(ddof=1)/np.sqrt(len(values)))])
    diagnostics = {}
    for variant, gate in gates.items():
        rows = np.asarray(draws[variant], dtype=float)
        valid = np.isfinite(rows).all(axis=1)
        rows = rows[valid]
        norm = np.sum(probabilities * gate)
        # Response includes contamination, reconstruction migration and phi
        # acceptance. Known only inside this MC toy, never a data correction.
        response = (float(2 * np.sum(probabilities * gate * signal
                                    * np.cos(2*phi) * np.cos(2*truth_phi)) / norm)
                    if norm > 0 else None)
        diagnostics[variant] = dict(
            valid_trials=int(valid.sum()), unavailable_trials=int((~valid).sum()),
            response=response,
            bias=float(rows[:, 0].mean() - .3) if len(rows) else None,
            bias_standard_error=float(rows[:, 0].std(ddof=1)/np.sqrt(len(rows))) if len(rows) > 1 else None,
            coverage_68=float(np.mean(abs(rows[:, 0]-.3) <= rows[:, 1])) if len(rows) else None,
            oracle_response_corrected_bias=(float(rows[:, 0].mean()/response-.3)
                                            if len(rows) and response else None),
            oracle_response_corrected_coverage_68=(float(np.mean(
                abs(rows[:, 0]/response-.3) <= rows[:, 1]/abs(response)))
                if len(rows) and response else None))
    return dict(injected_sigma=.3, polarization=.6, background_sigma=0., trials=trials,
                events_before_selection=events, known_signal_fractions=fractions,
                paired_replicas=draws, summary=diagnostics,
                limitation='Conditional VIS toy, eta-lab azimuth, moment estimator, fixed training prior; not production Sigma bias/coverage or a detector validation.')


def run(args):
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    spectrum = BeamSpectrum.load(args.beam_spectrum)
    if not np.allclose(spectrum.edges[[0, -1]], [.9313, 1.1], rtol=0, atol=1e-12):
        raise ValueError('This study requires the nominal VIS spectrum')
    names = ['eta_pi0', 'pi0pi0', '3pi0', 'eta_via_3pi0', '4pi0', 'eta_pi0_via_3pi0']
    records, samples, yields, proposal_yields = {}, {}, [], []
    for index, name in enumerate(names):
        print('audit', name, flush=True)
        record, data, current_y, proposal_y = audit_channel(
            Path(args.mc_dir) / CHANNELS[name].mc_filename, CHANNELS[name], spectrum,
            args.seed + index, args.cap)
        records[name], samples[name] = record, data
        yields.append(current_y)
        proposal_yields.append(proposal_y)
        np.savez_compressed(output / f'{name}_sample.npz', **data)
    write_json(output / 'audit.json', records)
    variants = {
        'current': names,
        'without_eta_decays': [name for name in names if name not in ('eta_via_3pi0', 'eta_pi0_via_3pi0')],
        'add_eta_6gamma': [name for name in names if name != 'eta_pi0_via_3pi0'],
        'without_unmeasured_4pi0': [name for name in names if name != '4pi0'],
        'proposal_weights': names,
    }
    reference_shares = compute_shares(yields, .5)
    reference_weights = weights_for(samples, reference_shares)
    metrics, all_gates = {}, {}
    for variant, included in variants.items():
        print('train', variant, flush=True)
        variant_dir = output / variant
        variant_dir.mkdir()
        proposals = variant == 'proposal_weights'
        shares = compute_shares([y for y in (proposal_yields if proposals else yields)
                                 if y.channel.name in included], .5)
        weights = weights_for(samples, shares, 'proposal_w' if proposals else 'w')
        arrays = {part: [np.concatenate([data[field][data['split'] == part] if field != 'w'
                                        else weights[name][data['split'] == part]
                                        for name, data in samples.items() if name in included])
                        for field in ('X', 'w')] for part in (0, 1)}
        labels = {part: np.concatenate([np.full(int((samples[name]['split'] == part).sum()), name == 'eta_pi0')
                                        for name in included]) for part in (0, 1)}
        train_X, train_w = arrays[0]
        model = XGBClassifier(n_estimators=100, max_depth=5, learning_rate=.05,
                              subsample=.8, colsample_bytree=.8, min_child_weight=1,
                              tree_method='hist', device='cpu', n_jobs=4, random_state=args.seed)
        model.fit(train_X, labels[0], sample_weight=train_w/train_w.mean())
        threshold = _find_best_threshold(labels[1], model.predict_proba(arrays[1][0])[:, 1], arrays[1][1])
        model.save_model(variant_dir / 'diagnostic_model.json')
        result = dict(shares=shares, threshold=threshold, channels={})
        gates = {}
        for name, data in samples.items():
            test = data['split'] == 2
            test_data = {field: values[test] for field, values in data.items()}
            score = model.predict_proba(data['X'][test])[:, 1]
            bdt = score >= threshold
            selected = bdt & data['selected'][test]
            gates[name] = selected
            ref_w = reference_weights[name][test]
            result['channels'][name] = dict(
                holdout_count=int(test.sum()), bdt_efficiency=efficiency(bdt, ref_w),
                no_fit_efficiency=efficiency(data['selected'][test], ref_w),
                combined_efficiency=efficiency(selected, ref_w),
                combined_count=int(selected.sum()), sculpting=histograms(test_data, selected, ref_w))
            np.savez_compressed(variant_dir / f'{name}_holdout.npz',
                                row_ids=data['row_ids'][test], scores=score, accepted=selected)
        metrics[variant], all_gates[variant] = result, gates
        write_json(variant_dir / 'metrics.json', result)
    comparisons = {variant: {name: paired_efficiency(gates[name], all_gates['current'][name],
                                                     reference_weights[name][samples[name]['split'] == 2])
                             for name in names} for variant, gates in all_gates.items()}
    write_json(output / 'comparisons.json', comparisons)
    write_json(output / 'injection.json', injection(samples, all_gates, reference_weights, args.seed+5000))
    code_paths = [Path(__file__), Path('00_common/physics/channels.py'), Path('00_common/physics/cross_sections.py'),
                  Path('00_common/physics/pairing.py'), Path('00_common/stage1/features.py'),
                  Path('04_bdt_training/beam_spectrum.py'), Path('04_bdt_training/photon_loss.py'),
                  Path('04_bdt_training/dataset/channel_weights.py'), Path('04_bdt_training/dataset/mc_samples.py'),
                  Path('04_bdt_training/training/stage1_training.py')]
    write_json(output / 'manifest.json', dict(
        command=sys.argv, revision=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
        seed=args.seed, cap_per_channel=args.cap, split='60/20/20, assigned once per channel',
        production_modified=False, kinfit=False, chi2_cut=10, missing_mass_window_gev=.06,
        beam_spectrum=identity(args.beam_spectrum), inputs=[v['input'] for v in records.values()],
        sources=[identity(path) for path in code_paths], photon_loss=asdict(LossParams()),
        features=feature_names(), profile='vis', signal_prior=.5,
        packages={name: importlib.metadata.version(name) for name in ('numpy', 'uproot', 'xgboost', 'scikit-learn')},
        missing_uv_channels=list(CHANNELS),
        limitations=['MC detector simplification', 'preselected energy target is not calibrated incident flux',
                     'background truth four-vectors and generator seed absent in existing ROOT files',
                     'production normalization and branching not certified',
                     'reweighted proposal diagnostic uses measured beam, not true-beam response unfolding',
                     'conditional injection toy is not production Sigma inference']))
    print('saved', output, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mc-dir', default='test_data/vis/mc')
    parser.add_argument('--beam-spectrum', default='test_data/vis/bdt/beam_spectrum.npz')
    parser.add_argument('--output', required=True)
    parser.add_argument('--seed', type=int, default=20261013)
    parser.add_argument('--cap', type=int, default=80000)
    run(parser.parse_args())
