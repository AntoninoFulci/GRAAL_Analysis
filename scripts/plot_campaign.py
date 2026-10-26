"""Regenerate canonical plots from an existing campaign's ROOT results."""

from __future__ import annotations

import argparse
from contextlib import ExitStack
from pathlib import Path
import shutil
import ROOT

from graal_common.io.filesystem import atomic_output_directory
from observable_extraction import combine_profiles
from observable_extraction.io.root_input import read_output_points, read_output_contract
from observable_extraction.plotting.diagnostics import (
    write_point_comparison_pdf,
    write_profile_estimator_comparison_pdf,
    write_profile_fit_diagnostics_pdf,
)
from observable_extraction.plotting.candle import write_candle_comparison_pdf
from observable_extraction.plotting.figure4 import profile_energy_rows, write_profile_figure4_pdf
from plots import dalitz
from plots.core import reconstruction_data
from reconstruction.runtime.provenance import validate_reconstruction_selection


STAGE7_PDFS = (
    "figure4_experimental.pdf", "comparison_reconstruction_samples.pdf",
    "comparison_estimators.pdf", "fit_diagnostics.pdf", "systematic_summary.pdf",
    "background_control.pdf", "false_asymmetry_controls.pdf", "photon_multiplicity.pdf",
    "period_stability.pdf",
)
REQUIRED_STAGE7_PDFS = (
    "systematic_summary.pdf", "false_asymmetry_controls.pdf", "photon_multiplicity.pdf",
)


def _copy_stage7_pdfs(
    root: Path, output: Path, *, require_candle: bool = False
) -> None:
    extraction = root / "beam_asymmetry/beam_asymmetry.root"
    extracted_at = extraction.stat().st_mtime_ns if extraction.exists() else None
    for filename in STAGE7_PDFS:
        found = False
        for origin in (root / "beam_asymmetry" / filename, root / "plots" / filename):
            if origin.is_file():
                if extracted_at is not None and origin.stat().st_mtime_ns < extracted_at:
                    continue
                with origin.open("rb") as stream:
                    if stream.read(5) != b"%PDF-":
                        raise ValueError(f"invalid Stage-08 PDF {origin}")
                shutil.copy2(origin, output / filename)
                found = True
                break
        if not found and filename in REQUIRED_STAGE7_PDFS:
            raise FileNotFoundError(f"missing Stage-08 diagnostic {filename} in {root}")
    if require_candle:
        source = root / "beam_asymmetry/candle_mass_plane.pdf"
        if not source.is_file():
            raise FileNotFoundError(f"missing candle_mass_plane.pdf in {root}")
        with source.open("rb") as stream:
            if stream.read(5) != b"%PDF-":
                raise ValueError(f"invalid Stage-08 PDF {source}")
        shutil.copy2(source, output / source.name)


def _read_profile(campaign: Path, profile: str):
    root = campaign / profile
    asymmetry = root / "beam_asymmetry/beam_asymmetry.root"
    points = read_output_points(asymmetry)
    if not points:
        raise ValueError(f"{asymmetry} has no asymmetry points")
    contract = combine_profiles._validate_profile_root(profile, asymmetry, points)
    candle_samples = {"raw_bdt_core", "raw_bdt_tails"}
    present_candle = {point.sample for point in points} & candle_samples
    if bool(present_candle) != (contract.candle is not None):
        raise ValueError("campaign candle samples and provenance do not agree")
    allowed = {"raw", "raw_bdt"} | (candle_samples if contract.candle else set())
    if any(point.sample not in allowed for point in points):
        raise ValueError("campaign requires raw/raw_bdt reconstruction samples")
    for name, tree_name in (("bdt", dalitz.BDT_TREE), ("chi2", dalitz.CHI2_TREE)):
        source, tree = reconstruction_data.open_tree(root / "reco" / f"reco_eta_pi0_{name}.root", tree_name)
        try:
            validate_reconstruction_selection(source, tree)
        finally:
            source.Close()
    return points


def _render_profile(campaign: Path, profile: str, points, output: Path) -> None:
    root = campaign / profile
    candle_enabled = any(
        point.sample in {"raw_bdt_core", "raw_bdt_tails"} for point in points
    )
    _copy_stage7_pdfs(root, output, require_candle=candle_enabled)
    ROOT.gROOT.GetListOfCanvases().Delete()
    dalitz.main([
        "--chi2", str(root / "reco/reco_eta_pi0_chi2.root"),
        "--bdt", str(root / "reco/reco_eta_pi0_bdt.root"),
        "--out-dir", str(output),
        "--profile", profile,
    ])
    contract = read_output_contract(root / "beam_asymmetry/beam_asymmetry.root")
    rows = profile_energy_rows(profile, contract.energy_edges_gev)
    mapping = {profile: points}
    write_profile_figure4_pdf(output / "figure4_experimental.pdf", mapping, rows)
    write_point_comparison_pdf(output / "comparison_reconstruction_samples.pdf",
                               [point for point in points if point.estimator == "ratio"], group_by="sample")
    write_profile_estimator_comparison_pdf(output / "comparison_estimators.pdf", mapping, rows)
    write_profile_fit_diagnostics_pdf(output / "fit_diagnostics.pdf",
                                      {profile: tuple(point for point in points if point.sample == "raw_bdt" and point.estimator == "ratio")},
                                      rows)
    if candle_enabled:
        for estimator in ("ratio", "likelihood"):
            write_candle_comparison_pdf(
                output / f"comparison_candle_{estimator}.pdf",
                mapping,
                rows,
                estimator=estimator,
            )


def _render_common(campaign: Path, output: Path, reference: Path) -> None:
    combine_profiles.run(argparse.Namespace(
        uv_root=campaign / "uv/beam_asymmetry/beam_asymmetry.root",
        vis_root=campaign / "vis/beam_asymmetry/beam_asymmetry.root",
        published_csv=reference,
        output_dir=output,
    ))


def render_campaign(campaign: Path, reference: Path, *, workers: int = 1) -> None:
    from graal_common.parallel import ordered_map, validate_workers
    validate_workers(workers)
    campaign = Path(campaign).expanduser().resolve()
    payloads = {profile: _read_profile(campaign, profile)
                for profile in ("uv", "vis")}
    with ExitStack() as stack:
        outputs = {
            profile: stack.enter_context(atomic_output_directory(campaign / profile / "plots"))
            for profile in ("uv", "vis")
        }
        common = stack.enter_context(atomic_output_directory(campaign / "common/plots"))
        def render(profile):
            if profile == "common":
                _render_common(campaign, common, reference)
            else:
                _render_profile(campaign, profile, payloads[profile], outputs[profile])
        ordered_map(render, ("uv", "vis", "common"), workers=min(workers, 3))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=1, help="isolated profile/common plot processes (up to 3)")
    parser.add_argument("--campaign", required=True, type=Path)
    parser.add_argument("--published-csv", type=Path,
                        default=Path(__file__).resolve().parents[1] / "08_observable_extraction/references/ajaka2008_figure4_digitized.csv")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    render_campaign(args.campaign, args.published_csv, workers=args.workers)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
