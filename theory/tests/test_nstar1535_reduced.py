"""Strong reduced N*(1535) input and kernel checks."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import numpy as np
import pytest

from graal_theory.amplitudes.nstar1535_reduced import (
    CHANNELS,
    C_COEFFICIENTS,
    load_reduced_parameters,
    wt_kernel,
)


REFERENCE_DIR = Path(__file__).resolve().parents[1] / "references"
PARAM = REFERENCE_DIR / "nstar1535_reduced_parameters.json"
SOURCES = REFERENCE_DIR / "sources.json"


def test_reduced_inputs_and_channel_order():
    p = load_reduced_parameters(PARAM, SOURCES)
    assert CHANNELS == (
        "pi0_p", "pi_plus_n", "eta_p",
        "k_plus_sigma0", "k_plus_lambda", "k0_sigma_plus",
    )
    assert p.mu_gev == 1.2
    assert p.subtraction_constants == (2.0, 2.0, 0.2, -2.8, 1.6, -2.8)
    np.testing.assert_allclose(
        p.decay_constants_gev,
        (0.093, 0.093, 0.093 * 1.3, 0.093 * 1.22, 0.093 * 1.22, 0.093 * 1.22),
    )


def test_wt_charge_coefficients_and_symmetry():
    p = load_reduced_parameters(PARAM, SOURCES)
    v = wt_kernel(1.5, p)
    np.testing.assert_allclose(v, v.T, atol=1e-13)
    assert C_COEFFICIENTS[0, 1] == pytest.approx(np.sqrt(2))
    assert C_COEFFICIENTS[0, 2] == C_COEFFICIENTS[1, 2] == 0
    e = (
        1.5**2 + p.baryon_masses_gev[0] ** 2 - p.meson_masses_gev[0] ** 2
    ) / (2 * 1.5)
    ej = (
        1.5**2 + p.baryon_masses_gev[1] ** 2 - p.meson_masses_gev[1] ** 2
    ) / (2 * 1.5)
    expected = (
        -np.sqrt(2)
        * (3.0 - p.baryon_masses_gev[0] - p.baryon_masses_gev[1])
        / (4 * 0.093**2)
        * np.sqrt((p.baryon_masses_gev[0] + e) / (2 * p.baryon_masses_gev[0]))
        * np.sqrt((p.baryon_masses_gev[1] + ej) / (2 * p.baryon_masses_gev[1]))
    )
    assert v[0, 1] == pytest.approx(expected)


def test_reduced_inputs_reject_bad_mass_unit_and_value(tmp_path):
    raw = json.loads(PARAM.read_text(encoding="utf-8"))
    raw["neutron_mass"]["unit"] = "MeV"
    changed = tmp_path / "wrong-unit.json"
    changed.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="neutron_mass"):
        load_reduced_parameters(changed, SOURCES)
    raw["neutron_mass"]["unit"] = "GeV"
    raw["neutron_mass"]["value"] = -1
    changed.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="neutron_mass"):
        load_reduced_parameters(changed, SOURCES)


def test_reduced_inputs_reject_nonfinite_unknown_source_and_missing_key(tmp_path):
    original = json.loads(PARAM.read_text(encoding="utf-8"))
    changed = tmp_path / "bad.json"
    for field, replacement in (("value", float("nan")), ("source_key", "not_a_source")):
        raw = copy.deepcopy(original)
        raw["a_piN"][field] = replacement
        changed.write_text(json.dumps(raw), encoding="utf-8")
        with pytest.raises(ValueError, match="a_piN"):
            load_reduced_parameters(changed, SOURCES)
    raw = copy.deepcopy(original)
    del raw["a_piN"]
    changed.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="names"):
        load_reduced_parameters(changed, SOURCES)
