"""Extract provisional mass-fit signal yields for the existing no-fit UV sample.

Run: python -m observable_extraction.signal_yields --output-dir OUTPUT
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from calibration.run_manifest import validate_manifest
from graal_common.physics.beam_profiles import get_beam_profile
from graal_common.physics.channels import M_ETA, M_PI0
from observable_extraction.calibration.flux_v2 import load_exposures
from observable_extraction.core.kinematics import project_all_pairs
from observable_extraction.core.signal_yields import (
    MassModel,
    fit_mass_model,
    yield_influence,
)
from observable_extraction.io.cross_section import (
    canonical_hash,
    cell_indices,
    reconstruction_metadata,
    selection_signature,
)
from observable_extraction.io.reconstructed_events import (
    read_reconstructed,
    read_run_universe,
    select_sigma_events,
)
from reconstruction.runtime.provenance import file_identities, validate_energy_domain
from scipy.linalg import block_diag


def write_json(path, record):
    def convert(value):
        if isinstance(value, np.ndarray):
            return value.tolist()
        if isinstance(value, np.generic):
            return value.item()
        raise TypeError(type(value).__name__)

    Path(path).write_text(
        json.dumps(record, default=convert, allow_nan=False, separators=(",", ":"))
        + "\n"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reconstructed",
        type=Path,
        default=Path("results/uv/reco/reco_eta_pi0_bdt.root"),
    )
    parser.add_argument(
        "--flux-file", type=Path, default=Path("results/common/flux_calibrated.root")
    )
    parser.add_argument(
        "--run-manifest", type=Path, default=Path("config/run_manifest.csv")
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--bootstrap-replicas", type=int, default=24)
    parser.add_argument("--seed", type=int, default=20261021)
    args = parser.parse_args()
    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)
    if (out / "index.json").exists():
        raise ValueError("refusing to replace completed extraction")
    metadata = reconstruction_metadata(args.reconstructed)
    selection = selection_signature(metadata)
    validate_energy_domain(metadata, "uv", (1.1, 1.5), requires_bdt=True)
    if (
        metadata["selection"]["chi2_cut"] != 10
        or metadata["selection"]["chi2_resolution_relative"] != 0.08
    ):
        raise ValueError("mass model requires chi2<10 with 8% reference resolutions")
    events = read_reconstructed(
        args.reconstructed, "reco_eta_pi0_bdt", vector_mode="raw", require_no_fit=True
    )
    universe, _ = read_run_universe(args.reconstructed)
    records = {r.run_number: r for r in validate_manifest(args.run_manifest)}
    if universe - set(records):
        raise ValueError("run universe missing from manifest")
    periods = sorted({records[r].source_period for r in universe})
    profile = get_beam_profile("uv")
    selected = []
    audits = []
    unavailable = []
    available_periods = []
    for period in periods:
        runs = {r for r in universe if records[r].source_period == period}
        if any(
            records[r].target != "P" or records[r].beam_type != profile.beam_type
            for r in runs
        ):
            raise ValueError("period is not proton UV")
        exposure_audit = {}
        try:
            exposures = load_exposures(
                args.flux_file,
                manifest_path=args.run_manifest,
                run_numbers=runs,
                target="P",
                beam_type=profile.beam_type,
                polarization_model=profile.polarization,
                energy_range=(1.1, 1.5),
                audit=exposure_audit,
            )
        except ValueError as error:
            if str(error) != "no complete P/UV exposures in energy range":
                raise
            unavailable.append(
                {"period": period, "reason": str(error), "inclusive_runs": sorted(runs)}
            )
            print(
                f"{period}: unavailable, no complete calibrated exposures", flush=True
            )
            continue
        available_periods.append(period)
        audit = {}
        sample = select_sigma_events(
            events.take(np.isin(events.run_number, sorted(runs))),
            exposures,
            energy_range=(1.1, 1.5),
            drop_missing=True,
            audit=audit,
        )
        selected.append(sample)
        audits.append(
            {
                "period": period,
                "runs": sorted({k[0] for k in exposures}),
                "event_selection": audit,
                "flux_audit": exposure_audit,
            }
        )
    periods = available_periods
    from dataclasses import fields

    from observable_extraction.io.reconstructed_events import EventArrays

    all_events = EventArrays(
        **{
            f.name: np.concatenate([getattr(s, f.name) for s in selected])
            for f in fields(EventArrays)
        }
    )
    period_index = np.concatenate(
        [np.full(len(s), i, dtype=int) for i, s in enumerate(selected)]
    )
    projections = project_all_pairs(all_events.proton, all_events.eta, all_events.pi0)
    energy_edges = np.round(np.linspace(1.1, 1.5, 9), 8)
    energy_bin = np.clip(
        np.searchsorted(energy_edges, all_events.beam_energy_gev, side="right") - 1,
        0,
        7,
    )
    model = MassModel(bins=20)
    x = (all_events.eta_mass_gev / M_ETA - 1) / 0.08
    y = (all_events.pi0_mass_gev / M_PI0 - 1) / 0.08
    if np.any(x * x + y * y >= 10.00001):
        raise ValueError("events outside stored mass selection")
    mass_bin = np.searchsorted(model.edges, x, side="right") - 1
    mass_bin = mass_bin * model.bins + np.searchsorted(model.edges, y, side="right") - 1
    fits = []
    bootstrap = []
    rng = np.random.default_rng(args.seed)
    fitdir = out / "fits"
    fitdir.mkdir(exist_ok=True)
    for i in range(8):
        counts = np.bincount(mass_bin[energy_bin == i], minlength=model.bins**2).astype(
            float
        )
        fit = fit_mass_model(model, counts)
        _, cov, info = yield_influence(model, fit, counts[None, :])
        if fit["boundary_parameters"]:
            raise ValueError(
                f"energy bin {i}: constrained fit cannot supply regular covariance"
            )
        alt_model = MassModel(bins=20, extended=True)
        alt = fit_mass_model(alt_model, counts, start=fit["theta"])
        record = {
            k: v for k, v in fit.items() if k not in ["counts", "expected", "weights"]
        }
        record.update(
            energy_low=energy_edges[i],
            energy_high=energy_edges[i + 1],
            stat_error=np.sqrt(cov[0, 0]),
            model_adequacy="failed"
            if fit["p_value_asymptotic"] < 0.01
            else "not_rejected",
            alternative_four_component_yield=alt["signal_yield"],
            alternative_converged=alt["converged"],
            alternative_boundary_parameters=alt["boundary_parameters"],
            hessian_eigenvalues=info["hessian_eigenvalues"],
        )
        replicas = []
        failures = []
        for j in range(args.bootstrap_replicas):
            try:
                replica = fit_mass_model(
                    model, rng.poisson(counts), start=fit["theta"], multistart=False
                )
                if replica["boundary_parameters"]:
                    failures.append({"replica": j, "reason": "boundary"})
                    continue
                replicas.append(replica["signal_yield"])
            except ValueError as error:
                failures.append({"replica": j, "reason": str(error)})
        record["bootstrap"] = {
            "requested": args.bootstrap_replicas,
            "accepted": len(replicas),
            "failures": failures,
            "yield_std": float(np.std(replicas, ddof=1)) if len(replicas) > 1 else None,
            "seed": args.seed,
            "role": "diagnostic; covariance uses analytic Poisson influence, not finite bootstrap rank",
        }
        write_json(fitdir / f"energy_{i}.json", record)
        np.savez_compressed(
            fitdir / f"energy_{i}.npz",
            counts=counts,
            expected=fit["expected"],
            weights=fit["weights"],
            theta=fit["theta"],
            edges=model.edges,
            bootstrap_yields=replicas,
        )
        fits.append(fit)
        bootstrap.append(record)
        print(
            f"energy {energy_edges[i]:.2f}–{energy_edges[i + 1]:.2f}: observed {counts.sum():.0f}, net {fit['signal_yield']:.1f} +/- {record['stat_error']:.1f}, deviance/ndf {fit['deviance'] / fit['dof']:.2f}; provisional",
            flush=True,
        )
    reco_hash = file_identities([args.reconstructed])[0]["sha256"]
    flux_hash = file_identities([args.flux_file])[0]["sha256"]
    local_edges = [1.1, 1.15, 1.25, 1.35, 1.45, 1.5]
    grids = {
        "total": {
            "observable": "total",
            "energy_edges_gev": energy_edges.tolist(),
            "mass_edges_gev": None,
            "phi_edges_rad": np.linspace(0, 2 * np.pi, 9).tolist(),
        }
    }
    for pair, lo, hi in [
        ("p_pi0", 1.05, 1.45),
        ("p_eta", 1.45, 1.85),
        ("eta_pi0", 0.65, 1.05),
    ]:
        grids[pair] = {
            "observable": pair,
            "energy_edges_gev": local_edges,
            "mass_edges_gev": np.round(np.linspace(lo, hi, 9), 8).tolist(),
            "phi_edges_rad": np.linspace(0, 2 * np.pi, 9).tolist(),
        }
    index = {
        "schema_version": 1,
        "status": "provisional_model_inadequate",
        "source": "Data-fitted skewed two-mass peak plus smooth exponential continuum inside actual chi2<10 ellipse; no Sigma correction",
        "fit_method": "binned maximum likelihood; 20x20 mass-pull bins; Gauss-Legendre integration over selection disk",
        "statistical_covariance": "Poisson influence of counts and same-data fitted weights; independent energy fits; shared cross-period shapes retained",
        "limitations": [
            "All UV mass-fit goodness-of-fit tests reject nominal model; these are provisional model-conditional yields, not validated signal purity.",
            "One-real-meson and double-peaking physics backgrounds are not independently calibrated.",
            "Mass-shape/kinematic independence within each energy slice is assumed; differential and phi weighting can be biased if it fails.",
            "Energy/model alternatives are diagnostic variations, not complete systematic uncertainty.",
            "Empty cells have zero observed information; no artificial variance floor.",
            "VIS mass separation is not identifiable in pilot fits; VIS yields not published.",
        ],
        "inputs": file_identities(
            [args.reconstructed, args.flux_file, args.run_manifest]
        ),
        "fits": bootstrap,
        "periods": audits,
        "unavailable_periods": unavailable,
        "products": {},
        "seed": args.seed,
    }
    for name, grid in grids.items():
        destination = out / name
        destination.mkdir(exist_ok=True)
        nm = 1 if grid["mass_edges_gev"] is None else len(grid["mass_edges_gev"]) - 1
        per_state = (len(grid["energy_edges_gev"]) - 1) * nm * 8
        per_period = per_state * 2
        nrows = per_period * len(periods)
        masses, angles = projections["eta_pi0" if name == "total" else name]
        cell = cell_indices(all_events.beam_energy_gev, angles, masses, grid)
        rows = (
            period_index * per_period + (all_events.polarization - 1) * per_state + cell
        )
        valid = cell >= 0
        raw = np.bincount(rows[valid], minlength=nrows).astype(float)
        net = np.zeros(nrows)
        diagonal = np.zeros(nrows)
        factors = []
        kernels = []
        for i, fit in enumerate(fits):
            use = valid & (energy_bin == i)
            hist = np.bincount(
                rows[use] * (model.bins**2) + mass_bin[use],
                minlength=nrows * model.bins**2,
            ).reshape(nrows, -1)
            values, _, info = yield_influence(model, fit, hist, full_covariance=False)
            net += values
            diagonal += info["diagonal"]
            factors.append(info["factors"])
            kernels.append(info["kernel"])
        factor = np.concatenate(factors, axis=1)
        kernel = block_diag(*kernels)
        np.savez_compressed(
            destination / "joint_covariance.npz",
            diagonal=diagonal,
            factors=factor,
            kernel=kernel,
        )
        signatures = []
        samples = []
        for p, period in enumerate(periods):
            signature = canonical_hash(
                {
                    "reconstruction": reco_hash,
                    "selection": selection,
                    "grid": grid,
                    "runs": audits[p]["runs"],
                    "states": [1, 2],
                    "flux": flux_hash,
                }
            )
            signatures.append(signature)
            sl = slice(p * per_period, (p + 1) * per_period)
            covariance = np.diag(diagonal[sl]) + factor[sl] @ kernel @ factor[sl].T
            record = {
                "schema_version": 1,
                "source": index["source"],
                "status": index["status"],
                "model_adequacy": "failed",
                "observation_signature": signature,
                "observed_counts": raw[sl],
                "net_yields": net[sl],
                "covariance": covariance,
                "grid": grid,
                "period": period,
                "outside_grid_events": int(
                    np.count_nonzero((period_index == p) & ~valid)
                ),
                "uncertainty": "statistical conditional on fitted model; systematics deferred",
                "joint_covariance": "joint_covariance.json",
            }
            write_json(destination / f"{period}.json", record)
            samples.append(
                {
                    "period": period,
                    "profile": "uv",
                    "reconstructed": str(args.reconstructed.resolve()),
                    "tree": "reco_eta_pi0_bdt",
                }
            )
        joint = {
            "schema_version": 1,
            "source": index["source"],
            "status": index["status"],
            "model_adequacy": "failed",
            "observation_signatures": signatures,
            "periods": periods,
            "background_files": [f"{period}.json" for period in periods],
            "row_counts": [per_period] * len(periods),
            "representation": "diagonal_plus_factors",
            "covariance_npz": "joint_covariance.npz",
            "covariance_formula": "diag(diagonal) + factors @ kernel @ factors.T",
            "note": "kernel need not be PSD by itself; complete covariance is PSD; cross-period covariance must not be discarded",
        }
        write_json(destination / "joint_covariance.json", joint)
        config = {
            "schema_version": 1,
            "grid": grid,
            "run_manifest": str(args.run_manifest.resolve()),
            "flux_file": str(args.flux_file.resolve()),
            "samples": samples,
        }
        write_json(destination / "observations_config.json", config)
        # Summaries retain correlated error after summing all periods, states, phi.
        table = []
        for e in range(len(grid["energy_edges_gev"]) - 1):
            for m in range(nm):
                inds = np.array(
                    [
                        p * per_period + s * per_state + (e * nm + m) * 8 + j
                        for p in range(len(periods))
                        for s in range(2)
                        for j in range(8)
                    ]
                )
                vector = factor[inds].sum(axis=0)
                variance = diagonal[inds].sum() + vector @ kernel @ vector
                table.append(
                    {
                        "energy_low_gev": grid["energy_edges_gev"][e],
                        "energy_high_gev": grid["energy_edges_gev"][e + 1],
                        "mass_low_gev": None if nm == 1 else grid["mass_edges_gev"][m],
                        "mass_high_gev": None
                        if nm == 1
                        else grid["mass_edges_gev"][m + 1],
                        "observed": raw[inds].sum(),
                        "net": net[inds].sum(),
                        "stat_error": np.sqrt(max(variance, 0)),
                    }
                )
        write_json(destination / "summary.json", table)
        index["products"][name] = {
            "grid": grid,
            "rows_per_period": per_period,
            "total_rows": nrows,
            "outside_grid_events": int(np.count_nonzero(~valid)),
            "summary": f"{name}/summary.json",
            "joint_covariance": f"{name}/joint_covariance.json",
            "background_files": joint["background_files"],
            "observation_signatures": signatures,
        }
    index["sources"] = file_identities(
        [Path(__file__), Path(__file__).parent / "core" / "signal_yields.py"]
    )
    plot_results(out, index)
    write_json(out / "index.json", index)


def plot_results(out, index):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages

    with PdfPages(out / "signal_yield_diagnostics.pdf") as pdf:
        for i, record in enumerate(index["fits"]):
            data = np.load(out / "fits" / f"energy_{i}.npz")
            observed = data["counts"].reshape(20, 20)
            expected = data["expected"].reshape(20, 20)
            templates, fractions = MassModel(bins=20).components(data["theta"])
            background = (observed.sum() * fractions[1] * templates[:, 1]).reshape(
                20, 20
            )
            fig, axs = plt.subplots(2, 2, figsize=(10, 8))
            centers = (data["edges"][1:] + data["edges"][:-1]) / 2
            for axis in range(2):
                obs = observed.sum(axis=1 - axis)
                pred = expected.sum(axis=1 - axis)
                axs[0, axis].errorbar(
                    centers, obs, yerr=np.sqrt(obs), fmt=".", label="Data"
                )
                axs[0, axis].plot(centers, pred, label="Nominal model")
                axs[0, axis].plot(
                    centers,
                    background.sum(axis=1 - axis),
                    "--",
                    label="Fitted continuum",
                )
                axs[0, axis].set_xlabel(("eta", "pi0")[axis] + " mass pull")
                axs[0, axis].legend()
            im = axs[1, 0].imshow(observed.T, origin="lower")
            fig.colorbar(im, ax=axs[1, 0])
            axs[1, 0].set_title("Observed mass bins")
            residual = (observed - expected) / np.sqrt(np.maximum(expected, 1))
            im = axs[1, 1].imshow(
                residual.T, origin="lower", vmin=-5, vmax=5, cmap="coolwarm"
            )
            fig.colorbar(im, ax=axs[1, 1])
            axs[1, 1].set_title("Pearson residuals")
            fig.suptitle(
                f"PROVISIONAL: {record['energy_low']:.2f}–{record['energy_high']:.2f} GeV; deviance/ndf={record['deviance'] / record['dof']:.2f}; model adequacy {record['model_adequacy']}"
            )
            fig.tight_layout()
            pdf.savefig(fig)
            plt.close(fig)
        for name, product in index["products"].items():
            table = json.loads((out / product["summary"]).read_text())
            fig, ax = plt.subplots(figsize=(10, 6))
            if name == "total":
                x = [(r["energy_low_gev"] + r["energy_high_gev"]) / 2 for r in table]
                ax.errorbar(
                    x,
                    [r["net"] for r in table],
                    yerr=[r["stat_error"] for r in table],
                    fmt="o",
                    label="Net, conditional statistical error",
                )
                ax.plot(x, [r["observed"] for r in table], "x", label="Observed")
                ax.set_xlabel("Photon energy [GeV]")
            else:
                for e in sorted({r["energy_low_gev"] for r in table}):
                    rows = [r for r in table if r["energy_low_gev"] == e]
                    ax.errorbar(
                        [(r["mass_low_gev"] + r["mass_high_gev"]) / 2 for r in rows],
                        [r["net"] for r in rows],
                        yerr=[r["stat_error"] for r in rows],
                        fmt="o-",
                        label=f"{e:.2f}–{rows[0]['energy_high_gev']:.2f} GeV",
                    )
                ax.set_xlabel(name + " mass [GeV]")
            ax.set_ylabel("Selected signal yield (events)")
            ax.set_title(
                "PROVISIONAL, mass-model adequacy failed; systematics deferred"
            )
            ax.legend()
            fig.tight_layout()
            pdf.savefig(fig)
            plt.close(fig)


if __name__ == "__main__":
    main()
