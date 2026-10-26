"""Fresh, allowlisted Graphify builds with auditable host semantic inputs.

Prepare, inspect detection/prompts, extract AST and host semantics, then build.
No previous graph, query memory, semantic cache or incremental mode is read.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "docs/reference/graph-corpus.json"


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def corpus(policy):
    candidates = set(policy["include_files"] + policy["selected_reference_files"])
    for dirname in policy["include_roots"]:
        for directory, dirs, files in os.walk(ROOT / dirname):
            dirs[:] = sorted(d for d in dirs if d not in policy["exclude_components"] and not d.startswith(".") and not d.endswith((".egg-info", ".dist-info")))
            for name in files:
                path = Path(directory) / name
                if path.suffix in policy["extensions"] or name == "CMakeLists.txt":
                    candidates.add(path.relative_to(ROOT).as_posix())
    selected = []
    overrides = set(policy["selected_reference_files"])
    for name in sorted(candidates):
        if any(part in policy["exclude_components"] for part in Path(name).parts):
            continue
        if name not in overrides and any(name.startswith(p) for p in policy["exclude_prefixes"]):
            continue
        path = ROOT / name
        if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(ROOT):
            raise ValueError(f"Missing, symlinked or out-of-root corpus source: {name}")
        selected.append(name)
    return selected


def verify_fingerprints(run):
    fingerprints = read(run / "corpus-fingerprints.json")
    if fingerprints["policy_sha256"] != sha(POLICY):
        raise ValueError("Corpus policy changed; prepare a new run")
    if corpus(read(POLICY)) != list(fingerprints["files"]):
        raise ValueError("Corpus membership changed; prepare a new run")
    changed = [p for p, digest in fingerprints["files"].items() if sha(ROOT / p) != digest]
    if changed:
        raise ValueError(f"Sources changed since preparation: {changed}; prepare fresh extraction")
    return fingerprints


def prepare(run, spec):
    from graphify.detect import detect
    if (run / "corpus-fingerprints.json").exists():
        raise ValueError("Run already prepared; use a new run directory for fresh evidence")
    policy = read(POLICY)
    files = corpus(policy)
    fingerprints = {p: sha(ROOT / p) for p in files}
    digest = hashlib.sha256(json.dumps(fingerprints, sort_keys=True).encode()).hexdigest()
    dump(run / "corpus-fingerprints.json", {"schema": 1, "root": str(ROOT), "corpus_sha256": digest, "policy_sha256": sha(POLICY), "files": fingerprints})
    groups = defaultdict(list)
    for p in files:
        groups[p.split("/")[0] if "/" in p else "root"].append(p)
    detection = {"files": {k: [] for k in ("code", "document", "paper", "image", "video")}, "total_words": 0, "total_files": len(files), "scan_root": str(ROOT), "shards": [], "skipped_sensitive": [], "unclassified": [], "walk_errors": []}
    for group, paths in sorted(groups.items()):
        for offset in range(0, len(paths), policy["max_files_per_shard"]):
            chunk = paths[offset:offset + policy["max_files_per_shard"]]
            name = f"{group}-{offset // policy['max_files_per_shard']:02d}"
            snapshot = run / "detection-corpus" / name
            for p in chunk:
                target = snapshot / p
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / p, target)
            found = detect(snapshot, cache_root=run / "detection-cache" / name, gitignore=False)
            dump(run / "detection" / f"{name}.json", found)
            if found["skipped_sensitive"] or found["walk_errors"]:
                raise ValueError(f"Detection skips/errors in {name}: inspect manifest")
            classified = set()
            for kind, items in found["files"].items():
                for item in items:
                    rel = Path(item).relative_to(snapshot).as_posix()
                    classified.add(rel)
                    # Markdown with code fences may be classified as code by
                    # detection; documentation still requires semantic reading.
                    actual_kind = "document" if Path(rel).suffix in (".md", ".json") else kind
                    detection["files"][actual_kind].append(str(ROOT / rel))
            # Graphify does not classify .cfg/.csv/.mac; retain text configs as
            # explicitly declared semantic inputs, without changing their paths.
            unsupported = sorted(set(chunk) - classified)
            detection["unclassified"].extend(unsupported)
            detection["files"]["document"].extend(str(ROOT / p) for p in unsupported)
            detection["total_words"] += found["total_words"] + sum(len((ROOT / p).read_text().split()) for p in unsupported)
            detection["shards"].append({"name": name, "files": chunk, "count": len(chunk)})
    for items in detection["files"].values():
        items.sort()
    dump(run / "detection.json", detection)
    semantic = detection["files"]["document"]
    template = spec.read_text().split("```", 2)[1].strip()
    shutil.copyfile(spec, run / "extraction-spec.md")
    size = policy["max_semantic_files_per_chunk"]
    chunks = [semantic[i:i + size] for i in range(0, len(semantic), size)]
    instructions = []
    for number, chunk in enumerate(chunks, 1):
        target = run / "semantic" / f"chunk-{number:02d}.json"
        prompt = template
        for key, value in {"FILE_LIST": "\n".join(chunk), "CHUNK_NUM": str(number), "TOTAL_CHUNKS": str(len(chunks)), "DEEP_MODE": "false", "CHUNK_PATH": str(target)}.items():
            prompt = prompt.replace(key, value)
        (run / "prompts").mkdir(exist_ok=True)
        (run / "prompts" / f"chunk-{number:02d}.txt").write_text(prompt + "\n")
        instructions.append({"chunk": number, "files": chunk, "output": str(target), "prompt": str(run / "prompts" / f"chunk-{number:02d}.txt")})
    dump(run / "semantic-chunks.json", {"corpus_sha256": digest, "spec_sha256": sha(spec), "chunks": instructions, "usage_status": "Host agent counters unavailable unless supplied by orchestrator; zero placeholders are not measured usage"})
    dump(run / "provenance.json", {"started_at": datetime.now(timezone.utc).isoformat(), "graphify_version": importlib.metadata.version("graphifyy"), "python": sys.version, "interpreter": sys.executable, "git_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(), "skill_spec": str(spec), "skill_spec_sha256": sha(spec), "corpus_sha256": digest, "commands": [sys.argv], "semantic_backend": "fresh host agent; explicit hash-bound inputs", "prior_cache_used": False})
    print(f"Prepared {len(files)} files, ~{detection['total_words']:,} words; {len(detection['shards'])} stage/theme shards; {len(chunks)} semantic chunks")
    print("Top roots:", Counter(p.split('/')[0] for p in files).most_common(5))
    print("Explicit semantic fallback for unsupported formats:", detection["unclassified"])


def extract_ast(run):
    from graphify import extract as ast_module
    from graphify.extract import extract
    # ROOT uses uppercase .C for C++; Graphify 0.9.68 otherwise falls back
    # to C and omits .hh/.hxx entirely. This affects this process only.
    for suffix in (".C", ".hh", ".hxx"):
        ast_module._DISPATCH[suffix] = ast_module.extract_cpp
    verify_fingerprints(run)
    detection = read(run / "detection.json")
    code = set(detection["files"]["code"])
    code.update(p for p in detection["files"]["document"] if Path(p).suffix in (".hh", ".hxx"))
    nodes, edges, failures = {}, [], []
    fresh_cache = run / f"ast-cache-{time.time_ns()}"
    shards = []
    for shard in detection["shards"]:
        paths = [ROOT / p for p in shard["files"] if str(ROOT / p) in code]
        if not paths:
            continue
        result = extract(paths, root=ROOT, cache_root=fresh_cache, parallel=False)
        dump(run / "ast-shards" / f"{shard['name']}.json", result)
        shards.append((shard, paths, result))
        for node in result["nodes"]:
            nodes[node["id"]] = node
        edges.extend(result["edges"])
    # Resolve cross-stage calls against this run's freshly parsed corpus. The
    # cache holds only this invocation's AST; there is no prior-run reuse.
    final_nodes, final_edges = {}, []
    for shard, paths, first in shards:
        result = extract(paths, root=ROOT, cache_root=fresh_cache, parallel=False, resolution_context_nodes=list(nodes.values()), resolution_context_edges=edges)
        dump(run / "ast-shards" / f"{shard['name']}-resolved.json", result)
        for node in result["nodes"]:
            final_nodes[node["id"]] = node
        final_edges.extend(result["edges"])
        failures.extend(result.get("failed_sources", result.get("_failed_sources", [])))
    dump(run / "ast.json", {"nodes": list(final_nodes.values()), "edges": final_edges, "hyperedges": [], "failed_sources": failures, "input_tokens": 0, "output_tokens": 0})
    print(f"Fresh AST: {len(final_nodes)} nodes, {len(final_edges)} raw edges; failures: {failures}")


def refresh(run):
    """Rebind after builder-only changes; never reuse changed semantic sources."""
    old = read(run / "corpus-fingerprints.json")
    chunks = read(run / "semantic-chunks.json")
    if old["policy_sha256"] != sha(POLICY) or corpus(read(POLICY)) != list(old["files"]):
        raise ValueError("Policy or membership changed; a new preparation is required")
    semantic = {str(Path(p).relative_to(ROOT)) for c in chunks["chunks"] for p in c["files"]}
    changed = {p for p, digest in old["files"].items() if sha(ROOT / p) != digest}
    if changed & semantic:
        raise ValueError(f"Semantic sources changed: {changed & semantic}; re-extract in a new run")
    if not changed <= {"scripts/rebuild_graph.py", "scripts/rebuild_graph.sh", "tests/test_graph_rebuild.py"}:
        raise ValueError(f"Only builder/test maintenance can be rebound: {changed}")
    dump(run / f"corpus-before-refresh-{time.time_ns()}.json", old)
    current = {p: sha(ROOT / p) for p in old["files"]}
    digest = hashlib.sha256(json.dumps(current, sort_keys=True).encode()).hexdigest()
    old.update(files=current, corpus_sha256=digest)
    dump(run / "corpus-fingerprints.json", old)
    detection = read(run / "detection.json")
    detection["total_words"] = sum(len((ROOT / p).read_text(errors="ignore").split()) for p in current)
    dump(run / "detection.json", detection)
    chunks["prepared_corpus_sha256"] = chunks.get("prepared_corpus_sha256", chunks["corpus_sha256"])
    chunks["corpus_sha256"] = digest
    chunks["semantic_source_hashes_unchanged"] = True
    dump(run / "semantic-chunks.json", chunks)
    provenance = read(run / "provenance.json")
    provenance.update(corpus_sha256=digest, builder_sha256=sha(Path(__file__)), cpp_dispatch_adapter=[".C", ".hh", ".hxx"], semantic_sources_unchanged=True, rebind_changed_sources=sorted(changed))
    dump(run / "provenance.json", provenance)
    if (run / "ast.json").exists():
        shutil.move(str(run / "ast.json"), str(run / f"ast-before-refresh-{time.time_ns()}.json"))
    if (run / "candidate").exists():
        shutil.move(str(run / "candidate"), str(run / f"candidate-before-refresh-{time.time_ns()}"))
    if (run / "candidate-inventory.json").exists():
        shutil.move(str(run / "candidate-inventory.json"), str(run / f"inventory-before-refresh-{time.time_ns()}.json"))
    print("Semantic source hashes unchanged; builder fingerprints rebound. Fresh AST extraction is now required.")


def complete_ast_endpoints(extraction, allowed):
    """Resolve installed package aliases and declare imported external symbols.

    No relationships are invented: these are endpoints already emitted by AST.
    Package aliases come from the project's explicit setuptools configuration.
    """
    try:
        import tomllib
    except ModuleNotFoundError:  # Python 3.10; supplied by the project dependency.
        import tomli as tomllib
    aliases = tomllib.loads((ROOT / "pyproject.toml").read_text())["tool"]["setuptools"]["package-dir"]
    nodes = {n["id"]: n for n in extraction["nodes"]}
    normalized = lambda value: re.sub(r"[^a-z0-9_]", "_", value.lower())
    targets = {}
    for path in sorted(allowed):
        if not path.endswith(".py"):
            continue
        for package, directory in aliases.items():
            if path.startswith(directory + "/"):
                tail = path[len(directory) + 1:-3]
                module = package + ("." + tail.replace("/", ".") if tail != "__init__" else "")
                module = module.removesuffix(".__init__")
                target = normalized(path[:-3])
                if target in nodes:
                    targets[normalized(module)] = target
    replacements, external = [], []
    for edge in extraction["edges"]:
        target = edge.get("target")
        if target not in nodes and target in targets:
            edge["target"] = targets[target]
            replacements.append({"import": target, "target": edge["target"], "source_file": edge.get("source_file")})
            target = edge["target"]
        if target not in nodes:
            if edge.get("relation") not in ("imports", "imports_from", "depends_on", "calls"):
                raise ValueError(f"Unexpected unresolved AST endpoint: {edge}")
            node = {"id": target, "label": target, "file_type": "concept", "source_file": None, "source_location": None, "external_or_unresolved": True, "rationale": "Named import/dependency/callee emitted by AST; definition is not resolved in the selected corpus."}
            nodes[target] = node
            external.append(target)
        if "confidence_score" not in edge:
            edge["confidence_score"] = {"EXTRACTED": 1.0, "INFERRED": 0.95, "AMBIGUOUS": 0.3}[edge["confidence"]]
    extraction["nodes"] = list(nodes.values())
    return {"package_alias_resolutions": replacements, "external_or_unresolved_endpoints": external}


def validate_sources(value, allowed):
    if isinstance(value, dict):
        source = value.get("source_file")
        if source:
            path = Path(source)
            relative = path.relative_to(ROOT).as_posix() if path.is_absolute() else source
            if relative not in allowed or not (ROOT / relative).is_file():
                raise ValueError(f"Non-corpus source: {source}")
            value["source_file"] = relative
        for child in value.values():
            validate_sources(child, allowed)
    elif isinstance(value, list):
        for child in value:
            validate_sources(child, allowed)


def build(run):
    started = time.monotonic()
    from graphify.build import build_from_json
    from graphify.cluster import cluster, score_all
    from graphify.analyze import god_nodes, surprising_connections, suggest_questions
    from graphify.diagnostics import diagnose_extraction, format_diagnostic_report
    from graphify.export import to_json, to_html
    from graphify.report import generate
    from graphify.detect import save_manifest
    from graphify.benchmark import run_benchmark, print_benchmark
    fingerprint = verify_fingerprints(run)
    allowed = set(fingerprint["files"])
    detection = read(run / "detection.json")
    chunks = read(run / "semantic-chunks.json")
    if chunks["corpus_sha256"] != fingerprint["corpus_sha256"]:
        raise ValueError("Semantic manifest is not bound to this corpus")
    extraction = read(run / "ast.json")
    endpoint_audit = complete_ast_endpoints(extraction, allowed)
    dump(run / "endpoint-audit.json", endpoint_audit)
    semantic_evidence = []
    for chunk in chunks["chunks"]:
        path = Path(chunk["output"])
        result = read(path)
        expected = set(chunk["files"])
        represented = {n.get("source_file") for n in result["nodes"]}
        if expected - represented:
            raise ValueError(f"Semantic chunk {chunk['chunk']} omitted files: {expected - represented}")
        for kind in ("nodes", "edges", "hyperedges"):
            for item in result.get(kind, []):
                if item.get("source_file") not in expected:
                    raise ValueError(f"Semantic source outside disjoint chunk: {item}")
            extraction.setdefault(kind, []).extend(result.get(kind, []))
        semantic_evidence.append({"chunk": chunk["chunk"], "sha256": sha(path), "files": {str(Path(p).relative_to(ROOT)): sha(Path(p)) for p in chunk["files"]}})
    nodes = {}
    for node in extraction["nodes"]:
        if node["id"] in nodes and nodes[node["id"]] != node:
            previous = nodes[node["id"]]
            source_a = previous.get("source_file")
            source_b = node.get("source_file")
            if not source_a or not source_b or (ROOT / source_a).resolve() != (ROOT / source_b).resolve():
                raise ValueError(f"Conflicting node ID/source: {node['id']}")
            nodes[node["id"]] = {**previous, **node}
        else:
            nodes[node["id"]] = node
    extraction["nodes"] = list(nodes.values())
    validate_sources(extraction, allowed)
    dangling = [e for e in extraction["edges"] if e.get("source") not in nodes or e.get("target") not in nodes]
    if dangling:
        dump(run / "dangling-edges.json", dangling)
        raise ValueError(f"{len(dangling)} dangling endpoints; inspect dangling-edges.json")
    if any(member not in nodes for edge in extraction.get("hyperedges", []) for member in edge.get("nodes", [])):
        raise ValueError("Dangling hyperedge members")
    health = diagnose_extraction(extraction, directed=True, root=ROOT)
    dump(run / "health.json", health)
    (run / "health.txt").write_text(format_diagnostic_report(health))
    dump(run / "extraction.json", extraction)
    graph = build_from_json(extraction, root=ROOT, directed=True)
    # Graphify's DiGraph folds parallel statements into a single edge. Keep
    # every original relation/location/confidence on that canonical pair.
    evidence = defaultdict(list)
    for edge in extraction["edges"]:
        evidence[(edge["source"], edge["target"])].append(dict(edge))
    for (source, target), statements in evidence.items():
        if not graph.has_edge(source, target):
            raise ValueError(f"Build dropped an extracted endpoint pair: {source}, {target}")
        graph[source][target]["evidence"] = statements
        graph[source][target]["relations"] = sorted({e["relation"] for e in statements})
    if sum(len(d["evidence"]) for _, _, d in graph.edges(data=True)) != len(extraction["edges"]):
        raise ValueError("Extracted relationship evidence was lost")
    if not graph.number_of_nodes():
        raise ValueError("Refusing to publish an empty graph")
    communities = cluster(graph)
    cohesion = score_all(graph, communities)
    # Stable plain-language labels from actual member provenance and labels;
    # every community's membership/representatives is retained for review.
    owner_names = {"00_common": "Shared Physics Utilities", "01_pre_analysis": "Detector Pre Analysis", "02_event_selector": "Event Track Selection", "03_mc_simulation": "Monte Carlo Geometry", "04_bdt_training": "BDT Training Features", "05_reconstruction": "Event Pairing Reconstruction", "06_calibration": "Calibration Flux Inputs", "07_flux_studies": "Flux Recovery Diagnostics", "08_observable_extraction": "Observable Statistical Extraction", "graal_workflow": "Workflow Planning Execution", "plots": "Physics Diagnostic Plots", "wiki": "Current Workflow Contracts", "config": "Scientific Runtime Configuration", "scripts": "Repository Command Tools", "tests": "Repository Contract Tests", "docs": "Scientific Reference Evidence"}
    labels, summaries = {}, {}
    for cid, members in communities.items():
        owners = Counter((graph.nodes[n].get("source_file") or "external").split("/")[0] for n in members)
        ranked = sorted(members, key=lambda n: (-graph.degree(n), n))[:8]
        owner = owners.most_common(1)[0][0]
        labels[cid] = owner_names.get(owner, "External Library Interfaces")
        summaries[str(cid)] = {"label": labels[cid], "size": len(members), "owners": dict(owners), "representatives": [{"label": graph.nodes[n].get("label"), "source_file": graph.nodes[n].get("source_file")} for n in ranked]}
    if (run / "curated-labels.json").exists():
        curated = {int(k): v for k, v in read(run / "curated-labels.json").items()}
        if set(curated) != set(communities):
            raise ValueError("Curated labels must cover every current community")
        labels = curated
    dump(run / "community-summary.json", summaries)
    gods = god_nodes(graph)
    surprises = surprising_connections(graph, communities)
    questions = suggest_questions(graph, communities, labels)
    output = run / "candidate"
    if output.exists():
        shutil.move(str(output), str(run / f"candidate-before-{time.time_ns()}"))
    output.mkdir()
    provenance = read(run / "provenance.json")
    provenance.update({"completed_at": datetime.now(timezone.utc).isoformat(), "semantic_evidence": semantic_evidence, "host_token_usage": None, "token_accounting": "unavailable; upstream numeric zeros are placeholders, not zero-cost claims", "nodes": graph.number_of_nodes(), "edges": graph.number_of_edges(), "raw_relationship_statements": len(extraction["edges"]), "graph_type": "DiGraph with complete per-pair evidence", "communities": len(communities), "html_mode": "community" if graph.number_of_nodes() > 5000 else "nodes", "builder_sha256": sha(Path(__file__)), "cpp_dispatch_adapter": [".C", ".hh", ".hxx"], "execution_history": read(run / "execution-history.json")})
    if not to_json(graph, communities, str(output / "graph.json"), community_labels=labels, built_at_commit=provenance["git_head"]):
        raise ValueError("Graph export refused")
    # Detection's native-format misses were explicitly routed to semantics;
    # they are represented, not omitted files as the stock report assumes.
    report_detection = dict(detection, unclassified=[])
    report = generate(graph, communities, cohesion, labels, gods, surprises, report_detection, {"input": 0, "output": 0}, str(ROOT), suggested_questions=questions, built_at_commit=provenance["git_head"])
    report = report.replace("- Token cost: 0 input · 0 output", "- Token cost: unavailable (host agent usage counters are not exposed)")
    report = report.replace("- Run `graphify update .` after code changes (no API cost).", "- Rebuild after source changes using `scripts/rebuild_graph.sh` and the allowlisted corpus workflow in `wiki/maintenance.md`.")
    report += "\n## Fresh rebuild provenance\n\nHost semantic token usage is **unavailable** from this orchestrator. Any numeric zero counters above are upstream placeholders, not measured costs. No old semantic cache or query memory was used. Full source fingerprints and semantic chunk hashes are in `build-provenance.json` and `corpus-fingerprints.json`.\n"
    report += f"\nSemantic backend: {provenance['semantic_backend']}. Native detection misses were explicitly covered by semantic extraction. Source hashes, rather than the base commit alone, identify this working-tree build.\n"
    report += f"\nThe directed graph has {graph.number_of_edges():,} unique endpoint pairs and preserves all {len(extraction['edges']):,} original relationship statements in per-edge `evidence` arrays; `relations` lists every relation for each pair. CLI and HTML summaries show the primary relation. The raw health diagnostic reports parallel-pair collapses, but their complete evidence is retained. {health.get('self_loop_edges', 0)} self-loop statements are retained.\n"
    (output / "GRAPH_REPORT.md").write_text(report)
    if graph.number_of_nodes() > 5000:
        print("HTML warning: >5,000 nodes; rendering aggregated communities, not a full node-level browser view.")
    if not to_html(graph, communities, str(output / "graph.html"), community_labels=labels, node_limit=5000):
        raise ValueError("HTML export was skipped")
    dump(output / ".graphify_labels.json", {str(k): v for k, v in labels.items()})
    dump(output / ".graphify_analysis.json", {"communities": communities, "cohesion": cohesion, "gods": gods, "surprises": surprises, "questions": questions})
    dump(output / ".graphify_health.json", health)
    dump(output / "build-provenance.json", provenance)
    dump(output / "corpus-fingerprints.json", fingerprint)
    dump(output / "cost.json", {"runs": [{"input_tokens": None, "output_tokens": None, "files": len(allowed), "date": provenance["completed_at"], "usage_status": "host counters unavailable"}], "total_input_tokens": None, "total_output_tokens": None})
    represented = {n.get("source_file") for n in graph.nodes.values() if n.get("source_file")}
    coverage = {"corpus_files": len(allowed), "represented_files": len(represented), "unrepresented_files": sorted(allowed - represented), "ast_failed_sources": extraction.get("failed_sources", []), "semantic_files": len(detection["files"]["document"])}
    dump(output / "coverage.json", coverage)
    if coverage["unrepresented_files"]:
        raise ValueError(f"Corpus coverage incomplete: {coverage['unrepresented_files']}")
    stamp = {k: [p for p in paths if str(Path(p).relative_to(ROOT)) in represented] for k, paths in detection["files"].items()}
    save_manifest(stamp, manifest_path=str(output / "manifest.json"), root=ROOT, scan_corpus={p for paths in detection["files"].values() for p in paths})
    (output / ".graphify_python").write_text(sys.executable + "\n")
    (output / ".graphify_root").write_text(str(ROOT) + "\n")
    benchmark = run_benchmark(str(output / "graph.json"), corpus_words=detection["total_words"])
    dump(output / "benchmark.json", benchmark)
    print_benchmark(benchmark)
    provenance["build_elapsed_seconds"] = time.monotonic() - started
    dump(output / "build-provenance.json", provenance)
    validate_candidate(run)
    print(f"Candidate verified: {graph.number_of_nodes()} nodes, {graph.number_of_edges()} edges, {len(communities)} communities")


def validate_candidate(run):
    fingerprint = verify_fingerprints(run)
    output = run / "candidate"
    if not output.is_dir():
        raise ValueError("No current candidate; fresh AST extraction and build are required")
    if read(output / "corpus-fingerprints.json") != fingerprint:
        raise ValueError("Candidate corpus fingerprints differ from the current run")
    provenance = read(output / "build-provenance.json")
    run_provenance = read(run / "provenance.json")
    if provenance.get("corpus_sha256") != fingerprint["corpus_sha256"] or run_provenance.get("corpus_sha256") != fingerprint["corpus_sha256"]:
        raise ValueError("Candidate or run provenance has a stale corpus hash")
    if provenance.get("builder_sha256") != sha(Path(__file__)):
        raise ValueError("Candidate provenance has a stale builder hash")
    data = read(output / "graph.json")
    validate_sources(data, set(fingerprint["files"]))
    ids = {n["id"] for n in data["nodes"]}
    links = data.get("links", data.get("edges", []))
    if len(ids) != len(data["nodes"]) or any(e["source"] not in ids or e["target"] not in ids for e in links):
        raise ValueError("Invalid graph IDs or endpoints")
    if (len(ids), len(links)) != (provenance["nodes"], provenance["edges"]):
        raise ValueError("Graph/provenance count mismatch")
    if not data.get("directed") or sum(len(e.get("evidence", [])) for e in links) != provenance["raw_relationship_statements"]:
        raise ValueError("Direction or relationship evidence was lost")
    labels = read(output / ".graphify_labels.json")
    if any(str(n.get("community")) not in labels for n in data["nodes"]):
        raise ValueError("Missing community labels")
    for name in ("GRAPH_REPORT.md", "graph.html", "manifest.json", "coverage.json", ".graphify_health.json"):
        if not (output / name).is_file() or not (output / name).stat().st_size:
            raise ValueError(f"Missing derivative {name}")
    dump(run / "candidate-inventory.json", {p.relative_to(output).as_posix(): sha(p) for p in sorted(output.rglob("*")) if p.is_file()})


def publish(run):
    validate_candidate(run)
    active = ROOT / "graphify-out"
    archive = run / f"previous-graph-{time.time_ns()}"
    inventory = {p.relative_to(active).as_posix(): sha(p) for p in sorted(active.rglob("*")) if p.is_file()} if active.exists() else {}
    if active.exists():
        shutil.copytree(active, archive, symlinks=True)
        copied = {p.relative_to(archive).as_posix(): sha(p) for p in sorted(archive.rglob("*")) if p.is_file()}
        if copied != inventory:
            raise ValueError("Old graph backup hash verification failed")
    dump(run / "previous-graph-inventory.json", {"archive": str(archive), "files": inventory})
    staging = run / "publish-staging"
    shutil.copytree(run / "candidate", staging)
    previous = run / f"previous-active-{time.time_ns()}"
    if active.exists():
        shutil.move(str(active), str(previous))
    try:
        shutil.move(str(staging), str(active))
    except BaseException:
        if previous.exists():
            if active.exists():
                shutil.move(str(active), str(run / f"failed-active-{time.time_ns()}"))
            shutil.move(str(previous), str(active))
        raise
    print(f"Published verified graph; previous output preserved at {archive}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("prepare", "refresh-builder", "ast", "build", "publish", "verify"))
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--extraction-spec", type=Path, default=Path.home() / ".agents/skills/graphify/references/extraction-spec.md")
    args = parser.parse_args()
    run = args.run_dir.resolve()
    if not run.is_relative_to(ROOT / "results_test"):
        parser.error("--run-dir must be inside this checkout's results_test/")
    run.mkdir(parents=True, exist_ok=True)
    for name in ("tmp", "mpl", "semantic"):
        (run / name).mkdir(exist_ok=True)
    os.environ["TMPDIR"] = str(run / "tmp")
    os.environ["MPLCONFIGDIR"] = str(run / "mpl")
    history_path = run / "execution-history.json"
    history = read(history_path) if history_path.exists() else []
    history.append({"at": datetime.now(timezone.utc).isoformat(), "argv": [sys.executable, "-B", *sys.argv], "builder_sha256": sha(Path(__file__))})
    dump(history_path, history)
    if args.phase == "prepare":
        prepare(run, args.extraction_spec.resolve())
    elif args.phase == "ast":
        extract_ast(run)
    elif args.phase == "refresh-builder":
        refresh(run)
    elif args.phase == "verify":
        validate_candidate(run)
    elif args.phase == "build":
        build(run)
    elif args.phase == "publish":
        publish(run)


if __name__ == "__main__":
    main()
