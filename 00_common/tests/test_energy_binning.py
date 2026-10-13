import argparse
import json

import pytest

from graal_common.physics.energy_binning import EnergyBinning, add_energy_arguments, energy_binning_from_args
from graal_common.physics.beam_profiles import UV_PROFILE, VIS_PROFILE


def test_defaults_and_low_uv_preserve_beam_identity(tmp_path):
    parser = argparse.ArgumentParser()
    add_energy_arguments(parser)
    assert energy_binning_from_args(parser.parse_args([]), "uv").edges_gev == UV_PROFILE.energy_edges_gev
    path = tmp_path / "grid.json"
    path.write_text(json.dumps({"uv": {"energy_edges_gev": list(VIS_PROFILE.energy_edges_gev)}}))
    grid = energy_binning_from_args(parser.parse_args(["--energy-config", str(path)]), "uv")
    assert grid.energy_range_gev == VIS_PROFILE.energy_range_gev
    assert UV_PROFILE.polarization(1.0) != VIS_PROFILE.polarization(1.0)
    override = energy_binning_from_args(parser.parse_args(["--energy-config", str(path), "--energy-edges", "1.1", "1.3", "1.5"]), "uv")
    assert override.edges_gev == (1.1, 1.3, 1.5)


@pytest.mark.parametrize("edges", [(1.,), (1., 1.), (1.1, 1.), (float("nan"), 1.1), (0., 1.), (True, 1.1)])
def test_invalid_edges(edges):
    with pytest.raises(ValueError):
        EnergyBinning(edges)


def test_profile_polarization_domain():
    with pytest.raises(ValueError, match="Compton"):
        EnergyBinning((1.1, 1.5)).validate_profile(VIS_PROFILE)


def test_config_rejects_unknown_fields_and_profiles(tmp_path):
    parser = argparse.ArgumentParser()
    add_energy_arguments(parser)
    path = tmp_path / "bad.json"
    for config in ({"uv": {"energy_edge_gev": [1., 1.1]}}, {"UV": {"energy_edges_gev": [1., 1.1]}}):
        path.write_text(json.dumps(config))
        with pytest.raises(ValueError):
            energy_binning_from_args(parser.parse_args(["--energy-config", str(path)]), "uv")
