"""Portable launcher failures must preserve inputs and fail before building."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "03_mc_simulation/geant4/run.py"


def test_launcher_refuses_existing_work_directory(tmp_path):
    sentinel = tmp_path / "keep"
    sentinel.write_text("untouched")
    result = subprocess.run([sys.executable, "-B", str(SCRIPT), "geometry",
                             "--work-dir", str(tmp_path)], capture_output=True, text=True)
    assert result.returncode != 0
    assert "refusing overwrite" in result.stderr
    assert sentinel.read_text() == "untouched"


def test_external_spack_environment_and_spec_are_forwarded(tmp_path, monkeypatch):
    assert SCRIPT.is_file(), "Portable Geant4 launcher is missing"
    spec = importlib.util.spec_from_file_location("geant4_run", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    prefix = tmp_path / "installed Geant4"
    (prefix / "lib/cmake/Geant4").mkdir(parents=True)
    log = tmp_path / "spack-args"
    spack = tmp_path / "spack"
    spack.write_text(f'#!{sys.executable}\nimport pathlib, sys\n'
                     f'pathlib.Path({str(log)!r}).write_text(repr(sys.argv[1:]))\n'
                     f'print({str(prefix)!r})\n')
    spack.chmod(0o755)
    monkeypatch.delenv("GEANT4_PREFIX", raising=False)
    monkeypatch.delenv("Geant4_DIR", raising=False)
    monkeypatch.setenv("SPACK_BIN", str(spack))
    monkeypatch.setenv("SPACK_ENV", str(tmp_path / "external env"))
    monkeypatch.setenv("SPACK_SPEC", "/specific-hash")
    monkeypatch.setenv("PATH", "")
    assert module.find_geant4(None) == prefix / "lib/cmake/Geant4"
    assert log.read_text() == repr(["-e", str(tmp_path / "external env"),
                                   "location", "-i", "/specific-hash"])


def test_explicit_prefix_does_not_need_spack(tmp_path, monkeypatch):
    assert SCRIPT.is_file(), "Portable Geant4 launcher is missing"
    spec = importlib.util.spec_from_file_location("geant4_run", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    config = tmp_path / "lib64/cmake/Geant4"
    config.mkdir(parents=True)
    monkeypatch.setenv("PATH", "")
    assert module.find_geant4(tmp_path) == config


def test_replay_checks_hashes_before_building(tmp_path):
    spec = importlib.util.spec_from_file_location("geant4_run", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    primary, mapping = tmp_path / "primaries.dat", tmp_path / "truth.csv"
    primary.write_text("2\n1 2212 0 0 0 0 0 .938272\n1 22 0 0 .2 0 0 0\n")
    mapping.write_text("event,source_entry,beam_energy_GeV,generation_weight\n0,0,1.5,1\n")
    report = {"schema_version": 1, "status": "diagnostic_truth_export", "units": "GeV",
              "vertex_mm": [0, 0, 0], "time_ns": 0, "generation_target": "free_proton",
              "geometry_target": "deuterium_diagnostic_only", "polarization": "not_modeled",
              "weight_policy": "unit_unweighted_no_flux_or_cross_section_normalization",
              "events": 1, "source_events": 2, "primary_sha256": module.digest(primary),
              "mapping_sha256": module.digest(mapping), "channel": "eta_pi0",
              "generator": "generate_eta_pi0_dataset", "generator_schema_version": 1,
              "sampling": "accept-reject-unweighted; TRandom3 shared with TGenPhaseSpace",
              "seed": 71, "beam_window_GeV": [1.5, 1.6], "source": "eta_pi0_mc.root",
              "source_uuid": "00000000-0000-0000-0000-000000000001", "source_sha256": "a" * 64,
              "generator_root_version": "6.40.04"}
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps(report))
    assert module.validate_truth(tmp_path) == report
    for key in ("source", "source_sha256", "source_uuid", "generator", "seed", "beam_window_GeV"):
        manifest.write_text(json.dumps({k: v for k, v in report.items() if k != key}))
        with pytest.raises(ValueError, match="provenance"):
            module.validate_truth(tmp_path)
    manifest.write_text(json.dumps(report))
    primary.write_text(primary.read_text() + "junk\n")
    work = tmp_path / "new"
    result = subprocess.run([sys.executable, "-B", str(SCRIPT), "replay", "--truth-dir", str(tmp_path),
                             "--work-dir", str(work)], capture_output=True, text=True)
    assert result.returncode != 0 and "hash mismatch" in result.stderr
    assert not work.exists()
    report["events"] = 3
    manifest.write_text(json.dumps(report))
    with pytest.raises(ValueError, match="counts"):
        module.validate_truth(tmp_path)
