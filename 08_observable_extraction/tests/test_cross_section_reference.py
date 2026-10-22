import json

import pytest
from observable_extraction.io.cross_section import load_reference


def reference_files(tmp_path):
    data = tmp_path / "points.csv"
    data.write_text("energy_gev,sigma_ub,error_ub\n1.1,1.2,0.1\n1.2,1.8,0.2\n")
    metadata = {
        "schema_version": 1,
        "observable": "total",
        "units": "ub",
        "energy_units": "GeV",
        "source": "https://doi.org/10.1103/PhysRevLett.100.052003",
        "figure": 2,
        "label": "Synthetic reference fixture",
        "data": "points.csv",
        "extraction": "synthetic test, not Ajaka numerical data",
        "errors": "published_total_including_systematics",
        "energy_bins": "centers_only",
        "digitization_uncertainty_ub": 0.01,
    }
    path = tmp_path / "reference.json"
    path.write_text(json.dumps(metadata))
    return path, metadata


def test_reference_loads_units_provenance_and_points(tmp_path):
    path, _ = reference_files(tmp_path)
    result = load_reference(path, {"observable": "total"})
    assert result["sigma_ub"] == [1.2, 1.8]
    assert len(result["inputs"]) == 2
    assert result["metadata"]["energy_bins"] == "centers_only"


@pytest.mark.parametrize(
    "field,value",
    [
        ("figure", 4),
        ("units", "ub/GeV"),
        ("observable", "sigma"),
        ("source", ""),
        ("digitization_uncertainty_ub", None),
    ],
)
def test_reference_rejects_wrong_quantity_or_missing_provenance(tmp_path, field, value):
    path, meta = reference_files(tmp_path)
    meta[field] = value
    path.write_text(json.dumps(meta))
    with pytest.raises(ValueError):
        load_reference(path, {"observable": "total"})


def test_reference_rejects_differential_unknown_energy_windows(tmp_path):
    path, _ = reference_files(tmp_path)
    with pytest.raises(ValueError, match="energy windows"):
        load_reference(path, {"observable": "p_pi0"})


def test_reference_rejects_nonfinite_points(tmp_path):
    path, _ = reference_files(tmp_path)
    (tmp_path / "points.csv").write_text("energy_gev,sigma_ub,error_ub\n1.1,nan,0.1\n")
    with pytest.raises(ValueError):
        load_reference(path, {"observable": "total"})


def test_unresolved_error_bars_remain_unknown(tmp_path):
    path, _ = reference_files(tmp_path)
    (tmp_path / "points.csv").write_text(
        "energy_gev,sigma_ub,error_ub,error_available\n1.1,1.2,,false\n1.2,1.8,0.2,true\n"
    )
    result = load_reference(path, {"observable": "total"})
    assert result["error_ub"] == [None, 0.2]
    assert result["error_available"] == [False, True]


def test_error_availability_must_match_values(tmp_path):
    path, _ = reference_files(tmp_path)
    (tmp_path / "points.csv").write_text(
        "energy_gev,sigma_ub,error_ub,error_available\n1.1,1.2,,true\n"
    )
    with pytest.raises(ValueError, match="availability"):
        load_reference(path, {"observable": "total"})


def test_figure3_explicit_nominal_overlay_preserves_local_windows(tmp_path):
    meta = {
        "schema_version": 1,
        "figure": 3,
        "observable": "invariant_mass",
        "units": "ub/MeV",
        "energy_units": "GeV",
        "mass_units": "GeV",
        "energy_bins": "nominal_centers_only",
        "errors": "not_resolvable_in_figure",
        "source": "synthetic",
        "label": "Synthetic Fig3",
        "extraction": "test",
        "digitization_uncertainty_ub_per_mev": 0.00001,
        "data": "points.csv",
    }
    path = tmp_path / "reference.json"
    path.write_text(json.dumps(meta))
    (tmp_path / "points.csv").write_text(
        "panel,row,pair,energy_gev,mass_gev,dsigma_ub_per_mev,error_ub_per_mev,error_available\n1,1,p_pi0,1.1,1.2,0.02,,false\n1,1,p_pi0,1.1,1.3,0.04,,false\n"
    )
    grid = {"observable": "p_pi0", "energy_edges_gev": [1.1, 1.15]}
    result = load_reference(path, grid, nominal_energies=[1.1])
    assert result["nominal_energies_gev"] == [1.1]
    assert result["analysis_energy_edges_gev"] == [1.1, 1.15]
    assert result["error_ub_per_mev"] == [None, None]
    with pytest.raises(ValueError, match="nominal"):
        load_reference(path, grid, nominal_energies=[1.2])


def test_checked_in_digitizations_load_without_inventing_errors():
    from pathlib import Path

    directory = Path(__file__).resolve().parents[1] / "references"
    total = load_reference(
        directory / "ajaka2008_figure2_manifest.json", {"observable": "total"}
    )
    assert len(total["sigma_ub"]) == 12
    assert sum(total["error_available"]) == 9
    mass = load_reference(
        directory / "ajaka2008_figure3_manifest.json",
        {
            "observable": "p_pi0",
            "energy_edges_gev": [1.05, 1.15, 1.25, 1.35, 1.45, 1.55],
        },
        nominal_energies=[1.1, 1.2, 1.3, 1.4, 1.5],
    )
    assert len(mass["dsigma_ub_per_mev"]) == 100
    assert not any(mass["error_available"])
    assert min(mass["dsigma_ub_per_mev"]) < 0
