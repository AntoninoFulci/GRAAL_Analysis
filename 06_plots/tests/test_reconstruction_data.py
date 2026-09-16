from types import SimpleNamespace

import numpy as np
import pytest

from plots.core import reconstruction_data


class _Vector:
    def __init__(self, px, py, pz, energy):
        self.values = [px, py, pz, energy]

    def Px(self):
        return self.values[0]

    def Py(self):
        return self.values[1]

    def Pz(self):
        return self.values[2]

    def E(self):
        return self.values[3]

    def M(self):
        px, py, pz, energy = self.values
        return np.sqrt(max(energy**2 - px**2 - py**2 - pz**2, 0.0))


class _Branch:
    def __init__(self, name):
        self._name = name

    def GetName(self):
        return self._name


class _Tree:
    def __init__(self, events, branches=()):
        self.events = events
        self._branches = [_Branch(name) for name in branches]

    def __iter__(self):
        return iter(self.events)

    def GetListOfBranches(self):
        return self._branches


def _event(*, fitted=False):
    values = {
        "eta": _Vector(0.0, 0.0, 0.0, 0.55),
        "pi0": _Vector(0.0, 0.0, 0.0, 0.14),
        "proton": _Vector(0.0, 0.0, 0.0, 0.94),
        "missing": _Vector(0.0, 0.0, 0.0, 0.95),
        "beam": _Vector(0.0, 0.0, 1.5, 1.5),
        "target": _Vector(0.0, 0.0, 0.0, 0.94),
        "eta_mass": 0.54,
        "pi0_mass": 0.13,
    }
    if fitted:
        values.update(
            eta_fit=_Vector(0.0, 0.0, 0.0, 0.56),
            pi0_fit=_Vector(0.0, 0.0, 0.0, 0.15),
        )
    return SimpleNamespace(**values)


def test_collect_raw_tree_returns_explicit_arrays_detached_from_tree():
    event = _event()
    tree = _Tree([event])

    arrays = reconstruction_data.collect(tree)
    event.eta.values[3] = 99.0

    assert isinstance(arrays, reconstruction_data.ReconstructionArrays)
    assert arrays.has_fit is False
    assert arrays.mep_meas == pytest.approx([1.49])
    assert arrays.mpp_meas == pytest.approx([1.08])
    assert arrays.mep_miss == pytest.approx([1.50])
    assert arrays.mpp_miss == pytest.approx([1.09])
    assert arrays.eta_mass == pytest.approx([0.54])
    assert arrays.pi0_mass == pytest.approx([0.13])
    assert arrays.eta_mass_raw == pytest.approx([0.54])
    assert arrays.pi0_mass_raw == pytest.approx([0.13])
    assert arrays.over_limit.tolist() == [False]
    assert arrays.eta_over_beam.tolist() == [False]


def test_collect_fit_tree_uses_fitted_vectors_and_preserves_raw_masses():
    tree = _Tree([_event(fitted=True)], branches=("fit_chi2",))

    arrays = reconstruction_data.collect(tree)

    assert arrays.has_fit is True
    assert arrays.mep_meas == pytest.approx([1.50])
    assert arrays.mpp_meas == pytest.approx([1.09])
    assert arrays.eta_mass == pytest.approx([0.56])
    assert arrays.pi0_mass == pytest.approx([0.15])
    assert arrays.eta_mass_raw == pytest.approx([0.54])
    assert arrays.pi0_mass_raw == pytest.approx([0.13])


def test_collect_legacy_preserves_current_dictionary_shape():
    tree = _Tree([_event()])

    legacy = reconstruction_data.collect_legacy(tree)

    assert set(legacy) == {
        "mep_meas",
        "mpp_meas",
        "mep_miss",
        "mpp_miss",
        "eta_mass",
        "pi0_mass",
        "eta_mass_raw",
        "pi0_mass_raw",
        "over_limit",
        "eta_over_beam",
        "has_fit",
    }
    assert legacy["eta_mass"] == pytest.approx([0.54])
    assert legacy["has_fit"] is False


def test_open_tree_preserves_validation_and_return_contract(
    monkeypatch, tmp_path, capsys
):
    path = tmp_path / "reco.root"
    path.touch()
    tree = SimpleNamespace(GetEntries=lambda: 7)
    root_file = SimpleNamespace(
        IsZombie=lambda: False,
        Get=lambda name: tree if name == "events" else None,
    )
    monkeypatch.setattr(
        reconstruction_data.ROOT,
        "TFile",
        SimpleNamespace(Open=lambda filename: root_file),
        raising=False,
    )

    result = reconstruction_data.open_tree(path, "events")

    assert result == (root_file, tree)
    assert capsys.readouterr().out == "  reco.root: 7 eventi\n"


def test_open_tree_rejects_missing_file(tmp_path):
    path = tmp_path / "missing.root"

    with pytest.raises(
        FileNotFoundError, match=f"file ricostruito non trovato: {path}"
    ):
        reconstruction_data.open_tree(path, "events")
