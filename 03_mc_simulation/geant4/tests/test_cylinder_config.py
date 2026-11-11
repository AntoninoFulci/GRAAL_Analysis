"""Selected26 OLD_CYL config is a separate source-backed ROOT boundary."""
import importlib.util
from pathlib import Path
import struct

import pytest

ROOT = Path(__file__).resolve().parents[3]
MODULE = ROOT / "03_mc_simulation/geant4/cylinder_config.py"
DATA = ROOT / "docs/reference/fortran/prog/data"


def module():
    spec = importlib.util.spec_from_file_location("cylinder_config", MODULE)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def test_selected26_source_and_distinct_half_lengths():
    c = module().read_selected26_cylinder(DATA)
    assert (c["rc1_cm"], c["rc2_cm"], c["zc1_cm"], c["zc2_cm"]) == (5, 8.5, 20, 25.25)
    assert c["tracking_profile"]["half_lengths_cm"] == [19.5, 24.75]
    assert c["nbord"] == 2 and [c[f"nb{i}"] for i in range(1, 5)] == [60, 64, 96, 96]
    assert c["conv"] == struct.unpack("f", struct.pack("f", 16e10))[0]
    assert len(c["sources"]) >= 10 and not c["physical_validation"]
    assert c["baseline"] == ["GRAAL_26", "GRAAL_NEW_PLAN", "GRAAL_OLD_CYL"]


def test_strict_source_fields(tmp_path):
    m = module()
    (tmp_path / "base").mkdir()
    original = (DATA / "base/data26.base").read_text()
    target = tmp_path / "base/data26.base"
    for before, after in [("!RC1", "!XX1"), ("00320", "00321"),
                          (" 0.13           !SIGCT", " -0.13          !SIGCT"),
                          ("1.00            !EFFCYC(1)", "1.01            !EFFCYC(1)")]:
        target.write_text(original.replace(before, after, 1))
        with pytest.raises(ValueError):
            m.read_selected26_cylinder(tmp_path)
    assert m._f15_3("123            ") == struct.unpack("f", struct.pack("f", .123))[0]
    assert m._f15_3("1E3            ") == 1
    with pytest.raises(ValueError): m._f15_3("nan            ")


def test_root_roundtrip_no_overwrite(tmp_path):
    uproot = pytest.importorskip("uproot")
    m = module()
    output = tmp_path / "config.root"
    c = m.write_cylinder_config(DATA, output)
    with uproot.open(output) as f:
        assert f["scalars"].num_entries == 1
        assert f["scalars"]["nb4"].array(library="np")[0] == 96
        assert f["scalars"]["conv"].array(library="np")[0] == c["conv"]
        assert "selected26_old_cyl" in str(f["metadata"])
    with pytest.raises(FileExistsError): m.write_cylinder_config(DATA, output)
