"""Public command-line contracts for reconstruction entry points."""

from pathlib import Path
import subprocess
import sys

import pytest

from graal_common.io import trees
from reconstruction import reconstruct_2pi0
from reconstruction import reconstruct_eta_pi0_bdt
from reconstruction import reconstruct_eta_pi0_chi2
from reconstruction.core import reco_physics as rp


COMMON_OPTIONS = {
    "--input-dir",
    "--output-file",
    "--input-tree",
    "--chi2-cut",
    "--partner",
    "--missing-mass-window",
}


@pytest.mark.parametrize(
    ("module", "extra_options", "absent_options"),
    [
        (
            "reconstruction.reconstruct_eta_pi0_chi2",
            {"--no-fit", "--fit-cl"},
            {"--model-dir"},
        ),
        (
            "reconstruction.reconstruct_eta_pi0_bdt",
            {"--no-fit", "--fit-cl", "--model-dir"},
            set(),
        ),
        (
            "reconstruction.reconstruct_2pi0",
            set(),
            {"--no-fit", "--fit-cl", "--model-dir"},
        ),
    ],
)
def test_help_exposes_expected_options(module, extra_options, absent_options):
    result = subprocess.run(
        [sys.executable, "-m", module, "--help"],
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    for option in COMMON_OPTIONS | extra_options:
        assert option in result.stdout
    for option in absent_options:
        assert option not in result.stdout


def test_eta_pi0_chi2_defaults_build_expected_configuration(monkeypatch):
    observed = {}
    monkeypatch.setattr(
        reconstruct_eta_pi0_chi2,
        "run_reconstruction",
        lambda cfg, channel, gate=None: observed.update(
            cfg=cfg, channel=channel, gate=gate
        ),
    )
    monkeypatch.setattr(sys, "argv", ["reconstruct_eta_pi0_chi2"])

    reconstruct_eta_pi0_chi2.main()

    cfg = observed["cfg"]
    assert cfg.input_dir == Path("data/selected")
    assert cfg.output_file == Path("results/reco/reco_eta_pi0_chi2.root")
    assert cfg.input_tree == trees.AUTO
    assert cfg.output_tree == "reco_eta_pi0_chi2"
    assert cfg.chi2_cut == 10.0
    assert cfg.partner_mass == rp.M_PROTON
    assert cfg.missing_mass_window == 0.06
    assert cfg.do_fit is True
    assert cfg.fit_cl == 0.01
    assert observed["channel"] is rp.ETA_PI0
    assert observed["gate"] is None


class _Gate:
    def __init__(self):
        self.checked = None

    def check_hypothesis(self, hypothesis):
        self.checked = hypothesis


def test_eta_pi0_bdt_defaults_load_gate_and_build_expected_configuration(monkeypatch):
    observed = {}
    gate = _Gate()

    def load_gate(_cls, path):
        observed["model_dir"] = path
        return gate

    monkeypatch.setattr(
        reconstruct_eta_pi0_bdt.Stage1Gate,
        "load",
        classmethod(load_gate),
    )
    monkeypatch.setattr(
        reconstruct_eta_pi0_bdt,
        "run_reconstruction",
        lambda cfg, channel, gate=None: observed.update(
            cfg=cfg, channel=channel, gate=gate
        ),
    )
    monkeypatch.setattr(sys, "argv", ["reconstruct_eta_pi0_bdt"])

    reconstruct_eta_pi0_bdt.main()

    cfg = observed["cfg"]
    assert observed["model_dir"] == reconstruct_eta_pi0_bdt.DEFAULT_MODEL_DIR
    assert cfg.input_dir == Path("data/selected")
    assert cfg.output_file == Path("results/reco/reco_eta_pi0_bdt.root")
    assert cfg.input_tree == trees.AUTO
    assert cfg.output_tree == "reco_eta_pi0_bdt"
    assert cfg.chi2_cut == 10.0
    assert cfg.partner_mass == rp.M_PROTON
    assert cfg.missing_mass_window == 0.06
    assert cfg.do_fit is True
    assert cfg.fit_cl == 0.01
    assert gate.checked is rp.ETA_PI0.hypothesis
    assert observed["channel"] is rp.ETA_PI0
    assert observed["gate"] is gate


def test_2pi0_defaults_build_expected_configuration(monkeypatch):
    observed = {}
    monkeypatch.setattr(
        reconstruct_2pi0,
        "run_reconstruction",
        lambda cfg, channel, gate=None: observed.update(
            cfg=cfg, channel=channel, gate=gate
        ),
    )
    monkeypatch.setattr(sys, "argv", ["reconstruct_2pi0"])

    reconstruct_2pi0.main()

    cfg = observed["cfg"]
    assert cfg.input_dir == Path("data/selected")
    assert cfg.output_file == Path("results/reco/reco_2pi0.root")
    assert cfg.input_tree == trees.AUTO
    assert cfg.output_tree == "reco_2pi0"
    assert cfg.chi2_cut == 10.0
    assert cfg.partner_mass == rp.M_PROTON
    assert cfg.missing_mass_window == 0.06
    assert cfg.do_fit is True
    assert cfg.fit_cl == 0.01
    assert observed["channel"] is rp.TWO_PI0
    assert observed["gate"] is None
