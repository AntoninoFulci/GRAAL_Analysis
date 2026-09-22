from array import array

import numpy as np
import pytest
import ROOT

from observable_extraction.core.models import FluxExposure
from observable_extraction.io.reconstructed_events import (
    read_reconstructed,
    select_brem_control,
    select_sigma_events,
)


def _write_reconstructed(path):
    output = ROOT.TFile(str(path), "RECREATE")
    tree = ROOT.TTree("reco", "reco")
    run = array("i", [811])
    strip = array("f", [17.75])
    polarization = array("i", [1])
    eta_mass = array("f", [0.55])
    pi0_mass = array("f", [0.135])
    score = array("f", [0.81])
    multiplicity = array("i", [5])
    vectors = {
        name: ROOT.TLorentzVector()
        for name in (
            "beam", "eta", "pi0", "proton", "missing",
            "eta_fit", "pi0_fit", "proton_fit",
        )
    }
    tree.Branch("RunNumber", run, "RunNumber/I")
    tree.Branch("Xstrip", strip, "Xstrip/F")
    tree.Branch("Polarization", polarization, "Polarization/I")
    tree.Branch("eta_mass", eta_mass, "eta_mass/F")
    tree.Branch("pi0_mass", pi0_mass, "pi0_mass/F")
    tree.Branch("bdt_score", score, "bdt_score/F")
    tree.Branch("n_photons_input", multiplicity, "n_photons_input/I")
    for name, vector in vectors.items():
        tree.Branch(name, "TLorentzVector", vector)

    vectors["beam"].SetPxPyPzE(0.0, 0.0, 1.25, 1.25)
    vectors["eta"].SetPxPyPzE(0.1, 0.0, 0.2, 0.72)
    vectors["pi0"].SetPxPyPzE(-0.1, 0.0, 0.1, 0.25)
    vectors["proton"].SetPxPyPzE(0.0, 0.0, 0.1, 0.95)
    vectors["missing"].SetPxPyPzE(0.0, 0.0, 0.0, 0.94)
    vectors["eta_fit"].SetPxPyPzE(0.08, 0.0, 0.2, 0.70)
    vectors["pi0_fit"].SetPxPyPzE(-0.08, 0.0, 0.1, 0.24)
    vectors["proton_fit"].SetPxPyPzE(0.0, 0.0, 0.1, 0.96)
    tree.Fill()

    polarization[0] = 0
    strip[0] = 18.75
    score[0] = 0.75
    multiplicity[0] = 4
    tree.Fill()
    tree.Write()
    output.Close()


def test_read_reconstructed_selects_raw_or_fitted_vectors(tmp_path):
    path = tmp_path / "reco.root"
    _write_reconstructed(path)

    raw = read_reconstructed(path, "reco", vector_mode="raw")
    fitted = read_reconstructed(path, "reco", vector_mode="fit")

    assert raw.eta[0, 3] == pytest.approx(0.72)
    assert fitted.eta[0, 3] == pytest.approx(0.70)
    assert raw.bdt_score[0] == pytest.approx(0.81)
    assert raw.n_photons_input[0] == 5
    assert raw.missing_mass_gev[0] == pytest.approx(0.94)
    assert raw.eta_mass_gev[0] == pytest.approx(0.55)
    assert raw.xstrip.tolist() == [17, 18]


def test_select_sigma_events_and_brem_control_are_disjoint(tmp_path):
    path = tmp_path / "reco.root"
    _write_reconstructed(path)
    events = read_reconstructed(path, "reco", vector_mode="raw")
    exposures = {
        (811, 17): FluxExposure(811, 17, 1.25, 120, 80, 25, 0.5, 0.5),
        (811, 18): FluxExposure(811, 18, 1.25, 120, 80, 25, 0.5, 0.5),
    }

    sigma = select_sigma_events(events, exposures)
    brem = select_brem_control(events, exposures)

    assert sigma.polarization.tolist() == [1]
    assert brem.polarization.tolist() == [0]


def test_select_sigma_events_fails_on_missing_selected_run_strip(tmp_path):
    path = tmp_path / "reco.root"
    _write_reconstructed(path)
    events = read_reconstructed(path, "reco", vector_mode="raw")

    with pytest.raises(ValueError, match=r"missing exposure.*\(811, 17\)"):
        select_sigma_events(events, {})
