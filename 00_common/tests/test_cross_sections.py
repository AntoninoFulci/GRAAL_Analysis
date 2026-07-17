"""Tests for the phase-space model behind sigma(E).

Phi_n is defined only up to an n-dependent constant, so nothing here may assert
an absolute value. Everything is a ratio, a sign, or a shape — which is exactly
how sigma_at uses it.
"""
import numpy as np
import pytest

# Masses come from the registry, never a second copy: a test that restates
# them is free to drift from the module it is testing, and would still pass.
from graal_common.channels import M_ETA, M_PI0, M_PROTON
from graal_common.cross_sections import W_of_E, phase_space_volume


class TestWofE:
    def test_at_zero_beam_energy_W_is_the_proton_mass(self):
        assert W_of_E(0.0) == pytest.approx(M_PROTON)

    def test_W_rises_with_beam_energy(self):
        E = np.linspace(0.0, 2.0, 50)
        assert np.all(np.diff(W_of_E(E)) > 0)

    def test_matches_the_closed_form(self):
        # W = sqrt(m_p^2 + 2 m_p E) — the same relation the thresholds in
        # channels.py invert. If these two ever disagree, a channel's sigma
        # turns on at an energy its own generator does not.
        assert W_of_E(1.2) == pytest.approx(np.sqrt(M_PROTON**2 + 2 * M_PROTON * 1.2))


class TestPhaseSpaceVolume:
    def test_two_body_is_zero_below_threshold(self):
        assert phase_space_volume(1.0, (M_PROTON, M_ETA)) == pytest.approx(0.0)

    def test_two_body_matches_the_analytic_q_over_W(self):
        # Phi_2 is proportional to q/W with q the CM momentum. The constant
        # cancels in any ratio, so compare two energies against the analytic
        # ratio rather than against an absolute value.
        ma, mb = M_PROTON, M_ETA

        def analytic(W):
            lam = (W**2 - (ma + mb) ** 2) * (W**2 - (ma - mb) ** 2)
            return np.sqrt(max(lam, 0.0)) / (2 * W) / W

        W1, W2 = 1.7, 1.9
        got = phase_space_volume(W2, (ma, mb)) / phase_space_volume(W1, (ma, mb))
        assert got == pytest.approx(analytic(W2) / analytic(W1), rel=1e-9)

    def test_is_zero_at_threshold_for_every_body_count(self):
        # sigma(E) must vanish where the channel does not yet exist. This is
        # the whole point of the exercise: omega_pi0 and etaprime open in the
        # last few percent of the beam range and today carry cross-sections
        # measured far above it.
        for masses in [
            (M_PROTON, M_PI0),
            (M_PROTON, M_PI0, M_PI0),
            (M_PROTON, M_PI0, M_PI0, M_PI0),
            (M_PROTON, M_PI0, M_PI0, M_PI0, M_PI0),
        ]:
            W_thr = sum(masses)
            assert phase_space_volume(W_thr, masses) == pytest.approx(0.0, abs=1e-12)

    def test_rises_monotonically_above_threshold(self):
        for masses in [
            (M_PROTON, M_PI0),
            (M_PROTON, M_PI0, M_PI0),
            (M_PROTON, M_PI0, M_PI0, M_PI0),
            (M_PROTON, M_PI0, M_PI0, M_PI0, M_PI0),
        ]:
            W = np.linspace(sum(masses) + 1e-3, sum(masses) + 0.8, 40)
            phi = phase_space_volume(W, masses)
            assert np.all(np.diff(phi) > 0), f"not monotonic for {len(masses)} bodies"

    def test_accepts_array_and_scalar_alike(self):
        masses = (M_PROTON, M_PI0, M_PI0)
        scalar = phase_space_volume(1.5, masses)
        array = phase_space_volume(np.array([1.5]), masses)
        assert np.asarray(scalar).shape == ()
        assert array.shape == (1,)
        assert float(scalar) == pytest.approx(float(array[0]))

    def test_more_bodies_turn_on_more_slowly(self):
        # Physics check: at a fixed excess above threshold, higher multiplicity
        # phase space opens more gradually. Compare each curve to its own value
        # further up, so the n-dependent constant cancels.
        excess_lo, excess_hi = 0.05, 0.40
        ratios = []
        for n in (2, 3, 4):
            masses = (M_PROTON,) + (M_PI0,) * n
            W_thr = sum(masses)
            lo = phase_space_volume(W_thr + excess_lo, masses)
            hi = phase_space_volume(W_thr + excess_hi, masses)
            ratios.append(float(lo / hi))
        assert ratios[0] > ratios[1] > ratios[2]

    def test_refuses_fewer_than_two_bodies(self):
        with pytest.raises(ValueError, match="at least two"):
            phase_space_volume(1.5, (M_PROTON,))
