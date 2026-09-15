#!/usr/bin/env python3
"""Build framework-native Sigma mass panels in a four-by-three comparison grid."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import subprocess
import sys
import tempfile

import numpy as np

from compton import load_period_curves
from contracts import (
    COMMIT_PATTERN,
    PolarizationContractError,
    load_json,
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
DIAGNOSTIC_USE = "diagnostic Figure-4 comparison only; not release physics"


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


def _relative_path(path: Path, repository_root: Path) -> str:
    try:
        return Path(path).resolve().relative_to(repository_root.resolve()).as_posix()
    except ValueError as exc:
        raise PolarizationContractError(
            f"Figure 4 artifact path is outside repository: {path}"
        ) from exc


def _artifact_record(
    path: Path,
    repository_root: Path,
    *,
    role: str,
    allowed_use: str,
    published_path: str | None = None,
) -> dict[str, object]:
    candidate = Path(path)
    return {
        "path": published_path or _relative_path(candidate, repository_root),
        "sha256": sha256_file(candidate),
        "bytes": candidate.stat().st_size,
        "role": role,
        "allowed_use": allowed_use,
    }


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
    repository_root,
    producer_commit,
    command,
    flux,
    state_mapping_sources,
    compton_sources,
) -> None:
    valid = sum(point.valid for points in results.values() for point in points)
    total = sum(len(points) for points in results.values())
    payload = {
        "schema_version": 2,
        "status": "diagnostic",
        "release_eligible": False,
        "reason": "Figure-comparison product; full S6 release gate remains separate",
        "artifact_role": "diagnostic_qa",
        "allowed_use": DIAGNOSTIC_USE,
        "producer": {"commit": producer_commit, "command": list(command)},
        "config": _artifact_record(
            config, repository_root, role="analysis_configuration",
            allowed_use="input to diagnostic Figure-4 comparison",
        ),
        "handoff": _artifact_record(
            handoff, repository_root, role="gate0_handoff",
            allowed_use="input to diagnostic Figure-4 comparison",
        ),
        "reconstruction_inventory": _artifact_record(
            reco_inventory, repository_root, role="reconstruction_inventory",
            allowed_use="input to diagnostic Figure-4 comparison",
        ),
        "flux": _artifact_record(
            flux, repository_root, role="normalization_flux",
            allowed_use="input to diagnostic Figure-4 comparison",
        ),
        "state_mapping_sources": [
            _artifact_record(
                source, repository_root, role="state_mapping_authority",
                allowed_use="input to diagnostic Figure-4 comparison",
            )
            for source in state_mapping_sources
        ],
        "compton_sources": [
            _artifact_record(
                source, repository_root, role="compton_polarization_authority",
                allowed_use="input to diagnostic Figure-4 comparison",
            )
            for source in compton_sources
        ],
        "reconstruction": [
            _artifact_record(
                item, repository_root, role="selected_reconstruction_events",
                allowed_use="input to diagnostic Figure-4 comparison",
            )
            for item in reco
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
                    "vertical_polarization_variance": item.vertical_polarization_variance,
                    "horizontal_polarization_variance": item.horizontal_polarization_variance,
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
                **_artifact_record(
                    points_csv, repository_root, role="diagnostic_sigma_points",
                    allowed_use=DIAGNOSTIC_USE,
                    published_path="figure4_comparison.csv",
                ),
            },
            "plot": {
                **_artifact_record(
                    plot, repository_root, role="diagnostic_visualization",
                    allowed_use=DIAGNOSTIC_USE,
                    published_path="figure4_comparison.png",
                ),
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
    parser.add_argument(
        "--producer-commit",
        help="40-character Git commit; defaults to repository HEAD",
    )
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
        producer_commit = args.producer_commit
        if producer_commit is None:
            producer_commit = subprocess.run(
                ["git", "-C", str(root), "rev-parse", "HEAD"],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        if COMMIT_PATTERN.fullmatch(producer_commit or "") is None:
            raise PolarizationContractError("producer_commit must be a Git hash")
        layout = load_figure4_config(config_path)
        raw_config = load_json(config_path)
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
        state_source = raw_config["state_mapping"]["source"]["path"]
        state_sources = (
            Path(state_source) if Path(state_source).is_absolute() else root / state_source,
        )
        compton_sources = tuple(
            Path(item["source"]["path"])
            if Path(item["source"]["path"]).is_absolute()
            else root / item["source"]["path"]
            for item in raw_config["compton_polarization"]["periods"]
        )
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
        event_runs = frozenset(map(int, events.run_number))
        if event_runs != inventory.observed_event_run_numbers:
            missing = inventory.observed_event_run_numbers - event_runs
            extra = event_runs - inventory.observed_event_run_numbers
            raise PolarizationContractError(
                "reconstruction ROOT observed run set disagrees with signed inventory "
                f"(missing={len(missing)}, extra={len(extra)})"
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
        mass_edges = tuple(
            physical_mass_edges(
                high,
                bins=layout.mass_bins,
                masses_gev=PARTICLE_MASSES_GEV,
            )
            for _, high in layout.energy_ranges
        )
        results = analyze_sigma_grid(
            events.beam_energy,
            events.beam,
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
                repository_root=root,
                producer_commit=producer_commit,
                command=(
                    "python", "08_polarization/build_figure4_comparison.py",
                    "--repository-root", ".",
                    "--config", _relative_path(config_path, root),
                    "--handoff", _relative_path(handoff_path, root),
                    "--reco-inventory", _relative_path(inventory_path, root),
                    "--output-dir", _relative_path(output_dir, root),
                    "--producer-commit", producer_commit,
                ),
                flux=flux_path,
                state_mapping_sources=state_sources,
                compton_sources=compton_sources,
            )
        publish_new_directory(output_dir, write_bundle)
    except (KeyError, TypeError, OSError, subprocess.CalledProcessError, PolarizationContractError) as exc:
        print(f"Figure 4 comparison blocked: {exc}", file=sys.stderr)
        return 1
    print(f"Published diagnostic bundle: {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
