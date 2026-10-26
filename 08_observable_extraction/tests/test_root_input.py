from dataclasses import replace

import numpy as np
import pytest
import ROOT

from observable_extraction.core.models import FitDiagnostics, SigmaPoint
from observable_extraction.io import root_input
from observable_extraction.io.root_input import read_output_points, read_output_contract
from observable_extraction.io.root_output import (
    OutputPoint,
    RootOutputPayload,
    write_root_output,
)


def _points():
    diagnostics = FitDiagnostics(True, 8.0, 10, 0.63, False)
    ratio = OutputPoint(
        sample="raw_bdt",
        estimator="ratio",
        point=SigmaPoint(
            "p_pi0", 0, 2, 1.1, 1.2, 1.08, 1.12, 1.099,
            0.3, 0.05, 0.06, diagnostics,
        ),
        sigma_uncorrected=0.28,
        systematic_total=0.04,
        background_fraction=0.12,
        count_vertical=120,
        count_horizontal=100,
        flux_vertical=1000.0,
        flux_horizontal=900.0,
        polarization_vertical=0.60,
        polarization_horizontal=0.58,
    )
    likelihood = replace(
        ratio,
        estimator="likelihood",
        point=replace(
            ratio.point,
            sigma=0.31,
            stat_low=0.04,
            stat_high=0.07,
            diagnostics=FitDiagnostics(True, 0.0, 0, 1.0, False),
        ),
    )
    return ratio, likelihood


def _write(path):
    points = _points()
    payload = RootOutputPayload(
        points=points,
        energy_edges=np.array([1.1, 1.2]),
        mass_edges={"p_pi0": np.array([1.08, 1.12])},
        covariance_total=np.eye(len(points)),
        systematic_covariances={},
        ratio_objects=(),
        provenance="synthetic",
    )
    write_root_output(path, payload)
    return payload


def test_root_output_points_round_trip(tmp_path):
    output = tmp_path / "beam_asymmetry.root"
    payload = _write(output)

    assert read_output_points(output) == payload.points


def _replace_provenance(path, text):
    source = ROOT.TFile(str(path), "UPDATE")
    source.Delete("provenance;*")
    ROOT.TNamed("provenance", text).Write()
    source.Close()


def _valid_candle_provenance():
    return (
        "profile=uv\n"
        "phi_bin_divisor=0.9549\n"
        "candle_enabled=true\n"
        "candle_eta_center_gev=0.547862\n"
        "candle_pi0_center_gev=0.134977\n"
        "candle_mass_half_width_gev=0.05\n"
        "candle_geometry=rectangular\n"
        "candle_core_logic=and\n"
        "candle_tail_logic=or_complement\n"
        "candle_boundary=inclusive\n"
        "candle_baseline_event_count=100\n"
        "candle_full_core_event_count=80\n"
        "candle_tail_event_count=20\n"
        "candle_balanced_core_event_count=20\n"
        "candle_excluded_nonfinite_event_count=0\n"
        "candle_balance_method=random_without_replacement\n"
        "candle_balance_seed=20261024\n"
        "candle_mass_source=raw_pre_fit"
    )


def test_contract_reads_complete_candle_provenance(tmp_path):
    output = tmp_path / "candle.root"
    _write(output)
    _replace_provenance(output, _valid_candle_provenance())

    assert read_output_contract(output).candle == root_input.CandleContract(
        eta_center_gev=0.547862,
        pi0_center_gev=0.134977,
        mass_half_width_gev=0.05,
        geometry="rectangular",
        core_logic="and",
        tail_logic="or_complement",
        boundary="inclusive",
        baseline_event_count=100,
        full_core_event_count=80,
        tail_event_count=20,
        balanced_core_event_count=20,
        excluded_nonfinite_event_count=0,
        balance_method="random_without_replacement",
        balance_seed=20261024,
        mass_source="raw_pre_fit",
    )


def test_legacy_contract_has_no_candle_metadata(tmp_path):
    output = tmp_path / "legacy_no_candle.root"
    _write(output)

    assert read_output_contract(output).candle is None


@pytest.mark.parametrize(
    "provenance",
    [
        _valid_candle_provenance().replace(
            "candle_pi0_center_gev=0.134977\n", ""
        ),
        _valid_candle_provenance() + "\ncandle_enabled=true",
        _valid_candle_provenance().replace(
            "candle_enabled=true", "candle_enabled=false"
        ),
        _valid_candle_provenance().replace(
            "candle_mass_half_width_gev=0.05", "candle_mass_half_width_gev=0"
        ),
        _valid_candle_provenance().replace(
            "candle_eta_center_gev=0.547862", "candle_eta_center_gev=nan"
        ),
        _valid_candle_provenance().replace(
            "candle_geometry=rectangular", "candle_geometry=elliptical"
        ),
        _valid_candle_provenance().replace(
            "candle_core_logic=and", "candle_core_logic=or"
        ),
        _valid_candle_provenance().replace(
            "candle_tail_logic=or_complement", "candle_tail_logic=and"
        ),
        _valid_candle_provenance().replace(
            "candle_boundary=inclusive", "candle_boundary=exclusive"
        ),
        _valid_candle_provenance().replace(
            "candle_baseline_event_count=100", "candle_baseline_event_count=0"
        ),
        _valid_candle_provenance().replace(
            "candle_full_core_event_count=80", "candle_full_core_event_count=79"
        ),
        _valid_candle_provenance().replace(
            "candle_tail_event_count=20", "candle_tail_event_count=21"
        ),
        _valid_candle_provenance().replace(
            "candle_balanced_core_event_count=20",
            "candle_balanced_core_event_count=19",
        ),
        _valid_candle_provenance().replace(
            "candle_excluded_nonfinite_event_count=0",
            "candle_excluded_nonfinite_event_count=-1",
        ),
        _valid_candle_provenance().replace(
            "candle_balance_method=random_without_replacement",
            "candle_balance_method=first",
        ),
        _valid_candle_provenance().replace(
            "candle_balance_seed=20261024", "candle_balance_seed=-1"
        ),
        _valid_candle_provenance().replace(
            "candle_mass_source=raw_pre_fit", "candle_mass_source=fit"
        ),
        _valid_candle_provenance() + "\ncandle_unknown=value",
        "candle_mass_half_width_gev=0.05",
    ],
)
def test_contract_rejects_malformed_candle_provenance(tmp_path, provenance):
    output = tmp_path / "bad_candle.root"
    _write(output)
    _replace_provenance(output, provenance)

    with pytest.raises(RuntimeError, match="candle"):
        read_output_contract(output)


def test_best_binning_rejects_points_without_per_point_choice(tmp_path):
    output = tmp_path / "invalid_best.root"
    _write(output)
    source = ROOT.TFile(str(output), "UPDATE")
    ROOT.TNamed("provenance", "profile=uv\nphi_bins=best-binning\nphi_bin_divisor=per_point").Write()
    source.Close()
    with pytest.raises(RuntimeError, match="per-point phi_bins"):
        read_output_contract(output)


def test_legacy_root_without_phi_edges_is_read_as_twelve_bins(tmp_path):
    output = tmp_path / "legacy.root"
    _write(output)
    source = ROOT.TFile(str(output), "UPDATE")
    source.GetDirectory("binning").Delete("phi_edges;*")
    source.Close()
    contract = read_output_contract(output)
    np.testing.assert_allclose(contract.phi_edges_rad, np.linspace(0.0, 2.0 * np.pi, 13))
    assert contract.phi_bin_divisor == 1.0


def test_contract_reads_applied_phi_bin_divisor(tmp_path):
    output = tmp_path / "corrected.root"
    _write(output)
    source = ROOT.TFile(str(output), "UPDATE")
    source.Delete("provenance;*")
    ROOT.TNamed("provenance", "profile=uv\nphi_bin_divisor=0.9549").Write()
    source.Close()
    assert read_output_contract(output).phi_bin_divisor == 0.9549


@pytest.mark.parametrize("value", ["nan", "0", "-1", "0.9003", "bad", "0.9549\nphi_bin_divisor=0.9549"])
def test_contract_rejects_invalid_or_inconsistent_phi_bin_divisor(tmp_path, value):
    output = tmp_path / "bad_correction.root"
    _write(output)
    source = ROOT.TFile(str(output), "UPDATE")
    source.Delete("provenance;*")
    ROOT.TNamed("provenance", f"phi_bin_divisor={value}").Write()
    source.Close()
    with pytest.raises(RuntimeError, match="phi_bin_divisor"):
        read_output_contract(output)


@pytest.mark.parametrize("values", [[0.0, 1.0, 0.5], [0.0, float("nan")], [0.0]])
def test_root_contract_rejects_malformed_phi_edges(tmp_path, values):
    output = tmp_path / "bad_phi.root"
    _write(output)
    source = ROOT.TFile(str(output), "UPDATE")
    source.GetDirectory("binning").cd()
    source.GetDirectory("binning").Delete("phi_edges;*")
    vector = ROOT.TVectorD(len(values))
    for index, value in enumerate(values):
        vector[index] = value
    vector.Write("phi_edges")
    source.Close()
    with pytest.raises(RuntimeError, match="invalid binning/phi_edges"):
        read_output_contract(output)


def test_reader_rejects_missing_sigma_tree_with_path(tmp_path):
    output = tmp_path / "empty.root"
    source = ROOT.TFile(str(output), "RECREATE")
    source.Close()

    with pytest.raises(RuntimeError, match=r"empty\.root.*sigma_points"):
        read_output_points(output)


@pytest.mark.parametrize("mapping", [None, "not a valid mapping"])
def test_reader_rejects_missing_or_malformed_id_mapping(tmp_path, mapping):
    output = tmp_path / "bad_mapping.root"
    _write(output)
    source = ROOT.TFile(str(output), "UPDATE")
    source.Delete("id_mapping;*")
    if mapping is not None:
        ROOT.TNamed("id_mapping", mapping).Write()
    source.Close()

    with pytest.raises(RuntimeError, match=r"bad_mapping\.root.*id_mapping"):
        read_output_points(output)
