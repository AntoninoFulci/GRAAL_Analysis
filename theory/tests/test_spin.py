import numpy as np

from graal_theory.spin import LEVI_CIVITA, PAULI, TRANSITION, transverse_polarizations


def test_transition_operators_satisfy_spin_identity():
    for i in range(3):
        for j in range(3):
            expected = (2.0 / 3.0) * (i == j) * np.eye(2, dtype=complex)
            expected -= (1j / 3.0) * sum(
                LEVI_CIVITA[i, j, k] * PAULI[k] for k in range(3)
            )
            np.testing.assert_allclose(
                TRANSITION[i] @ TRANSITION[j].conj().T,
                expected,
                atol=1e-14,
            )


def test_transverse_basis_is_orthonormal_for_z_axis():
    ex, ey = transverse_polarizations(np.array([0.0, 0.0, 1.0]))
    np.testing.assert_allclose([np.dot(ex, ex), np.dot(ey, ey), np.dot(ex, ey)], [1, 1, 0], atol=1e-14)
    np.testing.assert_allclose([ex[2], ey[2]], [0, 0], atol=1e-14)
