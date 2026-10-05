"""Independent source audits and observable comparison contracts for PRC73."""

from dataclasses import replace
from importlib import import_module
import csv
import json
from pathlib import Path
from shutil import copytree

import numpy as np
import pytest


REFERENCES = Path(__file__).resolve().parents[1] / "references"
PDF_SHA = "19a2fbce10ed8201a29bdfbcfb9f3690a280d943c1e83db01aa1b2057d20eccb"


def _api():
    try:
        return import_module("graal_theory.full_production_validation")
    except ModuleNotFoundError:
        pytest.fail("Task 7 source-audited full-production validation is missing")


def _reference(api, *, x=(1.50, 1.51, 1.52), y=(10., 0., 10.),
               reading_error=(.5, .5, .5), unresolved=False):
    return api.ReferenceCurve(figure=12, curve="contact", family="chiral_contact",
        photon_energy_gev=1.2, observable="eta_p", x=np.array(x), y=np.array(y),
        reading_error=np.array(reading_error), unresolved=unresolved,
        ambiguity_note="unidentified crossing" if unresolved else "")


def _prediction(api, *, x=(1.50, 1.51, 1.52), y=(13., .61, 13.01),
                numerical_error=(.5, .1, .5), converged=(True, True, True)):
    return api.PredictionCurve(np.array(x), np.array(y), np.array(numerical_error),
                               np.array(converged))


def _metadata():
    return {"model": "EtaPi0PFullModel", "command": "python -m graal_theory.full_production_validation",
        "config": {"sobol_powers": [4, 5], "bins": 8, "quadrature": {
            "q_order": 64, "angle_order": 48, "relative_tolerance": 1e-5,
            "absolute_tolerance": 1e-10}}, "git_commit": "5b021a2" + "0"*33,
        "parameter_file_sha256": {"central_parameters.json": "a"*64},
        "pdf_sha256": PDF_SHA, "conventions": ["quoted eta-Delta sign"]}


def test_source_records_have_independent_audit_and_link_existing_points():
    api = _api()
    references = api.load_full_production_reference(REFERENCES)
    assert len(references) == 13
    assert {reference.figure for reference in references.values()} == {12, 13, 14, 19}
    metadata = json.loads((REFERENCES / "p73_full_production_curves.json").read_text())
    assert metadata["pdf_sha256"] == PDF_SHA
    assert metadata["curves"]["fig14_tree"]["source"]["filename"] == "figure14_eta_p_tree.csv"
    assert metadata["curves"]["fig19_full"]["source"]["filename"] == "figure19_total_1202.csv"
    with (REFERENCES / "p73_full_production_curves.csv").open(newline="") as stream:
        reader = csv.DictReader(stream)
        assert reader.fieldnames == ["figure", "curve", "x_gev", "y", "reading_error"]
        rows = list(reader)
    assert not {"fig14_tree", "fig19_full"} & {row["curve"] for row in rows}
    assert len({(row["figure"], row["curve"], row["x_gev"]) for row in rows}) == len(rows)
    for reference in references.values():
        assert np.all(np.diff(reference.x) > 0)
        assert np.all(np.isfinite(reference.reading_error))
        assert np.all(reference.reading_error >= 0)
    np.testing.assert_allclose(references["fig14_tree"].y[:3], [0., 12.8, 19.83])
    assert references["fig19_full"].x.tolist() == [1.202]
    assert references["fig19_full"].y.tolist() == [2.30]


@pytest.mark.parametrize("mutation,match", [
    ("hash", "hash"), ("line", "line"), ("columns", "columns"),
    ("duplicate", "increas|duplicate"), ("negative_error", "uncertainty|reading"),
    ("unknown_curve", "curve"), ("link_escape", "filename|path"),
])
def test_loader_rejects_corrupted_or_untraceable_source_records(tmp_path, mutation, match):
    api = _api()
    copytree(REFERENCES, tmp_path / "references")
    root = tmp_path / "references"
    metadata_path = root / "p73_full_production_curves.json"
    metadata = json.loads(metadata_path.read_text())
    csv_path = root / "p73_full_production_curves.csv"
    rows = csv_path.read_text().splitlines()
    if mutation == "hash":
        metadata["pdf_sha256"] = "0"*64
    elif mutation == "line":
        metadata["curves"]["fig12_contact"]["line_style"] = "solid"
    elif mutation == "columns":
        rows[0] += ",unexpected"
    elif mutation == "duplicate":
        rows.append(rows[1])
    elif mutation == "negative_error":
        columns = rows[1].split(",")
        columns[-1] = "-1"
        rows[1] = ",".join(columns)
    elif mutation == "unknown_curve":
        rows[1] = rows[1].replace("fig12_contact", "invented")
    else:
        metadata["curves"]["fig14_tree"]["source"]["filename"] = "../figure14_eta_p_tree.csv"
    metadata_path.write_text(json.dumps(metadata))
    csv_path.write_text("\n".join(rows)+"\n")
    with pytest.raises(ValueError, match=match):
        api.load_full_production_reference(root)


def test_deliberately_ambiguous_loaded_stroke_remains_unresolved(tmp_path):
    api = _api()
    copytree(REFERENCES, tmp_path / "references")
    path = tmp_path / "references" / "p73_full_production_curves.json"
    metadata = json.loads(path.read_text())
    metadata["curves"]["fig12_contact"].update(unresolved=True, ambiguity_note="stroke crossing cannot be identified")
    path.write_text(json.dumps(metadata))
    reference = api.load_full_production_reference(path.parent)["fig12_contact"]
    prediction = api.PredictionCurve(reference.x, reference.y, np.zeros_like(reference.y),
                                     np.ones_like(reference.y, dtype=bool))
    result = api.compare_full_production({"contact": prediction}, {"contact": reference})
    assert result.counts["unresolved"] == result.total == 5
    assert result.counts["compatible"] == 0


def test_additive_tolerance_includes_zero_reference_absolute_errors():
    api = _api()
    result = api.compare_full_production({"contact": _prediction(api)}, {"contact": _reference(api)})
    assert result.counts == {"compatible": 1, "discrepant": 2, "unresolved": 0,
                             "masked_nonconverged": 0}
    assert result.total == 3
    assert [point["tolerance"] for point in result.points] == [3., .6, 3.]
    assert [(point["family"], point["figure"], point["photon_energy_gev"])
            for point in result.points] == [("chiral_contact", 12, 1.2)]*3


def test_ambiguous_mapping_never_becomes_compatible_even_when_equal():
    api = _api()
    reference = _reference(api, unresolved=True)
    prediction = _prediction(api, y=reference.y)
    result = api.compare_full_production({"contact": prediction}, {"contact": reference})
    assert result.counts["unresolved"] == 3
    assert result.counts["compatible"] == 0
    assert all(point["reason"] == "unidentified crossing" for point in result.points)


def test_nonfinite_and_failed_convergence_are_masked_with_reasons():
    api = _api()
    prediction = _prediction(api, y=(np.nan, 0., 10.), converged=(True, False, True))
    result = api.compare_full_production({"contact": prediction}, {"contact": _reference(api)})
    assert result.counts["masked_nonconverged"] == 2
    assert "nonfinite" in result.points[0]["reason"]
    assert "convergence" in result.points[1]["reason"]
    assert result.points[0]["prediction"] is None


def test_interpolation_never_crosses_a_mask_and_excludes_outside_domain():
    api = _api()
    reference = _reference(api, x=(1.49, 1.505, 1.515, 1.525, 1.54),
        y=(10.,)*5, reading_error=(.5,)*5)
    prediction = _prediction(api, x=(1.50, 1.51, 1.52, 1.53), y=(10.,)*4,
        numerical_error=(0.,)*4, converged=(True, False, True, True))
    result = api.compare_full_production({"contact": prediction}, {"contact": reference})
    assert result.total == 3
    assert [point["status"] for point in result.points] == [
        "masked_nonconverged", "masked_nonconverged", "compatible"]
    assert all(point["prediction"] is None for point in result.points[:2])


def test_missing_diagnostic_does_not_silently_drop_reference_points():
    api = _api()
    result = api.compare_full_production({}, {"contact": _reference(api)})
    assert result.counts["unresolved"] == result.total == 3
    assert all("missing prediction" in point["reason"] for point in result.points)


def test_report_preserves_provenance_counts_and_atomic_prior_files(tmp_path):
    api = _api()
    result = api.compare_full_production({"contact": _prediction(api)}, {"contact": _reference(api)})
    metadata = _metadata()
    json_path, markdown_path = api.write_full_production_report(tmp_path, result, metadata)
    document = json.loads(json_path.read_text())
    assert document["metadata"] == metadata
    assert document["counts"] == result.counts
    assert sum(document["counts"].values()) == document["total"] == 3
    assert "chiral_contact" in markdown_path.read_text()
    assert "5b021a2" in markdown_path.read_text()
    prior = (json_path.read_bytes(), markdown_path.read_bytes())
    for invalid_result, invalid_metadata in (
        (replace(result, total=999), metadata),
        (result, {**metadata, "conventions": []}),
        (result, {**metadata, "pdf_sha256": "0"*64}),
        (result, {**metadata, "parameter_file_sha256": {"bad": "wrong"}}),
        (result, {**metadata, "git_commit": "not-a-commit"}),
        (result, {**metadata, "config": {**metadata["config"], "sobol_powers": [4, 4]}}),
        (result, {**metadata, "config": {**metadata["config"], "quadrature": {}}}),
    ):
        with pytest.raises(ValueError):
            api.write_full_production_report(tmp_path, invalid_result, invalid_metadata)
        assert (json_path.read_bytes(), markdown_path.read_bytes()) == prior
    assert sorted(path.name for path in tmp_path.iterdir()) == sorted([json_path.name, markdown_path.name])


def test_component_adapter_uses_real_eq43_diagnostic_without_changing_full_model():
    api = _api()
    from graal_theory.models.eta_pi0_p import EtaPi0PModel
    from graal_theory.models.eta_pi0_p_full import EtaPi0PFullModel
    from graal_theory.observables import HistogramSpec, predict_energy
    from graal_theory.phase_space import SobolConfig

    full = EtaPi0PFullModel.from_files(REFERENCES)
    diagnostic = api._SelectedModel(full, ("eq43_tree",))
    prediction = predict_energy(1.2, diagnostic, SobolConfig(4), HistogramSpec(8))
    tree = predict_energy(1.2, EtaPi0PModel(full.parameters.tree), SobolConfig(4), HistogramSpec(8))
    assert diagnostic.masses == full.masses
    assert diagnostic.parameters.proton_mass_gev == full.parameters.proton_mass_gev
    assert prediction.partial_cross_section_microbarn == pytest.approx(tree.partial_cross_section_microbarn, rel=1e-12)
    assert full.parameters.production.electric_charge != 0


def test_baseline_histogram_masks_use_consecutive_resolutions_and_physical_support():
    api = _api()
    from graal_theory.models.eta_pi0_p import EtaPi0PModel
    from graal_theory.observables import HistogramSpec, predict_energy
    from graal_theory.phase_space import SobolConfig

    model = EtaPi0PModel.from_files(REFERENCES / "central_parameters.json", REFERENCES / "sources.json")
    low = predict_energy(1.2, model, SobolConfig(4), HistogramSpec(8))
    high = predict_energy(1.2, model, SobolConfig(5), HistogramSpec(8))
    reference = _reference(api, x=(1.486, 1.50, 1.51, 1.52, 1.635),
        y=(0., 10., 10., 10., 0.), reading_error=(.5,)*5)
    prediction = api._histogram_prediction(low, high, reference)
    assert prediction.x[0] == low.histograms["eta_p"].edges[0]
    assert prediction.x[-1] == low.histograms["eta_p"].edges[-1]
    assert not np.all(prediction.converged)
    assert np.all(prediction.numerical_error >= 0)
    with pytest.raises(ValueError, match="consecutive"):
        api._histogram_prediction(low, low, reference)


def test_validation_cache_reuses_nested_events_without_changing_real_tree_weights():
    api = _api()
    from graal_theory.models.eta_pi0_p_full import EtaPi0PFullModel
    from graal_theory.phase_space import SobolConfig, sample_three_body

    model = EtaPi0PFullModel.from_files(REFERENCES)
    cached = api._CachedModel(model.parameters)
    low = sample_three_body(1.82, model.masses, SobolConfig(4))
    high = sample_three_body(1.82, model.masses, SobolConfig(5))
    low_weight = cached.selected_matrix_element_squared(low, ("eq43_tree",))
    high_weight = cached.selected_matrix_element_squared(high, ("eq43_tree",))
    np.testing.assert_allclose(low_weight, model.selected_matrix_element_squared(low, ("eq43_tree",)), rtol=1e-12)
    np.testing.assert_allclose(high_weight, model.selected_matrix_element_squared(high, ("eq43_tree",)), rtol=1e-12)
    assert cached.evaluated_event_families == 64  # 32 unique events, two polarizations.


def test_failed_baseline_keeps_source_points_masked_without_inventing_values():
    api = _api()
    reference = _reference(api)
    failed = api._failed_prediction(reference, "eta_delta: checked quadrature failure event=7")
    result = api.compare_full_production({"contact": failed}, {"contact": reference})
    assert result.counts["masked_nonconverged"] == result.total == 3
    assert all(point["prediction"] is None and "event=7" in point["reason"] for point in result.points)


def test_validation_cache_preserves_polarization_validation_on_cache_hits():
    api = _api()
    from graal_theory.models.eta_pi0_p_full import EtaPi0PFullModel
    from graal_theory.phase_space import SobolConfig, sample_three_body

    original = EtaPi0PFullModel.from_files(REFERENCES)
    cached = api._CachedModel(original.parameters)
    sample = sample_three_body(1.82, original.masses, SobolConfig(4))
    cached.selected_amplitude(sample, np.array([1., 0., 0.]), ("eq43_tree",))
    with pytest.raises(ValueError, match="polarization"):
        cached.selected_amplitude(sample, np.array([1.+1j, 0j, 0j]), ("eq43_tree",))


@pytest.mark.parametrize("field,invalid", [
    ("x", np.array([1.5+1j])),
    ("y", np.array([10.+100j])),
    ("numerical_error", np.array([0.+1j])),
    ("y", ["10"]),
    ("numerical_error", ["0"]),
    ("y", [True]),
    ("y", [True, 10.]),
    ("numerical_error", [False, 0.]),
    ("converged", [np.nan]),
    ("converged", ["false"]),
    ("converged", [1]),
    ("converged", [False, 1]),
    ("converged", np.array([True], dtype=object)),
    ("converged", [None]),
])
def test_malformed_raw_predictions_are_rejected_before_comparison(field, invalid):
    api = _api()
    size = len(invalid)
    arguments = {"x": np.array([1.50, 1.51][:size]), "y": np.full(size, 10.),
                 "numerical_error": np.zeros(size), "converged": np.ones(size, dtype=bool)}
    arguments[field] = invalid
    with pytest.raises(ValueError, match=f"prediction.{field}"):
        api.PredictionCurve(**arguments)


@pytest.mark.parametrize("field,invalid", [
    ("x", np.array([1.5+1j])),
    ("y", np.array([10.+100j])),
    ("reading_error", np.array([.5+1j])),
    ("y", ["10"]),
    ("reading_error", [True]),
])
def test_malformed_raw_reference_arrays_are_rejected_with_context(field, invalid):
    api = _api()
    arguments = {"x": [1.5], "y": [10.], "reading_error": [.5]}
    arguments[field] = invalid
    with pytest.raises(ValueError, match=f"reference.{field}"):
        api.ReferenceCurve(figure=12, curve="contact", family="chiral_contact",
            photon_energy_gev=1.2, observable="eta_p", **arguments)


@pytest.mark.parametrize("field", ["y", "numerical_error"])
@pytest.mark.parametrize("value", [np.nan, np.inf, -np.inf])
def test_nonfinite_real_predictions_stay_masked(field, value):
    api = _api()
    arguments = {"x": [1.5], "y": [10.], "numerical_error": [0.], "converged": [True]}
    arguments[field] = [value]
    prediction = api.PredictionCurve(**arguments)
    reference = _reference(api, x=(1.5,), y=(10.,), reading_error=(.5,))
    result = api.compare_full_production({"contact": prediction}, {"contact": reference})
    assert result.counts["masked_nonconverged"] == result.total == 1
    assert result.counts["compatible"] == 0
    assert "nonfinite" in result.points[0]["reason"]


@pytest.mark.parametrize("reference_id,wrong_observable", [
    ("fig12_contact", "total"), ("fig14_tree", "total"), ("fig19_full", "eta_p"),
])
def test_loader_rejects_a_supported_but_wrong_scientific_observable(tmp_path, reference_id, wrong_observable):
    api = _api()
    copytree(REFERENCES, tmp_path / "references")
    path = tmp_path / "references" / "p73_full_production_curves.json"
    metadata = json.loads(path.read_text())
    metadata["curves"][reference_id]["observable"] = wrong_observable
    path.write_text(json.dumps(metadata))
    with pytest.raises(ValueError, match=f"{reference_id}.*observable"):
        api.load_full_production_reference(path.parent)


@pytest.mark.parametrize("bad_units", [
    {"x_gev": "MeV", "eta_p": "microbarn/GeV", "total": "microbarn"},
    {"x_gev": "GeV", "eta_p": "nanobarn/GeV", "total": "microbarn"},
    {"x_gev": "GeV", "eta_p": "microbarn/GeV", "total": "nanobarn"},
    {"x_gev": "GeV", "eta_p": "microbarn/GeV"},
    {"x_gev": "GeV", "eta_p": "microbarn/GeV", "total": "microbarn", "extra": "1"},
    {}, None,
])
def test_loader_requires_the_exact_scientific_unit_registry(tmp_path, bad_units):
    api = _api()
    copytree(REFERENCES, tmp_path / "references")
    path = tmp_path / "references" / "p73_full_production_curves.json"
    metadata = json.loads(path.read_text())
    metadata["units"] = bad_units
    path.write_text(json.dumps(metadata))
    with pytest.raises(ValueError, match="unit"):
        api.load_full_production_reference(path.parent)


def test_generated_convention_metadata_reports_the_sourced_pion_monopole_cutoff(tmp_path):
    api = _api()
    from graal_theory.models.eta_pi0_p_full import EtaPi0PFullModel

    model = EtaPi0PFullModel.from_files(REFERENCES)
    result = api.compare_full_production({"contact": _prediction(api)}, {"contact": _reference(api)})
    metadata = _metadata()
    metadata["conventions"] = api._baseline_conventions(model.parameters)
    path, markdown_path = api.write_full_production_report(tmp_path, result, metadata)
    conventions = json.loads(path.read_text())["metadata"]["conventions"]
    expected = "Pion monopole form-factor cutoff Lambda_pi=1.25 GeV."
    assert expected in conventions
    assert expected in markdown_path.read_text()
    varied = replace(model.parameters, production=replace(model.parameters.production,
                     pion_form_factor_cutoff_gev=1.3))
    assert "Pion monopole form-factor cutoff Lambda_pi=1.3 GeV." in api._baseline_conventions(varied)
