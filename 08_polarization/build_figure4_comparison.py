#!/usr/bin/env python3
"""Build framework-native Sigma mass panels in a four-by-three comparison grid."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys
import tempfile

import numpy as np

from compton import load_period_curves
from contracts import (
    PolarizationContractError,
    sha256_file,
    validate_gate0_handoff,
)
from exposures import build_panel_exposures
from figure4_analysis import PAIR_NAMES, analyze_sigma_grid, physical_mass_edges
from figure4_config import load_figure4_config
from figure4_plot import plot_sigma_grid
from reco_inventory import load_gate0_run_numbers, load_reco_inventory
from root_events import read_reco_root
from state_mapping import load_state_mapping, resolve_orientation


CANONICAL_FLUX = "results/observable_runs/flux_by_run_energy.csv"
CANONICAL_RUNS = "results/observable_runs/run_manifest_observables.csv"
PARTICLE_MASSES_GEV = {"proton": 0.938272, "eta": 0.547862, "pi0": 0.134977}


def publish_new_directory(destination: Path, writer) -> None:
    """Publish one immutable output directory or leave no destination."""
    destination = Path(destination)
    if destination.exists():
        raise PolarizationContractError(
            f"output directory already exists; refusing overwrite: {destination}"
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=f".{destination.name}-", dir=destination.parent
    ) as temporary:
        stage = Path(temporary)
        writer(stage)
        stage.rename(destination)


def _write_points(path: Path, results, energy_ranges) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "energy_low_gev", "energy_high_gev", "pair", "mass_low_gev",
        "mass_high_gev", "mass_center_gev", "sigma", "stat_uncertainty",
        "valid", "reason", "event_count", "fit_deviance", "fit_ndof",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for (row, pair), points in sorted(results.items()):
            energy_low, energy_high = energy_ranges[row]
            for point in points:
                writer.writerow(
                    {
                        "energy_low_gev": energy_low,
                        "energy_high_gev": energy_high,
                        "pair": pair,
                        "mass_low_gev": point.mass_low,
                        "mass_high_gev": point.mass_high,
                        "mass_center_gev": point.mass_center,
                        "sigma": point.sigma if point.valid else "",
                        "stat_uncertainty": point.stat_uncertainty if point.valid else "",
                        "valid": str(point.valid).lower(),
                        "reason": point.reason or "",
                        "event_count": point.event_count,
                        "fit_deviance": point.fit_deviance if point.valid else "",
                        "fit_ndof": point.fit_ndof,
                    }
                )


def _write_qa(
    path: Path,
    *,
    config,
    handoff,
    reco_inventory,
    reco,
    run_numbers,
    exposures,
    results,
    points_csv,
    plot,
) -> None:
    valid = sum(point.valid for points in results.values() for point in points)
    total = sum(len(points) for points in results.values())
    payload = {
        "schema_version": 1,
        "status": "diagnostic",
        "release_eligible": False,
        "reason": "Figure-comparison product; full S6 release gate remains separate",
        "config": {"path": str(config), "sha256": sha256_file(config)},
        "handoff": {"path": str(handoff), "sha256": sha256_file(handoff)},
        "reconstruction_inventory": {
            "path": str(reco_inventory),
            "sha256": sha256_file(reco_inventory),
        },
        "reconstruction": [
            {"path": str(path), "sha256": sha256_file(path)} for path in reco
        ],
        "run_numbers": sorted(run_numbers),
        "polarization_energy_weighting": {
            "method": "uniform_within_energy_bin",
            "status": "diagnostic_approximation",
            "panels": [
                {
                    "vertical_flux": item.vertical_flux,
                    "horizontal_flux": item.horizontal_flux,
                    "vertical_polarization": item.vertical_polarization,
                    "horizontal_polarization": item.horizontal_polarization,
                    "vertical_unknown_spectrum_bound": item.vertical_polarization_weighting_bound,
                    "horizontal_unknown_spectrum_bound": (
                        item.horizontal_polarization_weighting_bound
                    ),
                }
                for item in exposures
            ],
        },
        "outputs": {
            "points_csv": {
                "path": "figure4_comparison.csv",
                "sha256": sha256_file(points_csv),
            },
            "plot": {
                "path": "figure4_comparison.png",
                "sha256": sha256_file(plot),
            },
        },
        "panels": 12,
        "points_total": total,
        "points_valid": valid,
        "published_data_used": False,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reco-inventory", type=Path, required=True)
    parser.add_argument(
        "--config", type=Path, default=Path("config/physics/polarization_v1.json")
    )
    parser.add_argument(
        "--handoff", type=Path, default=Path("results/observable_runs/HANDOFF.json")
    )
    parser.add_argument(
        "--output-dir", type=Path, required=True,
        help="new directory published atomically; must not already exist",
    )
    parser.add_argument("--repository-root", type=Path, default=Path("."))
    args = parser.parse_args(argv)
    root = args.repository_root.resolve()
    config_path = args.config if args.config.is_absolute() else root / args.config
    handoff_path = args.handoff if args.handoff.is_absolute() else root / args.handoff
    inventory_path = (
        args.reco_inventory
        if args.reco_inventory.is_absolute()
        else root / args.reco_inventory
    )
    output_dir = args.output_dir if args.output_dir.is_absolute() else root / args.output_dir
    flux_path = root / CANONICAL_FLUX
    try:
        validate_gate0_handoff(handoff_path, root)
        layout = load_figure4_config(config_path)
        gate0_runs = load_gate0_run_numbers(root / CANONICAL_RUNS, target=layout.target)
        inventory = load_reco_inventory(
            inventory_path,
            root,
            expected_handoff_sha256=sha256_file(handoff_path),
            expected_tree=layout.tree,
            expected_vectors=layout.vectors,
            expected_run_numbers=gate0_runs,
        )
        intervals = load_state_mapping(config_path, root)
        curves = load_period_curves(config_path, root)
        exposures = build_panel_exposures(
            flux_path,
            intervals,
            curves,
            orientation_signs=layout.orientation_signs,
            energy_ranges=layout.energy_ranges,
            target=layout.target,
            run_numbers=inventory.run_numbers,
        )
        events = read_reco_root(
            inventory.paths, tree_name=layout.tree, vectors=layout.vectors
        )
        unexpected_runs = set(map(int, events.run_number)) - inventory.run_numbers
        if unexpected_runs:
            raise PolarizationContractError(
                "reconstruction events contain runs outside signed inventory: "
                + ", ".join(str(run) for run in sorted(unexpected_runs)[:5])
            )
        orientation_sign = np.asarray(
            [
                layout.orientation_signs[
                    resolve_orientation(int(run), int(state), intervals)
                ]
                for run, state in zip(events.run_number, events.state_code)
            ],
            dtype=int,
        )
        mass_edges = physical_mass_edges(
            max(high for _, high in layout.energy_ranges),
            bins=layout.mass_bins,
            masses_gev=PARTICLE_MASSES_GEV,
        )
        results = analyze_sigma_grid(
            events.beam_energy,
            events.proton,
            events.eta,
            events.pi0,
            orientation_sign,
            energy_ranges=layout.energy_ranges,
            mass_edges=mass_edges,
            phi_edges=np.linspace(0.0, np.pi, layout.phi_bins + 1),
            exposures=exposures,
        )
        def write_bundle(stage: Path) -> None:
            points_output = stage / "figure4_comparison.csv"
            plot_output = stage / "figure4_comparison.png"
            qa_output = stage / "figure4_comparison_qa.json"
            _write_points(points_output, results, layout.energy_ranges)
            figure = plot_sigma_grid(
                results,
                energy_ranges=layout.energy_ranges,
                pair_order=PAIR_NAMES,
                output_path=plot_output,
                analysis_label="GRAAL framework — diagnostic beam asymmetry",
            )
            import matplotlib.pyplot as plt

            plt.close(figure)
            _write_qa(
                qa_output,
                config=config_path,
                handoff=handoff_path,
                reco_inventory=inventory_path,
                reco=inventory.paths,
                run_numbers=inventory.run_numbers,
                exposures=exposures,
                results=results,
                points_csv=points_output,
                plot=plot_output,
            )
        publish_new_directory(output_dir, write_bundle)
    except (OSError, PolarizationContractError) as exc:
        print(f"Figure 4 comparison blocked: {exc}", file=sys.stderr)
        return 1
    print(f"Published diagnostic bundle: {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
