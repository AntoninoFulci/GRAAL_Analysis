"""Graph builds must never admit generated evidence or stale source hashes."""
import importlib.util
import json
from pathlib import Path
import shutil

import pytest


@pytest.fixture
def builder():
    path = Path(__file__).parents[1] / "scripts/rebuild_graph.py"
    spec = importlib.util.spec_from_file_location("rebuild_graph", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_operational_corpus_preserves_sources_and_excludes_generated_evidence(builder):
    selected = builder.corpus(builder.read(builder.POLICY))
    assert "plots/dalitz.py" in selected
    assert "09_theory/src/graal_theory/__init__.py" in selected
    assert "01_pre_analysis/cuts/ProtonFwdCut_2006_d.cpp" in selected
    assert "README.md" in selected and "AGENTS.md" in selected
    assert not any(p.startswith(("graphify-out/", "results/", "results_test/", "docs/plans/", "data/", "data_test/")) for p in selected)
    assert not any(p.endswith((".pdf", ".png", ".root")) for p in selected)


def test_source_validation_rejects_non_corpus_and_stale_paths(builder):
    with pytest.raises(ValueError, match="Non-corpus"):
        builder.validate_sources({"nodes": [{"source_file": "graphify-out/GRAPH_REPORT.md"}]}, {"README.md"})
    with pytest.raises(ValueError, match="Non-corpus"):
        builder.validate_sources({"source_file": "theory/README.md"}, {"theory/README.md"})
    value = {"nodes": [{"source_file": str(builder.ROOT / "README.md")}, {"source_file": None}]}
    builder.validate_sources(value, {"README.md"})
    assert value["nodes"][0]["source_file"] == "README.md"


def test_hash_binding_rejects_changed_source(builder, monkeypatch, tmp_path):
    source = tmp_path / "source.py"
    source.write_text("old source")
    policy = tmp_path / "policy.json"
    policy.write_text("{}")
    monkeypatch.setattr(builder, "ROOT", tmp_path)
    monkeypatch.setattr(builder, "POLICY", policy)
    monkeypatch.setattr(builder, "corpus", lambda _: ["source.py"])
    builder.dump(tmp_path / "corpus-fingerprints.json", {"policy_sha256": builder.sha(policy), "files": {"source.py": builder.sha(source)}})
    builder.verify_fingerprints(tmp_path)
    source.write_text("new source")
    with pytest.raises(ValueError, match="Sources changed"):
        builder.verify_fingerprints(tmp_path)


def test_cpp_parser_reads_root_macro_and_native_header():
    graphify = pytest.importorskip("graphify.extract")
    root = Path(__file__).parents[1]
    macro = graphify.extract_cpp(root / "03_mc_simulation/generators/generate_eta_pi0_dataset.C")
    header = graphify.extract_cpp(root / "06_calibration/native/strip_energy_rdf.hxx")
    assert any("generate_eta_pi0_dataset" in n["label"] for n in macro["nodes"])
    assert len(header["nodes"]) > 1
    assert not macro.get("error") and not header.get("error")


@pytest.fixture
def candidate_run(builder, monkeypatch, tmp_path):
    source = tmp_path / "scripts/rebuild_graph.py"
    source.parent.mkdir()
    source.write_text("# builder version one\n")
    policy = tmp_path / "policy.json"
    policy.write_text("{}")
    monkeypatch.setattr(builder, "ROOT", tmp_path)
    monkeypatch.setattr(builder, "POLICY", policy)
    monkeypatch.setattr(builder, "__file__", str(source))
    monkeypatch.setattr(builder, "corpus", lambda _: ["scripts/rebuild_graph.py"])
    run = tmp_path / "run"
    fingerprint = {"corpus_sha256": "initial-corpus", "policy_sha256": builder.sha(policy), "files": {"scripts/rebuild_graph.py": builder.sha(source)}}
    builder.dump(run / "corpus-fingerprints.json", fingerprint)
    provenance = {"corpus_sha256": "initial-corpus", "builder_sha256": builder.sha(source), "nodes": 1, "edges": 0, "raw_relationship_statements": 0}
    builder.dump(run / "provenance.json", provenance)
    builder.dump(run / "semantic-chunks.json", {"chunks": [], "corpus_sha256": "initial-corpus"})
    builder.dump(run / "detection.json", {})
    builder.dump(run / "ast.json", {"nodes": [], "edges": []})
    output = run / "candidate"
    builder.dump(output / "corpus-fingerprints.json", fingerprint)
    builder.dump(output / "build-provenance.json", provenance)
    builder.dump(output / "graph.json", {"directed": True, "nodes": [{"id": "builder", "source_file": "scripts/rebuild_graph.py", "community": 0}], "links": []})
    builder.dump(output / ".graphify_labels.json", {"0": "Builder Tools"})
    for name in ("GRAPH_REPORT.md", "graph.html", "manifest.json", "coverage.json", ".graphify_health.json"):
        (output / name).write_text("verified fixture\n")
    builder.validate_candidate(run)
    return run, source


def test_refresh_rejects_missing_and_restored_stale_candidate(builder, candidate_run):
    run, source = candidate_run
    stale = run / "saved-candidate"
    shutil.copytree(run / "candidate", stale)
    source.write_text("# builder version two\n")
    builder.refresh(run)
    assert not (run / "ast.json").exists()
    assert not (run / "candidate").exists()
    assert not (run / "candidate-inventory.json").exists()
    for operation in (builder.validate_candidate, builder.publish):
        with pytest.raises(ValueError, match="No current candidate"):
            operation(run)
    shutil.copytree(stale, run / "candidate")
    for operation in (builder.validate_candidate, builder.publish):
        with pytest.raises(ValueError, match="Candidate corpus fingerprints"):
            operation(run)


@pytest.mark.parametrize("field", ["fingerprints", "corpus_sha256", "builder_sha256"])
def test_candidate_binding_rejects_hash_changes_with_identical_graph_counts(builder, candidate_run, field):
    run, _ = candidate_run
    path = run / "candidate" / ("corpus-fingerprints.json" if field == "fingerprints" else "build-provenance.json")
    value = builder.read(path)
    if field == "fingerprints":
        value["files"]["scripts/rebuild_graph.py"] = "stale-file-hash"
    else:
        value[field] = "stale-hash"
    builder.dump(path, value)
    with pytest.raises(ValueError, match="Candidate"):
        builder.validate_candidate(run)
    with pytest.raises(ValueError, match="Candidate"):
        builder.publish(run)


def test_failed_staged_publication_restores_previous_active_output(builder, candidate_run, monkeypatch):
    run, _ = candidate_run
    active = builder.ROOT / "graphify-out"
    active.mkdir()
    (active / "graph.json").write_text("previous valid graph\n")
    original_hash = builder.sha(active / "graph.json")
    move = shutil.move

    def fail_install(source, target, *args, **kwargs):
        if Path(source).name == "publish-staging":
            Path(target).mkdir()
            (Path(target) / "partial").write_text("interrupted installation")
            raise OSError("injected install failure")
        return move(source, target, *args, **kwargs)

    monkeypatch.setattr(shutil, "move", fail_install)
    with pytest.raises(OSError, match="injected install failure"):
        builder.publish(run)
    assert builder.sha(active / "graph.json") == original_hash
    assert not (active / "partial").exists()
    assert list(run.glob("failed-active-*/partial"))
    assert list(run.glob("previous-graph-*/graph.json"))
