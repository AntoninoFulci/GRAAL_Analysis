"""Compose UV and VIS beam-asymmetry ROOT outputs into five-row figures."""

from __future__ import annotations

import argparse
import math
from pathlib import Path
from typing import Sequence

from graal_common.physics.beam_profiles import get_beam_profile
from observable_extraction.io.root_input import (
    read_output_contract,
    read_output_points,
)
from observable_extraction.plotting.diagnostics import (
    write_profile_estimator_comparison_pdf,
    write_profile_fit_diagnostics_pdf,
)
from observable_extraction.plotting.figure4 import (
    combined_energy_rows,
    load_published_points,
    write_profile_figure4_comparison_pdf,
    write_profile_figure4_pdf,
)

AJAKA_REFERENCE = (
    Path(__file__).resolve().parent
    / "references"
    / "ajaka2008_figure4_digitized.csv"
)
PRODUCTION_ROOT = Path("results/production")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--uv-root",
        type=Path,
        default=PRODUCTION_ROOT / "uv/beam_asymmetry/beam_asymmetry.root",
    )
    parser.add_argument(
        "--vis-root",
        type=Path,
        default=PRODUCTION_ROOT / "vis/beam_asymmetry/beam_asymmetry.root",
    )
    parser.add_argument(
        "--published-csv",
        type=Path,
        default=AJAKA_REFERENCE,
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PRODUCTION_ROOT / "combined",
    )
    return parser


def _validate_profile_root(profile_name: str, path: Path, points) -> None:
    label = profile_name.upper()
    profile = get_beam_profile(profile_name)
    contract = read_output_contract(path)
    if contract.profile is None:
        if profile_name != "uv":
            raise RuntimeError(f"{label} ROOT has no profile metadata: {path}")
    elif contract.profile != profile_name:
        raise RuntimeError(
            f"{label} ROOT profile is {contract.profile!r}, expected "
            f"{profile_name!r}: {path}"
        )

    expected_edges = profile.energy_edges_gev
    if len(contract.energy_edges_gev) != len(expected_edges) or any(
        not math.isclose(actual, expected, rel_tol=0.0, abs_tol=1e-12)
        for actual, expected in zip(contract.energy_edges_gev, expected_edges)
    ):
        raise RuntimeError(
            f"{label} ROOT energy edges {contract.energy_edges_gev!r} do not "
            f"match expected {expected_edges!r}: {path}"
        )

    for output in points:
        point = output.point
        energy_bin = point.energy_bin
        if not 0 <= energy_bin < len(expected_edges) - 1:
            raise RuntimeError(
                f"{label} ROOT point has invalid energy bin {energy_bin}: {path}"
            )
        expected_low = expected_edges[energy_bin]
        expected_high = expected_edges[energy_bin + 1]
        if not (
            math.isclose(
                point.energy_low_gev,
                expected_low,
                rel_tol=0.0,
                abs_tol=1e-12,
            )
            and math.isclose(
                point.energy_high_gev,
                expected_high,
                rel_tol=0.0,
                abs_tol=1e-12,
            )
        ):
            raise RuntimeError(
                f"{label} ROOT point energy interval "
                f"[{point.energy_low_gev}, {point.energy_high_gev}] does not "
                f"match bin {energy_bin}: {path}"
            )


def run(args: argparse.Namespace) -> int:
    uv_points = read_output_points(args.uv_root)
    if not uv_points:
        raise RuntimeError(f"UV ROOT file has no points: {args.uv_root}")
    vis_points = read_output_points(args.vis_root)
    if not vis_points:
        raise RuntimeError(f"VIS ROOT file has no points: {args.vis_root}")
    _validate_profile_root("uv", args.uv_root, uv_points)
    _validate_profile_root("vis", args.vis_root, vis_points)

    points_by_profile = {"uv": uv_points, "vis": vis_points}
    ratio_by_profile = {
        profile: tuple(point for point in points if point.estimator == "ratio")
        for profile, points in points_by_profile.items()
    }
    rows = combined_energy_rows()
    published = load_published_points(args.published_csv)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    write_profile_figure4_pdf(
        args.output_dir / "figure4_experimental.pdf",
        points_by_profile,
        rows,
    )
    write_profile_figure4_comparison_pdf(
        args.output_dir / "figure4_comparison_ajaka2008.pdf",
        points_by_profile,
        published,
        rows,
    )
    write_profile_estimator_comparison_pdf(
        args.output_dir / "comparison_estimators.pdf",
        points_by_profile,
        rows,
    )
    write_profile_fit_diagnostics_pdf(
        args.output_dir / "fit_diagnostics.pdf",
        ratio_by_profile,
        rows,
    )
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    return run(build_parser().parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
