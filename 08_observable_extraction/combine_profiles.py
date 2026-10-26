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
from observable_extraction.plotting.candle import write_candle_comparison_pdf
from observable_extraction.plotting.figure4 import (
    combined_energy_rows,
    profile_energy_rows,
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
        default=PRODUCTION_ROOT / "common/plots",
    )
    return parser


def _validate_profile_root(profile_name: str, path: Path, points):
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

    expected_edges = contract.energy_edges_gev if contract.explicit_energy_grid else profile.energy_edges_gev
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
    return contract


def _validate_candle_campaign(
    uv_contract, vis_contract, uv_points, vis_points
) -> bool:
    states = []
    for label, contract, points in (
        ("UV", uv_contract, uv_points),
        ("VIS", vis_contract, vis_points),
    ):
        has_core = any(item.sample == "raw_bdt_core" for item in points)
        has_tails = any(item.sample == "raw_bdt_tails" for item in points)
        has_contract = contract.candle is not None
        if has_core != has_contract or has_tails != has_contract:
            raise RuntimeError(
                f"{label} candle core/tails samples and provenance do not agree"
            )
        states.append(has_contract)
    if states[0] != states[1]:
        raise RuntimeError("UV/VIS candle enablement does not match")
    if not states[0]:
        return False

    uv_candle = uv_contract.candle
    vis_candle = vis_contract.candle
    float_fields = (
        "eta_center_gev",
        "pi0_center_gev",
        "mass_half_width_gev",
    )
    text_fields = (
        "geometry",
        "core_logic",
        "tail_logic",
        "boundary",
        "balance_method",
        "mass_source",
    )
    if any(
        not math.isclose(
            getattr(uv_candle, name),
            getattr(vis_candle, name),
            rel_tol=0.0,
            abs_tol=1e-12,
        )
        for name in float_fields
    ) or any(
        getattr(uv_candle, name) != getattr(vis_candle, name)
        for name in text_fields
    ):
        raise RuntimeError("UV/VIS candle definitions do not match")
    return True


def run(args: argparse.Namespace) -> int:
    uv_points = read_output_points(args.uv_root)
    if not uv_points:
        raise RuntimeError(f"UV ROOT file has no points: {args.uv_root}")
    vis_points = read_output_points(args.vis_root)
    if not vis_points:
        raise RuntimeError(f"VIS ROOT file has no points: {args.vis_root}")
    uv_contract = _validate_profile_root("uv", args.uv_root, uv_points)
    vis_contract = _validate_profile_root("vis", args.vis_root, vis_points)
    if uv_contract.best_binning != vis_contract.best_binning:
        raise RuntimeError("UV/VIS ROOT best-binning mode does not match")
    if not uv_contract.best_binning:
        if len(uv_contract.phi_edges_rad) != len(vis_contract.phi_edges_rad) or any(
            not math.isclose(uv, vis, rel_tol=0.0, abs_tol=1e-12)
            for uv, vis in zip(uv_contract.phi_edges_rad, vis_contract.phi_edges_rad)
        ):
            raise RuntimeError("UV/VIS ROOT phi binning does not match")
        if not math.isclose(uv_contract.phi_bin_divisor, vis_contract.phi_bin_divisor,
                            rel_tol=0.0, abs_tol=1e-12):
            raise RuntimeError("UV/VIS ROOT phi-bin correction does not match")
    candle_enabled = _validate_candle_campaign(
        uv_contract, vis_contract, uv_points, vis_points
    )

    points_by_profile = {"uv": uv_points, "vis": vis_points}
    ratio_by_profile = {
        profile: tuple(point for point in points if point.estimator == "ratio")
        for profile, points in points_by_profile.items()
    }
    rows = (profile_energy_rows("vis", vis_contract.energy_edges_gev)
            + profile_energy_rows("uv", uv_contract.energy_edges_gev))
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
    if candle_enabled:
        for estimator in ("ratio", "likelihood"):
            write_candle_comparison_pdf(
                args.output_dir / f"comparison_candle_{estimator}.pdf",
                points_by_profile,
                rows,
                estimator=estimator,
            )
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    return run(build_parser().parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
