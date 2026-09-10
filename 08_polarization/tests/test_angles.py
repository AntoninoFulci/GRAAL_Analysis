from __future__ import annotations

import numpy as np
import pytest

from angles import reaction_plane_phi
from contracts import PolarizationContractError


@pytest.mark.parametrize("degrees", [0.0, 30.0, 90.0, 179.999])
def test_phi_matches_hand_constructed_transverse_vectors(degrees):
    angle = np.deg2rad(degrees)
    momentum = np.array([np.cos(angle), np.sin(angle), 0.3])
    result = reaction_plane_phi([0, 0, 1], [1, 0, 0], momentum)
    assert result.valid
    assert result.reason is None
    assert 0.0 <= result.value < np.pi
    assert result.value == pytest.approx(angle % np.pi)


def test_phi_is_axial_and_invariant_under_positive_rescaling():
    beam = np.array([0.0, 0.0, 2.0])
    reference = np.array([3.0, 0.0, 0.0])
    momentum = np.array([0.4, -0.7, 1.2])
    nominal = reaction_plane_phi(beam, reference, momentum)
    reversed_plane_axis = reaction_plane_phi(beam, reference, -momentum)
    rescaled = reaction_plane_phi(5.0 * beam, 2.0 * reference, 7.0 * momentum)
    assert nominal.valid and reversed_plane_axis.valid and rescaled.valid
    assert reversed_plane_axis.value == pytest.approx(nominal.value)
    assert rescaled.value == pytest.approx(nominal.value)


def test_cos2phi_is_continuous_across_zero_pi_boundary():
    epsilon = 1e-9
    below_zero = reaction_plane_phi(
        [0, 0, 1], [1, 0, 0], [np.cos(-epsilon), np.sin(-epsilon), 0]
    )
    above_zero = reaction_plane_phi(
        [0, 0, 1], [1, 0, 0], [np.cos(epsilon), np.sin(epsilon), 0]
    )
    assert below_zero.value > np.pi - 1e-8
    assert above_zero.value < 1e-8
    assert np.cos(2 * below_zero.value) == pytest.approx(
        np.cos(2 * above_zero.value), abs=1e-14
    )


@pytest.mark.parametrize(
    "reference,momentum,reason",
    [
        ([0, 0, 2], [1, 0, 0], "reference axis"),
        ([1, 0, 0], [0, 0, 3], "reaction plane"),
    ],
)
def test_phi_marks_degenerate_transverse_planes_invalid(reference, momentum, reason):
    result = reaction_plane_phi([0, 0, 1], reference, momentum)
    assert not result.valid
    assert np.isnan(result.value)
    assert reason in result.reason


@pytest.mark.parametrize(
    "beam,reference,momentum,match",
    [
        ([0, 0], [1, 0, 0], [1, 1, 0], "shape"),
        ([0, 0, 0], [1, 0, 0], [1, 1, 0], "beam"),
        ([0, 0, 1], [np.nan, 0, 0], [1, 1, 0], "finite"),
    ],
)
def test_phi_rejects_malformed_coordinate_inputs(beam, reference, momentum, match):
    with pytest.raises(PolarizationContractError, match=match):
        reaction_plane_phi(beam, reference, momentum)


def test_phi_rejects_nonpositive_tolerance():
    with pytest.raises(PolarizationContractError, match="tolerance"):
        reaction_plane_phi([0, 0, 1], [1, 0, 0], [1, 1, 0], tolerance=0.0)
