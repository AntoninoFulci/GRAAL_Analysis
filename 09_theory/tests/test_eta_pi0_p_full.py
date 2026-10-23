"""Composition contracts for the seven coherent production families."""

from dataclasses import FrozenInstanceError, fields, replace
from importlib import import_module
import json
from pathlib import Path
from shutil import copy2
from types import MappingProxyType

import numpy as np
import pytest

from graal_theory.amplitudes.delta1700 import Delta1700Parameters, tree_amplitude
from graal_theory.amplitudes.nstar1535_final_fit import load_final_fit_parameters
from graal_theory.amplitudes.nstar1535_full import reconstructed_full_tmatrix
from graal_theory.amplitudes.nstar1535_grid import build_strong_t_grid
from graal_theory.amplitudes.nstar1535_reduced import load_reduced_parameters, reduced_tmatrix
from graal_theory.amplitudes.nstar1535_vmd import load_vector_masses
from graal_theory.amplitudes.production_loops import QuadratureSettings, load_production_parameters
from graal_theory.constants import GEV2_TO_MICROBARN
from graal_theory.models.eta_pi0_p import EtaPi0PModel, load_central_parameters
from graal_theory.observables import predict_energy
from graal_theory.phase_space import SobolConfig, sample_three_body


REFERENCES = Path(__file__).resolve().parents[1] / "references"
SOURCES = REFERENCES / "sources.json"
EX, EY = np.array([1., 0., 0.]), np.array([0., 1., 0.])
FAMILIES = (
    "chiral_contact", "external_pi0", "internal_pi0", "explicit_resonances",
    "eta_delta_rescattering", "k_sigma_star_rescattering", "eq43_tree",
)
FUNCTIONS = (
    "chiral_contact_amplitude", "external_pi0_amplitude", "internal_pi0_amplitude",
    "explicit_resonance_amplitude", "eta_delta_rescattering_amplitude",
    "k_sigma_star_rescattering_amplitude", "tree_amplitude",
)


@pytest.fixture(scope="module")
def full():
    try:
        return import_module("graal_theory.models.eta_pi0_p_full")
    except ModuleNotFoundError as exc:
        pytest.fail(f"Task 6 full-model implementation is missing: {exc}")


@pytest.fixture(scope="module")
def model(full):
    return full.EtaPi0PFullModel.from_files(REFERENCES)


@pytest.fixture(scope="module")
def sample(model):
    generated = sample_three_body(1.82, model.masses, SobolConfig(4))
    indices = [7, 13]
    return replace(generated, initial=generated.initial[indices],
                   momenta=generated.momenta[indices], weights_gev2=generated.weights_gev2[indices],
                   s12_gev2=generated.s12_gev2[indices])


def _patch_families(monkeypatch, full, values):
    calls = []
    for family, function in zip(FAMILIES, FUNCTIONS):
        def fake(sample, epsilon, *parameters, name=family):
            calls.append((name, sample, epsilon, parameters))
            value = values[name]
            return value(sample, epsilon) if callable(value) else value
        monkeypatch.setattr(full, function, fake)
    return calls


def _cancelling_matrices(sample):
    # The first two families cancel identically, including their phases.
    large = np.array([[10.+3j, -4.+2j], [1.-7j, 5.+6j]])
    small = np.array([[1.+2j, 0.], [0., -2.+1j]])
    values = (large, -large, small, 2*small, -small, 1j*small, -1j*small)
    return {key: np.broadcast_to(value, (len(sample.momenta), 2, 2)).copy()
            for key, value in zip(FAMILIES, values)}


def test_grid_bound_model_matches_direct_event_and_rejects_mismatch(full, model, sample):
    grid = build_strong_t_grid(model.parameters.strong, model.parameters.vector_masses)
    gridded = full.EtaPi0PFullModel(model.parameters, strong_grid=grid)
    one = replace(sample, initial=sample.initial[:1], momenta=sample.momenta[:1],
                  weights_gev2=sample.weights_gev2[:1], s12_gev2=sample.s12_gev2[:1])
    for epsilon in (EX, EY):
        direct = model.family_amplitudes(one, epsilon)
        fast = gridded.family_amplitudes(one, epsilon)
        for family in FAMILIES:
            np.testing.assert_allclose(fast[family], direct[family], rtol=0.003, atol=1e-8)
        weight_direct = model.polarized_matrix_element_squared(one, epsilon)
        weight_fast = gridded.polarized_matrix_element_squared(one, epsilon)
        np.testing.assert_allclose(weight_fast, weight_direct, rtol=0.0025, atol=1e-14)
    wrong = replace(model.parameters, vector_masses=replace(
        model.parameters.vector_masses, rho_gev=model.parameters.vector_masses.rho_gev+0.001))
    with pytest.raises(ValueError, match="grid.*match"):
        full.EtaPi0PFullModel(wrong, strong_grid=grid)


def test_full_amplitude_obeys_global_azimuth_rotation(full, model, sample):
    one = replace(sample, initial=sample.initial[:1], momenta=sample.momenta[:1],
                  weights_gev2=sample.weights_gev2[:1], s12_gev2=sample.s12_gev2[:1])
    p = model.parameters
    fast = replace(model, parameters=replace(p, production=replace(p.production,
        quadrature=QuadratureSettings(q_order=32, angle_order=32))))
    h_matrix = fast.amplitude(one, EX)[0]
    v_matrix = fast.amplitude(one, EY)[0]
    h = np.sum(abs(h_matrix)**2)/2
    v = np.sum(abs(v_matrix)**2)/2
    cross = np.real(np.vdot(h_matrix, v_matrix))/2
    beta = .7
    rotation = np.array([[np.cos(beta), -np.sin(beta), 0.],
                         [np.sin(beta), np.cos(beta), 0.], [0., 0., 1.]])
    rotated_momenta = one.momenta.copy()
    rotated_momenta[:, :, 1:] = np.einsum("ij,nkj->nki", rotation,
                                         one.momenta[:, :, 1:])
    rotated = replace(one, momenta=rotated_momenta)
    expected_h = np.cos(beta)**2*h+np.sin(beta)**2*v-2*np.sin(beta)*np.cos(beta)*cross
    expected_v = np.sin(beta)**2*h+np.cos(beta)**2*v+2*np.sin(beta)*np.cos(beta)*cross
    assert fast.polarized_matrix_element_squared(rotated, EX)[0] == pytest.approx(expected_h, rel=1e-10)
    assert fast.polarized_matrix_element_squared(rotated, EY)[0] == pytest.approx(expected_v, rel=1e-10)


def test_from_files_composes_independently_sourced_frozen_records():
    try:
        full = import_module("graal_theory.models.eta_pi0_p_full")
    except ModuleNotFoundError:
        pytest.fail("Task 6 must construct a sourced seven-family full model")
    model = full.EtaPi0PFullModel.from_files(REFERENCES)
    tree = Delta1700Parameters.from_parameters(load_central_parameters(
        REFERENCES / "central_parameters.json", SOURCES))
    reduced = load_reduced_parameters(REFERENCES / "nstar1535_reduced_parameters.json", SOURCES)
    final = load_final_fit_parameters(reduced, REFERENCES / "nstar1535_final_subtractions.json", SOURCES)
    assert model.parameters.tree == tree
    assert model.parameters.strong == final
    assert model.parameters.strong.subtraction_constants != reduced.subtraction_constants
    assert model.parameters.vector_masses == load_vector_masses(REFERENCES / "nstar1535_vmd_masses.json", SOURCES)
    assert model.parameters.production == load_production_parameters(REFERENCES / "eta_pi0_p_full_parameters.json", SOURCES)
    assert model.masses == (tree.eta_mass_gev, tree.pi0_mass_gev, tree.proton_mass_gev)
    assert model.parameters.proton_mass_gev == tree.proton_mass_gev
    with pytest.raises(FrozenInstanceError):
        model.parameters.tree = tree
    with pytest.raises(FrozenInstanceError):
        model.parameters.proton_mass_gev = 1.
    with pytest.raises(FrozenInstanceError):
        model.parameters = model.parameters
    with pytest.raises(TypeError):
        model.parameters.tree.provenance["proton_mass"] = None

    original = dict(tree.provenance)
    composed = replace(model.parameters, tree=replace(tree, provenance=original))
    original.clear()
    assert composed.tree.provenance == tree.provenance
    assert {field.name for field in fields(full.FullModelParameters)} == {
        "tree", "strong", "vector_masses", "production",
    }


def test_physical_sum_preserves_destructive_interference_and_calls_seven_once(full, model, sample, monkeypatch):
    values = _cancelling_matrices(sample)
    calls = _patch_families(monkeypatch, full, values)
    expected = np.broadcast_to(np.array([[2.+4j, 0.], [0., -4.+2j]]), (2, 2, 2))
    np.testing.assert_array_equal(model.amplitude(sample, EX), expected)
    assert [call[0] for call in calls] == list(FAMILIES)
    assert all(call[1] is sample for call in calls)
    calls.clear()
    np.testing.assert_allclose(model.polarized_matrix_element_squared(sample, EX), [20., 20.])
    assert [call[0] for call in calls] == list(FAMILIES)
    incoherent = sum(np.sum(np.abs(value)**2, axis=(1, 2))/2 for value in values.values())
    assert not np.allclose(incoherent, [20., 20.])


def test_every_rescattering_family_receives_same_final_full_strong_closure(full, model, sample, monkeypatch):
    values = _cancelling_matrices(sample)
    calls = _patch_families(monkeypatch, full, values)
    model.amplitude(sample, EX)
    p = model.parameters
    expected = reconstructed_full_tmatrix(1.55, p.strong, p.vector_masses)
    assert not np.allclose(expected, reduced_tmatrix(1.55, p.strong))
    closures = []
    for index, (_, _, _, args) in enumerate(calls[:-1]):
        assert args[0] is p.production
        if index < 3:
            assert args[1] is p.strong
        else:
            assert args[1] is p.tree
            assert args[2] is p.strong
        closures.append(args[-1])
        np.testing.assert_allclose(args[-1](1.55), expected, rtol=1e-13)
    assert all(closure is closures[0] for closure in closures)
    assert calls[-1][3] == (p.tree,)


def test_diagnostic_mapping_and_complex_arrays_are_read_only(full, model, sample, monkeypatch):
    values = _cancelling_matrices(sample)
    _patch_families(monkeypatch, full, values)
    result = model.family_amplitudes(sample, EX)
    assert isinstance(result, MappingProxyType)
    assert tuple(result) == FAMILIES
    with pytest.raises(TypeError):
        result["new"] = values[FAMILIES[0]]
    for key, value in result.items():
        assert value.shape == (2, 2, 2)
        assert value.dtype == np.complex128
        assert np.all(np.isfinite(value))
        assert not value.flags.writeable
        with pytest.raises(ValueError):
            value[0, 0, 0] = 0.
        # The wrapper must not freeze or retain mutable output owned by a family.
        assert values[key].flags.writeable
        values[key][0, 0, 0] += 1
        assert values[key][0, 0, 0] != value[0, 0, 0]


def test_selected_diagnostics_compute_only_whole_requested_families(full, model, sample, monkeypatch):
    values = _cancelling_matrices(sample)
    calls = _patch_families(monkeypatch, full, values)
    selected = ("eq43_tree", "external_pi0")
    np.testing.assert_array_equal(model.selected_amplitude(sample, EX, selected),
                                  values[selected[0]]+values[selected[1]])
    assert [call[0] for call in calls] == list(selected)
    calls.clear()
    expected = np.sum(np.abs(values[selected[0]]+values[selected[1]])**2, axis=(1, 2))/2
    np.testing.assert_allclose(model.selected_matrix_element_squared(sample, selected), expected)
    assert [call[0] for call in calls] == list(selected)*2


@pytest.mark.parametrize("method,args", [
    ("amplitude", (EX,)), ("polarized_matrix_element_squared", (EX,)), ("matrix_element_squared", ()),
])
def test_physical_methods_accept_no_family_selection(model, sample, method, args):
    with pytest.raises(TypeError):
        getattr(model, method)(sample, *args, families=("eq43_tree",))


@pytest.mark.parametrize("selection", [
    (), ("eq43_tree", "eq43_tree"), ("unknown",), ("delta_kr_pole",),
    ("sigma_star_kr",), ("eta_kr",), ("internal_pi0_pole",),
    "eq43_tree", ["eq43_tree"], (1,), (True,), (["eq43_tree"],), None,
])
def test_invalid_diagnostic_selection_is_rejected_before_evaluation(full, model, sample, monkeypatch, selection):
    calls = _patch_families(monkeypatch, full, _cancelling_matrices(sample))
    for method, args in ((model.selected_amplitude, (sample, EX, selection)),
                         (model.selected_matrix_element_squared, (sample, selection))):
        with pytest.raises(ValueError, match="famil"):
            method(*args)
    assert calls == []


def test_photon_average_and_rotated_basis_are_coherent(full, model, sample, monkeypatch):
    a = np.array([[1.+2j, 3.], [2j, -1.]])
    b = np.array([[2., -3j], [1.+1j, 4.]])
    values = {family: (lambda sample, epsilon, scale=index+1:
                        np.broadcast_to(scale*(epsilon[0]*a+epsilon[1]*b), (len(sample.momenta), 2, 2)).copy())
              for index, family in enumerate(FAMILIES)}
    calls = _patch_families(monkeypatch, full, values)
    x = model.polarized_matrix_element_squared(sample, EX)
    y = model.polarized_matrix_element_squared(sample, EY)
    assert np.all(x >= 0) and np.all(y >= 0)
    calls.clear()
    np.testing.assert_allclose(model.matrix_element_squared(sample), (x+y)/2)
    assert [call[0] for call in calls] == list(FAMILIES)*2
    angle = .37
    rotated = (np.cos(angle)*EX+np.sin(angle)*EY, -np.sin(angle)*EX+np.cos(angle)*EY)
    np.testing.assert_allclose(model.matrix_element_squared(sample, polarizations=rotated), (x+y)/2, rtol=1e-12)
    np.testing.assert_allclose(model.selected_matrix_element_squared(sample, FAMILIES, polarizations=rotated), (x+y)/2, rtol=1e-12)


@pytest.mark.parametrize("epsilon", [
    [0., 0., 1.], [0., 0., 0.], [2., 0., 0.], [1., 0.],
    [1., 0., 1e-10], [1.+0j, 0., 0.], [True, False, False],
    [np.nan, 0., 0.], [np.inf, 0., 0.], ["1", "0", "0"],
    [1.000001, 0., 0.],
    [True, 0., 0.],
])
def test_invalid_polarization_is_rejected_before_families(full, model, sample, monkeypatch, epsilon):
    calls = _patch_families(monkeypatch, full, _cancelling_matrices(sample))
    for method, args in ((model.family_amplitudes, (sample, epsilon)),
                         (model.amplitude, (sample, epsilon)),
                         (model.polarized_matrix_element_squared, (sample, epsilon)),
                         (model.selected_amplitude, (sample, epsilon, ("eq43_tree",)))):
        with pytest.raises(ValueError, match="polarization"):
            method(*args)
    assert calls == []


@pytest.mark.parametrize("basis", [
    (EX,), (EX, EX), (EX, np.array([0., 0., 1.])),
    ([True, False, False], [False, True, False]),
    (EX.astype(complex), EY), (EX, [0., np.nan, 0.]),
    (EX, 1.000001*EY), ([1., 0.], [0., 1.]),
    (EX, [1e-7, np.sqrt(1-1e-14), 0.]), 3,
])
def test_invalid_basis_is_rejected_by_physical_and_diagnostic_weights(full, model, sample, monkeypatch, basis):
    calls = _patch_families(monkeypatch, full, _cancelling_matrices(sample))
    with pytest.raises(ValueError, match="polarization"):
        model.matrix_element_squared(sample, polarizations=basis)
    with pytest.raises(ValueError, match="polarization"):
        model.selected_matrix_element_squared(sample, ("eq43_tree",), polarizations=basis)
    assert calls == []


@pytest.mark.parametrize("bad", ["mass_order", "particle_order", "cm", "mixed_energy", "off_shell",
                                 "nonfinite", "complex", "bool", "shape", "empty", "weights", "s12"])
def test_invalid_samples_are_rejected_before_family_evaluation(full, model, sample, monkeypatch, bad):
    calls = _patch_families(monkeypatch, full, _cancelling_matrices(sample))
    if bad == "mass_order":
        broken = replace(sample, masses=(sample.masses[1], sample.masses[0], sample.masses[2]))
    elif bad == "particle_order":
        broken = replace(sample, momenta=sample.momenta[:, [1, 0, 2]])
    elif bad == "cm":
        initial = sample.initial.copy(); initial[:, 1] = .01
        broken = replace(sample, initial=initial)
    elif bad == "mixed_energy":
        other = sample_three_body(1.81, sample.masses, SobolConfig(4))
        initial, momenta = sample.initial.copy(), sample.momenta.copy()
        initial[1], momenta[1] = other.initial[7], other.momenta[7]
        broken = replace(sample, initial=initial, momenta=momenta)
    elif bad == "off_shell":
        momenta = sample.momenta.copy(); momenta[0, 0, 0] += .01
        broken = replace(sample, momenta=momenta)
    elif bad == "nonfinite":
        momenta = sample.momenta.copy(); momenta[0, 0, 0] = np.nan
        broken = replace(sample, momenta=momenta)
    elif bad == "complex":
        broken = replace(sample, initial=sample.initial.astype(complex))
    elif bad == "bool":
        broken = replace(sample, momenta=np.ones((2, 3, 4), dtype=bool))
    elif bad == "shape":
        broken = replace(sample, initial=sample.initial[0])
    elif bad == "empty":
        broken = replace(sample, initial=sample.initial[:0], momenta=sample.momenta[:0])
    elif bad == "weights":
        broken = replace(sample, weights_gev2=np.array([np.nan, 1.]))
    else:
        broken = replace(sample, s12_gev2=sample.s12_gev2.astype(complex))
    with pytest.raises(ValueError):
        model.amplitude(broken, EX)
    with pytest.raises(ValueError):
        model.selected_amplitude(broken, EX, ("eq43_tree",))
    assert calls == []


@pytest.mark.parametrize("output", [
    np.zeros((2, 2), dtype=complex), np.zeros((2, 2, 2)),
    np.zeros((2, 2, 2), dtype=np.complex64), np.ones((2, 2, 2), dtype=bool),
    np.full((2, 2, 2), np.nan+1j), np.full((2, 2, 2), np.inf+1j),
    np.full((2, 2, 2), "1"),
])
def test_malformed_family_outputs_name_the_family(full, model, sample, monkeypatch, output):
    values = _cancelling_matrices(sample)
    values["chiral_contact"] = output
    _patch_families(monkeypatch, full, values)
    with pytest.raises(ValueError, match="chiral_contact"):
        model.family_amplitudes(sample, EX)
    with pytest.raises(ValueError, match="chiral_contact"):
        model.selected_amplitude(sample, EX, ("chiral_contact",))


@pytest.mark.parametrize("block", ["tree", "strong", "vector_masses", "production"])
def test_composition_rejects_wrong_parameter_record_types(model, block):
    with pytest.raises(ValueError, match=block):
        replace(model.parameters, **{block: object()})


@pytest.mark.parametrize("block,field,value", [
    ("tree", "proton_mass_gev", True), ("tree", "g1_prime", 1.+0j),
    ("tree", "eta_mass_gev", np.nan), ("tree", "delta_width_gev", -.01),
    ("tree", "g_eta_delta", True), ("tree", "g_eta_delta", complex(1., np.inf)),
    ("tree", "width_parameters", object()),
    ("production", "electric_charge", True), ("production", "axial_d", 1.+0j),
    ("production", "sigma_star_mass_gev", 0.), ("production", "sigma_star_width_gev", -1.),
    ("production", "first_loop_cutoff_gev", np.inf),
    ("production", "g_k_sigma_star", "3.3+0.7j"),
    ("production", "g_k_sigma_star", np.nan), ("production", "quadrature", object()),
])
def test_composition_validates_replacement_records(model, block, field, value):
    replacement = replace(getattr(model.parameters, block), **{field: value})
    with pytest.raises(ValueError, match=field):
        replace(model.parameters, **{block: replacement})


def test_composition_validates_nested_width_and_shared_masses(model):
    width = replace(model.parameters.tree.width_parameters, f_rho=True)
    with pytest.raises(ValueError, match="f_rho"):
        replace(model.parameters, tree=replace(model.parameters.tree, width_parameters=width))
    with pytest.raises(ValueError, match="mass"):
        replace(model.parameters, tree=replace(model.parameters.tree, eta_mass_gev=.55))


def test_composition_rejects_real_scalars_outside_float64_range(model):
    tree = replace(model.parameters.tree, g1_prime=10**400)
    with pytest.raises(ValueError, match="g1_prime"):
        replace(model.parameters, tree=tree)


@pytest.mark.parametrize("component,value", [("real", True), ("imag", False), ("real", "1.7")])
def test_from_files_rejects_complex_components_before_legacy_loader_casts(full, tmp_path, component, value):
    for source in REFERENCES.glob("*.json"):
        copy2(source, tmp_path / source.name)
    path = tmp_path / "central_parameters.json"
    record = json.loads(path.read_text())
    record["g_eta_delta"]["value"][component] = value
    path.write_text(json.dumps(record))
    with pytest.raises(ValueError, match="g_eta_delta"):
        full.EtaPi0PFullModel.from_files(tmp_path)


@pytest.mark.parametrize("field", ["tree", "strong", "vector_masses", "production"])
def test_model_accepts_valid_replaced_couplings_and_rejects_noncomposite_parameters(full, model, field):
    with pytest.raises(ValueError, match="parameters"):
        full.EtaPi0PFullModel(getattr(model.parameters, field))
    production = replace(model.parameters.production, axial_d=.77, g_k_sigma_star=0j)
    composed = replace(model.parameters, production=production)
    assert full.EtaPi0PFullModel(composed).parameters.production == production


@pytest.mark.parametrize("method", ["amplitude", "selected_amplitude", "polarized_matrix_element_squared",
                                     "matrix_element_squared", "selected_matrix_element_squared"])
def test_nonfinite_coherent_sum_or_spin_weight_is_never_exposed(full, model, sample, monkeypatch, method):
    # Every family is finite; their sum or squared norm can still overflow.
    magnitude = 1e308 if "amplitude" in method else 1e200
    values = {name: np.full((2, 2, 2), magnitude+0j, dtype=np.complex128) for name in FAMILIES}
    _patch_families(monkeypatch, full, values)
    if method == "selected_matrix_element_squared":
        args = (sample, FAMILIES)
    elif method == "selected_amplitude":
        args = (sample, EX, FAMILIES)
    elif method == "matrix_element_squared":
        args = (sample,)
    else:
        args = (sample, EX)
    with pytest.raises(ValueError, match="nonfinite|overflow"):
        getattr(model, method)(*args)


def test_real_families_and_tree_preservation(full, model, sample):
    families = model.family_amplitudes(sample, EX)
    assert tuple(families) == FAMILIES
    for matrix in families.values():
        assert matrix.shape == (2, 2, 2) and matrix.dtype == np.complex128
        assert np.all(np.isfinite(matrix)) and not matrix.flags.writeable
    np.testing.assert_allclose(families["eq43_tree"], tree_amplitude(sample, EX, model.parameters.tree), rtol=1e-12)
    isolated = EtaPi0PModel(model.parameters.tree)
    np.testing.assert_allclose(model.selected_matrix_element_squared(sample, ("eq43_tree",)),
                               isolated.matrix_element_squared(sample), rtol=1e-12)


def test_full_model_duck_types_into_physical_predict_energy(full, model, monkeypatch):
    # The real two-event test above owns family integration. Here the physical
    # coherent model and real observable own duck typing and normalization.
    a = np.array([[1.+2j, 0.], [0., -2.+1j]])
    b = np.array([[0., 1.], [2j, 0.]])
    coefficients = (10., -10., 1., 2., -1., 1j, -1j)
    values = {name: (lambda sample, epsilon, coefficient=coefficient:
                        np.broadcast_to(coefficient*(epsilon[0]*a+epsilon[1]*b),
                                        (len(sample.momenta), 2, 2)).copy())
              for name, coefficient in zip(FAMILIES, coefficients)}
    calls = _patch_families(monkeypatch, full, values)

    def diagnostic_forbidden(*args, **kwargs):
        pytest.fail("physical prediction must not use a diagnostic family selection")

    monkeypatch.setattr(full.EtaPi0PFullModel, "selected_amplitude", diagnostic_forbidden)
    monkeypatch.setattr(full.EtaPi0PFullModel, "selected_matrix_element_squared", diagnostic_forbidden)
    config = SobolConfig(4, scramble=True, seed=17)
    prediction = predict_energy(1.1, model, config)
    assert [call[0] for call in calls] == list(FAMILIES)*2
    assert prediction.sample_size == 16
    assert np.isfinite(prediction.partial_cross_section_microbarn)
    assert prediction.partial_cross_section_microbarn > 0
    mass = model.parameters.tree.proton_mass_gev
    s = mass**2+2*mass*1.1
    generated = sample_three_body(np.sqrt(s), model.masses, config)
    # Sum of the seven coefficients is 2: |2a|^2/2=20, |2b|^2/2=10.
    expected = GEV2_TO_MICROBARN*4*mass**2/(2*(s-mass**2))*np.mean(generated.weights_gev2)*15.
    np.testing.assert_allclose(prediction.partial_cross_section_microbarn, expected, rtol=1e-12)
    assert all(np.all(np.isfinite(hist.values)) for hist in prediction.histograms.values())
    for histogram in prediction.histograms.values():
        np.testing.assert_allclose(np.sum(histogram.values*np.diff(histogram.edges)), expected, rtol=1e-12)
