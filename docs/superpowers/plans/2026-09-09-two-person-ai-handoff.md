# Two-Person AI Handoff Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the repository into a clone-ready, Git-LFS-backed project package and publish an executable roadmap split between exactly two physics collaborators.

**Architecture:** Keep code and compact text artifacts in ordinary Git, publish selected ROOT snapshots through path-scoped Git LFS, and retain raw/multi-gigabyte corpora outside Git. A deterministic inventory records every published data/result artifact. Root-level agent instructions and Make targets provide one maintenance interface, while a separate roadmap fixes two non-overlapping physics ownership areas and their handoffs.

**Tech Stack:** Git, Git LFS 3.x, Python 3.10+, ROOT/PyROOT, pytest, Make, Graphify

**Spec:** `docs/superpowers/specs/2026-09-09-two-person-ai-handoff-design.md`

## Global Constraints

- Publish current compact `data/` inputs and current `results/` snapshots, but do not publish raw detector corpora, multi-gigabyte MC samples, virtual environments, caches, credentials, or machine-specific Graphify state.
- Track large published ROOT/NPZ artifacts through path-scoped Git LFS; never bypass GitHub's ordinary-blob size limit.
- `config/run_manifest.csv` remains authoritative; `data/run_manifest.generated.csv` remains generated and non-authoritative.
- Only `results/observable_runs/` with `observable_run_qa.json` containing `valid: true` may normalize observables.
- Review/bad runs remain available for cut and kinematic studies but never enter normalized observables.
- Current `results/reco/*.root` files are legacy plot inputs and invalid for run-flux normalization because they lack `RunNumber`, `Polarization`, and `Xstrip`.
- Keep `.superpowers/`, `.worktrees/`, Graphify caches/interpreter pointers, checkpoints, and temporary files ignored.
- Use the Python interpreter against which PyROOT was built.
- Every task ends with verification and a focused Conventional Commit.

---

### Task 1: Publish path-scoped data and result snapshots

**Files:**
- Modify: `.gitignore`
- Modify: `.gitattributes`
- Import: `data/flux/flux.root`
- Import: `data/run_manifest.generated.csv`
- Import: `results/reco/`
- Import: `results/plots/`
- Import: `results/strip_energy_flux/`
- Import: `results/strip_energy_flux.run.log`
- Generate: `results/observable_runs/`

**Interfaces:**
- Consumes: current ignored artifacts from primary checkout resolved through `git rev-parse --git-common-dir`
- Produces: selected clone-visible data/result snapshot, with ROOT files stored as Git LFS pointers

- [ ] **Step 1: Record source checkout and copy selected artifacts**

Run inside isolated worktree:

```bash
SOURCE_CHECKOUT="$(dirname "$(git rev-parse --path-format=absolute --git-common-dir)")"
rsync -a "$SOURCE_CHECKOUT/data/flux/" data/flux/
cp "$SOURCE_CHECKOUT/data/run_manifest.generated.csv" data/run_manifest.generated.csv
rsync -a "$SOURCE_CHECKOUT/results/reco/" results/reco/
rsync -a "$SOURCE_CHECKOUT/results/plots/" results/plots/
rsync -a "$SOURCE_CHECKOUT/results/strip_energy_flux/" results/strip_energy_flux/
cp "$SOURCE_CHECKOUT/results/strip_energy_flux.run.log" results/strip_energy_flux.run.log
```

Expected: copied artifacts match source sizes and SHA-256 values.

- [ ] **Step 2: Replace broad ignores with explicit publication allowlists**

Keep generic binary protection, then add later path-specific exceptions:

```gitignore
*.root
*.npz

/data/*
!/data/flux/
!/data/flux/flux.root
!/data/run_manifest.generated.csv

/results/*
!/results/reco/
!/results/reco/**
!/results/plots/
!/results/plots/**
!/results/strip_energy_flux/
!/results/strip_energy_flux/**
!/results/strip_energy_flux.run.log
!/results/observable_runs/
!/results/observable_runs/**

03_mc_simulation/data/
04_bdt_training/data/

graphify-out/*
!graphify-out/GRAPH_REPORT.md
!graphify-out/graph.json
!graphify-out/graph.html
!graphify-out/.graphify_labels.json
!graphify-out/manifest.json

.superpowers/
.worktrees/
```

Remove broad `docs/`, `/data/`, `/results/`, and `graphify-out/` rules. Preserve
existing cache, environment, test-data, and temporary-directory rules.

- [ ] **Step 3: Configure path-scoped Git LFS**

Append exact rules to `.gitattributes`:

```gitattributes
data/flux/*.root filter=lfs diff=lfs merge=lfs -text
results/reco/*.root filter=lfs diff=lfs merge=lfs -text
results/plots/*.root filter=lfs diff=lfs merge=lfs -text
results/**/*.npz filter=lfs diff=lfs merge=lfs -text
```

Run:

```bash
git lfs install --local
git check-attr filter -- data/flux/flux.root results/reco/reco_eta_pi0_chi2.root
```

Expected: both paths report `filter: lfs`.

- [ ] **Step 4: Regenerate accepted observable bundle**

Run:

```bash
python scripts/build_observable_run_database.py \
  --manifest config/run_manifest.csv \
  --strip-energy-dir results/strip_energy_flux \
  --output-dir results/observable_runs
```

Expected: exit 0, six files written, `good=2372`, and
`observable_run_qa.json` has `valid: true`.

- [ ] **Step 5: Verify ordinary Git never stages large ROOT payloads**

Run:

```bash
git add .gitignore .gitattributes data results
git lfs status
git lfs ls-files
git diff --cached --check
```

Expected: every staged ROOT path is listed by `git lfs ls-files`; no staged
ordinary blob exceeds 100 MB.

- [ ] **Step 6: Commit snapshot policy and artifacts**

```bash
git commit -m "chore(data): publish analysis snapshot via LFS"
```

---

### Task 2: Add deterministic artifact provenance

**Files:**
- Create: `scripts/build_artifact_inventory.py`
- Create: `00_common/tests/test_build_artifact_inventory.py`
- Create: `ARTIFACTS.json`
- Create: `docs/artifact-policy.md`

**Interfaces:**
- Consumes: repository root and published paths under `data/`, `results/`, and `graphify-out/`
- Produces: deterministic `ARTIFACTS.json` with `schema_version`, `generated_at_commit`, path, byte count, SHA-256, role, validity, and allowed use

Public Python interface:

```python
class ArtifactInventoryError(ValueError):
    pass


def build_inventory(
    repo_root: Path,
    commit: str,
    roots: tuple[Path | str, ...] = ("data", "results", "graphify-out"),
) -> dict[str, object]:
    """Return deterministic inventory for published artifact roots."""
```

- [ ] **Step 1: Write failing inventory tests**

Tests must create a temporary repository-shaped tree and assert:

```python
import hashlib
from pathlib import Path

import pytest

from scripts.build_artifact_inventory import ArtifactInventoryError, build_inventory


def put(root: Path, relative: str, payload: bytes = b"payload") -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return path


def records(payload: dict) -> dict[str, dict]:
    return {row["path"]: row for row in payload["artifacts"]}


def test_inventory_is_sorted_and_hashes_file_bytes(tmp_path):
    put(tmp_path, "results/plots/z.pdf", b"z")
    put(tmp_path, "data/run_manifest.generated.csv", b"run_number\n1\n")
    payload = build_inventory(tmp_path, "abc123")
    paths = [row["path"] for row in payload["artifacts"]]
    assert paths == sorted(paths)
    row = records(payload)["results/plots/z.pdf"]
    assert row["sha256"] == hashlib.sha256(b"z").hexdigest()
    assert row["bytes"] == 1


def test_inventory_rejects_symlinks(tmp_path):
    target = put(tmp_path, "target.root")
    link = tmp_path / "data/flux/flux.root"
    link.parent.mkdir(parents=True)
    link.symlink_to(target)
    with pytest.raises(ArtifactInventoryError, match="symlink"):
        build_inventory(tmp_path, "abc123")


def test_inventory_rejects_paths_outside_declared_roots(tmp_path):
    outside = tmp_path.parent / "outside"
    outside.mkdir(exist_ok=True)
    with pytest.raises(ArtifactInventoryError, match="outside repository"):
        build_inventory(tmp_path, "abc123", roots=(outside,))


def test_inventory_marks_legacy_reco_as_not_for_normalization(tmp_path):
    put(tmp_path, "results/reco/reco_eta_pi0_chi2.root")
    row = records(build_inventory(tmp_path, "abc123"))[
        "results/reco/reco_eta_pi0_chi2.root"
    ]
    assert row["role"] == "legacy"
    assert row["valid"] is True
    assert "not run-flux normalization" in row["allowed_use"]


def test_inventory_excludes_itself_and_machine_graphify_files(tmp_path):
    put(tmp_path, "ARTIFACTS.json")
    put(tmp_path, "graphify-out/.graphify_python")
    put(tmp_path, "graphify-out/graph.json")
    assert list(records(build_inventory(tmp_path, "abc123"))) == [
        "graphify-out/graph.json"
    ]
```

Run:

```bash
python -m pytest -q 00_common/tests/test_build_artifact_inventory.py
```

Expected: FAIL because module/script does not exist.

- [ ] **Step 2: Implement inventory builder**

CLI:

```text
python scripts/build_artifact_inventory.py \
  --repo-root PATH \
  --commit COMMIT \
  --output ARTIFACTS.json
```

Required deterministic record shape:

```json
{
  "path": "results/reco/reco_eta_pi0_chi2.root",
  "bytes": 171699156,
  "sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "role": "legacy",
  "valid": true,
  "allowed_use": "legacy plots only; not run-flux normalization"
}
```

Use `Path.resolve()` containment checks, reject symlinks, stream SHA-256 in
1 MiB chunks, sort by POSIX relative path, and write JSON atomically. Exclude
`.graphify_python`, `.graphify_root`, `cache/`, `cost.json`, temporary files,
and `ARTIFACTS.json` itself.

- [ ] **Step 3: Run focused tests**

```bash
python -m pytest -q 00_common/tests/test_build_artifact_inventory.py
```

Expected: PASS.

- [ ] **Step 4: Document authority and usage policy**

`docs/artifact-policy.md` must distinguish:

- authoritative `config/run_manifest.csv`;
- generated `data/run_manifest.generated.csv`;
- source `results/strip_energy_flux/`;
- accepted `results/observable_runs/`;
- legacy `results/reco/`;
- diagnostic-only `results/plots/` and run log;
- portable versus local Graphify files.

Include commands for SHA verification, LFS pull, observable bundle rebuild,
and rejection conditions.

- [ ] **Step 5: Generate repository inventory**

```bash
python scripts/build_artifact_inventory.py \
  --repo-root . \
  --commit "$(git rev-parse HEAD)" \
  --output ARTIFACTS.json
```

Expected: every selected published data/result file appears once, paths are
relative, hashes are lowercase SHA-256, and machine Graphify state is absent.

- [ ] **Step 6: Commit provenance tooling**

```bash
git add scripts/build_artifact_inventory.py \
  00_common/tests/test_build_artifact_inventory.py \
  ARTIFACTS.json docs/artifact-policy.md
git commit -m "feat(provenance): inventory published artifacts"
```

---

### Task 3: Add clone-ready maintenance interface

**Files:**
- Create: `AGENTS.md`
- Create: `requirements-dev.txt`
- Create: `Makefile`
- Modify: `README.md`
- Modify: `wiki/testing.md`
- Test: `00_common/tests/test_repository_contract.py`

**Interfaces:**
- Consumes: existing Python packaging, scripts, test suites, and artifact policy
- Produces: stable commands usable by people and AI agents across local/farm environments

- [ ] **Step 1: Write failing repository-contract tests**

Tests must assert:

```python
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_agents_file_names_authoritative_observable_bundle():
    text = read("AGENTS.md")
    assert "results/observable_runs/run_manifest_observables.csv" in text
    assert "observable_run_qa.valid=true" in text.replace(" ", "")
    assert "review/bad" in text


def test_requirements_include_scipy_and_pytest():
    requirements = {
        line.split("=", 1)[0].split(">", 1)[0].strip()
        for line in read("requirements-dev.txt").splitlines()
        if line and not line.startswith("#")
    }
    assert {"scipy", "pytest"} <= requirements


def test_makefile_exposes_required_targets():
    makefile = read("Makefile")
    required = {
        "help", "setup", "syntax", "test-root-free", "test",
        "validate-manifest", "observable-runs", "graph-update",
        "artifact-inventory", "verify",
    }
    declared = set(re.findall(r"^([a-z][a-z0-9-]*):", makefile, re.MULTILINE))
    assert required <= declared


def test_readme_documents_lfs_clone_flow():
    text = read("README.md")
    assert "git lfs install" in text
    assert "git lfs pull" in text
    assert "make setup" in text
    assert "make verify" in text


def test_makefile_root_free_suite_omits_pyroot_importing_tests():
    makefile = read("Makefile")
    recipe = makefile.split("test-root-free:", 1)[1].split("\n\n", 1)[0]
    assert "test_build_strip_energy_flux.py" not in recipe
    assert "05_reconstruction/tests" not in recipe
    assert "06_plots/tests" not in recipe
```

Required Make targets:

```text
help setup syntax test-root-free test validate-manifest
observable-runs graph-update artifact-inventory verify
```

Run:

```bash
python -m pytest -q 00_common/tests/test_repository_contract.py
```

Expected: FAIL because contract files/targets do not yet exist.

- [ ] **Step 2: Create dependency contract**

`requirements-dev.txt` must contain direct Python dependencies used by source
or tests, including:

```text
uproot==5.7.4
awkward==2.9.1
xgboost==3.2.0
scikit-learn>=1.5
numpy>=2.0
scipy>=1.14
matplotlib>=3.10
tqdm>=4.0
pytest>=8.0
```

Add comment: ROOT/PyROOT is external and selected Python must match PyROOT.

- [ ] **Step 3: Create stable Make targets**

Use overridable variables:

```make
PYTHON ?= python
GRAPHIFY ?= graphify
```

`syntax` must compile tracked Python files and run `bash -n` on
`run_pipeline.sh` and `scripts/sync-wiki.sh`. `test-root-free` must explicitly
list ROOT-free test modules. `observable-runs` must call existing CLI with
checked-in snapshot paths. `verify` must depend on `syntax`,
`validate-manifest`, `test-root-free`, and `artifact-inventory`, but not run
expensive farm processing. `test` runs full `python -m pytest -q`.

- [ ] **Step 4: Create root agent contract**

`AGENTS.md` must include:

- pipeline stage map and package mapping;
- source-of-truth files;
- good/review/bad physics rule;
- current legacy-reco limitation;
- setup and verification commands;
- farm flux command, exit meanings, and `--resume` invariant;
- Graphify query/update workflow;
- data/LFS and provenance policy;
- two-person ownership and shared-interface review rule;
- requirement to preserve unrelated edits and use isolated worktrees.

- [ ] **Step 5: Update human onboarding docs**

README must start clone instructions with `git lfs install`, `git clone`, and
`git lfs pull`, then point to `make setup` and `make verify`. `wiki/testing.md`
must explain ROOT-free versus PyROOT suites and exact Make commands.

- [ ] **Step 6: Run contract and maintenance tests**

```bash
python -m pytest -q 00_common/tests/test_repository_contract.py
make syntax
make validate-manifest
make test-root-free
```

Expected: all commands exit 0.

- [ ] **Step 7: Commit maintenance interface**

```bash
git add AGENTS.md requirements-dev.txt Makefile README.md \
  wiki/testing.md 00_common/tests/test_repository_contract.py
git commit -m "docs(agents): add maintenance contract"
```

---

### Task 4: Publish exactly-two-person physics roadmap

**Files:**
- Create: `docs/collaboration/two-person-physics-roadmap.md`
- Modify: `wiki/Current-Status.md`
- Modify: `wiki/publication-roadmap.md`
- Modify: `AGENTS.md`
- Test: `00_common/tests/test_repository_contract.py`

**Interfaces:**
- Consumes: observable-run bundle contract, current pipeline status, P0/P1/P2 publication roadmap
- Produces: non-overlapping ownership map, milestone sequence, artifact handoffs, and acceptance criteria

- [ ] **Step 1: Extend contract tests**

Assert roadmap contains exactly two primary ownership headings and exact shared
handoff paths:

```text
results/physics/normalization/handoffs/<acceptance_release_id>/acceptance_v1.csv
results/physics/normalization/handoffs/<acceptance_release_id>/acceptance_phi_response_v1.csv
results/physics/normalization/handoffs/<acceptance_release_id>/acceptance_qa.json
results/physics/polarization/sigma_v1.csv
results/physics/polarization/sigma_covariance.npz
results/physics/polarization/polarization_qa.json
```

Assert roadmap marks D2/neutron and eta-prime work deferred.

- [ ] **Step 2: Write Person 1 workstream**

Exclusive ownership:

```text
07_physics_normalization/
07_physics_normalization/tests/
config/physics/normalization_v1.json
results/physics/normalization/
docs/physics/normalization.md
```

Plan Gate 0, acceptance schema, metadata-bearing reconstruction regeneration,
MC efficiency, good-only yields, normalization factors, cross sections,
Ajaka closure, uncertainty propagation, and provenance. Every milestone must
name inputs, outputs, validation command, and rejection condition.

- [ ] **Step 3: Write Person 2 workstream**

Exclusive ownership:

```text
08_polarization/
08_polarization/tests/
config/physics/polarization_v1.json
results/physics/polarization/
docs/physics/polarization.md
```

Plan authoritative polarization mapping, `P(Egamma)` inputs, periodic phi
definition, and the acceptance-aware `cos(2phi)` fit. S4 builds azimuthal
counts directly from metadata-bearing N2 reconstruction and applies the N3
response; it must not consume the separate N4 cross-section yields. Include
injected-asymmetry closure, sign convention, Sigma outputs, covariance,
systematic components, and P1/P2 binning. Every milestone must name inputs,
outputs, validation command, and rejection condition.

- [ ] **Step 4: Define shared handoff gates**

Document:

- Gate 0 observable bundle `HANDOFF.json` content and hash checks;
- Person 1 immutable `acceptance_release_id` directory with the common table,
  separate phi-response table, QA, N2 provenance, masks, uncertainties, and
  hashes;
- Person 2 Sigma table/covariance schema and fit QA;
- shared-interface changes requiring both reviewers;
- final P0 release gate;
- D2/neutron and eta-prime deferral.

Planned future commands must be explicitly labeled “interface to implement,”
not presented as commands available in current checkout.

- [ ] **Step 5: Link roadmap from current status and agent contract**

Update status pages without replacing current observed counts. Correct stale
local verification text to current verified result only after a fresh suite
run records evidence.

- [ ] **Step 6: Run documentation contract tests and commit**

```bash
python -m pytest -q 00_common/tests/test_repository_contract.py
git diff --check
git add docs/collaboration/two-person-physics-roadmap.md \
  wiki/Current-Status.md wiki/publication-roadmap.md AGENTS.md \
  00_common/tests/test_repository_contract.py
git commit -m "docs(physics): split roadmap between two owners"
```

---

### Task 5: Refresh Graphify and prove fresh-clone operation

**Files:**
- Import/update: `graphify-out/GRAPH_REPORT.md`
- Import/update: `graphify-out/graph.json`
- Import/update: `graphify-out/graph.html`
- Import/update: `graphify-out/.graphify_labels.json`
- Import/update: `graphify-out/manifest.json`
- Modify: `ARTIFACTS.json`

**Interfaces:**
- Consumes: final branch code, documentation, agent contract, and published snapshot
- Produces: current portable knowledge graph and disposable-clone verification evidence

- [ ] **Step 1: Seed portable Graphify state**

Copy only reusable current outputs/cache needed for incremental extraction from
the primary checkout. Rewrite ignored `.graphify_root` and `.graphify_python`
for current worktree; never stage them.

- [ ] **Step 2: Refresh graph after durable files exist**

Run Graphify incremental update against repository root according to installed
Graphify skill instructions:

```bash
graphify . --update
```

Expected: `graph.json`, report, HTML, labels, and portable manifest describe
current branch rather than old commit `7fa8b3a`.

- [ ] **Step 3: Verify graph integrity and portability**

Run:

```bash
graphify query "How are good runs selected for observable extraction?" --budget 1200
```

Expected: traversal names observable classification, filtered manifest, QA,
and flux artifacts. Scan tracked Graphify files for primary-checkout absolute
paths and credentials; expected zero matches.

- [ ] **Step 4: Regenerate final artifact inventory**

```bash
python scripts/build_artifact_inventory.py \
  --repo-root . \
  --commit "$(git rev-parse HEAD)" \
  --output ARTIFACTS.json
```

Expected: graph outputs appear with fresh hashes; local Graphify files remain
excluded.

- [ ] **Step 5: Run full repository verification**

```bash
make verify
make test
git diff --check
git lfs status
git lfs ls-files
```

Expected: all tests pass, no invalid QA, every published ROOT file uses LFS,
and only intended changes remain.

- [ ] **Step 6: Commit refreshed graph**

```bash
git add graphify-out/GRAPH_REPORT.md graphify-out/graph.json \
  graphify-out/graph.html graphify-out/.graphify_labels.json \
  graphify-out/manifest.json ARTIFACTS.json
git commit -m "docs(graph): publish current project graph"
```

- [ ] **Step 7: Verify disposable clone**

Create a temporary clone of the branch with Git LFS enabled. In that clone run:

```bash
git lfs pull
python -m pip install -r requirements-dev.txt
python -m pip install -e .
make syntax
make validate-manifest
make test-root-free
graphify query "What must happen before extracting cross sections?" --budget 1200
python scripts/build_observable_run_database.py \
  --manifest config/run_manifest.csv \
  --strip-energy-dir results/strip_energy_flux \
  --output-dir results/observable_runs.clone-check
```

Expected: clone contains real LFS payloads rather than pointer text, maintenance
commands pass, graph query returns project nodes, and regenerated observable
counts match published snapshot.

- [ ] **Step 8: Final review and shared-branch publication**

Run whole-branch review against this plan and spec. Address all Critical and
Important findings, repeat scoped verification, merge into `main`, and push
Git commits plus Git LFS objects to `origin/main` only after explicit shared
branch authorization.
