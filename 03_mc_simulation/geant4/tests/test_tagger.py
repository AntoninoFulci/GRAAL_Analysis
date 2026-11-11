"""Recovered TAG/PREAN oracle, exact histogram payload and fail-closed ledger."""
import json
import os
from pathlib import Path
import shutil
import subprocess

import numpy as np
import pytest
import uproot

REPO = Path(__file__).resolve().parents[3]
G4 = REPO / "03_mc_simulation/geant4"
ARCHIVE = REPO / "docs/reference/fortran/prog"
CAMPAIGN = REPO / "results_test/geant4-selection-inputs-20261110/tagger-work"
from mc_simulation.geant4 import tagger


@pytest.fixture(scope="module")
def oracle(tmp_path_factory):
    compiler = shutil.which("gfortran")
    if not compiler:
        pytest.skip("gfortran required for preserved-source oracle")
    work = tmp_path_factory.mktemp("tagger-oracle")
    (work / "pilot.h").write_text("#define GRAAL_LINUX\n")
    (work / "GRAAL_machine.h").write_text("/* controlled diagnostic machine */\n")
    sources = []
    for component, names in (("lagdig", ("tag",)), ("prean", ("anastrip_tag", "swap_strip", "eg_tag_sim"))):
        target = work / component
        target.mkdir()
        for name in names:
            shutil.copyfile(ARCHIVE / component / "src" / f"{name}.F", target / f"{name}.F")
            sources.append(target / f"{name}.F")
        for include in (ARCHIVE / component / "include").glob("*.inc"):
            shutil.copyfile(include, target / include.name)
    executable = work / "oracle"
    result = subprocess.run([compiler, "-cpp", "-O0", "-ffixed-line-length-none", "-fno-fast-math",
                             "-ffp-contract=off", "-I"+str(work), "-I"+str(work / "prean"),
                             str(G4 / "tests/tagger_oracle.F"), *map(str, sources), "-o", str(executable)],
                            capture_output=True, text=True,
                            env=dict(os.environ, MACOSX_DEPLOYMENT_TARGET="15.0"))
    assert result.returncode == 0, result.stderr
    return executable


def test_preserved_tag_and_prean_oracle(oracle):
    rng = np.random.default_rng(721)
    cases = [(run, energy, displacement) for run in (1321, 3172, 3173, 4511, 4512, 4580)
             for energy, displacement in zip(rng.uniform(.1, 2.1, 250), rng.uniform(-3, 3, 250))]
    cases += [(1321, e, 0.) for e in (.15, .15001, .2499, .25, .35, 1.85, 1.94999, 1.95)]
    config = tagger.read_config(1321)
    base = tagger.respond(1., 0., config).position_mm
    cases += [(run, 1., float(np.float32(config["offset_mm"] + (strip-.5)*config["pitch_mm"] - base)))
              for run in (1321, 3173, 4580) for strip in range(1, 129)]
    result = subprocess.run([str(oracle)], input="".join(f"{run} {e:.17g} {d:.17g}\n" for run, e, d in cases),
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    rows = result.stdout.splitlines()
    assert len(rows) == len(cases)
    for (run, energy, displacement), line in zip(cases, rows):
        ident, digit, count, strip, measured = map(float, line.split())
        modern = tagger.respond(energy, displacement, tagger.read_config(run))
        assert modern.histogram_id == ident
        assert modern.digit == digit
        assert int(modern.status == 0) == count
        if count:
            assert modern.xstrip == strip
            assert modern.energy_GeV == measured


def test_original_upper_aperture_stop_is_unavailable(oracle):
    config = tagger.read_config(1321)
    base = tagger.respond(1., 0., config).position_mm
    endpoint = np.float32(np.float32(config["offset_mm"]) + np.float32(config["length_mm"]))
    displacement = float(np.float32(endpoint - np.float32(base)))
    result = subprocess.run([str(oracle)], input=f"1321 1. {displacement:.17g}\n", capture_output=True, text=True)
    assert "Pb with NTAG" in result.stderr
    assert not result.stdout.strip()
    assert tagger.respond(1., displacement, config).status == 5


def test_source_domains_and_aperture():
    c = tagger.read_config(1321)
    assert tagger.histogram_id(.15001) == 101  # INT is not floor.
    assert tagger.histogram_id(.15) == 100
    assert tagger.histogram_id(.25) == 101
    assert tagger.histogram_id(1.95) == 118
    assert tagger.respond(float("nan"), 0, c).status == 4
    assert tagger.respond(1., float("inf"), c).status == 4
    assert tagger.respond(.1, 0, c).status == 3
    assert tagger.respond(1., -100, c).status == 1
    assert tagger.respond(1., -100, c).available
    base = np.float32(np.float32(c["a0_mm"]) * np.float32(1.) / np.float32(np.float32(c["ee_GeV"])-1.))
    lower = np.float32(c["offset_mm"])
    upper = np.float32(lower + np.float32(c["length_mm"]))
    assert tagger.respond(1., float(np.float32(lower-base)), c).digit == 1
    endpoint = tagger.respond(1., float(np.float32(upper-base)), c)
    assert endpoint.status == 5 and endpoint.digit == 129 and not endpoint.available


def test_histogram_cdf_sampling():
    class FixedRandom:
        def __init__(self, values):
            self.values = iter(values)
        def random(self):
            return next(self.values)
    histogram = np.array([0., 1., 3., 0.]), np.array([-2., -1., 0., 1., 2.])
    assert tagger.sample_displacement(histogram, FixedRandom([0., .5])) == -.5
    assert tagger.sample_displacement(histogram, FixedRandom([.25, .5])) == .5
    assert tagger.sample_displacement(histogram, FixedRandom([np.nextafter(1., 0.), 0.])) == 0.
    a, b = np.random.default_rng(32), np.random.default_rng(32)
    assert [tagger.sample_displacement(histogram, a) for _ in range(20)] == [tagger.sample_displacement(histogram, b) for _ in range(20)]


@pytest.fixture
def histogram_root(tmp_path, monkeypatch):
    source = ARCHIVE / "data/simul_beam/tag.hist"
    path = tmp_path / "hist.root"
    # Isolate ledger tests with an explicitly synthetic response payload.
    synthetic = {ident: (np.array([1.]), np.array([-.01, .01], dtype="float32").astype("float64")) for ident in range(101, 118)}
    monkeypatch.setattr(tagger, "HISTOGRAM_PAYLOAD_SHA256", tagger.histogram_payload_sha256(synthetic))
    with uproot.create(path) as root:
        root["metadata"] = json.dumps(dict(mode="exact_hbook_tagger_response", source_sha256=tagger.sha256(source),
                                           source_histogram_ids=list(range(101, 118)), displacement_unit="mm"))
        for ident in range(101, 118):
            root[f"response_{ident}"] = synthetic[ident]
    return path


def transport(path):
    with uproot.create(path) as root:
        root["summary"] = json.dumps(dict(status="diagnostic_transport_only", hit_schema_version=2,
                                           output_format="ROOT_TTree", events=4, attempted_events=4, aborted=0))
        tagger._write_table(root, "events", dict(run="int32", event="int32", aborted="int32"),
                            [dict(run=0, event=i, aborted=0) for i in range(4)])


@pytest.mark.parametrize('compact', [False, True])
def test_all_event_missing_beam_and_provenance(tmp_path, histogram_root, compact):
    source = tmp_path / "transport.root"
    transport(source)
    if compact:
        from tests.test_geant4_compact_summary import mark_compact
        mark_compact(source)
    output = tagger.reconstruct(source, None, histogram_root, tmp_path / "out", acquisition_run=1321, seed=15)
    with uproot.open(output) as root:
        assert root["tagger_events"].num_entries == 4
        assert root["tagger_clusters"].num_entries == 0
        assert root["tagger_events/status"].array(library="np").tolist() == [2]*4
        assert root["tagger_events/available"].array(library="np").tolist() == [0]*4
        assert root["tagger_events/source_entry"].array(library="np").tolist() == list(range(4))
    with uproot.open(output.with_name("provenance.root")) as root:
        meta = json.loads(str(root["metadata"]))
        assert meta["result_sha256"] == tagger.sha256(output)
        assert meta["transport_sha256"] == tagger.sha256(source)
    with pytest.raises(FileExistsError):
        tagger.reconstruct(source, None, histogram_root, tmp_path / "out", acquisition_run=1321, seed=15)


def test_compact_storage_metadata_required_before_tagger_publication(tmp_path, histogram_root):
    from tests.test_geant4_compact_summary import mark_compact
    source = tmp_path/'transport.root'
    transport(source)
    mark_compact(source, summary_changes={'stored_detector_steps': True})
    with pytest.raises(ValueError, match='compact storage count'):
        tagger.reconstruct(source, None, histogram_root, tmp_path/'out', acquisition_run=1321, seed=15)
    assert not (tmp_path/'out').exists()


def test_beam_identity_and_response(tmp_path, histogram_root):
    source = tmp_path / "transport.root"
    transport(source)
    beam_source = tmp_path / "beam_source.root"
    with uproot.create(beam_source) as root:
        root["metadata"] = "synthetic test incident beam, not transport truth"
    beam = tmp_path / "beam.root"
    def write_beam(order):
        with uproot.recreate(beam) as root:
            root["metadata"] = json.dumps(dict(role="incident_beam_response_input", transport_path=str(source),
                transport_sha256=tagger.sha256(source), source_sha256={str(beam_source): tagger.sha256(beam_source)}))
            tagger._write_table(root, "beam_events", dict(run="int32", event="int32", source_entry="uint64", energy_GeV="float64"),
                                [dict(run=0, event=i, source_entry=i, energy_GeV=e)
                                 for i, e in zip(order, (1., .25, 1.95, float("nan")))])
    write_beam([0, 1, 2, 3])
    output = tagger.reconstruct(source, beam, histogram_root, tmp_path / "out", acquisition_run=1321, seed=15)
    with uproot.open(output) as root:
        assert root["tagger_events/status"].array(library="np").tolist() == [0, 1, 3, 4]
        assert root["tagger_events/available"].array(library="np").tolist() == [1, 1, 0, 0]
        assert root["tagger_clusters"].num_entries == 1
        assert root["tagger_clusters/xstrip"].array(library="np").tolist() == [26.]
    write_beam([1, 0, 2, 3])
    with pytest.raises(ValueError, match="source order"):
        tagger.reconstruct(source, beam, histogram_root, tmp_path / "bad", acquisition_run=1321, seed=15)
    assert not (tmp_path / "bad").exists()


def test_recovered_archive_if_present():
    path = Path(os.environ.get("GRAAL_TAGGER_HISTOGRAM_ROOT", CAMPAIGN / "tagger_histograms.root"))
    if not path.exists():
        pytest.skip("Exact HBOOK extraction is a campaign artifact")
    histograms, metadata = tagger.read_histograms(path)
    assert metadata["source_sha256"] == tagger.sha256(ARCHIVE / "data/simul_beam/tag.hist")
    assert len(histograms) == 17
    for values, edges in histograms.values():
        assert len(values) == 200
        assert edges[0] == -3. and edges[-1] == 3.
        assert values.sum() > 0


@pytest.mark.parametrize("mutation", ("summary", "gaps", "duplicate_json", "rntuple"))
def test_malformed_transport_fails_closed(tmp_path, histogram_root, mutation):
    source = tmp_path / "transport.root"
    summary = dict(status="diagnostic_transport_only", hit_schema_version=2,
                   output_format="ROOT_TTree", events=4, attempted_events=4, aborted=0)
    if mutation == "summary":
        summary["attempted_events"] = 5
    rows = [dict(run=0, event=i, aborted=0) for i in (0, 1, 2, 4) if mutation == "gaps"]
    if not rows:
        rows = [dict(run=0, event=i, aborted=0) for i in range(4)]
    with uproot.create(source) as root:
        root["summary"] = json.dumps(summary) if mutation != "duplicate_json" else '{"events":4,"events":4}'
        if mutation == "rntuple":
            root["events"] = {k: np.array([r[k] for r in rows], dtype="int32") for k in rows[0]}
        else:
            tagger._write_table(root, "events", dict(run="int32", event="int32", aborted="int32"), rows)
    with pytest.raises(ValueError):
        tagger.reconstruct(source, None, histogram_root, tmp_path / "out", acquisition_run=1321, seed=15)
    assert not (tmp_path / "out").exists()


def test_substituted_histogram_is_rejected(tmp_path, histogram_root, monkeypatch):
    monkeypatch.setattr(tagger, "HISTOGRAM_PAYLOAD_SHA256", "acd41e1862942e22beab9110bedebbda24951146bd7a2c647300656f18f60473")
    with pytest.raises(ValueError, match="exact original"):
        tagger.read_histograms(histogram_root)
