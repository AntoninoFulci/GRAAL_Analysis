"""Diagnostic UV/VIS comparison with grouped, untouched MC test events.

Run with --help. Outputs always require a new directory. Current channel and
detector weights are assumptions, not validated physical contamination rates.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, replace
import hashlib
import importlib.metadata
from pathlib import Path
import shutil
import subprocess
import sys

import numpy as np
from sklearn.metrics import average_precision_score, precision_recall_fscore_support, roc_auc_score
import uproot

from bdt_training.beam_spectrum import (
    default_bins_for_range, from_energies, reweight, validate_signal_support,
)
from bdt_training.dataset.channel_weights import channel_yield, compute_shares
from bdt_training.dataset.grouped_split import assign_group_splits, audit_group_splits
from bdt_training.dataset.mc_samples import build_channel_features, _load_4vec
from bdt_training.dataset.stage1_dataset import (
    Stage1Dataset, Stage1DatasetMetadata, Stage1Rows, _validate_dataset, save_stage1_dataset,
)
from bdt_training.photon_loss import LossParams
from bdt_training.training.stage1_training import TrainingConfig, fit_stage1
from bdt_training.training.stage1_reporting import format_metrics_text
from graal_common.physics.beam_profiles import get_beam_profile
from graal_common.physics.channels import CHANNELS, ETA_PI0_HYP, TAGGER_FWHM_GEV, TAGGER_SIGMA_GEV
from graal_common.stage1.artifacts import Stage1ArtifactPaths, Stage1Provenance
from graal_common.stage1.features import FEATURE_NAMES_S1
from scripts.audit_bdt_backgrounds import (
    identity, write_json, observable_selection, signed_mass, paired_efficiency, injection,
)


def comparison_datasets(uv: Stage1Dataset, vis: Stage1Dataset) -> dict[str, Stage1Dataset]:
    """Preserve origins and splits, fix equal profile weight in every partition."""
    for name, data in (("uv", uv), ("vis", vis)):
        if data.rows is None or data.rows.split is None:
            raise ValueError("comparison requires origin identity and persisted grouped splits; regenerate legacy NPZ")
        _validate_dataset(data)
        if data.metadata.beam_profile != name:
            raise ValueError(f"expected {name} dataset")
        if data.metadata.feature_names != tuple(FEATURE_NAMES_S1):
            raise ValueError("comparison requires the canonical ordered feature schema")
        if data.metadata.hypothesis != "eta_pi0" or data.metadata.signal_channel != "eta_pi0":
            raise ValueError("comparison requires eta_pi0 signal and hypothesis")
        if data.metadata.signal_prior != .5 or data.metadata.beam_reweighted is not True:
            raise ValueError("diagnostic protocol requires signal prior 0.5 and beam reweighting")

    rows = Stage1Rows(**{key: np.concatenate([getattr(data.rows, key) for data in (uv, vis)])
                         for key in ("origin_id", "channel", "profile", "detector_variant", "split")})
    audit_group_splits(rows.origin_id, rows.split)
    result = {}
    for name, data in (("uv", uv), ("vis", vis)):
        weights = data.w.astype(float).copy()
        for part in (0, 1, 2):
            mask = data.rows.split == part
            if any(not np.any(mask & (data.y == label) & (weights > 0)) for label in (0, 1)):
                raise ValueError(f"{name} split {part} lacks positive-weight signal or background")
            weights[mask] *= mask.sum() / weights[mask].sum()
        result[name] = replace(data, w=weights)
    weights = np.concatenate([uv.w, vis.w]).astype(float)
    for part in (0, 1, 2):
        mask = rows.split == part
        for name in ("uv", "vis"):
            selected = mask & (rows.profile == name)
            weights[selected] *= .5 * mask.sum() / weights[selected].sum()
    result["shared"] = Stage1Dataset(
        np.concatenate([uv.X, vis.X]), np.concatenate([uv.y, vis.y]), weights,
        replace(uv.metadata, beam_profile=None, energy_min_gev=None, energy_max_gev=None), rows,
    )
    _validate_dataset(result["shared"])
    return result


def efficiency_threshold(y, scores, weights, *, target=.8) -> float:
    """Lowest descending weighted validation quantile reaching target signal efficiency."""
    mask = (np.asarray(y) == 1) & (np.asarray(weights) > 0)
    if not 0 < target <= 1 or not np.any(mask):
        raise ValueError("signal efficiency needs a target in (0,1] and positive signal weights")
    order = np.argsort(-np.asarray(scores)[mask], kind="stable")
    s, w = np.asarray(scores)[mask][order], np.asarray(weights)[mask][order]
    index = min(int(np.searchsorted(np.cumsum(w), target * w.sum())), len(s) - 1)
    return float(s[index])


def metrics(y, scores, weights, threshold) -> dict:
    """Weighted test metrics; absent classes are unavailable, never zero AUC."""
    y, scores, weights = map(np.asarray, (y, scores, weights))
    active = weights > 0
    pred = scores >= threshold
    precision, recall, f1, _ = precision_recall_fscore_support(
        y, pred, average="binary", sample_weight=weights, zero_division=0,
    ) if np.any(active) else (None, None, None, None)
    both = all(np.any(active & (y == label)) for label in (0, 1))
    def efficiency(label):
        mask = y == label
        return float(np.dot(weights[mask], pred[mask]) / weights[mask].sum()) if weights[mask].sum() > 0 else None
    signal, background = efficiency(1), efficiency(0)
    return dict(n=len(y), positive_weight_rows=int(active.sum()), sum_weight=float(weights.sum()),
                auc=float(roc_auc_score(y, scores, sample_weight=weights)) if both else None,
                average_precision=float(average_precision_score(y, scores, sample_weight=weights)) if both else None,
                precision=float(precision) if precision is not None else None,
                recall=float(recall) if recall is not None else None,
                f1=float(f1) if f1 is not None else None,
                signal_efficiency=signal, background_rejection=1-background if background is not None else None)


def train_comparison(datasets, output: Path, config: TrainingConfig):
    """Write protocol first, fit exactly three models, then lock thresholds."""
    output = Path(output)
    if (output / "protocol.json").exists():
        raise FileExistsError("comparison already registered; use a new output directory")
    protocol = dict(schema_version=1, status="diagnostic_only", profile_mixture={"uv": .5, "vis": .5},
                    config=asdict(config), hyperparameter_search_budget=0,
                    primary_threshold="weighted_validation_f1_single",
                    secondary="per-profile thresholds at validation signal efficiency 0.8",
                    sigma_validation="not performed; conditional MC moment toy only")
    write_json(output / "protocol.json", protocol)
    shared = datasets["shared"]
    save_stage1_dataset(output / "shared_dataset.npz", shared)
    np.savez_compressed(output / "split.npz", origin_id=shared.rows.origin_id,
                        split=shared.rows.split, channel=shared.rows.channel, profile=shared.rows.profile)
    audit = audit_group_splits(shared.rows.origin_id, shared.rows.split)
    audit["by_profile"] = {name: audit_group_splits(data.rows.origin_id, data.rows.split)
                           for name, data in datasets.items() if name != "shared"}
    write_json(output / "split_audit.json", audit)
    dataset_hash = identity(output / "shared_dataset.npz")["sha256"]
    split_hash = identity(output / "split.npz")["sha256"]
    results, locked = {}, {}
    for name in ("uv", "vis", "shared"):
        data = datasets[name]
        result = fit_stage1(data, config)
        directory = output / name
        directory.mkdir(exist_ok=False)
        artifacts = Stage1ArtifactPaths.from_directory(directory)
        result.model.save_model(artifacts.model)
        # Preserve the exact operating point used by diagnostics and runtime.
        artifacts.threshold.write_text(f"{result.threshold:.17g}\n")
        provenance = Stage1Provenance(
            "eta_pi0", "eta_pi0", .5, True, "accept-reject-unweighted", TAGGER_FWHM_GEV,
            TAGGER_SIGMA_GEV, "legacy-uncalibrated", data.metadata.feature_names,
            data.metadata.beam_profile, data.metadata.energy_min_gev, data.metadata.energy_max_gev,
            shared_training=(dict(schema_version=1,
                supported_profiles={p: [datasets[p].metadata.energy_min_gev, datasets[p].metadata.energy_max_gev]
                                    for p in ("uv", "vis")},
                profile_mixture={"uv": .5, "vis": .5}, dataset_sha256=dataset_hash,
                split_sha256=split_hash, training_seed=config.seed,
                threshold_policy="weighted_validation_f1_single", validation_status="diagnostic_only")
                if name == "shared" else None),
        )
        artifacts.provenance.write_text(provenance.to_json())
        artifacts.metrics.write_text(format_metrics_text(result))
        validation = data.rows.split == 1
        val_profiles = data.rows.profile[validation]
        equal = {p: efficiency_threshold(result.y_val[val_profiles == p], result.scores_val[val_profiles == p],
                                         result.w_val[val_profiles == p]) for p in np.unique(val_profiles)}
        locked[name] = dict(threshold=result.threshold, secondary_thresholds=equal,
                            model=identity(artifacts.model), provenance=identity(artifacts.provenance),
                            validation_metrics=result.metrics, n_train=result.n_train, n_validation=result.n_val)
        results[name] = result
    write_json(output / "training_locked.json", locked)
    return results


def prepare_profile(name, mc_dir, selected_file, output, seed):
    """Freeze run spectrum and all MC weight estimates on training partitions."""
    profile = get_beam_profile(name)
    directory = output / f"inputs_{name}"
    directory.mkdir()
    with uproot.open(selected_file) as root:
        tree = root["h85"]
        runs = np.asarray(tree["RunNumber"].array(library="np"))
        coords = tree["beam"].array(library="ak")["fCoordinates"]
        energy = np.asarray(coords["fCoordinates.fT"])
    unique = np.unique(runs)
    if len(unique) < 5:
        raise ValueError("insufficient real runs to reserve a separate spectrum-training subset")
    order = np.random.default_rng(seed).permutation(unique)
    train_runs = np.sort(order[:int(.6 * len(order))])
    reserved_runs = np.sort(order[int(.6 * len(order)):])
    spectrum = from_energies(energy[np.isin(runs, train_runs)],
                             bins=default_bins_for_range(profile.energy_range_gev), range_=profile.energy_range_gev)
    spectrum.save(directory / "beam_spectrum.npz")
    run_record = dict(input=identity(selected_file), spectrum_training_runs=train_runs.tolist(),
                      reserved_runs=reserved_runs.tolist(), intersection=0,
                      caveat="prospective separation for this diagnostic; these runs appeared in historical analyses")
    write_json(directory / "run_partition.json", run_record)
    del runs, energy, coords

    samples, yields, records = {}, [], []
    for ci, (channel_name, channel) in enumerate(CHANNELS.items()):
        if channel.production_threshold_gev >= profile.energy_range_gev[1]:
            continue
        path = Path(mc_dir) / channel.mc_filename
        source = identity(path)
        with uproot.open(path) as root:
            tree = root["mc"]
            origins = np.array([f"{source['sha256']}:{entry}" for entry in range(tree.num_entries)])
            # The same file/channel/seed yields the same assignment in either
            # profile, before acceptance or reweighting can create copies.
            full_split = assign_group_splits(origins, np.full(len(origins), channel_name),
                                              np.full(len(origins), name), seed=seed+ci)
            loss_seed = seed + ci + (100 if name == "vis" else 0)
            sample = build_channel_features(tree, channel, ETA_PI0_HYP,
                np.random.default_rng(loss_seed), LossParams(), spectrum, retain_kinematics=True)
            split = full_split[sample.origin_entries]
            train = split == 0
            weights = reweight(sample.beam_E, spectrum, reference_E=sample.beam_E[train])
            if channel_name == "eta_pi0":
                validate_signal_support(sample.beam_E[train], weights[train], spectrum)
            value = channel_yield(channel, sample.beam_E[train], weights[train], int((full_split == 0).sum()))
            yields.append(replace(value, is_signal=channel_name == "eta_pi0"))
            selected, heavy, light = observable_selection(sample.observed_photons, sample.observed_beams, sample.X)
            phi = np.arctan2(heavy[:, 1], heavy[:, 0])
            truth_phi = phi.copy()
            if channel_name == "eta_pi0":
                eta = _load_4vec(tree, "eta_gamma1_true") + _load_4vec(tree, "eta_gamma2_true")
                truth_phi = np.arctan2(eta[:, 1], eta[:, 0])[sample.origin_entries]
            samples[channel_name] = dict(X=sample.X, w=weights, split=split,
                origin_id=origins[sample.origin_entries], beam_E=sample.beam_E,
                selected=selected, mass_eta=signed_mass(heavy), mass_pi0=signed_mass(light),
                phi=phi, truth_phi=truth_phi, detector_variant=f"{LossParams()!r};loss_seed={loss_seed}")
            np.savez_compressed(directory / f"{channel_name}_source_split.npz", split=full_split)
            records.append(dict(source=source, channel=channel_name, generated=sample.n_gen,
                survived=len(sample.X), zero_weight=int((weights == 0).sum()), loss_seed=loss_seed,
                generated_training=int((full_split == 0).sum())))
        print(f"{name}/{channel_name}: {len(sample.X)} survivors", flush=True)
    shares = compute_shares(yields, .5)
    for channel, sample in samples.items():
        total = sample["w"][sample["split"] == 0].sum()
        if total <= 0:
            raise ValueError(f"{name}/{channel} lacks training weight")
        sample["w"] *= shares[channel] / total
    rows = Stage1Rows(
        origin_id=np.concatenate([s["origin_id"] for s in samples.values()]),
        channel=np.concatenate([np.full(len(s["X"]), c) for c, s in samples.items()]),
        profile=np.full(sum(len(s["X"]) for s in samples.values()), name),
        detector_variant=np.concatenate([np.full(len(s["X"]), s["detector_variant"]) for s in samples.values()]),
        split=np.concatenate([s["split"] for s in samples.values()]),
    )
    data = Stage1Dataset(np.concatenate([s["X"] for s in samples.values()]),
        (rows.channel == "eta_pi0").astype(np.int8), np.concatenate([s["w"] for s in samples.values()]),
        Stage1DatasetMetadata(tuple(FEATURE_NAMES_S1), "eta_pi0", "eta_pi0", .5, True,
                              name, *profile.energy_range_gev), rows)
    save_stage1_dataset(directory / "features.npz", data)
    for channel, sample in samples.items():
        np.savez_compressed(directory / f"{channel}_observables.npz",
            **{k: v for k, v in sample.items() if k != "detector_variant"})
    write_json(directory / "manifest.json", dict(profile=name, inputs=records, shares=shares,
        spectrum=identity(directory / "beam_spectrum.npz"), run_partition=run_record,
        weighting="current survivor-based density and channel model; fitted on training only"))
    return data, samples


def evaluate_comparison(datasets, results, samples_by_profile, output):
    """Open held-out MC only after all models and operating points are fixed."""
    import json
    locked = json.loads((output / "training_locked.json").read_text())
    report = {"status": "diagnostic_only", "profiles": {}}
    for profile in ("uv", "vis"):
        data = datasets[profile]
        mask = data.rows.split == 2
        y, weights = data.y[mask], data.w[mask]
        channels = data.rows.channel[mask]
        energies = data.X[mask, FEATURE_NAMES_S1.index("beam_E")]
        scores = {name: results[name].model.predict_proba(data.X[mask])[:, 1] for name in (profile, "shared")}
        tests, accepted = {}, {name: {} for name in scores}
        for name, score in scores.items():
            threshold = locked[name]["threshold"]
            value = metrics(y, score, weights, threshold)
            value["threshold"] = threshold
            value["equal_efficiency_secondary"] = dict(
                threshold=locked[name]["secondary_thresholds"][profile],
                metrics=metrics(y, score, weights, locked[name]["secondary_thresholds"][profile]))
            value["channels"] = {channel: metrics(y[channels == channel], score[channels == channel],
                                                   weights[channels == channel], threshold) for channel in np.unique(channels)}
            edges = get_beam_profile(profile).energy_edges_gev
            value["energy"] = []
            for i, (low, high) in enumerate(zip(edges[:-1], edges[1:])):
                keep = (energies >= low) & ((energies <= high) if i == len(edges)-2 else (energies < high))
                value["energy"].append(dict(range_gev=[low, high], metrics=metrics(y[keep], score[keep], weights[keep], threshold)))
            sculpting = {}
            for channel, sample in samples_by_profile[profile].items():
                keep = channels == channel
                held = sample["split"] == 2
                gate = score[keep] >= threshold
                selected = gate & sample["selected"][held]
                accepted[name][channel] = selected
                w = weights[keep]
                value["channels"][channel]["bdt_plus_no_fit_efficiency"] = float(np.dot(w, selected) / w.sum()) if w.sum() else None
                sculpting[channel] = {}
                for field, bounds in (("mass_eta", (0., .9)), ("mass_pi0", (0., .4)),
                                      ("phi", (-np.pi, np.pi)), ("beam_E", get_beam_profile(profile).energy_range_gev)):
                    bins = np.linspace(*bounds, 33)
                    values = sample[field][held]
                    sculpting[channel][field] = dict(edges=bins.tolist(),
                        before=np.histogram(values, bins, weights=w)[0].tolist(),
                        after_bdt=np.histogram(values[gate], bins, weights=w[gate])[0].tolist(),
                        after_bdt_no_fit=np.histogram(values[selected], bins, weights=w[selected])[0].tolist(),
                        outside_rows=int(((values < bins[0]) | (values > bins[-1])).sum()))
            write_json(output / f"sculpting_{profile}_{name}.json", sculpting)
            tests[name] = value
        primary = {name: score >= locked[name]["threshold"] for name, score in scores.items()}
        paired = {label: paired_efficiency(primary["shared"][y == cls], primary[profile][y == cls], weights[y == cls])
                  for label, cls in (("signal", 1), ("background", 0))}
        tests["paired_efficiency_shared_minus_separate"] = paired
        secondary = {name: score >= locked[name]["secondary_thresholds"][profile] for name, score in scores.items()}
        tests["paired_secondary_shared_minus_separate"] = {
            label: paired_efficiency(secondary["shared"][y == cls], secondary[profile][y == cls], weights[y == cls])
            for label, cls in (("signal", 1), ("background", 0))}
        difference = scores["shared"] - scores[profile]
        tests["score_stability"] = dict(
            weighted_mean_difference=float(np.average(difference, weights=weights)),
            weighted_rms_difference=float(np.sqrt(np.average(difference**2, weights=weights))),
            weighted_disagreement=float(np.average(primary["shared"] != primary[profile], weights=weights)))
        tests["paired_bdt_plus_no_fit_by_channel"] = {
            channel: paired_efficiency(accepted["shared"][channel], accepted[profile][channel],
                                        weights[channels == channel])
            for channel in np.unique(channels)}
        report["profiles"][profile] = tests
        np.savez_compressed(output / f"test_scores_{profile}.npz", origin_id=data.rows.origin_id[mask],
            channel=channels, y=y, w=weights, beam_E=energies, separate=scores[profile], shared=scores["shared"])
        sample_weights = {c: s["w"] for c, s in samples_by_profile[profile].items()}
        toy = injection(samples_by_profile[profile], accepted, sample_weights, seed=20261013,
                        trials=200, events=2000)
        toy["limitation"] = "Conditional MC moment toy in eta-lab phi, fixed P=0.6 and prior; not production Sigma, profile polarization calibration or detector validation."
        separate = np.asarray(toy["paired_replicas"][profile], dtype=float)[:, 0]
        shared = np.asarray(toy["paired_replicas"]["shared"], dtype=float)[:, 0]
        valid = np.isfinite(separate) & np.isfinite(shared)
        delta = shared[valid] - separate[valid]
        toy["paired_difference"] = dict(valid_trials=int(valid.sum()),
            mean=float(delta.mean()) if len(delta) else None,
            sampling_sd=float(delta.std(ddof=1)) if len(delta)>1 else None,
            covariance=np.cov(np.array([separate[valid], shared[valid]])).tolist() if len(delta)>1 else None)
        write_json(output / f"injection_{profile}.json", toy)
    write_json(output / "test_metrics.json", report)
    return report


def run(args):
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    sources = [Path(__file__), Path("scripts/audit_bdt_backgrounds.py")]
    for directory in ("04_bdt_training", "00_common/stage1", "00_common/physics", "05_reconstruction/runtime"):
        sources.extend(p for p in Path(directory).rglob("*.py") if "tests" not in p.parts)
    source_records = []
    for path in sources:
        record = identity(path)
        relative = path.resolve().relative_to(Path.cwd())
        target = output / "source_snapshot" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
        source_records.append(record)
    write_json(output / "execution.json", dict(command=sys.argv,
        revision=subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        sources=source_records, packages={p: importlib.metadata.version(p) for p in ("numpy", "scikit-learn", "xgboost", "uproot")},
        production_modified=False, seed=args.seed, kinfit=False, signal_prior=.5,
        limitations=["current physical mixture unvalidated", "legacy detector model", "no production Sigma claim"]))
    uv, uv_samples = prepare_profile("uv", args.uv_mc_dir, args.uv_selected, output, args.seed)
    vis, vis_samples = prepare_profile("vis", args.vis_mc_dir, args.vis_selected, output, args.seed)
    datasets = comparison_datasets(uv, vis)
    config = TrainingConfig(seed=args.seed, n_estimators=100, max_depth=5, nthread=args.nthread, verbose=False)
    results = train_comparison(datasets, output, config)
    evaluate_comparison(datasets, results, {"uv": uv_samples, "vis": vis_samples}, output)
    # Run the real runtime consumer against all three bundles.
    from reconstruction.runtime.stage1_gate import Stage1Gate
    for name in ("uv", "vis", "shared"):
        gate = Stage1Gate.load(output / name)
        for profile in (("uv", "vis") if name == "shared" else (name,)):
            gate.check_profile(get_beam_profile(profile))
    for source in source_records:
        if identity(source["path"])["sha256"] != source["sha256"]:
            raise RuntimeError(f"source changed during study: {source['path']}")
    write_json(output / "complete.json", dict(status="diagnostic_complete", physics_validation="suspended"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for profile in ("uv", "vis"):
        parser.add_argument(f"--{profile}-mc-dir", required=True, type=Path)
        parser.add_argument(f"--{profile}-selected", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--seed", default=20261013, type=int)
    parser.add_argument("--nthread", default=4, type=int)
    run(parser.parse_args())


if __name__ == "__main__":
    main()
