from __future__ import annotations

import csv

import numpy as np
import pytest

from compton import PolarizationCurve
from contracts import PolarizationContractError
from exposures import build_panel_exposures
from state_mapping import StateInterval


def write_flux(path):
    fieldnames = [
        "binning", "run_number", "source_period", "target", "beam_type", "group",
        "energy_low_gev", "energy_high_gev", "pol1", "brem", "pol2",
        "pol1_net", "pol2_net", "total_net", "status",
    ]
    rows = []
    for run, pol1, pol2 in ((7, 100.0, 80.0), (8, 60.0, 40.0)):
        for low, high in ((1.1, 1.2), (1.2, 1.3)):
            rows.append(
                {
                    "binning": "ajaka_sigma", "run_number": run,
                    "source_period": "2002_p", "target": "P", "beam_type": "UV",
                    "group": "P_UV", "energy_low_gev": low, "energy_high_gev": high,
                    "pol1": pol1 + 1, "brem": 1, "pol2": pol2 + 1,
                    "pol1_net": pol1, "pol2_net": pol2,
                    "total_net": pol1 + pol2, "status": "valid",
                }
            )
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def intervals():
    return (
        StateInterval(7, 8, 1, "parallel", "2002_p", "pol1_net"),
        StateInterval(7, 8, 2, "perpendicular", "2002_p", "pol2_net"),
    )


def curves():
    return {
        "2002_p": PolarizationCurve(
            [1100.0, 1300.0], [0.7, 0.9], np.diag([0.01, 0.01])
        )
    }


def test_exposure_aggregates_explicit_flux_components_and_flux_weights_polarization(tmp_path):
    path = tmp_path / "flux.csv"
    write_flux(path)
    result = build_panel_exposures(
        path,
        intervals(),
        curves(),
        orientation_signs={"parallel": -1, "perpendicular": 1},
        energy_ranges=((1.1, 1.2), (1.2, 1.3)),
        target="P",
        run_numbers={7, 8},
    )
    assert result[0].horizontal_flux == pytest.approx(160.0)
    assert result[0].vertical_flux == pytest.approx(120.0)
    assert result[0].horizontal_polarization == pytest.approx(0.75)
    assert result[0].vertical_polarization == pytest.approx(0.75)
    assert result[1].horizontal_polarization == pytest.approx(0.85)
    assert result[1].vertical_polarization == pytest.approx(0.85)


def test_exposure_ignores_other_binnings_and_targets(tmp_path):
    path = tmp_path / "flux.csv"
    write_flux(path)
    with path.open("a") as handle:
        handle.write("other,7,2002_p,P,UV,P_UV,1.1,1.2,999,0,999,999,999,1998,valid\n")
        handle.write("ajaka_sigma,7,2002_p,D,UV,D_UV,1.1,1.2,999,0,999,999,999,1998,valid\n")
    result = build_panel_exposures(
        path,
        intervals(),
        curves(),
        orientation_signs={"parallel": -1, "perpendicular": 1},
        energy_ranges=((1.1, 1.2), (1.2, 1.3)),
        target="P",
        run_numbers={7, 8},
    )
    assert result[0].horizontal_flux == pytest.approx(160.0)
    assert result[0].vertical_flux == pytest.approx(120.0)


def test_exposure_rejects_missing_orientation_sign_and_period_curve(tmp_path):
    path = tmp_path / "flux.csv"
    write_flux(path)
    with pytest.raises(PolarizationContractError, match="orientation_signs"):
        build_panel_exposures(
            path, intervals(), curves(), orientation_signs={},
            energy_ranges=((1.1, 1.2), (1.2, 1.3)), target="P",
            run_numbers={7, 8},
        )
    with pytest.raises(PolarizationContractError, match="Compton curve"):
        build_panel_exposures(
            path, intervals(), {},
            orientation_signs={"parallel": -1, "perpendicular": 1},
            energy_ranges=((1.1, 1.2), (1.2, 1.3)), target="P",
            run_numbers={7, 8},
        )


def test_exposure_rejects_duplicate_component_assignment(tmp_path):
    path = tmp_path / "flux.csv"
    write_flux(path)
    duplicate = intervals() + (
        StateInterval(7, 8, 3, "perpendicular", "2002_p", "pol1_net"),
    )
    with pytest.raises(PolarizationContractError, match="duplicate flux_component"):
        build_panel_exposures(
            path, duplicate, curves(),
            orientation_signs={"parallel": -1, "perpendicular": 1},
            energy_ranges=((1.1, 1.2), (1.2, 1.3)), target="P",
            run_numbers={7, 8},
        )


def test_exposure_uses_exact_reconstruction_run_inventory(tmp_path):
    path = tmp_path / "flux.csv"
    write_flux(path)
    result = build_panel_exposures(
        path, intervals(), curves(),
        orientation_signs={"parallel": -1, "perpendicular": 1},
        energy_ranges=((1.1, 1.2), (1.2, 1.3)), target="P",
        run_numbers={7},
    )
    assert result[0].horizontal_flux == pytest.approx(100.0)
    assert result[0].vertical_flux == pytest.approx(80.0)

    with pytest.raises(PolarizationContractError, match="missing flux"):
        build_panel_exposures(
            path, intervals(), curves(),
            orientation_signs={"parallel": -1, "perpendicular": 1},
            energy_ranges=((1.1, 1.2), (1.2, 1.3)), target="P",
            run_numbers={7, 9},
        )


def test_polarization_weighting_bound_includes_internal_curve_knots(tmp_path):
    path = tmp_path / "flux.csv"
    write_flux(path)
    energy = [1100.0, 1140.0, 1150.0, 1160.0, 1200.0, 1300.0]
    value = [0.5, 0.5, 1.0, 0.5, 0.5, 0.5]
    result = build_panel_exposures(
        path, intervals(),
        {"2002_p": PolarizationCurve(energy, value, np.eye(6) * 0.001)},
        orientation_signs={"parallel": -1, "perpendicular": 1},
        energy_ranges=((1.1, 1.2), (1.2, 1.3)), target="P",
        run_numbers={7, 8},
    )
    assert result[0].vertical_polarization == pytest.approx(0.55)
    assert result[0].vertical_polarization_weighting_bound == pytest.approx(0.45)
