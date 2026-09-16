"""ROOT-adapter contracts exercised with small in-memory test doubles."""

from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from graal_common.physics.pairing import Pairing
from reconstruction.runtime import reco_core
from reconstruction.core import reco_physics as rp
from reconstruction.core.event_logic import ReconstructedEvent


class _LorentzVector:
    def __init__(self, px=0.0, py=0.0, pz=0.0, energy=0.0):
        self.SetPxPyPzE(px, py, pz, energy)

    def SetPxPyPzE(self, px, py, pz, energy):
        self.values = tuple(float(value) for value in (px, py, pz, energy))

    def Px(self):
        return self.values[0]

    def Py(self):
        return self.values[1]

    def Pz(self):
        return self.values[2]

    def E(self):
        return self.values[3]


class _VectorList(list):
    def size(self):
        return len(self)


class _Chain:
    def __init__(self, events):
        self.events = events

    def GetEntries(self):
        return len(self.events)

    def GetEntry(self, index):
        event = self.events[index]
        self.gammas = _VectorList(_LorentzVector(*v) for v in event["photons"])
        self.protons = _VectorList([_LorentzVector(*event["proton"])])
        self.neutrons = _VectorList([_LorentzVector(*event["neutron"])])
        self.beam = _LorentzVector(*event["beam"])
        self.RunNumber = event["run_number"]
        self.Polarization = event["polarization"]
        self.Xstrip = event["strip"]


class _Tree:
    def __init__(self, name, _title):
        self.name = name
        self.branches = {}
        self.entries = []

    def Branch(self, name, first, second):
        self.branches[name] = second if isinstance(first, str) else first

    def Fill(self):
        entry = {}
        for name, value in self.branches.items():
            if isinstance(value, _LorentzVector):
                entry[name] = value.values
            else:
                entry[name] = value[0]
        self.entries.append(entry)

    def Write(self, *_args):
        return None

    def GetEntries(self):
        return len(self.entries)


class _File:
    def __init__(self, *_args):
        pass

    def cd(self):
        return None

    def Close(self):
        return None


class _Gate:
    def __init__(self, accepted):
        self.accepted = accepted

    def accepts_many(self, photons, protons, beams):
        assert photons.shape == (1, 4, 4)
        assert protons.shape == (1, 4)
        assert beams.shape == (1, 4)
        return np.array([self.accepted])


def _input_event():
    return {
        "photons": np.array(
            [
                [0.10, 0.00, 0.20, 0.30],
                [-0.10, 0.00, 0.20, 0.30],
                [0.00, 0.05, 0.10, 0.15],
                [0.00, -0.05, 0.10, 0.15],
            ]
        ),
        "proton": np.array([0.0, 0.0, 0.0, rp.M_PROTON]),
        "neutron": np.zeros(4),
        "beam": np.array([0.0, 0.0, 1.5, 1.5]),
        "run_number": 4242,
        "polarization": 2,
        "strip": 73.0,
    }


@pytest.fixture
def root_adapter(monkeypatch, tmp_path):
    trees = []

    def make_tree(name, title):
        tree = _Tree(name, title)
        trees.append(tree)
        return tree

    root = SimpleNamespace(
        TFile=_File,
        TTree=make_tree,
        TLorentzVector=_LorentzVector,
        TObject=SimpleNamespace(kOverwrite=1),
    )
    monkeypatch.setattr(reco_core, "ROOT", root)
    monkeypatch.setattr(
        reco_core,
        "_build_chain",
        lambda _input_dir, _input_tree: _Chain([_input_event()]),
    )
    config = reco_core.RecoConfig(
        input_dir=tmp_path,
        output_file=tmp_path / "result.root",
        input_tree="h80",
        output_tree="reco",
        do_fit=False,
        missing_mass_window=None,
    )
    return config, trees


def test_root_adapter_routes_accepted_event_through_pure_core(
    root_adapter,
    monkeypatch,
):
    config, trees = root_adapter
    config.do_fit = True
    photons = _input_event()["photons"][[2, 3, 0, 1]]
    fitted_photons = photons + np.array([0.01, 0.02, 0.03, 0.04])
    observed = {}
    reconstructed = ReconstructedEvent(
        pairing=Pairing(heavy=(2, 3), light=(0, 1)),
        photons=photons,
        proton=np.array([0.1, 0.2, 0.3, 1.1]),
        neutron=np.array([0.4, 0.5, 0.6, 1.2]),
        beam=np.array([0.0, 0.0, 1.4, 1.4]),
        heavy=np.array([0.0, 0.0, 0.2, 0.3]),
        light=np.array([0.0, 0.0, 0.4, 0.6]),
        missing=np.array([0.0, 0.0, 0.8, 1.438272]),
        heavy_mass=0.22,
        light_mass=0.44,
        chi2=2.5,
        run_number=4242,
        polarization=2,
        strip=73.0,
        fitted_photons=fitted_photons,
        fitted_proton=np.array([0.2, 0.3, 0.4, 1.2]),
        fitted_heavy=fitted_photons[0] + fitted_photons[1],
        fitted_light=fitted_photons[2] + fitted_photons[3],
        fit_chi2=6.0,
        fit_ndf=6,
        fit_converged=True,
    )

    def decide(event, channel, cfg, *, pairing_fn, fit_fn):
        observed.update(
            event=event,
            channel=channel,
            config=cfg,
            pairing_fn=pairing_fn,
            fit_fn=fit_fn,
        )
        return reconstructed

    monkeypatch.setattr(reco_core, "reconstruct_event", decide)

    assert reco_core.run_reconstruction(config, rp.ETA_PI0) == 1

    assert observed["channel"] is rp.ETA_PI0
    assert observed["config"] is config
    assert observed["pairing_fn"] is reco_core.pr.best_pairing
    assert observed["fit_fn"] is reco_core.fit_event
    assert observed["event"].run_number == 4242
    assert observed["event"].polarization == 2
    assert observed["event"].strip == 73.0
    entry = trees[0].entries[0]
    assert entry["chi2"] == pytest.approx(2.5)
    assert entry["eta_mass"] == pytest.approx(0.22)
    assert entry["pi0_mass"] == pytest.approx(0.44)
    assert entry["RunNumber"] == 4242
    assert entry["Polarization"] == 2
    assert entry["Xstrip"] == pytest.approx(73.0)
    assert entry["eta_gamma1"] == tuple(photons[0])
    assert entry["eta_gamma2"] == tuple(photons[1])
    assert entry["pi0_gamma1"] == tuple(photons[2])
    assert entry["pi0_gamma2"] == tuple(photons[3])
    assert entry["eta"] == tuple(reconstructed.heavy)
    assert entry["pi0"] == tuple(reconstructed.light)
    assert entry["missing"] == tuple(reconstructed.missing)
    assert entry["eta_fit_gamma1"] == tuple(fitted_photons[0])
    assert entry["eta_fit_gamma2"] == tuple(fitted_photons[1])
    assert entry["pi0_fit_gamma1"] == tuple(fitted_photons[2])
    assert entry["pi0_fit_gamma2"] == tuple(fitted_photons[3])
    assert entry["eta_fit"] == tuple(reconstructed.fitted_heavy)
    assert entry["pi0_fit"] == tuple(reconstructed.fitted_light)
    assert entry["proton_fit"] == tuple(reconstructed.fitted_proton)
    assert entry["fit_chi2"] == pytest.approx(6.0)
    assert entry["fit_ndf"] == 6
    assert entry["fit_converged"] == 1


def test_accept_all_gate_matches_ungated_output(root_adapter, monkeypatch):
    config, trees = root_adapter
    monkeypatch.setattr(
        reco_core.pr,
        "best_pairing",
        lambda _photons, _hypothesis: (
            Pairing(heavy=(0, 1), light=(2, 3)),
            0.0,
        ),
    )

    assert reco_core.run_reconstruction(config, rp.ETA_PI0) == 1
    ungated_entry = trees[-1].entries[0]

    config.output_file = Path(config.output_file).with_name("gated.root")
    assert reco_core.run_reconstruction(config, rp.ETA_PI0, gate=_Gate(True)) == 1
    gated_entry = trees[-1].entries[0]

    assert gated_entry == ungated_entry


def test_reject_all_gate_writes_nothing_without_pairing_or_fit(
    root_adapter,
    monkeypatch,
):
    config, trees = root_adapter

    def forbidden(*_args, **_kwargs):
        raise AssertionError("pairing or fit ran after gate rejection")

    monkeypatch.setattr(reco_core.pr, "best_pairing", forbidden)
    monkeypatch.setattr(reco_core, "fit_event", forbidden)

    assert reco_core.run_reconstruction(config, rp.ETA_PI0, gate=_Gate(False)) == 0
    assert trees[-1].entries == []
