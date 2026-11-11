"""Period geometry and observed beam profiles must reach transport unchanged."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest
import uproot
from mc_simulation.geant4.root_output import read_json, read_table

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "03_mc_simulation/geant4"


def module():
    path = MODULE / "period_conditions.py"
    assert path.is_file(), "Missing Geant4 period conditions consumer"
    spec = importlib.util.spec_from_file_location("period_conditions", path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


@pytest.fixture
def published(tmp_path):
    products = tmp_path / "products"
    products.mkdir()
    archive = products / "run_plots.npz"
    np.savez(archive, period_test_x_edges_mm=[2., 4., 6.],
             period_test_y_edges_mm=[-2., 0., 2.],
             period_test_xy_probability=[[0., .25], [.75, 0.]])
    conditions = tmp_path / "conditions"
    conditions.mkdir()
    row = dict(status="diagnostic_approximation_not_applied", coverage_status="complete",
               geometry_status="compatible_lengths", weighting="equal_weight_per_valid_run",
               included_runs=[1, 2], excluded_runs=[3], missing_runs=[],
               target=dict(length_mm=111., center_z_mm=3., center_xy_mm=None,
                           diameter_mm=50., diameter_source="historical_reference_assumption_not_run_measurement",
                           material_label="P"),
               photon_beam_proxy=dict(available=True, profile_file="../products/run_plots.npz",
                                     archive_prefix="period_test_", probability_key="period_test_xy_probability",
                                     frame="native_h70_detector", units="mm",
                                     kind="equal_run_mean_observed_interaction_xy_not_unfolded_incident_beam"),
               limitations=["observed XY includes acceptance and resolution"])
    candidate = conditions / "geant4_candidates.json"
    candidate.write_text(json.dumps(dict(schema=2, periods={"test": row})))
    periods = conditions / "target_periods.csv"
    periods.write_text("period,target_labels,beam_labels\ntest,P,UV\n")
    publication = dict(schema=1, source_products="../products",
                       output_checksums={p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                         for p in (candidate, periods)},
                       source_checksums={archive.name: hashlib.sha256(archive.read_bytes()).hexdigest()})
    (conditions / "publication.json").write_text(json.dumps(publication))
    return conditions


def change_candidate(published, mutate):
    path = published / "geant4_candidates.json"
    payload = json.loads(path.read_text())
    mutate(payload["periods"]["test"])
    path.write_text(json.dumps(payload))
    publication = json.loads((published / "publication.json").read_text())
    publication["output_checksums"][path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    (published / "publication.json").write_text(json.dumps(publication))


def test_period_preserves_xy_offsets_weights_and_provenance(published, tmp_path):
    api = module()
    period = api.load_period(published, "test")
    assert period["xy_probability"] == [[0., .25], [.75, 0.]]
    assert period["x_edges_mm"] == [2., 4., 6.]
    output = tmp_path / "prepared"
    output.mkdir()
    api.write_inputs(period, output, MODULE / "reference/geometry.g3", seed=123)
    report = json.loads((output / "period.json").read_text())
    assert report["included_runs"] == [1, 2]
    assert report["seed"] == 123
    assert report["target"]["center_xy_mm"] == [0., 0.]
    assert report["target"]["length_mm"] == 111.
    assert report["source_hashes"]["run_plots.npz"]
    assert report["beam_type"] == "UV"
    assert report["beam_window_GeV"] == [1.1, 1.5]
    lines = (output / "conditions.dat").read_text().splitlines()
    assert lines[0].split() == ["GRAAL_PERIOD_V1", "test", "P", "111", "3", "50", "123"]
    assert [list(map(float, line.split())) for line in lines[1:]] == [
        [2., 4., 0., 2., .25], [4., 6., -2., 0., .75]]


def test_geometry_moves_caps_and_retracts_feed_tube(published, tmp_path):
    api = module()
    output = tmp_path / "prepared"
    output.mkdir()
    api.write_inputs(api.load_period(published, "test"), output, MODULE / "reference/geometry.g3", seed=7)
    lines = [line.split() for line in (output / "geometry.g3").read_text().splitlines()]
    target = next(row for row in lines if row[:2] == ["V", "CIBM"])
    assert list(map(float, target[5:])) == pytest.approx([0, 2.5, 5.55])
    cap = next(row for row in lines if row[:3] == ["P", "FEN3", "2"])
    assert float(cap[6]) == pytest.approx((3-55.5)/10-.006, abs=1e-8)
    tube = next(row for row in lines if row[:2] == ["V", "ENVI"])
    placement = next(row for row in lines if row[:2] == ["P", "ENVI"])
    assert float(placement[6])+float(tube[7]) == pytest.approx(float(cap[6])-.006, abs=1e-8)
    original = (MODULE / "reference/geometry.g3").read_text().splitlines()
    edited = (output / "geometry.g3").read_text().splitlines()
    changed = [a.split()[:3] for a, b in zip(original, edited) if a != b]
    assert len(original) == len(edited)
    assert len(changed) == 9


@pytest.mark.parametrize("mutate", [
    lambda r: r.update(geometry_status="no_valid_runs"),
    lambda r: r["target"].update(length_mm=None),
    lambda r: r["target"].update(material_label="P;D"),
    lambda r: r["photon_beam_proxy"].update(available=False),
    lambda r: r["photon_beam_proxy"].update(units="cm"),
])
def test_invalid_period_cannot_be_applied(published, mutate):
    change_candidate(published, mutate)
    with pytest.raises(ValueError):
        module().load_period(published, "test")


def test_changed_publication_or_archive_is_refused(published):
    api = module()
    path = published / "geant4_candidates.json"
    original = path.read_bytes()
    path.write_bytes(original+b" ")
    with pytest.raises(ValueError, match="checksum"):
        api.load_period(published, "test")
    path.write_bytes(original)
    archive = published.parent / "products/run_plots.npz"
    archive.write_bytes(archive.read_bytes()+b"changed")
    with pytest.raises(ValueError, match="checksum"):
        api.load_period(published, "test")


def test_unknown_period_and_invalid_seed_fail_before_build(published, tmp_path):
    with pytest.raises(ValueError, match="period"):
        module().load_period(published, "unknown")
    work = tmp_path / "new"
    result = subprocess.run([sys.executable, "-B", str(MODULE / "run.py"), "smoke",
                             "--period", "test", "--conditions", str(published),
                             "--seed", "0", "--work-dir", str(work)], capture_output=True, text=True)
    assert result.returncode != 0
    assert "seed" in result.stderr
    assert not work.exists()


@pytest.fixture
def native_period(published, tmp_path):
    transport, converter = os.environ.get("GRAAL_G4_EXE"), os.environ.get("GRAAL_GEOMETRY_EXE")
    if not transport or not converter:
        pytest.skip("Set GRAAL_G4_EXE and GRAAL_GEOMETRY_EXE for native period tests")
    api = module()
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    api.write_inputs(api.load_period(published, "test"), inputs, MODULE / "reference/geometry.g3", seed=123)
    geometry = tmp_path / "geometry"
    result = subprocess.run([converter, str(inputs / "geometry.g3"), str(geometry)],
                            text=True, capture_output=True, timeout=120)
    assert result.returncode == 0, result.stdout[-4000:] + result.stderr[-4000:]
    assert json.loads((geometry / "summary.json").read_text())["overlap_volumes"] == 0
    return transport, geometry / "geometry.gdml", inputs


def test_native_period_samples_xy_bins_and_uniform_cell_z(native_period, tmp_path):
    transport, gdml, inputs = native_period
    macro = tmp_path / "input.mac"
    macro.write_text("/run/initialize\n/gps/particle geantino\n/gps/energy 1 MeV\n"
                     "/gps/position 0 0 0 mm\n/gps/direction 0 0 1\n/run/beamOn 1000\n")
    for name in ("one", "two"):
        macro.write_text(f"/random/setSeeds {11 if name == 'one' else 99} 7\n"
                         "/run/initialize\n/gps/particle geantino\n/gps/energy 1 MeV\n"
                         "/gps/direction 0 0 1\n/run/beamOn 1000\n")
        result = subprocess.run([transport, str(gdml), str(macro), str(tmp_path/name),
                                 "--conditions", str(inputs / "conditions.dat")],
                                capture_output=True, text=True, timeout=120)
        assert result.returncode == 0, result.stdout[-4000:]+result.stderr[-4000:]
    assert read_table(tmp_path/"one/transport.root", "vertices") == read_table(tmp_path/"two/transport.root", "vertices")
    with uproot.open(tmp_path/"one/transport.root") as root:
        vertices = root["vertices"].arrays(library="np")
    assert len(vertices["x_mm"]) == 1000
    x, y, z = (vertices[key] for key in ("x_mm", "y_mm", "z_mm"))
    assert np.all(((2 <= x) & (x < 4) & (0 <= y) & (y < 2)) |
                  ((4 <= x) & (x < 6) & (-2 <= y) & (y < 0)))
    assert np.mean(x < 4) == pytest.approx(.25, abs=.05)
    assert z.min() >= 3-111/2 and z.max() <= 3+111/2
    assert z.mean() == pytest.approx(3, abs=4)
    summary = read_json(tmp_path/"one/transport.root")
    assert summary["period"] == "test" and summary["target"] == "hydrogen"
    materials = read_json(tmp_path/"one/transport.root", "materials")["materials"]
    hydrogen = next(row for row in materials if row["id"] == 1)
    assert hydrogen["density_g_cm3"] == pytest.approx(.0708)
    assert hydrogen["elements"][0]["isotopes"] == [{"A": 1, "abundance": 1}]


def test_native_refuses_conditions_geometry_mismatch(native_period, tmp_path):
    transport, gdml, inputs = native_period
    source = inputs / "conditions.dat"
    changed = tmp_path / "mismatch.dat"
    changed.write_text(source.read_text().replace("P 111 3 50", "P 112 3 50"))
    macro = tmp_path / "input.mac"
    macro.write_text("/run/initialize\n/run/beamOn 1\n")
    result = subprocess.run([transport, str(gdml), str(macro), str(tmp_path/"failed"),
                             "--conditions", str(changed)], text=True, capture_output=True, timeout=120)
    assert result.returncode != 0
    assert "do not match target solid" in result.stderr
    assert not (tmp_path/"failed/transport.root").exists()


def test_truth_beam_window_must_match_period(published):
    api = module()
    conditions = api.load_period(published, "test")
    assert hasattr(api, "validate_period_truth"), "Missing period/truth compatibility check"
    api.validate_period_truth(conditions, {"generation_target": "free_proton", "beam_window_GeV": [1.1, 1.4]})
    with pytest.raises(ValueError, match="beam"):
        api.validate_period_truth(conditions, {"generation_target": "free_proton", "beam_window_GeV": [.95, 1.1]})
    conditions["target"]["material_label"] = "D"
    with pytest.raises(ValueError, match="deuterium"):
        api.validate_period_truth(conditions, {"generation_target": "free_proton", "beam_window_GeV": [1.1, 1.4]})


@pytest.mark.parametrize("arrays", [
    dict(period_test_x_edges_mm=[2., 1., 6.], period_test_y_edges_mm=[-2., 0., 2.],
         period_test_xy_probability=[[0., .25], [.75, 0.]]),
    dict(period_test_x_edges_mm=[2., 4., 6.], period_test_y_edges_mm=[-2., 0., 2.],
         period_test_xy_probability=[[0., -.25], [1.25, 0.]]),
    dict(period_test_x_edges_mm=[2., 4., 6.], period_test_y_edges_mm=[-2., 0., 2.],
         period_test_xy_probability=[[1.]]),
])
def test_bad_histogram_refused_even_with_matching_checksum(published, arrays):
    archive = published.parent / "products/run_plots.npz"
    np.savez(archive, **arrays)
    path = published / "publication.json"
    publication = json.loads(path.read_text())
    publication["source_checksums"]["run_plots.npz"] = hashlib.sha256(archive.read_bytes()).hexdigest()
    path.write_text(json.dumps(publication))
    with pytest.raises(ValueError, match="histogram"):
        module().load_period(published, "test")


def test_native_records_rejection_of_xy_outside_nominal_cell(native_period, tmp_path):
    transport, gdml, inputs = native_period
    source = inputs / "conditions.dat"
    # One bin straddles the 25 mm radius. Clipping must preserve the actual
    # generated denominator while recording all rejected proxy draws.
    source.write_text(source.read_text().splitlines()[0]+"\n24 26 0 1 1\n")
    macro = tmp_path / "clipping.mac"
    macro.write_text("/run/initialize\n/gps/particle geantino\n/gps/energy 1 MeV\n"
                     "/gps/direction 0 0 1\n/run/beamOn 100\n")
    output = tmp_path / "clipped"
    result = subprocess.run([transport, str(gdml), str(macro), str(output),
                             "--conditions", str(source)], text=True, capture_output=True, timeout=120)
    assert result.returncode == 0, result.stderr[-4000:]
    with uproot.open(output/"transport.root") as root:
        vertices = root["vertices"].arrays(library="np")
    assert len(vertices["x_mm"]) == 100
    assert np.all(vertices["x_mm"]**2+vertices["y_mm"]**2 < 25**2)
    assert vertices["xy_attempts"].sum() > 100
