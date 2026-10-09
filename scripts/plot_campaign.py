"""Regenerate canonical plots from an existing campaign's ROOT results."""

from __future__ import annotations

import argparse
from contextlib import ExitStack
from pathlib import Path
import shutil
import ROOT

from graal_common.io.filesystem import atomic_output_directory
from observable_extraction import combine_profiles
from observable_extraction.io.root_input import read_output_points
from observable_extraction.plotting.diagnostics import (
    write_point_comparison_pdf,
    write_profile_estimator_comparison_pdf,
    write_profile_fit_diagnostics_pdf,
    write_raw_fit_comparison_pdf,
)
from observable_extraction.plotting.figure4 import profile_energy_rows, combined_energy_rows, write_profile_figure4_pdf
from plots import dalitz, mass_comparison
from plots.core import reconstruction_data


STAGE7_PDFS = (
    "figure4_experimental.pdf", "comparison_reconstruction_samples.pdf",
    "comparison_estimators.pdf", "fit_diagnostics.pdf", "systematic_summary.pdf",
    "background_control.pdf", "false_asymmetry_controls.pdf", "photon_multiplicity.pdf",
)
REQUIRED_STAGE7_PDFS = (
    "systematic_summary.pdf", "false_asymmetry_controls.pdf", "photon_multiplicity.pdf",
)


def _copy_stage7_pdfs(root: Path, output: Path) -> None:
    for filename in STAGE7_PDFS:
        found = False
        for origin in (root / "plots" / filename, root / "beam_asymmetry" / filename):
            if origin.is_file():
                with origin.open("rb") as stream:
                    if stream.read(5) != b"%PDF-":
                        raise ValueError(f"invalid Stage-07 PDF {origin}")
                shutil.copy2(origin, output / filename)
                found = True
                break
        if not found and filename in REQUIRED_STAGE7_PDFS:
            raise FileNotFoundError(f"missing Stage-07 diagnostic {filename} in {root}")


def _read_profile(campaign: Path, profile: str):
    root = campaign / profile
    asymmetry = root / "beam_asymmetry/beam_asymmetry.root"
    points = read_output_points(asymmetry)
    if not points:
        raise ValueError(f"{asymmetry} has no asymmetry points")
    combine_profiles._validate_profile_root(profile, asymmetry, points)
    bdt = root / "reco/reco_eta_pi0_bdt.root"
    source, tree = reconstruction_data.open_tree(bdt, dalitz.BDT_TREE)
    try:
        arrays = reconstruction_data.collect(tree, require_fit=True)
    finally:
        source.Close()
    source, tree = reconstruction_data.open_tree(root / "reco/reco_eta_pi0_chi2.root", dalitz.CHI2_TREE)
    source.Close()
    return points, arrays


def _render_profile(campaign: Path, profile: str, payload, output: Path) -> None:
    points, arrays = payload
    root = campaign / profile
    _copy_stage7_pdfs(root, output)
    ROOT.gROOT.GetListOfCanvases().Delete()
    dalitz.main([
        "--chi2", str(root / "reco/reco_eta_pi0_chi2.root"),
        "--bdt", str(root / "reco/reco_eta_pi0_bdt.root"),
        "--out-dir", str(output),
    ])
    mass_comparison.write_profile_masses(arrays, output, profile)
    rows = profile_energy_rows(profile)
    mapping = {profile: points}
    write_profile_figure4_pdf(output / "figure4_experimental.pdf", mapping, rows)
    write_point_comparison_pdf(output / "comparison_reconstruction_samples.pdf",
                               [point for point in points if point.estimator == "ratio"], group_by="sample")
    write_profile_estimator_comparison_pdf(output / "comparison_estimators.pdf", mapping, rows)
    write_profile_fit_diagnostics_pdf(output / "fit_diagnostics.pdf",
                                      {profile: tuple(point for point in points if point.sample == "raw_bdt" and point.estimator == "ratio")},
                                      rows)
    for estimator in ("ratio", "likelihood"):
        write_raw_fit_comparison_pdf(output / f"comparison_raw_fit_{estimator}.pdf", mapping, rows, estimator=estimator)


def _render_common(campaign: Path, payloads: dict, output: Path, reference: Path) -> None:
    combine_profiles.run(argparse.Namespace(
        uv_root=campaign / "uv/beam_asymmetry/beam_asymmetry.root",
        vis_root=campaign / "vis/beam_asymmetry/beam_asymmetry.root",
        published_csv=reference,
        output_dir=output,
    ))
    mass_comparison.write_common_masses({profile: value[1] for profile, value in payloads.items()}, output)
    mapping = {profile: value[0] for profile, value in payloads.items()}
    for estimator in ("ratio", "likelihood"):
        write_raw_fit_comparison_pdf(output / f"comparison_raw_fit_{estimator}.pdf",
                                     mapping, combined_energy_rows(), estimator=estimator)


def render_campaign(campaign: Path, reference: Path) -> None:
    campaign = Path(campaign).expanduser().resolve()
    payloads = {profile: _read_profile(campaign, profile) for profile in ("uv", "vis")}
    with ExitStack() as stack:
        outputs = {
            profile: stack.enter_context(atomic_output_directory(campaign / profile / "plots"))
            for profile in ("uv", "vis")
        }
        common = stack.enter_context(atomic_output_directory(campaign / "common/plots"))
        for profile in ("uv", "vis"):
            _render_profile(campaign, profile, payloads[profile], outputs[profile])
        _render_common(campaign, payloads, common, reference)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign", required=True, type=Path)
    parser.add_argument("--published-csv", type=Path, default=combine_profiles.AJAKA_REFERENCE)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    render_campaign(args.campaign, args.published_csv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
