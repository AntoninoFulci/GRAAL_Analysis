"""Real native MT replay: ordered identities, RNG policy and stream offsets."""
import json
import os
from pathlib import Path
import subprocess

import numpy as np
import pytest
import uproot


@pytest.fixture(scope="module")
def replay():
    names = ("GRAAL_G4_EXE", "GRAAL_MT_GDML", "GRAAL_PERIOD_CONDITIONS", "GRAAL_MT_TRUTH")
    values = [os.environ.get(name) for name in names]
    if not all(values):
        pytest.skip("Set native MT replay binary, geometry, conditions and truth")
    return values


def run(replay, output, threads, storage="compact", env=None):
    binary, gdml, conditions, truth = replay
    return subprocess.run([binary, gdml, "--root-events", truth, str(output),
        "--conditions", conditions, "--storage", storage, "--threads", str(threads)],
        capture_output=True, text=True, timeout=240, env=env)


@pytest.mark.parametrize("threads", ["0", "-1", "bad", "2x", "2147483648"])
def test_invalid_threads_rejected_before_output(replay, tmp_path, threads):
    output = tmp_path / "bad"
    result = run(replay, output, threads)
    assert result.returncode != 0
    assert "threads" in result.stderr
    assert not output.exists()


def test_mt_reproducible_across_workers_and_storage(replay, tmp_path):
    paths = []
    for count, storage in [(1, "compact"), (2, "compact"), (4, "compact"), (2, "full")]:
        output = tmp_path / f"{count}-{storage}"
        result = run(replay, output, count, storage)
        assert result.returncode == 0, result.stdout[-2000:] + result.stderr[-4000:]
        assert {p.name for p in output.iterdir()} == {"transport.root"}
        paths.append(output / "transport.root")
        with uproot.open(paths[-1]) as f:
            summary = json.loads(str(f["summary"]))
            assert summary["execution_mode"] == "multithreaded"
            assert summary["threads"] == count and summary["event_modulo"] == 1
            assert summary["run_seed_policy"] == "geant4_mt_per_event"
            assert summary["aborted"] == 0
            n = summary["events"]
            assert n == summary["attempted_events"] == f["vertices"].num_entries
            np.testing.assert_array_equal(f["events/event"].array(library="np"), np.arange(n))
            c = f["cylinder_step_context"].arrays(library="np")
            np.testing.assert_array_equal(c["callback_index"], c["source_step_entry"] + c["passive_epoch"])
            assert np.all(np.diff(c["source_step_entry"].astype(np.int64)) > 0)
    with uproot.open(paths[0]) as a:
        for path in paths[1:3]:
            with uproot.open(path) as b:
                for name in a.keys(cycle=False):
                    if a[name].classname == "TTree":
                        for key in a[name].keys():
                            np.testing.assert_array_equal(a[name][key].array(library="np"),
                                                          b[name][key].array(library="np"), err_msg=f"{path}:{name}/{key}")
        with uproot.open(paths[-1]) as b:
            for name in ("events", "vertices", "primaries", "bgo_hits", "cylinder_step_context"):
                for key in a[name].keys():
                    np.testing.assert_array_equal(a[name][key].array(library="np"), b[name][key].array(library="np"))
            index = a["detector_steps/source_step_entry"].array(library="np")
            for key in a["detector_steps"].keys():
                if key != "source_step_entry":
                    np.testing.assert_array_equal(a["detector_steps"][key].array(library="np"),
                                                  b["detector_steps"][key].array(library="np")[index])


def test_mt_rejects_environment_thread_override(replay, tmp_path):
    output = tmp_path / "override"
    result = run(replay, output, 2, env=dict(os.environ, G4FORCENUMBEROFTHREADS="3"))
    assert result.returncode != 0
    assert "G4FORCENUMBEROFTHREADS" in result.stderr
    assert not (output / "transport.root").exists()


@pytest.mark.parametrize("mode", ["ordered", "failure"])
def test_ordered_writer_offsets_and_cancels_waiting_workers(replay, tmp_path, mode):
    binary = Path(replay[0]).with_name("graal_mt_writer_check")
    result = subprocess.run([str(binary), str(tmp_path), mode], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    if mode == "failure":
        assert not (tmp_path / "transport.root").exists()
        assert (tmp_path / "transport.partial.root").exists()
    else:
        with uproot.open(tmp_path / "transport.root") as f:
            c = f["cylinder_step_context"].arrays(library="np")
            np.testing.assert_array_equal(c["event"], [0,1])
            np.testing.assert_array_equal(c["source_step_entry"], [0,2])
            np.testing.assert_array_equal(c["callback_index"], [1,5])
            np.testing.assert_array_equal(c["passive_epoch"], [1,3])
            np.testing.assert_array_equal(f["detector_steps/source_step_entry"].array(library="np"), [0,2])


def test_worker_error_never_promotes_output_or_hangs(replay, tmp_path):
    binary, gdml, conditions, truth = replay
    failed = tmp_path / "conditions.dat"
    failed.write_text(Path(conditions).read_text().splitlines()[0] +
        "\n1000 1001 1000 1001 1\n0 1 0 1 1e-30\n")
    output = tmp_path / "failed"
    result = run([binary, gdml, str(failed), truth], output, 4)
    assert result.returncode != 0
    assert "rejection limit" in result.stderr
    assert not (output / "transport.root").exists()


def test_mt_preserves_events_without_sensitive_hits(replay, tmp_path):
    # Synthetic low-energy Compton final states stop in the target. This probes
    # empty detector tables, not reaction-generator provenance or efficiency.
    with uproot.open(replay[3]) as source:
        meta = json.loads(str(source["metadata"]))
    n, mass, energy = 4, .938272, 1e-6
    gamma = energy / (1 + energy / mass)
    meta["events"] = n
    truth = tmp_path / "empty-truth.root"
    with uproot.recreate(truth) as out:
        out["metadata"] = json.dumps(meta)
        types = dict(event="int32",source_entry="uint64",energy_GeV="float64",generation_weight="float64",nprimaries="int32")
        out.mktree("events", types).extend(dict(event=np.arange(n,dtype="int32"),
            source_entry=np.arange(n,dtype="uint64"),energy_GeV=np.full(n,energy),
            generation_weight=np.ones(n),nprimaries=np.full(n,2,dtype="int32")))
        rows = dict(event=np.repeat(np.arange(n,dtype="int32"),2),
                    primary_index=np.tile(np.array([0,1],dtype="int32"),n),
                    pdg=np.tile(np.array([2212,22],dtype="int32"),n))
        for key, values in dict(px=[-gamma,gamma],py=[0.,0.],pz=[energy,0.],
                                energy=[energy+mass-gamma,gamma],mass=[mass,0.]).items():
            rows[key+"_GeV"] = np.tile(np.array(values,dtype="float64"),n)
        out.mktree("primaries", {k:v.dtype for k,v in rows.items()}).extend(rows)
    output = tmp_path / "nohit"
    result = run([*replay[:3], str(truth)], output, 2)
    assert result.returncode == 0, result.stdout[-2000:] + result.stderr[-2000:]
    with uproot.open(output / "transport.root") as f:
        assert f["events"].num_entries == f["vertices"].num_entries == n
        assert f["primaries"].num_entries == 2*n
        assert f["detector_steps"].num_entries == 0
        assert f["cylinder_step_context"].num_entries == 0
        assert f["storage_events"].num_entries == n
        assert np.all(f["events/hit_steps"].array(library="np") == 0)
