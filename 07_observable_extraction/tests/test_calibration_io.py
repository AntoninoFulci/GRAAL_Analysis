import csv
from array import array
import math

import pytest
import ROOT

from calibration.run_manifest import RunRecord, write_manifest
from calibration.strip_energy_flux import STRIP_EXPOSURE_FIELDS
from graal_common.physics.beam_profiles import get_beam_profile
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


def test_load_exposures_can_skip_invalid_selected_rows_with_warning(
    tmp_path, capsys
):
    path = tmp_path / "flux_by_run_strip.csv"
    _write_rows(
        path,
        [
            _row(status="invalid", flux_pol1=0.0),
            _row(run_number=812, xstrip=18),
        ],
    )

    exposures = load_exposures(
        path,
        polarization_model=lambda energy: 0.5,
        skip_invalid=True,
    )

    assert set(exposures) == {(812, 18)}
    assert "warning: skipped 1 invalid selected flux exposure" in capsys.readouterr().err


def _write_flux_root(
    path, suffixes_by_run, *, axis_offsets=None, bin_values=None
):
    output = ROOT.TFile(str(path), "RECREATE")
    axis_offsets = axis_offsets or {}
    bin_values = bin_values or {}
    try:
        for run_number, suffixes in suffixes_by_run.items():
            for suffix in suffixes:
                offset = axis_offsets.get(suffix, 0.0)
                edges = array(
                    "d",
                    [1.0 + offset + 0.6 * index / 128 for index in range(129)],
                )
                histogram = ROOT.TH1D(
                    f"run{run_number}_{suffix}", "", 128, edges
                )
                for bin_number in range(1, 129):
                    histogram.SetBinContent(
                        bin_number,
                        bin_values.get(
                            (run_number, suffix, bin_number), 10.0
                        ),
                    )
                histogram.Write()
    finally:
        output.Close()


def test_root_loader_skips_entire_run_without_complete_flux_triplet(
    tmp_path, capsys
):
    """Removing any one state must exclude that run from every exposure."""
    manifest = tmp_path / "run_manifest.csv"
    write_manifest(
        [
            RunRecord(811, "uv", "P", "UV", "P_UV", "manual", "uv/run811.root"),
            RunRecord(812, "uv", "P", "UV", "P_UV", "manual", "uv/run812.root"),
        ],
        manifest,
    )
    root_path = tmp_path / "flux_calibrated.root"
    _write_flux_root(
        root_path,
        {
            811: ("POL1", "POL2", "BREM"),
            812: ("POL1", "POL2"),
        },
    )

    exposures = load_exposures(
        root_path,
        manifest_path=manifest,
        polarization_model=lambda energy: 0.5,
    )

    assert {run_number for run_number, _ in exposures} == {811}
    warning = capsys.readouterr().err
    assert "skipped run 812" in warning
    assert "missing BREM" in warning


def test_root_loader_uses_each_polarization_states_calibrated_energy(tmp_path):
    """Collapsing POL1/POL2 onto one energy would bias their transfer values."""
    manifest = tmp_path / "run_manifest.csv"
    write_manifest(
        [RunRecord(811, "uv", "P", "UV", "P_UV", "manual", "uv/run811.root")],
        manifest,
    )
    root_path = tmp_path / "flux_calibrated.root"
    _write_flux_root(
        root_path,
        {811: ("POL1", "POL2", "BREM")},
        axis_offsets={"POL2": 0.02},
    )

    exposures = load_exposures(
        root_path,
        manifest_path=manifest,
        polarization_model=lambda energy: energy / 2.0,
    )

    item = exposures[(811, 30)]
    vertical_energy = 1.0 + (29.5 * 0.6 / 128)
    horizontal_energy = vertical_energy + 0.02
    assert item.energy_gev == pytest.approx(
        0.5 * (vertical_energy + horizontal_energy)
    )
    assert item.polarization_vertical == pytest.approx(vertical_energy / 2.0)
    assert item.polarization_horizontal == pytest.approx(horizontal_energy / 2.0)


def test_root_loader_skips_strata_outside_compton_polarization_domain(
    tmp_path, capsys
):
    """Extending a histogram above the UV edge must not abort valid strata."""
    manifest = tmp_path / "run_manifest.csv"
    write_manifest(
        [RunRecord(811, "uv", "P", "UV", "P_UV", "manual", "uv/run811.root")],
        manifest,
    )
    root_path = tmp_path / "flux_calibrated.root"
    _write_flux_root(root_path, {811: ("POL1", "POL2", "BREM")})

    exposures = load_exposures(root_path, manifest_path=manifest)

    assert exposures
    assert all(
        0.0 <= item.polarization_vertical <= 1.0
        and 0.0 <= item.polarization_horizontal <= 1.0
        for item in exposures.values()
    )
    assert "outside polarization domain" in capsys.readouterr().err


@pytest.mark.parametrize("state", ["POL1", "POL2", "BREM"])
@pytest.mark.parametrize("invalid_value", [math.nan, math.inf])
def test_root_loader_skips_nonfinite_flux_stratum_without_aborting_valid_ones(
    tmp_path, capsys, state, invalid_value
):
    manifest = tmp_path / "run_manifest.csv"
    write_manifest(
        [RunRecord(811, "uv", "P", "UV", "P_UV", "manual", "uv/run811.root")],
        manifest,
    )
    root_path = tmp_path / "flux_calibrated.root"
    _write_flux_root(
        root_path,
        {811: ("POL1", "POL2", "BREM")},
        bin_values={(811, state, 30): invalid_value},
    )

    exposures = load_exposures(
        root_path,
        manifest_path=manifest,
        polarization_model=lambda energy: 0.5,
    )

    assert exposures
    assert (811, 30) not in exposures
    assert "non-finite flux" in capsys.readouterr().err


def test_root_loader_limits_exposure_to_runs_present_in_event_sample(tmp_path):
    """Adding calibrated runs absent from data would bias flux normalization."""
    manifest = tmp_path / "run_manifest.csv"
    write_manifest(
        [
            RunRecord(811, "uv", "P", "UV", "P_UV", "manual", "uv/run811.root"),
            RunRecord(812, "uv", "P", "UV", "P_UV", "manual", "uv/run812.root"),
        ],
        manifest,
    )
    root_path = tmp_path / "flux_calibrated.root"
    _write_flux_root(
        root_path,
        {
            811: ("POL1", "POL2", "BREM"),
            812: ("POL1", "POL2", "BREM"),
        },
    )

    exposures = load_exposures(
        root_path,
        manifest_path=manifest,
        polarization_model=lambda energy: 0.5,
        run_numbers={811},
    )

    assert {run_number for run_number, _ in exposures} == {811}


def test_root_loader_routes_vis_profile_and_skips_incomplete_run(
    tmp_path, capsys
):
    manifest = tmp_path / "run_manifest.csv"
    write_manifest(
        [
            RunRecord(
                1999,
                "vis",
                "P",
                "VIS",
                "P_VIS",
                "manual",
                "vis/run1999.root",
            ),
            RunRecord(
                2071,
                "vis",
                "P",
                "VIS",
                "P_VIS",
                "manual",
                "vis/run2071.root",
            ),
        ],
        manifest,
    )
    root_path = tmp_path / "flux_calibrated.root"
    _write_flux_root(
        root_path,
        {
            1999: ("POL1", "POL2", "BREM"),
            2071: ("POL1", "POL2"),
        },
    )
    profile = get_beam_profile("vis")

    exposures = load_exposures(
        root_path,
        manifest_path=manifest,
        polarization_model=profile.polarization,
        target=profile.target,
        beam_type=profile.beam_type,
        energy_range=profile.energy_range_gev,
    )

    assert {run_number for run_number, _ in exposures} == {1999}
    assert all(
        0.9313 <= exposure.energy_gev <= 1.10
        for exposure in exposures.values()
    )
    warning = capsys.readouterr().err
    assert "skipped run 2071" in warning
    assert "missing BREM" in warning
