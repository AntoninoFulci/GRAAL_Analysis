import json

import pytest
from mc_simulation.geant3 import IMAGE, docker_command, prepare_response


def test_geant3_run_is_isolated_and_digest_pinned(tmp_path):
    card = tmp_path / "input.dat"
    card.write_text("TRIG 2\nSTOP\n")
    command = docker_command(card, tmp_path / "output", "old", "graal-test")
    assert IMAGE in command and "@sha256:" in IMAGE
    assert command[command.index("--platform") + 1] == "linux/386"
    assert command[command.index("--network") + 1] == "none"
    assert "--privileged" not in command
    assert "--read-only" in command
    assert "/home/gmandaglio/graal/software/prog/laggen/laggen_oc" in command
    assert not any("docker.sock" in x for x in command)
    with pytest.raises(ValueError):
        docker_command(card, tmp_path / "output", "guess", "graal-test")


def test_prepare_response_records_all_generated_and_input_hashes(tmp_path):
    (tmp_path / "generated.csv").write_text("event_id,cell\n1,0\n2,0\n3,1\n4,1\n")
    (tmp_path / "selected.csv").write_text("event_id,cell\n1,0\n3,1\n")
    metadata = {
        "schema_version": 1,
        "grid": {
            "energy_edges_gev": [1.1, 1.2],
            "phi_edges_rad": [0, 3.141592653589793, 6.283185307179586],
            "observable": "total",
            "mass_edges_gev": None,
        },
        "selection_signature": "a" * 64,
        "provenance": {
            "simulator": "GEANT3",
            "geometry": "test",
            "independent_of_training": True,
            "generated_complete": True,
            "migration_domain": "closed",
            "decays": "forced_gamma_gamma",
            "validation": "not validated",
        },
    }
    (tmp_path / "metadata.json").write_text(json.dumps(metadata))
    out = tmp_path / "response.json"
    result = prepare_response(
        tmp_path / "generated.csv",
        tmp_path / "selected.csv",
        tmp_path / "metadata.json",
        out,
    )
    assert result["generated"] == [2, 2]
    assert result["selected"] == [[1, 0], [0, 1]]
    assert len(result["input_identities"]) == 3
    assert len(result["sample_id"]) == 64
    with pytest.raises(FileExistsError):
        prepare_response(
            tmp_path / "generated.csv",
            tmp_path / "selected.csv",
            tmp_path / "metadata.json",
            out,
        )


def test_prepare_response_rejects_truncated_truth_or_unknown_identity(tmp_path):
    (tmp_path / "generated.csv").write_text("event_id,cell\n1,0\n")
    (tmp_path / "selected.csv").write_text("event_id,cell\n2,0\n")
    metadata = {
        "schema_version": 1,
        "grid": {
            "energy_edges_gev": [1, 2],
            "phi_edges_rad": [0, 6.283185307179586],
            "observable": "total",
            "mass_edges_gev": None,
        },
        "selection_signature": "a" * 64,
        "provenance": {
            "simulator": "GEANT3",
            "geometry": "test",
            "independent_of_training": True,
            "generated_complete": True,
            "migration_domain": "closed",
            "decays": "inclusive",
            "validation": "test",
        },
    }
    (tmp_path / "metadata.json").write_text(json.dumps(metadata))
    with pytest.raises(ValueError, match="absent"):
        prepare_response(
            tmp_path / "generated.csv",
            tmp_path / "selected.csv",
            tmp_path / "metadata.json",
            tmp_path / "out.json",
        )
    assert not (tmp_path / "out.json").exists()


def test_run_rejects_fortran_stop_with_zero_exit(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from mc_simulation.geant3 import run_geant3

    card = tmp_path / "card.dat"
    card.write_text("TRIG 2\nSTOP\n")
    output = tmp_path / "run"

    def stopped(command, **kwargs):
        (output / "out_laggen/sample.hit").write_bytes(bytes(48))
        kwargs["stdout"].write("File FLUKAAF.DAT not found\nProgram STOP\n")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr("mc_simulation.geant3.subprocess.run", stopped)
    with pytest.raises(RuntimeError, match="failed"):
        run_geant3(card, output, "old")
    assert json.loads((output / "run.json").read_text())["status"] == "failed"
