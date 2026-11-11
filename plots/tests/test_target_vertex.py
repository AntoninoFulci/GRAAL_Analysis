"""Vertex geometry and raw association tests; no assumptions about target shape."""
import json
from pathlib import Path
import shutil
import subprocess

import awkward as ak
import numpy as np
import pytest
import uproot

from plots.core.vertex import closest_vertex, central_pairs
from plots.target_vertex import analyze


def test_intersection_requires_extrapolation_not_segment_clamping():
    result = closest_vertex([5, 0, 3], [8, 0, 3], [0, 5, 3], [0, 8, 3])
    assert result.status == "ok"
    assert result.xyz == pytest.approx([0, 0, 3])
    assert result.dca == pytest.approx(0)


def test_skew_lines_midpoint_and_swap_symmetry():
    a, b, c, d = [5, 0, 2], [8, 0, 2], [0, 5, 4], [0, 8, 4]
    result = closest_vertex(a, b, c, d)
    assert result.xyz == pytest.approx([0, 0, 3])
    assert result.dca == pytest.approx(2)
    assert result.sin2 == pytest.approx(1)
    assert closest_vertex(c, d, a, b).xyz == pytest.approx(result.xyz)


@pytest.mark.parametrize("points,status", [
    (([0, 0, 0], [1, 0, 0], [0, 1, 0], [1, 1, 0]), "parallel"),
    (([0, 0, 0], [1, 0, 0], [0, 1, 0], [1, 1+1e-8, 0]), "parallel"),
    (([0, 0, 0], [0, 0, 0], [0, 1, 0], [1, 1, 0]), "zero_length"),
    (([np.nan, 0, 0], [1, 0, 0], [0, 1, 0], [1, 1, 0]), "nonfinite"),
    (([-1000, 0, 0], [1, 0, 0], [0, 1, 0], [1, 1, 0]), "sentinel"),
])
def test_undefined_vertices_are_flagged_not_origin(points, status):
    result = closest_vertex(*points)
    assert result.status == status
    assert np.isnan(result.xyz).all()


def test_association_indices_are_one_based_and_deduplicated():
    # Columns are BGO, barrel, cylinder. Missing barrel and cylinder excluded.
    pairs, n = central_pairs([[1, 1, 3], [2, 2, 1], [3, 3, 3], [0, 0, 2], [4, 4, 0]], 3)
    assert n == 2
    assert pairs == [(0, 1)]  # association rows, not cylinder indices
    with pytest.raises(ValueError, match="cylinder"):
        central_pairs([[1, 1, 4]], 3)


def test_three_charges_keep_every_pair():
    assert central_pairs([[1, 1, 1], [2, 2, 2], [3, 3, 3]], 3) == ([(0, 1), (0, 2), (1, 2)], 3)


def test_shared_barrel_does_not_define_two_independent_charges():
    assert central_pairs([[1, 1, 1], [2, 1, 2]], 2) == ([], 2)


def test_matches_compiled_original_fortran_arithmetic(tmp_path):
    compiler = shutil.which("gfortran")
    original = Path(__file__).resolve().parents[2] / "docs/reference/fortran/pimdeu_2apr2009/src/vertex2.F"
    if not compiler or not original.is_file():
        pytest.skip("historical source and gfortran required for independent comparison")
    text = original.read_text()
    arithmetic = text[text.index("      AA = TR1X2"):text.index("      IF(IWHERE.eq.1)THEN", text.index("      AA = TR1X2"))]
    # Compile the unchanged arithmetic section, using original default REAL.
    driver = tmp_path / "reference.f"
    driver.write_text("""      PROGRAM CHECK_VERTEX
      REAL AA,BB,CC,DD,EE,FF,ALPHA,BETA,GAM,CHI,PSI,OMEGA
      REAL CSI,RO,DELTA,HMIN,TMIN,RX1,RX2,RY1,RY2,RZ1,RZ2
      REAL TR1X1,TR1X2,TR1Y1,TR1Y2,TR1Z1,TR1Z2
      REAL TR2X1,TR2X2,TR2Y1,TR2Y2,TR2Z1,TR2Z2
      DO
      READ(*,*,END=100) TR1X1,TR1Y1,TR1Z1,
     & TR1X2,TR1Y2,TR1Z2,TR2X1,TR2Y1,TR2Z1,
     & TR2X2,TR2Y2,TR2Z2
""" + arithmetic + """      WRITE(*,*) (RX1+RX2)/2,(RY1+RY2)/2,(RZ1+RZ2)/2
      END DO
 100  CONTINUE
      END
""")
    executable = tmp_path / "reference"
    subprocess.run([compiler, "-o", str(executable), str(driver)], check=True, capture_output=True)
    rng = np.random.default_rng(73)
    points = rng.uniform(-10, 10, (200, 4, 3)).astype("float32")
    points = [p for p in points if closest_vertex(*p).sin2 > .01]
    output = subprocess.run([str(executable)], input="\n".join(" ".join(map(str, p.ravel())) for p in points)+"\n",
                            text=True, capture_output=True, check=True).stdout
    expected = np.array([[float(x) for x in row.split()] for row in output.splitlines()])
    actual = np.array([closest_vertex(*p).xyz for p in points])
    np.testing.assert_allclose(actual, expected, atol=.002, rtol=1e-4)


def write_raw(path, *, missing=False):
    # Regular association dimensions in fixture; real h70 jagged layout is also
    # exercised by the local raw-data smoke run.
    payload = {"Idrun": np.array([42, 43, 42], dtype="uint32"),
               "Idevt": np.array([8, 9, 10], dtype="uint32"),
               "Nass_3": np.array([2, 2, 2], dtype="int32"),
               "Nb_traces_cyl": np.array([2, 2, 2], dtype="int32"),
               "Iass_3": np.array([[[1, 1, 2], [2, 2, 1]]] * 3, dtype="int32"),
               "Itipo_track": np.array([[14, 14]] * 3, dtype="int32")}
    for name, values in {"X_trace_int": [5, 0], "Y_trace_int": [0, 5],
                         "Z_trace_int": [3, 3], "X_trace_ext": [8, 0],
                         "Y_trace_ext": [0, 8], "Z_trace_ext": [3, 3]}.items():
        payload[name] = np.array([values] * 3, dtype="float32")
    if missing:
        del payload["X_trace_int"]
    with uproot.recreate(path) as f:
        f.mktree("h70", payload)


def test_raw_to_per_run_outputs_and_no_overwrite(tmp_path):
    raw = tmp_path / "raw.root"
    write_raw(raw)
    out = tmp_path / "output"
    summary = analyze([raw], out, max_entries=2, step_size=1)
    assert summary["runs"]["42"]["events_read"] == 1
    assert summary["runs"]["43"]["valid_pairs"] == 1
    with uproot.open(out / "vertices.root") as f:
        data = f["vertices"].arrays(library="np")
        assert data["source_entry"].tolist() == [0, 1]
        assert data["x_cm"] == pytest.approx([0, 0])
        assert data["z_cm"] == pytest.approx([3, 3])
        assert data["cylinder1"].tolist() == [2, 2]
    assert (out / "run_42.png").stat().st_size > 1000
    assert json.loads((out / "summary.json").read_text())["files"][0]["entries_read"] == 2
    with pytest.raises(FileExistsError):
        analyze([raw], out)


def test_missing_geometry_and_duplicate_sources_fail_without_partial_output(tmp_path):
    raw = tmp_path / "missing.root"
    write_raw(raw, missing=True)
    out = tmp_path / "output"
    with pytest.raises(ValueError, match="X_trace_int"):
        analyze([raw], out)
    assert not out.exists()
    with pytest.raises(ValueError, match="duplicate"):
        analyze([raw, raw], out)


def test_no_pairs_still_reports_run_and_writes_empty_tree(tmp_path):
    raw = tmp_path / "no_pairs.root"
    write_raw(raw)
    with uproot.open(raw) as f:
        payload = f["h70"].arrays(library="np")
    payload["Iass_3"][:, :, 1] = 0
    with uproot.recreate(raw) as f:
        f.mktree("h70", payload)
    out = tmp_path / "empty"
    summary = analyze([raw], out)
    assert summary["runs"]["42"]["events_read"] == 2
    assert summary["runs"]["42"]["display_inside_box"] == 0
    with uproot.open(out / "vertices.root") as f:
        assert f["vertices"].num_entries == 0
