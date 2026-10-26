from array import array
from dataclasses import fields
import json

import numpy as np
import pytest
import ROOT

from observable_extraction.core.models import FluxExposure
from graal_common.physics.channels import M_ETA, M_PI0
from observable_extraction.io import reconstructed_events
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


def _events_with_candidate_masses(
    eta_mass_gev: np.ndarray,
    pi0_mass_gev: np.ndarray,
) -> EventArrays:
    count = len(eta_mass_gev)
    scalars = np.arange(count, dtype=np.float64)
    vectors = np.arange(count * 4, dtype=np.float64).reshape(count, 4)
    return EventArrays(
        run_number=np.arange(100, 100 + count, dtype=np.int64),
        xstrip=np.arange(1, count + 1, dtype=np.int64),
        polarization=np.resize(np.array([1, 2], dtype=np.int64), count),
        beam_energy_gev=1.1 + scalars / 100.0,
        eta=vectors + 100.0,
        pi0=vectors + 200.0,
        proton=vectors + 300.0,
        missing_mass_gev=scalars + 0.9,
        eta_mass_gev=np.asarray(eta_mass_gev, dtype=np.float64),
        pi0_mass_gev=np.asarray(pi0_mass_gev, dtype=np.float64),
        bdt_score=scalars / 10.0,
        n_photons_input=np.arange(4, 4 + count, dtype=np.int64),
    )


def test_core_tail_split_uses_inclusive_core_and_or_complement():
    width = 0.05
    epsilon = 1.0e-12
    events = _events_with_candidate_masses(
        np.array([
            M_ETA - width, M_ETA + width, M_ETA, M_ETA,
            M_ETA + width + epsilon, M_ETA, M_ETA - width - epsilon, M_ETA,
        ]),
        np.array([
            M_PI0, M_PI0, M_PI0 - width, M_PI0 + width,
            M_PI0, M_PI0 + width + epsilon, M_PI0, M_PI0 - width - epsilon,
        ]),
    )

    split = reconstructed_events.split_candle_core_tails(
        events, width, seed=1208
    )

    assert isinstance(split, reconstructed_events.CandleSplit)
    assert split.full_core_count == 4
    assert split.tail_count == 4
    assert split.excluded_nonfinite_count == 0
    assert split.core.run_number.tolist() == [100, 101, 102, 103]
    assert split.tails.run_number.tolist() == [104, 105, 106, 107]


def test_core_tail_split_excludes_nonfinite_masses_from_both_samples():
    events = _events_with_candidate_masses(
        np.array([M_ETA, M_ETA + 0.06, np.nan, M_ETA, np.inf]),
        np.array([M_PI0, M_PI0, M_PI0, -np.inf, M_PI0]),
    )

    split = reconstructed_events.split_candle_core_tails(
        events, 0.05, seed=7
    )

    assert split.full_core_count == 1
    assert split.tail_count == 1
    assert split.excluded_nonfinite_count == 3
    assert split.core.run_number.tolist() == [100]
    assert split.tails.run_number.tolist() == [101]


def test_core_tail_split_is_equal_reproducible_and_preserves_field_alignment():
    events = _events_with_candidate_masses(
        np.array([
            M_ETA, M_ETA + 0.001, M_ETA + 0.002, M_ETA + 0.003,
            M_ETA + 0.004, M_ETA + 0.06, M_ETA,
        ]),
        np.array([
            M_PI0, M_PI0, M_PI0, M_PI0, M_PI0, M_PI0, M_PI0 - 0.06,
        ]),
    )

    first = reconstructed_events.split_candle_core_tails(
        events, 0.05, seed=20261024
    )
    second = reconstructed_events.split_candle_core_tails(
        events, 0.05, seed=20261024
    )

    assert len(first.core) == len(first.tails) == 2
    assert first.full_core_count == 5
    assert first.tail_count == 2
    assert first.core.run_number.tolist() == sorted(first.core.run_number.tolist())
    assert set(first.core.run_number).isdisjoint(first.tails.run_number)
    for field in fields(EventArrays):
        np.testing.assert_array_equal(
            getattr(first.core, field.name),
            getattr(second.core, field.name),
        )
    source_index = {run: index for index, run in enumerate(events.run_number)}
    for selected in (first.core, first.tails):
        indices = np.array([source_index[run] for run in selected.run_number])
        for field in fields(EventArrays):
            np.testing.assert_array_equal(
                getattr(selected, field.name),
                getattr(events, field.name)[indices],
            )


@pytest.mark.parametrize("width", [0.0, -0.05, np.nan, np.inf, -np.inf])
def test_core_tail_split_rejects_invalid_half_width(width):
    events = _events_with_candidate_masses(
        np.array([M_ETA, M_ETA + 0.06]),
        np.array([M_PI0, M_PI0]),
    )

    with pytest.raises(ValueError, match="half_width_gev"):
        reconstructed_events.split_candle_core_tails(events, width, seed=1)


@pytest.mark.parametrize("seed", [-1, 1.5, True])
def test_core_tail_split_rejects_invalid_seed(seed):
    events = _events_with_candidate_masses(
        np.array([M_ETA, M_ETA + 0.06]),
        np.array([M_PI0, M_PI0]),
    )

    with pytest.raises(ValueError, match="seed"):
        reconstructed_events.split_candle_core_tails(events, 0.05, seed=seed)


@pytest.mark.parametrize(
    ("eta_masses", "pi0_masses", "message"),
    [
        ([M_ETA + 0.06], [M_PI0], "core=0 tails=1"),
        ([M_ETA], [M_PI0], "core=1 tails=0"),
        (
            [M_ETA, M_ETA + 0.06, M_ETA - 0.06],
            [M_PI0, M_PI0, M_PI0],
            "core=1 tails=2",
        ),
    ],
)
def test_core_tail_split_rejects_unbalanceable_populations(
    eta_masses, pi0_masses, message
):
    events = _events_with_candidate_masses(
        np.array(eta_masses),
        np.array(pi0_masses),
    )

    with pytest.raises(ValueError, match=message):
        reconstructed_events.split_candle_core_tails(events, 0.05, seed=1)
