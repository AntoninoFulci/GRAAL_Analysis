"""Shared command-line options for reconstruction entry points."""

from __future__ import annotations

import argparse
from pathlib import Path

from reconstruction.runtime.reco_core import AUTO_TREE, RecoConfig
from reconstruction.core.reco_physics import PARTNER_MASSES, partner_mass


def _positive_workers(value: str) -> int:
    workers = int(value)
    if workers <= 0:
        raise argparse.ArgumentTypeError("workers must be a positive integer")
    return workers


def add_common_reconstruction_arguments(
    parser: argparse.ArgumentParser,
    *,
    default_output_file: Path,
    partner_help: str,
    fit_options_exposed: bool,
) -> None:
    """Add options shared by reconstruction commands."""
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("data/03_selected"),
        help="folder with the preselected ROOT files",
    )
    parser.add_argument(
        "--output-file",
        type=Path,
        default=default_output_file,
    )
    parser.add_argument(
        "--input-tree",
        default=AUTO_TREE,
        help="tree inside the selected files; 'auto' takes whichever "
        "known preselection tree is there (h85, or the older h80)",
    )
    parser.add_argument("--chi2-cut", type=float, default=10.0)
    parser.add_argument("--workers", type=_positive_workers, default=1,
                        help="independent reconstruction processes (default 1)")
    parser.add_argument(
        "--partner",
        choices=sorted(PARTNER_MASSES),
        default="proton",
        help=partner_help,
    )
    parser.add_argument(
        "--missing-mass-window",
        type=float,
        default=0.06,
        help="half-width [GeV] of the missing-mass window around the "
        "partner; <= 0 disables the cut (default 0.06)",
    )
    if fit_options_exposed:
        fit_group = parser.add_mutually_exclusive_group()
        fit_group.add_argument("--with-kinematic-fit", dest="no_fit", action="store_false",
                               help="explicitly enable archived kinematic-fit analysis")
        fit_group.add_argument(
            "--no-fit",
            action="store_true",
            default=True,
            help="disable the kinematic fit; fall back to the missing-mass "
            "cut for selection",
        )
        parser.add_argument(
            "--fit-cl",
            type=float,
            default=0.01,
            help="keep events whose kinematic-fit confidence level is above "
            "this (default 0.01)",
        )


def reco_config_from_args(
    args: argparse.Namespace,
    *,
    output_tree: str,
    fit_options_exposed: bool,
) -> RecoConfig:
    """Build a reconstruction configuration from parsed common options."""
    values = {
        "input_dir": args.input_dir,
        "output_file": args.output_file,
        "input_tree": args.input_tree,
        "output_tree": output_tree,
        "chi2_cut": args.chi2_cut,
        "partner_mass": partner_mass(args.partner),
        "missing_mass_window": args.missing_mass_window,
        "workers": args.workers,
    }
    if fit_options_exposed:
        values["do_fit"] = not args.no_fit
        values["fit_cl"] = args.fit_cl
    return RecoConfig(**values)
