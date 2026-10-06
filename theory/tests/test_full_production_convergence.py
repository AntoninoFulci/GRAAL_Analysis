"""Physical Increment A audit: converged results and explicit masks are distinct.

The audit helpers are test-local: there is no new physical/public API.  Every
prediction below uses real sourced amplitudes and deterministic nested Sobol
events; no fitted golden parameters or surrogate family weights are used.
"""

from dataclasses import replace
import json
import os
from pathlib import Path
import subprocess
import sys
from time import perf_counter

import numpy as np
import pytest

from graal_theory.models.eta_pi0_p import EtaPi0PModel
from graal_theory.observables import HistogramSpec, predict_energy
from graal_theory.phase_space import SobolConfig


REFERENCES = Path(__file__).resolve().parents[1] / "references"
THRESHOLD_ENERGY = (sum((.547862, .1349768, .93827208816))**2
                    - .93827208816**2)/(2*.93827208816)
# Upper publication intervals are [1.30,1.40), [1.40,1.50] GeV.
ENERGIES = (THRESHOLD_ENERGY+.001, 1.2, 1.4, 1.5)


def _compare_predictions(low, high):
    """The 1e-4 rule is a *fraction* at either resolution, including edges.

    This deliberately does not use legacy compare_resolutions, whose absolute
    edge-bin exclusion is unsuitable for the tiny near-threshold cross section.
    Loop comparisons use the same power; Sobol comparisons use p and p+1.
    """
    assert low.photon_energy_gev == high.photon_energy_gev
    total_low, total_high = (low.partial_cross_section_microbarn,
                            high.partial_cross_section_microbarn)
    assert np.isfinite([total_low, total_high]).all()
    assert total_low > 0 and total_high > 0
    total_change = abs(total_high-total_low)/total_high
    changes, populated, bin_passed = {}, {}, {}
    for name, a in low.histograms.items():
        b = high.histograms[name]
        np.testing.assert_array_equal(a.edges, b.edges)
        low_yield = a.values*np.diff(a.edges)
        high_yield = b.values*np.diff(b.edges)
        mask = np.maximum(low_yield/total_low, high_yield/total_high) >= 1e-4
        change = np.divide(abs(high_yield-low_yield), high_yield,
                           out=np.full_like(high_yield, np.inf), where=high_yield > 0)
        changes[name], populated[name] = change, mask
        bin_passed[name] = (~mask) | (change < .03)
    maximum = max(float(np.max(changes[name][mask]))
                  for name, mask in populated.items() if np.any(mask))
    return {"passed": bool(total_change < .01 and maximum < .03),
            "total_relative_change": float(total_change),
            "max_populated_bin_relative_change": maximum,
            "populated": populated, "bin_passed": bin_passed}


@pytest.mark.parametrize("energy", ENERGIES)
def test_gate_accepts_converged_real_eq43_spectrum(energy):
    """Catch a gate that rejects the real, adequately resolved isolated tree."""
    model = EtaPi0PModel.from_files(
        REFERENCES / "central_parameters.json", REFERENCES / "sources.json")
    low, high = [predict_energy(energy, model, SobolConfig(power), HistogramSpec(8))
                 for power in (16, 17)]
    report = _compare_predictions(low, high)
    assert report["passed"], report


def test_tiny_threshold_cross_section_keeps_populated_edge_bins_in_gate():
    """Catch absolute microbarn exclusion or unjustified edge-bin exemption."""
    model = EtaPi0PModel.from_files(
        REFERENCES / "central_parameters.json", REFERENCES / "sources.json")
    low, high = [predict_energy(ENERGIES[0], model, SobolConfig(power), HistogramSpec(8))
                 for power in (4, 5)]
    assert high.partial_cross_section_microbarn < 1e-6
    report = _compare_predictions(low, high)
    # The upper eta-p edge contains a substantial fraction of this tiny yield.
    assert report["populated"]["eta_p"][-1]
    assert not report["passed"]
    assert report["max_populated_bin_relative_change"] > .03


def test_gate_excludes_real_nonzero_bins_below_total_weight_fraction():
    """Catch treating a tiny density or any nonzero bin as populated."""
    model = EtaPi0PModel.from_files(
        REFERENCES / "central_parameters.json", REFERENCES / "sources.json")
    low, high = [predict_energy(1.2, model, SobolConfig(power), HistogramSpec(64))
                 for power in (10, 11)]
    report = _compare_predictions(low, high)
    # Real phase-space tails are nonzero but carry <1e-4 of total weight.
    for name, index in (("eta_p", -1), ("pi0_p", 0)):
        assert high.histograms[name].values[index] > 0
        assert not report["populated"][name][index]
        assert report["bin_passed"][name][index]


@pytest.mark.parametrize("energy", (1.4, 1.5))
def test_upper_energy_strong_domain_is_open_on_interior_phase_space(energy):
    """Catch a residual 1.70 GeV guard on populated upper-bin events."""
    from graal_theory.kinematics import invariant_mass, s_from_lab_photon_energy
    from graal_theory.models.eta_pi0_p_full import EtaPi0PFullModel
    from graal_theory.phase_space import sample_three_body

    model = EtaPi0PFullModel.from_files(REFERENCES)
    sample = sample_three_body(np.sqrt(s_from_lab_photon_energy(energy, model.masses[-1])),
                               model.masses, SobolConfig(5))
    z = invariant_mass(sample.momenta[:, 0]+sample.momenta[:, 2])
    # A substantial phase-space-volume contribution lies above the old 1.70
    # ceiling. This is not a cross-section or convergence estimate.
    indices = np.flatnonzero((z > 1.7)
                            & (sample.weights_gev2 > 1e-4*np.sum(sample.weights_gev2)))[:1]
    assert len(indices) == 1
    interior = replace(sample, initial=sample.initial[indices], momenta=sample.momenta[indices],
                       weights_gev2=sample.weights_gev2[indices], s12_gev2=sample.s12_gev2[indices])
    amplitude = model.selected_amplitude(
        interior, np.array([1., 0., 0.]), ("chiral_contact",))
    assert amplitude.shape == (1, 2, 2)
    assert np.isfinite(amplitude).all()


def _physical_audit(energy):
    """Screen physical settings; a failed/incomplete audit yields no curve.

    The 16/32 GL orders are a measured *screen*, not claimed-converged controls.
    Each model additionally checks its integrals against 32/64 internally.
    No tolerance is loosened from the authoritative direct-loop defaults.
    """
    from graal_theory.amplitudes.production_loops import QuadratureSettings
    from graal_theory.full_production_validation import PredictionCurve
    from graal_theory.models.eta_pi0_p_full import EtaPi0PFullModel

    original = EtaPi0PFullModel.from_files(REFERENCES)
    predictions, attempts = {}, []
    for order in (16, 32):
        controls = QuadratureSettings(order, order)
        model = EtaPi0PFullModel(replace(original.parameters, production=replace(
            original.parameters.production, quadrature=controls)))
        for power in (4, 5):
            start, reason, status = perf_counter(), "", "finite_unvalidated"
            if energy >= 1.4:
                attempts.append({"q_order": order, "angle_order": order, "power": power,
                                 "relative_tolerance": controls.relative_tolerance,
                                 "absolute_tolerance": controls.absolute_tolerance,
                                 "status": "not_completed_runtime_bound",
                                 "reason": "1.80 GeV strong domain is open; upper-energy full-loop "
                                           "convergence awaits conditional Figure 4 integrator",
                                 "runtime_seconds": 0.})
                continue
            # Measured q32 threshold p4 costs 505 s; p5 remains a separate
            # physical audit run, not a 25-minute addition to every test suite.
            # This is incompleteness, never a fabricated convergence failure.
            if energy == ENERGIES[0] and order == 32:
                attempts.append({"q_order": order, "angle_order": order, "power": power,
                                 "relative_tolerance": controls.relative_tolerance,
                                 "absolute_tolerance": controls.absolute_tolerance,
                                 "status": "not_completed_runtime_bound",
                                 "reason": "q32 threshold p4 measured 505 seconds; "
                                           "high-order comparison excluded from routine screen",
                                 "runtime_seconds": 0.})
                continue
            try:
                predictions[(order, power)] = predict_energy(
                    energy, model, SobolConfig(power), HistogramSpec(8))
            except ValueError as exc:
                reason = str(exc)
                if "outside reduced real-axis domain" in reason:
                    status = "masked_unsupported_domain"
                elif "convergence failure" in reason:
                    status = "masked_nonconverged"
                else:
                    raise  # A programming/input error must not masquerade as convergence.
            attempts.append({"q_order": order, "angle_order": order, "power": power,
                             "relative_tolerance": controls.relative_tolerance,
                             "absolute_tolerance": controls.absolute_tolerance,
                             "status": status, "reason": reason,
                             "runtime_seconds": perf_counter()-start})
    comparisons = []
    for first, second in (((16, 4), (32, 4)), ((16, 5), (32, 5)),
                          ((16, 4), (16, 5)), ((32, 4), (32, 5))):
        if first in predictions and second in predictions:
            comparisons.append(_compare_predictions(predictions[first], predictions[second]))
    passed = len(comparisons) == 4 and all(row["passed"] for row in comparisons)
    failures = [row for row in attempts if row["reason"]]
    reason = "; ".join(f"q={row['q_order']} angle={row['angle_order']} p={row['power']}: "
                       f"{row['status']}: {row['reason']}" for row in failures)
    if not failures and not passed:
        reason = "total <1% and every >=1e-4 total-weight bin <3% gate failed"
    best = predictions.get((32, 5))
    if best is None:
        mass_min = sum(original.masses[::2])
        mass_max = np.sqrt(original.masses[-1]**2+2*original.masses[-1]*energy)-original.masses[1]
        edges = np.linspace(mass_min, mass_max, 9)
        values = np.full(8, np.nan)
    else:
        edges, values = best.histograms["eta_p"].edges, best.histograms["eta_p"].values
    centers = (edges[:-1]+edges[1:])/2
    # Gate the whole curve on *both* loop and Sobol checks. No plotted segment
    # may imply that a masked energy is an accepted production prediction.
    curve = PredictionCurve(centers, values, np.zeros(8), np.full(8, passed), reason)
    return {"passed": passed, "attempts": attempts, "comparisons": comparisons,
            "curve": curve}


@pytest.mark.parametrize("energy", ENERGIES)
def test_real_seven_family_loop_and_sobol_audit_has_explicit_outcome(energy):
    """Catch dropped loop/Sobol checks or an uncontextualized masked result."""
    audit = _physical_audit(energy)
    assert {(row["q_order"], row["power"]) for row in audit["attempts"]} == {
        (16, 4), (16, 5), (32, 4), (32, 5)}
    if energy >= 1.4:
        assert all(row["status"] == "not_completed_runtime_bound" for row in audit["attempts"])
    for row in audit["attempts"]:
        if row["status"].startswith("masked_"):
            assert "event=" in row["reason"] and "channel=" in row["reason"]
            assert "z=" in row["reason"]
        assert row["relative_tolerance"] == 1e-5
        assert row["absolute_tolerance"] == 1e-10
    if audit["passed"]:
        assert len(audit["comparisons"]) == 4
        assert all(row["total_relative_change"] < .01
                   and row["max_populated_bin_relative_change"] < .03
                   for row in audit["comparisons"])
        assert np.all(audit["curve"].converged)
    else:
        from graal_theory.full_production_validation import _sample_prediction

        curve = audit["curve"]
        assert curve.reason and not np.any(curve.converged)
        # Check interpolation between samples too: there is no bridging line.
        for point in (curve.x[2], (curve.x[2]+curve.x[3])/2):
            value, error, reason = _sample_prediction(curve, float(point))
            assert value is None and error is None and reason
    print("PHYSICAL_AUDIT", json.dumps({"energy_gev": energy, "passed": audit["passed"],
                                      "attempts": audit["attempts"]}))


def test_source_internal_pi0_real_strong_amplitude_at_converged_loop_orders():
    """Catch instability in the specific K+Lambda event that masks Task 7.

    This is a one-event family check, not end-to-end full-model convergence.
    Orders 16 and 32 failed experimentally; 64/128 are the first sampled
    passing pair with the unchanged 1e-5/1e-10 direct-loop tolerances.
    """
    from graal_theory.amplitudes.production_loops import QuadratureSettings
    from graal_theory.kinematics import s_from_lab_photon_energy
    from graal_theory.models.eta_pi0_p_full import EtaPi0PFullModel
    from graal_theory.phase_space import sample_three_body

    original = EtaPi0PFullModel.from_files(REFERENCES)
    generated = sample_three_body(np.sqrt(s_from_lab_photon_energy(1.2, original.masses[-1])),
                                  original.masses, SobolConfig(4))
    indices = [15]
    sample = replace(generated, initial=generated.initial[indices],
                     momenta=generated.momenta[indices], weights_gev2=generated.weights_gev2[indices],
                     s12_gev2=generated.s12_gev2[indices])
    amplitudes = []
    for order in (64, 128):
        model = EtaPi0PFullModel(replace(original.parameters, production=replace(
            original.parameters.production, quadrature=QuadratureSettings(order, order))))
        amplitudes.append(model.selected_amplitude(sample, np.array([1., 0., 0.]),
                                                   ("internal_pi0",)))
    assert np.isfinite(amplitudes).all()
    assert np.linalg.norm(amplitudes[1]) > 0
    np.testing.assert_allclose(amplitudes[0], amplitudes[1], rtol=1e-5, atol=1e-10)


def test_cold_full_model_import_preserves_eq43_and_three_real_strong_variants():
    """Catch full-production import/construction mutating legacy model inputs.

    A fresh interpreter is necessary: pytest imports other full-model tests at
    collection time. Fingerprints are recomputed before/after, never fitted.
    """
    code = r'''
import importlib
import json
from pathlib import Path
import sys
import numpy as np
from graal_theory.amplitudes.delta1700 import tree_amplitude
from graal_theory.amplitudes.nstar1535_final_fit import load_final_fit_parameters
from graal_theory.amplitudes.nstar1535_full import reconstructed_full_tmatrix
from graal_theory.amplitudes.nstar1535_pipi_n import pipi_n_tmatrix
from graal_theory.amplitudes.nstar1535_reduced import load_reduced_parameters, reduced_tmatrix
from graal_theory.amplitudes.nstar1535_vmd import load_vector_masses
from graal_theory.models.eta_pi0_p import EtaPi0PModel
from graal_theory.observables import HistogramSpec, predict_energy
from graal_theory.phase_space import SobolConfig, sample_three_body
root = Path(sys.argv[1])
def snapshot():
    tree = EtaPi0PModel.from_files(root/'central_parameters.json', root/'sources.json')
    sample = sample_three_body(1.82, tree.masses, SobolConfig(4))
    amplitude = np.stack([tree_amplitude(sample, e, tree.parameters)
                          for e in (np.array([1.,0.,0.]),np.array([0.,1.,0.]))])
    prediction = predict_energy(1.2, tree, SobolConfig(10), HistogramSpec(16))
    spectrum = np.concatenate([[prediction.partial_cross_section_microbarn],
                               *[h.values for h in prediction.histograms.values()]])
    reduced = load_reduced_parameters(root/'nstar1535_reduced_parameters.json',root/'sources.json')
    final = load_final_fit_parameters(reduced,root/'nstar1535_final_subtractions.json',root/'sources.json')
    vectors = load_vector_masses(root/'nstar1535_vmd_masses.json',root/'sources.json')
    strong = np.stack([[reduced_tmatrix(w,reduced),pipi_n_tmatrix(w,final),
                       reconstructed_full_tmatrix(w,final,vectors)] for w in (1.1,1.55,1.7)])
    return amplitude,spectrum,strong
assert 'graal_theory.models.eta_pi0_p_full' not in sys.modules
before = snapshot()
full = importlib.import_module('graal_theory.models.eta_pi0_p_full').EtaPi0PFullModel.from_files(root)
after = snapshot()
for original,current in zip(before,after):
    np.testing.assert_allclose(current,original,rtol=1e-12,atol=0)
sample=sample_three_body(1.82,full.masses,SobolConfig(4))
for i,epsilon in enumerate((np.array([1.,0.,0.]),np.array([0.,1.,0.]))):
    np.testing.assert_allclose(full.selected_amplitude(sample,epsilon,('eq43_tree',)),
                               before[0][i],rtol=1e-12,atol=0)
print(json.dumps({'max_absolute_differences':[float(np.max(abs(a-b))) for a,b in zip(before,after)],
                  'complex_amplitude_shape':list(before[0].shape),
                  'spectrum_size':len(before[1]),'strong_shape':list(before[2].shape)}))
'''
    completed = subprocess.run([sys.executable, "-c", code, str(REFERENCES)],
                               env={**os.environ, "PYTHONPATH": str(REFERENCES.parent/"src")},
                               capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
    fingerprint = json.loads(completed.stdout)
    assert np.isfinite(fingerprint["max_absolute_differences"]).all()
    assert fingerprint["complex_amplitude_shape"] == [2, 16, 2, 2]
    assert fingerprint["spectrum_size"] == 49
    assert fingerprint["strong_shape"] == [3, 3, 6, 6]
