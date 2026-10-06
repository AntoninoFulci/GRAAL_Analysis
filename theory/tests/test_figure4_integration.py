"""Publication-bin integration contracts independent of sourced amplitudes."""

from types import SimpleNamespace

import numpy as np
import pytest
from scipy.integrate import quad

from graal_theory.constants import GEV2_TO_MICROBARN
from graal_theory.figure4_integration import (
    covariance_from_replicates, predict_figure4_bin, project_polarized_moments,
    convergence_reasons, integrate_figure4_panel, certify_figure4_panel,
    project_azimuth_averaged_moments, apply_pair_total_gate,
)
from graal_theory.phase_space import SobolConfig, phase_space_volume_quad
from graal_theory.kinematics import kallen
from graal_theory.figure4_reference import PAIR_MASS_AXES


def test_polarized_moment_has_ajaka_sign_and_normalization():
    phi = (np.arange(128)+.5)*2*np.pi/128
    vertical, horizontal = 1+.3*np.cos(2*phi), 1-.3*np.cos(2*phi)
    numerator, denominator = project_polarized_moments(
        phi, vertical, horizontal, np.ones(128))
    assert numerator/denominator == pytest.approx(.3, abs=1e-12)
    reverse, same = project_polarized_moments(phi, horizontal, vertical, np.ones(128))
    assert reverse/same == pytest.approx(-.3, abs=1e-12)


class FlatModel:
    masses = (.547862, .1349768, .93827208816)
    parameters = SimpleNamespace(proton_mass_gev=masses[2])

    def polarized_matrix_element_squared(self, sample, epsilon):
        return np.ones(len(sample.initial))

    def amplitude(self, sample, epsilon):
        matrix = np.eye(2, dtype=complex) if epsilon[0] else np.diag([1., -1.]).astype(complex)
        return np.broadcast_to(matrix,
                               (len(sample.initial), 2, 2)).copy()


def test_exact_global_azimuth_average_matches_rotated_polarizations():
    horizontal = np.array([[[1+.4j, .3], [.2j, .5]]])
    vertical = np.array([[[.1, .7j], [.4, .8-.2j]]])
    alpha = np.array([.43])
    averaged = project_azimuth_averaged_moments(
        alpha, vertical, horizontal, np.ones(1))
    beta = (np.arange(256)+.5)*2*np.pi/256
    c, s = np.cos(beta)[:, None, None], np.sin(beta)[:, None, None]
    rotated_h = c*horizontal-s*vertical
    rotated_v = s*horizontal+c*vertical
    h = np.sum(abs(rotated_h)**2, axis=(1, 2))/2
    v = np.sum(abs(rotated_v)**2, axis=(1, 2))/2
    numeric = project_polarized_moments(alpha+beta, v, h,
                                         np.full(len(beta), 1/len(beta)))
    np.testing.assert_allclose(averaged, numeric, rtol=1e-13, atol=1e-13)


def test_exact_global_average_equalizes_polarized_normalizations():
    class UnequalModel(FlatModel):
        def amplitude(self, sample, epsilon):
            return super().amplitude(sample, epsilon)*(1. if epsilon[0] else 2.)
    moment = predict_figure4_bin(UnequalModel(), "p_eta", (1.4, 1.5),
                                  (1.6, 1.64), energy_order=2, sobol=SobolConfig(4))
    assert moment.vertical_normalization == pytest.approx(moment.horizontal_normalization)
    assert moment.vertical_normalization == pytest.approx(moment.denominator/2)


def test_upper_edge_uses_exact_energy_onset_and_masks_inaccessible_bin():
    model = FlatModel()
    low_mass = 1.70
    onset = ((low_mass+model.masses[1])**2-model.masses[2]**2)/(2*model.masses[2])
    assert 1.30 < onset < 1.40
    result = predict_figure4_bin(model, "p_eta", (1.30, 1.40),
                                  (low_mass, 1.80), energy_order=4, sobol=SobolConfig(5))
    assert result.status == "calculated"
    assert np.all(result.energy_nodes_gev >= onset)
    assert np.all(result.energy_nodes_gev <= 1.40)
    assert result.accessible_energy_gev[0] == pytest.approx(onset)
    assert result.sigma == pytest.approx(0., abs=1e-12)
    assert result.denominator > 0
    missing = predict_figure4_bin(model, "p_eta", (1.30, 1.40),
                                   (1.80, 1.90), energy_order=4, sobol=SobolConfig(5))
    assert missing.status == "masked_kinematic"


def test_near_onset_weight_matches_independent_energy_and_mass_integral():
    model = FlatModel()
    proton = model.masses[2]
    lower_mass = 1.70
    onset = ((lower_mass+model.masses[1])**2-proton**2)/(2*proton)
    moment = predict_figure4_bin(model, "p_eta", (1.30, 1.40),
                                  (lower_mass, 1.80), energy_order=8,
                                  sobol=SobolConfig(12))
    def energy_density(energy):
        s = proton**2+2*proton*energy
        sqrt_s = np.sqrt(s)
        m1, m2, m3 = proton, model.masses[0], model.masses[1]
        upper = (sqrt_s-m3)**2
        def mass_density(s_pair):
            return (np.sqrt(kallen(s, s_pair, m3**2, atol=1e-12))
                    *np.sqrt(kallen(s_pair, m1**2, m2**2, atol=1e-12))
                    /(128*np.pi**3*s*s_pair))
        volume = quad(mass_density, lower_mass**2, upper, epsabs=1e-12)[0]
        return 2*GEV2_TO_MICROBARN*4*proton**2/(2*(s-proton**2))*volume
    expected = quad(energy_density, onset, 1.40, epsabs=1e-10)[0]/.10
    assert moment.denominator == pytest.approx(expected, rel=0.005)


def test_three_ten_bin_projections_recover_same_full_space_normalization():
    model = FlatModel()
    proton = model.masses[2]
    def full_energy_density(energy):
        s = proton**2+2*proton*energy
        flux = GEV2_TO_MICROBARN*4*proton**2/(2*(s-proton**2))
        return 2*flux*phase_space_volume_quad(np.sqrt(s), model.masses)
    expected = quad(full_energy_density, 1.4, 1.5, epsabs=1e-10)[0]/.1
    totals = []
    for pair, (lower, upper) in PAIR_MASS_AXES.items():
        edges = np.linspace(lower, upper, 11)
        moments = (predict_figure4_bin(model, pair, (1.4, 1.5),
                    (float(a), float(b)), energy_order=8, sobol=SobolConfig(10))
                   for a, b in zip(edges[:-1], edges[1:]))
        totals.append(sum(moment.denominator for moment in moments))
    np.testing.assert_allclose(totals, expected, rtol=.01, atol=0)




def test_covariance_uses_independent_replicate_means():
    replicas = np.array([[.05, .1], [.1, .2], [.15, .3], [.2, .4],
                         [.25, .5], [.3, .6], [.35, .7], [.4, .8]])
    np.testing.assert_allclose(covariance_from_replicates(replicas),
                               np.cov(replicas, rowvar=False, ddof=1)/8,
                               rtol=1e-14, atol=1e-14)


@pytest.mark.parametrize("change,reason", [
    ({"energy_delta_sigma": .006}, "energy_sigma"),
    ({"energy_vertical_relative": .01}, "energy_vertical"),
    ({"sobol_delta_sigma": .011}, "sobol_sigma"),
    ({"sobol_total_relative": .011}, "sobol_total"),
    ({"sobol_vertical_relative": .031}, "sobol_vertical"),
    ({"replica_se": .011}, "replica_se"),
    ({"grid_direct_delta_sigma": .003}, "grid_direct_sigma"),
])
def test_convergence_gate_keeps_each_failure_typed(change, reason):
    values = dict(sigma=.2, energy_delta_sigma=0., energy_vertical_relative=0.,
                  energy_horizontal_relative=0., sobol_delta_sigma=0.,
                  sobol_total_relative=0., sobol_vertical_relative=0.,
                  sobol_horizontal_relative=0., replica_se=0.,
                  grid_direct_delta_sigma=0., populated=True)
    values.update(change)
    assert reason in convergence_reasons(**values)


def test_panel_keeps_masks_and_requires_eight_replicas():
    model = FlatModel()
    edges = np.array([1.60, 1.64, 1.80, 1.84])
    raw = integrate_figure4_panel(model, "p_eta", (1.40, 1.50), edges,
                                   energy_order=2, sobol=SobolConfig(5))
    assert len(raw.bins) == 3
    assert raw.bins[-1].status == "masked_kinematic"
    assert raw.bins[0].status == "masked_nonconverged"
    with pytest.raises(ValueError, match="eight"):
        certify_figure4_panel(model, "p_eta", (1.40, 1.50), edges,
                              energy_order=2, sobol_power=5,
                              replica_seeds=tuple(range(2026, 2033)))


def test_pair_total_gate_masks_disagreeing_accessible_panels():
    from graal_theory.figure4_integration import Figure4CertifiedBin, Figure4PanelResult
    from dataclasses import replace
    panels = {}
    for pair, total in (("p_pi0", 1.), ("p_eta", 1.), ("eta_pi0", 1.2)):
        moment = replace(predict_figure4_bin(FlatModel(), "p_eta", (1.4,1.5),
            (1.6,1.64), energy_order=2, sobol=SobolConfig(5)),
            pair=pair, denominator=total, vertical_normalization=total/2,
            horizontal_normalization=total/2)
        item = Figure4CertifiedBin(moment, "calculated", (), .001, {})
        panels[(3,pair)] = Figure4PanelResult(pair, (1.4,1.5),
            np.array([1.6,1.64]), (item,), np.array([[1e-6]]), 2, 5,
            tuple(range(2026,2034)), "direct")
    checked = apply_pair_total_gate(panels)
    assert all(checked[key].bins[0].status == "masked_nonconverged" for key in panels)
    assert all("pair_total_mismatch" in checked[key].bins[0].reason for key in panels)
