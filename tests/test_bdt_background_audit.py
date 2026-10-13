"""Independent checks for the background study's quantitative diagnostics."""

import numpy as np
import pytest

from scripts.audit_bdt_backgrounds import (
    exact_four_probability, paired_efficiency, injection, observable_selection,
)


def test_file_identity_supports_python310_hashlib(tmp_path, monkeypatch):
    import hashlib

    from scripts.audit_bdt_backgrounds import identity

    monkeypatch.delattr(hashlib, "file_digest", raising=False)
    path = tmp_path / "sample.bin"
    payload = b"GRAAL\x00" * 200000
    path.write_bytes(payload)

    assert identity(path) == {
        "path": str(path.resolve()),
        "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


def test_exact_four_probability_includes_every_loss_combination():
    # Six/eight independent fair coins: C(6,4)/64 and C(8,4)/256.
    assert exact_four_probability(np.full((1, 6), .5))[0] == pytest.approx(15/64)
    assert exact_four_probability(np.full((1, 8), .5))[0] == pytest.approx(70/256)
    np.testing.assert_array_equal(
        exact_four_probability(np.array([[1, 1, 1, 1, 0], [1, 1, 1, 1, 1]])),
        [1, 0],
    )


def test_paired_efficiency_uses_same_events_and_shared_covariance():
    same = np.array([True, False, True, False])
    result = paired_efficiency(same, same, np.ones(4))
    assert result['difference'] == 0
    assert result['standard_error'] == 0
    flipped = paired_efficiency(~same, same, np.ones(4))
    assert flipped['difference'] == 0
    assert flipped['standard_error'] == pytest.approx(.5)


def test_zero_weight_efficiency_is_unavailable_not_zero():
    assert paired_efficiency(np.array([True]), np.array([False]), np.zeros(1)) is None


def test_injection_closes_for_uniform_perfectly_reconstructed_azimuth():
    phi = np.linspace(-np.pi, np.pi, 1000, endpoint=False)
    samples = {'eta_pi0': dict(phi=phi, truth_phi=phi, split=np.full(1000, 2))}
    result = injection(samples, {'current': {'eta_pi0': np.ones(1000, bool)}},
                       {'eta_pi0': np.ones(1000)}, seed=100, trials=200, events=2000)
    closure = result['summary']['current']
    assert closure['response'] == pytest.approx(1)
    assert abs(closure['bias']) < .015
    assert .58 < closure['coverage_68'] < .78


def test_no_fit_selection_distinguishes_closure_and_bad_masses():
    from graal_common.physics.channels import M_ETA, M_PI0, M_PROTON
    from graal_common.stage1.features import compute_stage1_features

    # Two mesons at rest; beam solved analytically for an on-shell recoil.
    photons = np.array([[M_ETA/2, 0, 0, M_ETA/2], [-M_ETA/2, 0, 0, M_ETA/2],
                        [0, M_PI0/2, 0, M_PI0/2], [0, -M_PI0/2, 0, M_PI0/2]])
    mass = M_ETA + M_PI0
    energy = (M_PROTON**2 - (M_PROTON-mass)**2) / (2*(M_PROTON-mass))
    beam = np.array([0, 0, energy, energy])
    proton = beam + [0, 0, 0, M_PROTON] - photons.sum(axis=0)
    events = np.stack([photons, photons, 1.5*photons])
    beams = np.stack([beam, beam + [0, 0, .4, .4], beam])
    features = compute_stage1_features(events, np.stack([proton]*3), beams)
    accepted, _, _ = observable_selection(events, beams, features)
    np.testing.assert_array_equal(accepted, [True, False, False])
