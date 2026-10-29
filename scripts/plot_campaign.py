"""Regenerate canonical plots from an existing campaign's ROOT results."""

from __future__ import annotations

import argparse
from contextlib import ExitStack
from pathlib import Path
import shutil
import ROOT

from graal_common.io.filesystem import atomic_output_directory
from graal_workflow.publication import organize_campaign_reports
from observable_extraction import combine_profiles
from observable_extraction.io.root_input import read_output_points, read_output_contract
from observable_extraction.plotting.diagnostics import (
    write_point_comparison_pdf,
    write_profile_estimator_comparison_pdf,
    write_profile_fit_diagnostics_pdf,
)
from observable_extraction.plotting.candle import (
    available_candle_estimators,
    write_candle_comparison_pdf,
)
from observable_extraction.plotting.figure4 import profile_energy_rows
from plots import dalitz
from plots.core import reconstruction_data
from reconstruction.runtime.provenance import validate_reconstruction_selection


STAGE7_PDFS = (
    "comparison_reconstruction_samples.pdf",
    "comparison_estimators.pdf", "fit_diagnostics.pdf", "systematic_summary.pdf",
    "background_control.pdf", "false_asymmetry_controls.pdf", "photon_multiplicity.pdf",
    "period_stability.pdf", "comparison_candle_ratio.pdf", "comparison_candle_likelihood.pdf",
)
REQUIRED_STAGE7_PDFS = (
    "systematic_summary.pdf", "false_asymmetry_controls.pdf", "photon_multiplicity.pdf",
)


def _copy_stage7_pdfs(
    root: Path, output: Path, *, require_candle: bool = False, plots: Path | None = None
) -> None:
    extraction = root / "beam_asymmetry/beam_asymmetry.root"
    extracted_at = extraction.stat().st_mtime_ns if extraction.exists() else None
    for filename in STAGE7_PDFS:
        found = False
        for origin in (root / "beam_asymmetry" / filename, (plots or root / "plots") / filename):
            if origin.is_file():
                if plots is None and origin.parent == root / "plots" and filename in {
                    "comparison_reconstruction_samples.pdf", "comparison_estimators.pdf", "fit_diagnostics.pdf",
                    "comparison_candle_ratio.pdf", "comparison_candle_likelihood.pdf",
                }:
                    continue
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
            source = (plots or root / "plots") / "candle_mass_plane.pdf"
        if not source.is_file():
            raise FileNotFoundError(f"missing candle_mass_plane.pdf in {root}")
        if extracted_at is not None and source.stat().st_mtime_ns < extracted_at:
            raise ValueError(
                f"candle_mass_plane.pdf is older than current extraction in {root}"
            )
        with source.open("rb") as stream:
            if stream.read(5) != b"%PDF-":
                raise ValueError(f"invalid Stage-08 PDF {source}")
        shutil.copy2(source, output / source.name)


def _profile_root(campaign: Path, profile: str) -> Path:
    root = campaign / "root" / profile
    return root if (root / "beam_asymmetry/beam_asymmetry.root").is_file() else campaign / profile


def _read_profile(campaign: Path, profile: str):
    root = _profile_root(campaign, profile)
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
    root = _profile_root(campaign, profile)
    candle_enabled = any(
        point.sample in {"raw_bdt_core", "raw_bdt_tails"} for point in points
    )
    _copy_stage7_pdfs(root, output, require_candle=candle_enabled,
                      plots=campaign / "plots" / profile if (campaign / "plots" / profile).is_dir() else None)
    periods = campaign / "plots" / profile / "periods"
    if periods.is_dir():
        shutil.copytree(periods, output / "periods")
    ROOT.gROOT.GetListOfCanvases().Delete()
    dalitz.main([
        "--chi2", str(root / "reco/reco_eta_pi0_chi2.root"),
        "--bdt", str(root / "reco/reco_eta_pi0_bdt.root"),
        "--out-dir", str(output),
        "--profile", profile,
        "--mass-only",
        "--quality-controls",
    ])
    contract = read_output_contract(root / "beam_asymmetry/beam_asymmetry.root")
    rows = profile_energy_rows(profile, contract.energy_edges_gev)
    mapping = {profile: points}
    if not (output / "comparison_reconstruction_samples.pdf").is_file():
        write_point_comparison_pdf(output / "comparison_reconstruction_samples.pdf",
                                   [point for point in points if point.estimator == "ratio"], group_by="sample")
    if not (output / "comparison_estimators.pdf").is_file():
        write_profile_estimator_comparison_pdf(output / "comparison_estimators.pdf", mapping, rows)
    if not (output / "fit_diagnostics.pdf").is_file():
        write_profile_fit_diagnostics_pdf(output / "fit_diagnostics.pdf",
                                          {profile: tuple(point for point in points if point.sample == "raw_bdt" and point.estimator == "ratio")},
                                          rows)
    if candle_enabled:
        for estimator in available_candle_estimators(mapping):
            if (output / f"comparison_candle_{estimator}.pdf").is_file():
                continue
            write_candle_comparison_pdf(
                output / f"comparison_candle_{estimator}.pdf",
                mapping,
                rows,
                estimator=estimator,
            )


def _render_common(campaign: Path, output: Path, reference: Path) -> None:
    combine_profiles.run(argparse.Namespace(
        uv_root=_profile_root(campaign, "uv") / "beam_asymmetry/beam_asymmetry.root",
        vis_root=_profile_root(campaign, "vis") / "beam_asymmetry/beam_asymmetry.root",
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
            profile: stack.enter_context(atomic_output_directory(campaign / "plots" / profile))
            for profile in ("uv", "vis")
        }
        common = stack.enter_context(atomic_output_directory(campaign / "plots/common"))
        def render(profile):
            if profile == "common":
                _render_common(campaign, common, reference)
            else:
                _render_profile(campaign, profile, payloads[profile], outputs[profile])
        ordered_map(render, ("uv", "vis", "common"), workers=min(workers, 3))
    organize_campaign_reports(campaign)


def render_reconstruction(
    chi2: Path, bdt: Path, output_dir: Path, *, profile: str,
    mass: bool = True, quality_controls: bool = True, dalitz_plots: bool = False,
) -> None:
    """Publish reconstruction diagnostics without requiring extraction products."""
    chi2, bdt, output_dir = (Path(path).expanduser().resolve()
                            for path in (chi2, bdt, output_dir))
    if any(path.is_relative_to(output_dir) for path in (chi2, bdt)):
        raise ValueError("plot output directory cannot contain reconstruction inputs")
    with atomic_output_directory(output_dir) as output:
        ROOT.gROOT.GetListOfCanvases().Delete()
        dalitz.main([
            "--chi2", str(chi2), "--bdt", str(bdt),
            "--out-dir", str(output), "--profile", profile,
            "--mass" if mass else "--no-mass",
            "--quality-controls" if quality_controls else "--no-quality-controls",
            "--dalitz" if dalitz_plots else "--no-dalitz",
        ])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=1, help="isolated profile/common plot processes (up to 3)")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--campaign", type=Path)
    mode.add_argument("--reconstruction-only", action="store_true",
                      help="plot only the explicitly supplied reconstructions")
    parser.add_argument("--profile", choices=("uv", "vis"))
    parser.add_argument("--chi2", type=Path)
    parser.add_argument("--bdt", type=Path)
    parser.add_argument("--output-dir", type=Path)
    for name, default in (("mass", True), ("quality-controls", True), ("dalitz", False)):
        parser.add_argument(f"--{name}", action=argparse.BooleanOptionalAction,
                            default=default, help="reconstruction-only plot family")
    parser.add_argument("--published-csv", type=Path,
                        default=Path(__file__).resolve().parents[1] / "08_observable_extraction/references/ajaka2008_figure4_digitized.csv")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.reconstruction_only:
        missing = [f"--{name.replace('_', '-')}" for name in
                   ("profile", "chi2", "bdt", "output_dir") if getattr(args, name) is None]
        if missing:
            parser.error("--reconstruction-only requires " + ", ".join(missing))
        render_reconstruction(args.chi2, args.bdt, args.output_dir, profile=args.profile,
                              mass=args.mass, quality_controls=args.quality_controls,
                              dalitz_plots=args.dalitz)
    else:
        render_campaign(args.campaign, args.published_csv, workers=args.workers)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
