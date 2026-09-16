"""Shared reconstruction CLI option and configuration contracts."""

import argparse
from contextlib import contextmanager
import importlib
from pathlib import Path
import sys
import types

import pytest

import reconstruction.core.kinematic_fit as kinematic_fit


@contextmanager
def _import_with_root_stub(*module_names):
    """Import CLI modules without requiring PyROOT for parser-only tests."""
    modules_before = set(sys.modules)
    previous_root = sys.modules.get("ROOT")
    sys.modules["ROOT"] = types.ModuleType("ROOT")
    try:
        yield tuple(importlib.import_module(name) for name in module_names)
    finally:
        for name in set(sys.modules) - modules_before:
            if name.startswith("reconstruction."):
                sys.modules.pop(name, None)
        if previous_root is None:
            sys.modules.pop("ROOT", None)
        else:
            sys.modules["ROOT"] = previous_root


def test_common_options_build_fit_enabled_configuration():
    with _import_with_root_stub("reconstruction.runtime.cli_options") as (cli_options,):
        parser = argparse.ArgumentParser(add_help=False)
        cli_options.add_common_reconstruction_arguments(
            parser,
            default_output_file=Path("default.root"),
            partner_help="partner help",
            fit_options_exposed=True,
        )

        args = parser.parse_args(
            [
                "--input-dir",
                "selected",
                "--output-file",
                "custom.root",
                "--input-tree",
                "h85",
                "--chi2-cut",
                "7.5",
                "--partner",
                "deuteron",
                "--missing-mass-window",
                "0.2",
                "--no-fit",
                "--fit-cl",
                "0.15",
            ]
        )
        cfg = cli_options.reco_config_from_args(
            args,
            output_tree="custom_tree",
            fit_options_exposed=True,
        )

    assert cfg.input_dir == Path("selected")
    assert cfg.output_file == Path("custom.root")
    assert cfg.input_tree == "h85"
    assert cfg.output_tree == "custom_tree"
    assert cfg.chi2_cut == 7.5
    assert cfg.partner_mass == 1.875613
    assert cfg.missing_mass_window == 0.2
    assert cfg.do_fit is False
    assert cfg.fit_cl == 0.15
    assert cfg.fit_reaction is kinematic_fit.PROTON_TARGET_REACTION
    assert cfg.fit_reaction.recoil_mass != cfg.partner_mass


def test_common_options_keep_fit_flags_out_of_non_fit_cli():
    with _import_with_root_stub("reconstruction.runtime.cli_options") as (cli_options,):
        parser = argparse.ArgumentParser(add_help=False)
        cli_options.add_common_reconstruction_arguments(
            parser,
            default_output_file=Path("two_pi0.root"),
            partner_help="partner help",
            fit_options_exposed=False,
        )

        args = parser.parse_args([])
        cfg = cli_options.reco_config_from_args(
            args,
            output_tree="reco_2pi0",
            fit_options_exposed=False,
        )
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(["--no-fit"])

    assert exc_info.value.code == 2
    assert "no_fit" not in vars(args)
    assert "fit_cl" not in vars(args)
    assert cfg.input_dir == Path("data/selected")
    assert cfg.output_file == Path("two_pi0.root")
    assert cfg.input_tree == "auto"
    assert cfg.output_tree == "reco_2pi0"
    assert cfg.chi2_cut == 10.0
    assert cfg.partner_mass == 0.938272
    assert cfg.missing_mass_window == 0.06
    assert cfg.do_fit is True
    assert cfg.fit_cl == 0.01


def test_bdt_hypothesis_mismatch_stops_before_reconstruction(monkeypatch):
    with _import_with_root_stub(
        "reconstruction.reconstruct_eta_pi0_bdt"
    ) as (bdt_cli,):
        events = []

        class _RejectingGate:
            def check_hypothesis(self, _hypothesis):
                events.append("check")
                raise ValueError("hypothesis mismatch")

        def load_gate(_cls, _path):
            events.append("load")
            return _RejectingGate()

        monkeypatch.setattr(bdt_cli.Stage1Gate, "load", classmethod(load_gate))
        monkeypatch.setattr(
            bdt_cli,
            "run_reconstruction",
            lambda *_args, **_kwargs: events.append("reconstruct"),
        )
        monkeypatch.setattr(sys, "argv", ["reconstruct_eta_pi0_bdt"])

        with pytest.raises(ValueError, match="hypothesis mismatch"):
            bdt_cli.main()

    assert events == ["load", "check"]
