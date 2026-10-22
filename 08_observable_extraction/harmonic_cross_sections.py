"""Provisional single-period total cross section with an explicit energy guard.

Uses generated-event harmonic moments, the unchanged data selection and its
net-yield covariance. The below-domain cross section is fitted as a nuisance;
it is never fixed to Ajaka. Conditional on the phase-space production model
and uniform energy within truth bins. Full systematics remain outstanding.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from graal_common.physics.beam_profiles import get_beam_profile
from mc_simulation.native_validation import verified_reconstruction
from mc_simulation.response import harmonic_response
from observable_extraction.calibration.flux_v2 import load_exposures
from observable_extraction.core.cross_section import (
    fit_cross_sections,
    weighted_harmonic_mc_covariance,
)
from observable_extraction.core.kinematics import mass_and_phi
from observable_extraction.io.cross_section import (
    _background,
    _number,
    _source,
    cell_indices,
    load_reference,
    prepare_analysis,
    read_json,
    write_result,
)
from reconstruction.runtime.provenance import file_identities


def exposure_weights(exposures, observed_exposures, truth_edges, bins, strips, scale):
    """Run-flux-weighted reconstructed-strip masks for each selected MC event."""
    nt = len(truth_edges) - 1
    runs = sorted({run for run, _ in observed_exposures})
    weights = np.zeros((len(bins), 2, 2))
    photons = np.zeros((2, nt))
    for run in runs:
        flux = np.zeros((2, nt))
        polarized = np.zeros_like(flux)
        for (source_run, _), exposure in exposures.items():
            if source_run != run:
                continue
            k = np.searchsorted(truth_edges, exposure.energy_gev, side="right") - 1
            if exposure.energy_gev == truth_edges[-1]:
                k = nt - 1
            if not 0 <= k < nt:
                continue
            for state, value, pol in (
                (0, exposure.flux_vertical, exposure.polarization_vertical),
                (1, exposure.flux_horizontal, exposure.polarization_horizontal),
            ):
                flux[state, k] += value
                polarized[state, k] += value * pol
        mask = np.isin(strips, [strip for r, strip in observed_exposures if r == run])
        photons += flux
        weights[:, 0] += flux[:, bins].T * mask[:, None]
        weights[:, 1] += polarized[:, bins].T * mask[:, None] * [1, -1]
    return weights * scale, photons


def prepare(config_path, mc_directories):
    config_path = Path(config_path).resolve()
    root = config_path.parent
    config = read_json(config_path)
    if len(config["samples"]) != 1 or config["grid"]["observable"] != "total":
        raise ValueError("harmonic pilot requires one period and total cross section")
    sample, grid = config["samples"][0], config["grid"]
    if sample["period"] != "2002_uv1" or sample["profile"] != "uv":
        raise ValueError("available detector calibration is period21/2002_uv1 only")
    observed = prepare_analysis(config_path, observations_only=True)
    audit = observed["audit"]
    sample_audit = audit["samples"][0]
    paths = {config_path}
    raw = np.asarray(sample_audit["raw_counts"])
    yields, covariance, warning = _background(
        sample["background"],
        raw,
        sample_audit["observation_signature"],
        root,
        paths,
        allow_shared_covariance=True,
    )
    energy = np.asarray(grid["energy_edges_gev"])
    if energy[0] != 1.1 or energy[-1] != 1.5:
        raise ValueError("pilot guard is defined for analysis energy 1.1–1.5 GeV")
    truth_edges = np.r_[0.95, energy]
    ids, ebin, angles, selected_ids, selected_cells, strips = [], [], [], [], [], []
    seen_sources = set()
    seen_seeds = set()
    for index, directory in enumerate(mc_directories):
        directory = Path(directory).resolve()
        validation = verified_reconstruction(directory)
        if (
            validation["generated_sample_sha256"] in seen_sources
            or tuple(validation["seeds"]) in seen_seeds
        ):
            raise ValueError(
                "same generated MC sample or random stream supplied more than once"
            )
        seen_sources.add(validation["generated_sample_sha256"])
        seen_seeds.add(tuple(validation["seeds"]))
        record = read_json(directory / "selection_audit.json")
        if (
            record["period"] != sample["period"]
            or record["selection_signature"] != sample_audit["selection_signature"]
        ):
            raise ValueError("MC/data period or selection signature mismatch")
        if (
            "TRANSPORT PROBE PASS"
            not in (directory.parent / "transport_probe.log").read_text()
        ):
            raise ValueError("MC execution lacks the required transport probe")
        source = directory / "matched_events.npz"
        paths.update(
            (
                source,
                directory / "selection_audit.json",
                directory / "validation.json",
                directory.parent / "transport_probe.log",
            )
        )
        with np.load(source, allow_pickle=False) as mc:
            generated = mc["generated_p4"]
            selected = mc["selected_p4"]
            _, phi = mass_and_phi(generated[:, 0] + generated[:, 1])
            mass, reco_phi = mass_and_phi(selected[:, 0] + selected[:, 1])
            true_bin = (
                np.searchsorted(truth_edges, mc["generated_energy_gev"], side="right")
                - 1
            )
            cells = cell_indices(mc["selected_energy_gev"], reco_phi, mass, grid)
            offset = index * 2**32
            if np.any(mc["generated_ids"] >= 2**32):
                raise ValueError("MC event identity exceeds batch namespace")
            ids.append(mc["generated_ids"] + offset)
            ebin.append(true_bin)
            angles.append(phi)
            selected_ids.append(mc["selected_ids"] + offset)
            selected_cells.append(cells)
            strips.append(mc["selected_strip"])
    if not ids:
        raise ValueError("at least one independent MC sample required")
    ids, ebin, angles, selected_ids, selected_cells, strips = map(
        np.concatenate, (ids, ebin, angles, selected_ids, selected_cells, strips)
    )
    nt, nr = len(truth_edges) - 1, len(raw) // 2
    # Count guard migration independently, before inference; never discard it.
    order = np.argsort(ids)
    selected_truth_bins = ebin[order[np.searchsorted(ids[order], selected_ids)]]
    guard_infeed = int(
        np.count_nonzero((selected_truth_bins == 0) & (selected_cells >= 0))
    )
    target, branching = sample["target"], config["branching"]
    _source(target, "target")
    _source(branching, "branching")
    density = _number(target["areal_density_cm2"], "target density", positive=True)
    br = _number(branching["value"], "branching ratio", positive=True, upper=1)
    profile = get_beam_profile("uv")
    exposures = load_exposures(
        root / config["flux_file"],
        manifest_path=root / config["run_manifest"],
        run_numbers=set(sample_audit["runs"]),
        target="P",
        beam_type=profile.beam_type,
        polarization_model=profile.polarization,
        energy_range=(truth_edges[0], truth_edges[-1]),
    )
    observed_exposures = load_exposures(
        root / config["flux_file"],
        manifest_path=root / config["run_manifest"],
        run_numbers=set(sample_audit["runs"]),
        target="P",
        beam_type=profile.beam_type,
        polarization_model=profile.polarization,
        energy_range=(energy[0], energy[-1]),
    )
    weights, photons = exposure_weights(
        exposures,
        observed_exposures,
        truth_edges,
        selected_truth_bins,
        strips,
        density * br * 1e-30,
    )
    generated, moments, mc_cov = harmonic_response(
        ids,
        ebin,
        angles,
        selected_ids,
        selected_cells,
        nt,
        nr,
        selected_weights=weights,
    )
    design = np.concatenate((moments[:, 0].T, moments[:, 1].T), axis=1)
    fit = fit_cross_sections(yields, covariance, design)
    mc_parameter_covariance = weighted_harmonic_mc_covariance(fit, mc_cov)
    # The GLS objective above uses yield covariance only. Its chi-square is
    # not a goodness test including finite MC statistics. Retain a separate
    # post-fit diagnostic with MC prediction variance; this is not a refit
    # or a calibrated p-value for an estimated response.
    prediction_covariance = np.zeros_like(covariance)
    for k in range(nt):
        derivative = np.concatenate(
            [np.eye(len(raw)) * fit.coefficients[k + moment * nt] for moment in (0, 1)],
            axis=1,
        )
        prediction_covariance += derivative @ mc_cov[k] @ derivative.T
    residual = yields - design @ fit.coefficients
    chi2_with_mc = float(
        residual @ np.linalg.solve(covariance + prediction_covariance, residual)
    )
    keep = np.arange(1, nt)  # guard is fitted and retained in full fit, not plotted
    components = {
        "yield_statistical_conditional": fit.covariance[np.ix_(keep, keep)],
        "mc_statistical_shared_states": mc_parameter_covariance[np.ix_(keep, keep)],
    }
    reference = load_reference(root / config["reference"], grid)
    audit.update(
        status="diagnostic_harmonic_total_detector_and_background_unvalidated",
        plot_note="2002_uv1; phase-space MC; provisional detector/target\nDetector/background model unvalidated; full systematic uncertainties pending",
        analysis_kind="experimental",
        estimator="Gaussian GLS; event-level 1 and cos(2phi) MC moments; all truth energy coefficients fitted",
        truth_energy_edges_gev=truth_edges.tolist(),
        generated_by_truth_energy=generated.tolist(),
        selected_guard_infeed=guard_infeed,
        reconstructed_strip_masks="same as data, per run; weighted by state-specific truth-bin flux",
        selected_zero_exposure_weight=int(
            np.count_nonzero(~np.any(weights[:, 0] > 0, axis=1))
        ),
        photons_by_state_truth_energy=photons.tolist(),
        fitted_guard_sigma_ub=float(fit.coefficients[0]),
        fitted_guard_stat_error_ub=float(
            np.sqrt(fit.covariance[0, 0] + mc_parameter_covariance[0, 0])
        ),
        chi2=fit.chi2,
        chi2_covariance="yield covariance only; excludes finite-MC prediction variance",
        postfit_chi2_with_mc_prediction_variance=chi2_with_mc,
        postfit_chi2_interpretation="diagnostic only; no refit and no calibrated p-value",
        dof=fit.dof,
        condition_number=fit.condition,
        reference_comparison="visual overlay; no rescaling or use of Ajaka normalization",
        missing_uncertainties=[
            "target_period_and_density",
            "absolute_flux",
            "branching",
            "production_model",
            "intra_bin_energy_spectrum",
            "detector_configuration",
            "background_model_adequacy",
            "polarization_scale",
        ],
        limitations=[
            warning,
            "provisional OLD_CYL period21 with 12cm hydrogen and BGO trigger",
            "uniform energy and three-body phase space within each truth bin",
            "guard sigma and polarized amplitude fitted, constant across 0.95–1.1 GeV",
            "first-order conditional Gaussian uncertainties, not full systematics",
            "generation begins at0.95GeV; threshold-to0.95GeV infeed remains unmeasured",
        ],
        additional_inputs=file_identities(paths),
        reference=reference,
    )
    return {
        "reference": reference,
        "values": fit.coefficients[keep],
        "components": components,
        "known_covariance": sum(components.values()),
        "fit": fit,
        "audit": audit,
        "grid": grid,
        "raw_counts": raw,
        "net_yields": yields,
        "yield_covariance": covariance,
        "design": design,
        "responses": {},
        "harmonic_response": {
            "generated": generated,
            "moments": moments,
            "covariance": mc_cov,
            "truth_energy_edges_gev": truth_edges,
        },
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--mc-dir", type=Path, action="append", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    result = prepare(args.config, args.mc_dir)
    write_result(result, args.output_dir)
    np.savez_compressed(
        args.output_dir / "harmonic_response.npz", **result["harmonic_response"]
    )
    (args.output_dir / "result.json").write_text(
        json.dumps(
            {
                "sigma_ub": result["values"].tolist(),
                "conditional_errors_ub": np.sqrt(
                    np.diag(result["known_covariance"])
                ).tolist(),
                "audit": result["audit"],
            },
            indent=2,
            allow_nan=False,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
