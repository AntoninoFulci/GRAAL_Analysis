import csv

import pytest

from graal_common.calibration.strip_energy_flux import STRIP_EXPOSURE_FIELDS
from observable_extraction.calibration.flux_v2 import load_exposures


def _write_rows(path, rows):
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=STRIP_EXPOSURE_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def _row(**updates):
    row = {
        "schema_version": 2,
        "run_number": 811,
        "source_period": "uv_a",
        "target": "P",
        "beam_type": "UV",
        "group": "P_UV",
        "xstrip": 17,
        "energy_median_gev": 1.25,
        "flux_pol1": 120.0,
        "flux_pol2": 80.0,
        "flux_brem": 25.0,
        "status": "valid",
    }
    row.update(updates)
    return row


def test_load_exposures_maps_pol1_vertical_and_pol2_horizontal(tmp_path):
    path = tmp_path / "flux_by_run_strip.csv"
    _write_rows(path, [_row()])

    exposures = load_exposures(path, polarization_model=lambda energy: 0.5)
    item = exposures[(811, 17)]

    assert item.flux_vertical == 120.0
    assert item.flux_horizontal == 80.0
    assert item.flux_brem == 25.0
    assert item.polarization_vertical == 0.5
    assert item.polarization_horizontal == 0.5


def test_load_exposures_filters_to_proton_uv_energy_window(tmp_path):
    path = tmp_path / "flux_by_run_strip.csv"
    _write_rows(
        path,
        [
            _row(),
            _row(run_number=812, target="D", group="D_UV"),
            _row(run_number=813, beam_type="VIS", group="P_VIS"),
            _row(run_number=814, energy_median_gev=1.05),
        ],
    )

    exposures = load_exposures(path, polarization_model=lambda energy: 0.5)

    assert set(exposures) == {(811, 17)}


def test_load_exposures_rejects_duplicate_selected_run_strip(tmp_path):
    path = tmp_path / "flux_by_run_strip.csv"
    _write_rows(path, [_row(), _row()])

    with pytest.raises(ValueError, match="duplicate exposure"):
        load_exposures(path, polarization_model=lambda energy: 0.5)


def test_load_exposures_rejects_wrong_schema_version(tmp_path):
    path = tmp_path / "flux_by_run_strip.csv"
    _write_rows(path, [_row(schema_version=1)])

    with pytest.raises(ValueError, match="schema version 2"):
        load_exposures(path, polarization_model=lambda energy: 0.5)
