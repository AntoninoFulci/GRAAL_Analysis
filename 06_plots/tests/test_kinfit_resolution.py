import numpy as np
import pytest

from plots import kinfit_resolution as kr


def test_core_sigma_is_rms_inside_the_window():
    # a clean gaussian core well inside +-0.3 -> core_sigma ~ its std
    rng = np.random.default_rng(0)
    x = rng.normal(0.0, 0.05, 100000)
    assert kr.core_sigma(x) == pytest.approx(0.05, rel=0.05)


def test_core_sigma_ignores_the_tails():
    # a tight core plus far-out junk: the junk is outside +-0.3 and dropped,
    # so the reported width stays the core width, not inflated by the tail.
    core = np.zeros(1000)          # zero-width core
    tail = np.full(1000, 5.0)      # far outside the window
    assert kr.core_sigma(np.concatenate([core, tail])) == pytest.approx(0.0)


def test_core_sigma_empty_window_is_nan():
    # everything outside the window -> nothing to take the RMS of
    assert np.isnan(kr.core_sigma(np.full(10, 9.0)))


def test_pairing_matches_the_reco_stacking_order():
    # eta is the heavy pair, pi0 the light pair: the order reco_core stacks the
    # photons in before calling the fit. A mismatch would fit the wrong masses.
    assert kr.PAIRING.heavy == (0, 1)
    assert kr.PAIRING.light == (2, 3)
