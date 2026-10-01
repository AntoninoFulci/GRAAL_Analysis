import pytest

from graal_common.physics.beam_profiles import (
    BeamProfile,
    UV_PROFILE,
    VIS_PROFILE,
    get_beam_profile,
)
from graal_common.physics.compton import (
    ELECTRON_ENERGY_MEV,
    linear_polarization_transfer,
)


def test_vis_profile_drives_visible_beam_analysis_contract():
    profile = get_beam_profile("vis")

    assert profile.target == "P"
    assert profile.beam_type == "VIS"
    assert profile.manifest_group == "P_VIS"
    assert profile.laser_wavelength_nm == 514.0
    assert profile.energy_edges_gev == (0.9313, 1.10)
    assert profile.energy_range_gev == (0.9313, 1.10)


def test_uv_profile_preserves_existing_energy_binning():
    assert UV_PROFILE.energy_edges_gev == (1.10, 1.20, 1.30, 1.40, 1.50)
    assert get_beam_profile("uv") is UV_PROFILE


def test_unknown_profile_lists_valid_names():
    with pytest.raises(ValueError, match="uv, vis"):
        get_beam_profile("green")


def test_vis_polarization_uses_green_laser_transfer():
    expected = linear_polarization_transfer(
        1000.0,
        ELECTRON_ENERGY_MEV,
        514.0,
    )

    assert VIS_PROFILE.polarization(1.0) == pytest.approx(expected)


@pytest.mark.parametrize(
    ("updates", "message"),
    [
        ({"name": ""}, "name"),
        ({"laser_wavelength_nm": 0.0}, "wavelength"),
        ({"energy_edges_gev": (1.0,)}, "at least two"),
        ({"energy_edges_gev": (1.0, 1.0)}, "strictly increasing"),
        ({"energy_edges_gev": (1.0, float("nan"))}, "finite"),
    ],
)
def test_profile_rejects_invalid_physics_contract(updates, message):
    values = {
        "name": "test",
        "target": "P",
        "beam_type": "VIS",
        "manifest_group": "P_VIS",
        "laser_wavelength_nm": 514.0,
        "energy_edges_gev": (0.9313, 1.10),
    }
    values.update(updates)

    with pytest.raises(ValueError, match=message):
        BeamProfile(**values)
