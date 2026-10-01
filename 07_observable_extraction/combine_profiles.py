"""Compose UV and VIS beam-asymmetry ROOT outputs into five-row figures."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from observable_extraction.io.root_input import read_output_points
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--uv-root",
        type=Path,
        default=Path("test_data/beam_asymmetry/beam_asymmetry.root"),
    )
    parser.add_argument(
        "--vis-root",
        type=Path,
        default=Path("test_data/vis/beam_asymmetry/beam_asymmetry.root"),
    )
    parser.add_argument(
        "--published-csv",
        type=Path,
        default=Path(
            "test_data/beam_asymmetry/ajaka2008_figure4_digitized.csv"
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("test_data/beam_asymmetry/uv_vis"),
    )
    return parser


def run(args: argparse.Namespace) -> int:
    uv_points = read_output_points(args.uv_root)
    if not uv_points:
        raise RuntimeError(f"UV ROOT file has no points: {args.uv_root}")
    vis_points = read_output_points(args.vis_root)
    if not vis_points:
        raise RuntimeError(f"VIS ROOT file has no points: {args.vis_root}")

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
