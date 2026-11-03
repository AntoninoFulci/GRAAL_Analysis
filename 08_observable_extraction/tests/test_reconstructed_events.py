from array import array
import json

import numpy as np
import pytest
import ROOT

from observable_extraction.core.models import FluxExposure
from observable_extraction.io.reconstructed_events import (
    EventArrays,
    read_reconstructed,
    select_brem_control,
    select_sigma_events,
)


def _write_reconstructed(path, *, certified=True):
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
    tree.Fill()

    polarization[0] = 0
    strip[0] = 18.75
    score[0] = 0.75
    multiplicity[0] = 4
    tree.Fill()
    tree.Write()
    if certified:
        ROOT.TNamed("reconstruction_provenance", json.dumps(dict(schema=2, selection_algorithm="pairing_missing_mass"))).Write()
    output.Close()


def test_read_reconstructed_preserves_raw_vectors(tmp_path):
    path = tmp_path / "reco.root"
    _write_reconstructed(path)

    raw = read_reconstructed(path, "reco")

    assert raw.eta[0, 3] == pytest.approx(0.72)
    assert raw.bdt_score[0] == pytest.approx(0.81)
    assert raw.n_photons_input[0] == 5
    assert raw.missing_mass_gev[0] == pytest.approx(0.94)
    assert raw.eta_mass_gev[0] == pytest.approx(0.55)
    assert raw.xstrip.tolist() == [17, 18]


def test_select_sigma_events_and_brem_control_are_disjoint(tmp_path):
    path = tmp_path / "reco.root"
    _write_reconstructed(path)
    events = read_reconstructed(path, "reco")
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
    events = read_reconstructed(path, "reco")

    with pytest.raises(ValueError, match=r"missing exposure.*\(811, 17\)"):
        select_sigma_events(events, {})


def test_select_sigma_events_can_drop_missing_exposures_with_warning(
    tmp_path, capsys
):
    path = tmp_path / "reco.root"
    _write_reconstructed(path)
    events = read_reconstructed(path, "reco")

    selected = select_sigma_events(events, {}, drop_missing=True)

    assert len(selected) == 0
    assert (
        "warning: dropped 1 event across 1 run/strip without valid flux exposure"
        in capsys.readouterr().err
    )


def test_vis_energy_range_keeps_exact_boundaries_after_exposure_filtering():
    energies = np.array([0.9312, 0.9313, 1.10, 1.1001])
    count = len(energies)
    vectors = np.zeros((count, 4), dtype=np.float64)
    events = EventArrays(
        run_number=np.full(count, 811),
        xstrip=np.full(count, 17),
        polarization=np.array([1, 1, 2, 2]),
        beam_energy_gev=energies,
        eta=vectors,
        pi0=vectors,
        proton=vectors,
        missing_mass_gev=np.zeros(count),
        eta_mass_gev=np.zeros(count),
        pi0_mass_gev=np.zeros(count),
        bdt_score=np.zeros(count),
        n_photons_input=np.full(count, 4),
    )
    exposures = {
        (811, 17): FluxExposure(811, 17, 1.0, 1.0, 1.0, 1.0, 0.6, 0.6)
    }

    selected = select_sigma_events(
        events,
        exposures,
        energy_range=(0.9313, 1.10),
    )

    assert selected.beam_energy_gev.tolist() == pytest.approx([0.9313, 1.10])


def test_baseline_reader_rejects_historical_fit_selected_raw(tmp_path):
    path = tmp_path / "historical.root"
    _write_reconstructed(path, certified=False)
    with pytest.raises(ValueError, match="provenance"):
        read_reconstructed(path, "reco")
