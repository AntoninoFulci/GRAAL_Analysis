"""Stage 07 point identity, tree order and covariance alignment."""

from pathlib import Path

import numpy as np
import pytest

from graal_theory.native_sigma import load_native_sigma_root


class FakeObject:
    def __init__(self, value):
        self.value = value

    def member(self, name):
        assert name in ("fTitle", "fElements")
        return self.value

    def values(self):
        return self.value


class FakeTree:
    def __init__(self, columns):
        self.columns = columns
        self.num_entries = len(columns["sigma"])

    def arrays(self, names, library):
        assert library == "np"
        return {name: self.columns[name] for name in names}


class FakeRoot:
    def __init__(self, columns, covariance, *, mapping=None, provenance=None, bootstrap=None):
        self.objects = {
            "sigma_points": FakeTree(columns),
            "id_mapping": FakeObject(mapping or "sample 0 raw\nsample 1 raw_bdt\nestimator 0 likelihood\nestimator 1 ratio\npair 0 p_pi0\npair 1 p_eta\npair 2 eta_pi0"),
            "provenance": FakeObject(provenance or "sample=raw_bdt\nestimator=both\nprofile=uv\nbackground=uncorrected"),
            "binning/energy_edges": FakeObject(np.array([1.1, 1.2, 1.3])),
            "binning/p_pi0_mass_edges": FakeObject(np.array([1.05, 1.2, 1.35])),
            "binning/p_eta_mass_edges": FakeObject(np.array([1.48, 1.63, 1.78])),
            "binning/eta_pi0_mass_edges": FakeObject(np.array([.68, .83, .98])),
            "covariance/total": FakeObject(covariance),
        }
        if bootstrap is not None:
            self.objects["covariance/bootstrap_run"] = FakeObject(bootstrap)

    def __getitem__(self, name):
        return self.objects[name]

    def __contains__(self, name):
        return name in self.objects

    def keys(self, recursive=False, cycle=True):
        return [name + ";1" for name in self.objects if "/" not in name]

    def close(self):
        pass


@pytest.fixture
def root(monkeypatch, tmp_path):
    path = tmp_path / "points.root"
    path.write_bytes(b"test root identity")
    columns = {
        "sample_id": np.array([0, 1, 0, 1, 1, 1]),
        "estimator_id": np.array([1, 1, 0, 0, 1, 1]),
        "pair_id": np.array([0, 1, 2, 0, 0, 2]),
        "energy_bin": np.array([0, 1, 0, 1, 0, 1]),
        "mass_bin": np.array([0, 1, 0, 0, 0, 1]),
        "energy_low_gev": np.array([1.1, 1.2, 1.1, 1.2, 1.1, 1.2]),
        "energy_high_gev": np.array([1.2, 1.3, 1.2, 1.3, 1.2, 1.3]),
        "mass_low_gev": np.array([1.05, 1.63, .68, 1.05, 1.05, .83]),
        "mass_high_gev": np.array([1.2, 1.78, .83, 1.2, 1.2, .98]),
        "sigma": np.array([.9, .2, -.4, .8, -.1, .3]),
        "stat_low": np.full(6, .04),
        "stat_high": np.full(6, .06),
    }
    a = np.arange(36, dtype=float).reshape(6, 6)/100
    covariance = a @ a.T + np.eye(6)*.1
    fake = FakeRoot(columns, covariance)
    monkeypatch.setattr("uproot.open", lambda _: fake)
    return path, fake


def test_selected_rows_keep_tree_order_and_matching_covariance(root):
    path, fake = root
    data = load_native_sigma_root(path)
    assert data.keys == (("p_eta", 1, 1), ("p_pi0", 0, 0), ("eta_pi0", 1, 1))
    np.testing.assert_array_equal(data.tree_indices, [1, 4, 5])
    np.testing.assert_allclose(data.sigma, [.2, -.1, .3])
    np.testing.assert_allclose(data.covariance, fake.objects["covariance/total"].value[np.ix_([1, 4, 5], [1, 4, 5])])
    assert data.status == "pilot"
    assert len(data.source_sha256) == 64


@pytest.mark.parametrize("change", ["duplicate_mapping", "duplicate_key", "bad_profile", "bad_edge", "bad_shape", "nonsymmetric", "singular", "nonfinite"])
def test_invalid_root_contract_fails(root, change):
    path, fake = root
    if change == "duplicate_mapping":
        fake.objects["id_mapping"].value += "\npair 1 p_eta"
    elif change == "duplicate_key":
        fake.objects["sigma_points"].columns["pair_id"][5] = 0
        fake.objects["sigma_points"].columns["energy_bin"][5] = 0
        fake.objects["sigma_points"].columns["mass_bin"][5] = 0
    elif change == "bad_profile":
        fake.objects["provenance"].value = "profile=not_uv\nbackground=uncorrected"
    elif change == "bad_edge":
        fake.objects["sigma_points"].columns["mass_low_gev"][4] = 1.06
    elif change == "bad_shape":
        fake.objects["covariance/total"].value = np.eye(5)
    elif change == "nonsymmetric":
        fake.objects["covariance/total"].value[1, 4] += .1
    elif change == "singular":
        fake.objects["covariance/total"].value = np.zeros((6, 6))
    else:
        fake.objects["sigma_points"].columns["sigma"][4] = np.nan
    with pytest.raises(ValueError):
        load_native_sigma_root(path)


def test_final_requires_background_and_bootstrap(root):
    path, fake = root
    with pytest.raises(ValueError, match="final"):
        load_native_sigma_root(path, require_final=True)
    fake.objects["provenance"].value = "sample=raw_bdt\nestimator=both\nprofile=uv\nbackground=sideband-corrected"
    fake.objects["covariance/bootstrap_run"] = FakeObject(np.eye(6)*.01)
    data = load_native_sigma_root(path, require_final=True)
    assert data.status == "final_input"
    np.testing.assert_allclose(data.bootstrap_covariance, np.eye(3)*.01)
