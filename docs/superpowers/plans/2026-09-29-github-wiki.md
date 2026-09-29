# GRAAL Analysis GitHub Wiki Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and locally validate a detailed English GitHub Wiki for the current GRAAL analysis architecture, restore its explicit synchronization script, and link it from the repository README.

**Architecture:** Keep `wiki/` as the versioned source of truth for GitHub Wiki pages. Organize pages as a layered handbook: orientation first, scientific and stage narratives second, cross-cutting reference last. Use source-backed prose, focused Mermaid diagrams, and pytest checks for navigation, links, required sections, stale references, and publication behavior.

**Tech Stack:** GitHub-flavored Markdown, Mermaid, Python 3.10+, pytest, Bash, Git, GitHub Wiki repositories.

**Spec:** `docs/superpowers/specs/2026-09-29-github-wiki-design.md`

## Global Constraints

- Write all published wiki content in English.
- Treat the current working tree, including uncommitted architectural moves, as the source of truth.
- Do not restore or document the removed `graal_pipeline` orchestrator as supported behavior.
- Do not change scientific algorithms, runtime behavior, data schemas, or existing CLI interfaces.
- Do not add runtime or documentation dependencies.
- Do not publish, clone, or push to a network remote during implementation.
- Preserve all unrelated working-tree changes; stage and commit only explicit task paths.
- Use repository-relative source paths and stable symbol names; avoid fragile source line links.
- Use Mermaid only for verified relationships and provide prose or tabular equivalents.
- Give each component page the applicable parts of the approved page contract: purpose, scientific role, inputs, processing, invariants, outputs, commands, failures, implementation map, tests, and limitations.
- Keep `README.md` concise; detailed content belongs in `wiki/`.
- Run from the existing checkout rather than an isolated worktree, because the approved documentation target is the uncommitted reorganized architecture visible only here.

## Review Focus

- Internal links containing anchors, `.md` suffixes, or extensionless wiki slugs must resolve, while external URLs and pure anchors remain exempt; Task 1 adds direct tests.
- `_Sidebar.md` must list every public wiki page exactly once and never list itself; Task 1 adds a completeness test.
- Mermaid fences must be closed even when a page contains several ordinary code fences; Task 1 adds a targeted parser test.
- An empty local Git wiki remote must receive a `master` branch and the complete page set without relying on global `init.defaultBranch`; Task 9 adds an integration test.
- Missing or empty `wiki/` input must stop synchronization before remote content is replaced; Task 9 adds a failure-path test.

---

## File Structure

### Navigation and orientation

- Create: `wiki/Home.md` — purpose, supported analysis, two reader paths, pipeline summary, documentation map.
- Create: `wiki/_Sidebar.md` — complete hierarchical navigation.
- Create: `wiki/getting-started.md` — requirements, local/farm setup, first commands, verification.
- Create: `wiki/architecture.md` — system context, package boundaries, external boundaries, architecture diagrams.
- Create: `wiki/workflow.md` — manual execution order, artifact reuse, training/calibration branches, failure boundaries.
- Create: `wiki/repository-structure.md` — directory ownership and numbered-directory/package-name mapping.
- Create: `wiki/architecture-decisions.md` — code-backed design decisions and consequences.

### Scientific foundations

- Create: `wiki/scientific-foundations.md` — reaction, final state, hypotheses, reconstruction comparison, measured observable.
- Create: `wiki/physics-channels.md` — channel registry, signal/background roles, thresholds, generator ownership.
- Create: `wiki/photon-pairing.md` — pairing enumeration, heavy/light hypotheses, chi-square contract.
- Create: `wiki/compton-beam-and-polarization.md` — beam spectrum, Compton edge, transfer function, Figure 7 output.

### Pipeline stages

- Create: `wiki/01-pre-analysis.md` — ROOT selector lifecycle and `h80` output.
- Create: `wiki/01-detector-cuts.md` — cut manager, period-specific particle/topology cuts, extension rules.
- Create: `wiki/02-event-selection.md` — `h80` to `h85`, branch guards, filtering, atomic replacement.
- Create: `wiki/03-monte-carlo-simulation.md` — generators, registry contract, trees, status semantics.
- Create: `wiki/04-bdt-training.md` — full Stage-1 training flow.
- Create: `wiki/04-dataset-and-features.md` — four-photon normalization, feature schema, NPZ contract.
- Create: `wiki/04-weighting-and-photon-loss.md` — acceptance, beam reweighting, cross sections, signal prior.
- Create: `wiki/04-training-artifacts.md` — grid search, model, threshold, metrics, provenance, runtime bundle.
- Create: `wiki/05-reconstruction.md` — shared reconstruction flow and entry points.
- Create: `wiki/05-chi-square-pairing.md` — standard reconstruction path.
- Create: `wiki/05-stage1-gate.md` — model loading, score/threshold semantics, hypothesis checks.
- Create: `wiki/05-kinematic-fit.md` — fit inputs, six constraints, convergence, fitted branches, validation.
- Create: `wiki/05-sidebands-and-two-pion.md` — sideband and alternate reconstruction paths.
- Create: `wiki/06-calibration.md` — manifest, strip-energy lookup, flux integration, QA, atomic publication.
- Create: `wiki/07-observable-extraction.md` — extraction orchestration and public outputs.
- Create: `wiki/07-beam-asymmetry-estimators.md` — ratio and conditional-likelihood estimators.
- Create: `wiki/07-background-correction.md` — regions, templates, fitted fraction, correction and leakage gate.
- Create: `wiki/07-systematics-and-outputs.md` — bootstrap, covariance, ROOT schema, diagnostics and Figure 4.

### Cross-cutting reference

- Create: `wiki/plotting-and-diagnostics.md` — plotting entry points, inputs, outputs, ROOT/matplotlib split.
- Create: `wiki/data-and-artifacts.md` — artifact lineage, ROOT trees/branches, NPZ/JSON/CSV/model/PDF ownership.
- Create: `wiki/commands-and-configuration.md` — verified command matrix, options, defaults, configuration sources.
- Create: `wiki/development.md` — environment, editable install, package imports, focused development workflow.
- Create: `wiki/testing.md` — pytest layout, ROOT-dependent boundaries, test doubles, focused/full commands.
- Create: `wiki/troubleshooting.md` — symptom-to-cause-to-action table for supported failure modes.
- Create: `wiki/known-limitations.md` — factual present constraints, no roadmap promises.

### Repository integration and verification

- Create: `tests/test_wiki.py` — page-set, navigation, link, required-section, stale-reference, placeholder, and Mermaid checks.
- Create: `tests/test_wiki_sync.py` — static and local-bare-repository integration tests for synchronization.
- Restore/modify: `scripts/sync-wiki.sh` — default GitHub remote plus local override, source validation, deterministic `master` branch.
- Modify: `README.md` — concise GitHub Wiki link and terminology consistency only.

---

### Task 1: Establish Complete Wiki Navigation and Validation Contract

**Files:**
- Create: `tests/test_wiki.py`
- Create: all Markdown files listed in **File Structure** under `wiki/`

**Interfaces:**
- Consumes: approved page hierarchy from the design spec.
- Produces: complete page set, stable extensionless wiki slugs, `_Sidebar.md` navigation, and reusable validation tests that later tasks strengthen with required sections.

- [ ] **Step 1: Write the failing structural tests**

Create `tests/test_wiki.py` with this base contract:

```python
from __future__ import annotations

import re
from pathlib import Path

import pytest


ROOT = Path(__file__).parents[1]
WIKI = ROOT / "wiki"

EXPECTED_PAGES = {
    "Home.md",
    "_Sidebar.md",
    "getting-started.md",
    "architecture.md",
    "workflow.md",
    "repository-structure.md",
    "architecture-decisions.md",
    "scientific-foundations.md",
    "physics-channels.md",
    "photon-pairing.md",
    "compton-beam-and-polarization.md",
    "01-pre-analysis.md",
    "01-detector-cuts.md",
    "02-event-selection.md",
    "03-monte-carlo-simulation.md",
    "04-bdt-training.md",
    "04-dataset-and-features.md",
    "04-weighting-and-photon-loss.md",
    "04-training-artifacts.md",
    "05-reconstruction.md",
    "05-chi-square-pairing.md",
    "05-stage1-gate.md",
    "05-kinematic-fit.md",
    "05-sidebands-and-two-pion.md",
    "06-calibration.md",
    "07-observable-extraction.md",
    "07-beam-asymmetry-estimators.md",
    "07-background-correction.md",
    "07-systematics-and-outputs.md",
    "plotting-and-diagnostics.md",
    "data-and-artifacts.md",
    "commands-and-configuration.md",
    "development.md",
    "testing.md",
    "troubleshooting.md",
    "known-limitations.md",
}

LINK = re.compile(r"(?<!!)\[[^]]+\]\(([^)]+)\)")
PLACEHOLDER = re.compile(r"\b(?:TODO|TBD|FIXME)\b")


def _pages() -> dict[str, str]:
    return {path.name: path.read_text(encoding="utf-8") for path in WIKI.glob("*.md")}


def _internal_page(target: str) -> str | None:
    clean = target.split("#", 1)[0].split("?", 1)[0]
    if not clean or "://" in clean or clean.startswith("../"):
        return None
    name = Path(clean).name
    return name if name.endswith(".md") else f"{name}.md"


def test_wiki_contains_exactly_the_supported_pages():
    assert set(_pages()) == EXPECTED_PAGES


def test_sidebar_lists_every_public_page_once():
    sidebar = _pages()["_Sidebar.md"]
    targets = [
        page
        for raw in LINK.findall(sidebar)
        if (page := _internal_page(raw)) is not None
    ]
    assert set(targets) == EXPECTED_PAGES - {"_Sidebar.md"}
    assert len(targets) == len(set(targets))


def test_all_internal_links_resolve():
    for source, text in _pages().items():
        for raw in LINK.findall(text):
            target = _internal_page(raw)
            if target is not None:
                assert target in EXPECTED_PAGES, f"{source}: broken link {raw!r}"


@pytest.mark.parametrize("source", sorted(EXPECTED_PAGES))
def test_pages_have_no_placeholders(source: str):
    text = (WIKI / source).read_text(encoding="utf-8")
    assert not PLACEHOLDER.search(text), source


def test_mermaid_blocks_are_closed():
    for source, text in _pages().items():
        starts = text.count("```mermaid")
        closed = len(re.findall(r"```mermaid\n.*?\n```", text, flags=re.DOTALL))
        assert closed == starts, source
```

- [ ] **Step 2: Run the tests and verify the missing wiki fails**

Run:

```bash
pytest tests/test_wiki.py -q
```

Expected: FAIL because `wiki/` does not contain the approved page set.

- [ ] **Step 3: Create the complete page set with substantive introductions**

Create each listed page with its final H1, a two-to-four sentence purpose/scope introduction grounded in the design spec, and links only to pages in `EXPECTED_PAGES`. Do not use placeholder headings or promises such as “content will be added.” Create `_Sidebar.md` with these groups in this order:

```text
GRAAL Analysis
  Home
  Getting started
Architecture
  Architecture
  End-to-end workflow
  Repository structure
  Architectural decisions
Scientific foundations
  Scientific foundations
  Physics channels
  Photon pairing
  Compton beam and polarization
Pipeline stages
  01 Pre-analysis
    Detector cuts
  02 Event selection
  03 Monte Carlo simulation
  04 Stage-1 BDT training
    Dataset and features
    Weighting and photon loss
    Training artifacts
  05 Reconstruction
    Chi-square pairing
    Stage-1 gate
    6C kinematic fit
    Sidebands and two-pion paths
  06 Calibration
  07 Observable extraction
    Beam-asymmetry estimators
    Background correction
    Systematics and outputs
Reference
  Plotting and diagnostics
  Data and artifacts
  Commands and configuration
  Development
  Testing
  Troubleshooting
  Known limitations
```

- [ ] **Step 4: Run structural tests**

Run:

```bash
pytest tests/test_wiki.py -q
```

Expected: PASS for page set, navigation, internal links, placeholder scan, and Mermaid-fence scan.

- [ ] **Step 5: Commit navigation contract and page set**

```bash
git add tests/test_wiki.py wiki
git commit -m "docs: establish wiki navigation"
```

### Task 2: Write Orientation, Architecture, and Workflow Pages

**Files:**
- Modify: `wiki/Home.md`
- Modify: `wiki/getting-started.md`
- Modify: `wiki/architecture.md`
- Modify: `wiki/workflow.md`
- Modify: `wiki/repository-structure.md`
- Modify: `wiki/architecture-decisions.md`
- Modify: `tests/test_wiki.py`

**Interfaces:**
- Consumes: `README.md`, `pyproject.toml`, `scripts/setup.sh`, package initializers, current directory layout, `graal_common.io.filesystem.atomic_output_directory`, and repository-layout/setup tests.
- Produces: analyst/developer entry paths, authoritative system map, manual execution model, package mapping, and architecture decision record used by every stage page.

- [ ] **Step 1: Add required-section expectations and verify they fail**

Add this mapping and test to `tests/test_wiki.py`:

```python
REQUIRED_SECTIONS = {
    "Home.md": ("## Choose Your Path", "## Pipeline at a Glance", "## Documentation Map"),
    "getting-started.md": ("## Requirements", "## Local Setup", "## Farm Setup", "## Verify the Installation"),
    "architecture.md": ("## System Context", "## End-to-End Flow", "## Package Boundaries", "## External Boundaries"),
    "workflow.md": ("## Execution Model", "## Main Data Flow", "## Training Branch", "## Calibration Branch", "## Reuse and Failure Boundaries"),
    "repository-structure.md": ("## Top-Level Layout", "## Package Name Mapping", "## Generated and External Data"),
    "architecture-decisions.md": ("## Shared Contracts", "## ROOT-Free Cores", "## Explicit Artifacts", "## Fail-Loud Boundaries"),
}


@pytest.mark.parametrize("source,headings", sorted(REQUIRED_SECTIONS.items()))
def test_pages_contain_required_sections(source: str, headings: tuple[str, ...]):
    text = (WIKI / source).read_text(encoding="utf-8")
    for heading in headings:
        assert heading in text, f"{source}: missing {heading}"
```

Run `pytest tests/test_wiki.py -q`; expect required-section failures.

- [ ] **Step 2: Write `Home.md` and `getting-started.md`**

Document the `gamma p -> p eta pi0` focus, chi-square versus BDT-gated comparison, analyst and developer reading paths, Python 3.10+/PyROOT requirements, `./scripts/setup.sh --mode local`, farm-mode target arguments, activation, `pytest -q`, and first `--help` commands from current README. Explain that stages are invoked explicitly and no central orchestrator is supported.

- [ ] **Step 3: Write architecture and workflow diagrams**

In `architecture.md`, include system-context and package-boundary Mermaid diagrams. In `workflow.md`, include the approved end-to-end diagram plus an artifact-oriented table. Explicitly separate detector-data, MC/training, calibration, reconstruction, observable, and plotting branches. State which flows can run independently and which artifacts join them.

- [ ] **Step 4: Write repository structure and decisions**

Use `pyproject.toml` to map numbered physical directories to import packages. Explain `00_common` as contracts rather than a stage; calibration as stage 06; observable extraction as stage 07; `plots/` as an unnumbered consumer. Record decisions visible in code: shared registries, ROOT-free numerical cores, runtime adapters, explicit persisted schemas, atomic publication, fail-loud compatibility checks, and versioned Stage-1 runtime bundle.

- [ ] **Step 5: Verify orientation pages**

Run:

```bash
pytest tests/test_wiki.py -q
rg -n "graal_pipeline|06_observable_extraction|06_plots" wiki/Home.md wiki/getting-started.md wiki/architecture.md wiki/workflow.md wiki/repository-structure.md wiki/architecture-decisions.md
```

Expected: pytest PASS; `rg` exits 1 with no stale matches.

- [ ] **Step 6: Commit orientation and architecture pages**

```bash
git add tests/test_wiki.py wiki/Home.md wiki/getting-started.md wiki/architecture.md wiki/workflow.md wiki/repository-structure.md wiki/architecture-decisions.md
git commit -m "docs: explain project architecture"
```

### Task 3: Document Scientific Foundations

**Files:**
- Modify: `wiki/scientific-foundations.md`
- Modify: `wiki/physics-channels.md`
- Modify: `wiki/photon-pairing.md`
- Modify: `wiki/compton-beam-and-polarization.md`
- Modify: `tests/test_wiki.py`

**Interfaces:**
- Consumes: `00_common/physics/channels.py`, `cross_sections.py`, `pairing.py`, `compton.py`, their tests, MC generator names, and `plots/fig7_compton_polarization.py`.
- Produces: common scientific vocabulary and equations referenced by training, reconstruction, calibration, observable, and plot pages.

- [ ] **Step 1: Extend required-section checks**

Add these entries to `REQUIRED_SECTIONS`:

```python
"scientific-foundations.md": ("## Reaction and Final State", "## Analysis Hypotheses", "## Reconstruction Comparison", "## Measured Observable"),
"physics-channels.md": ("## Channel Registry", "## Signal and Background Roles", "## Thresholds and Cross Sections", "## Adding a Channel"),
"photon-pairing.md": ("## Pairing Space", "## Heavy and Light Mesons", "## Chi-Square Definition", "## Shared Contract"),
"compton-beam-and-polarization.md": ("## GRAAL Beam", "## Compton Edge", "## Polarization Transfer", "## Figure 7 Reproduction"),
```

Run `pytest tests/test_wiki.py -q`; expect failures for these headings.

- [ ] **Step 2: Write reaction, hypothesis, and observable narrative**

Explain four-photon eta/pi0 reconstruction with recoil proton, distinguish final-state channel from feature/reconstruction hypothesis, compare standard chi-square and optional Stage-1 gate, and define beam asymmetry as the downstream observable without claiming a measured result.

- [ ] **Step 3: Document registry and cross-section ownership**

Enumerate current `CHANNEL_NAMES` from `channels.py`, generator filename ownership, threshold behavior, fixed versus callable cross sections, and tests that prevent registry drift. Explain why signal prior is not a measured signal cross section.

- [ ] **Step 4: Document pairing and Compton equations**

Map pairing indices and heavy/light mass targets to `Pairing` and `Hypothesis`. Present the implemented chi-square inputs. Present laser energy, Compton parameter/edge, and linear polarization transfer using names and units from `compton.py`; identify Figure 7 PDF/ROOT outputs without embedding generated binaries.

- [ ] **Step 5: Verify and commit scientific pages**

```bash
pytest tests/test_wiki.py 00_common/tests/test_channels.py 00_common/tests/test_cross_sections.py 00_common/tests/test_pairing.py 00_common/tests/test_compton.py -q
git add tests/test_wiki.py wiki/scientific-foundations.md wiki/physics-channels.md wiki/photon-pairing.md wiki/compton-beam-and-polarization.md
git commit -m "docs: describe scientific foundations"
```

Expected: all selected tests PASS.

### Task 4: Document Pre-Analysis, Event Selection, and Monte Carlo

**Files:**
- Modify: `wiki/01-pre-analysis.md`
- Modify: `wiki/01-detector-cuts.md`
- Modify: `wiki/02-event-selection.md`
- Modify: `wiki/03-monte-carlo-simulation.md`
- Modify: `tests/test_wiki.py`

**Interfaces:**
- Consumes: `01_pre_analysis/PreAnalysis.C`, `PreAnalysis.h`, `CutManager.h`, `cuts/*.cpp`, `02_event_selector/select_events.py`, `03_mc_simulation/generators/*`, `mc_status.py`, registry data, and related tests.
- Produces: verified stage 01-03 contracts, ROOT tree lineage, cut ownership, generator command patterns, and status exit-code semantics.

- [ ] **Step 1: Add stage 01-03 section requirements and run failing tests**

```python
"01-pre-analysis.md": ("## Purpose", "## Input and Output Trees", "## Processing Lifecycle", "## Implementation Map"),
"01-detector-cuts.md": ("## Cut Manager", "## Cut Families", "## Run-Period Variants", "## Extension Rules"),
"02-event-selection.md": ("## Selection Contract", "## Required Branches", "## Atomic Output", "## Failure Behavior"),
"03-monte-carlo-simulation.md": ("## Generator Set", "## ROOT Output Contract", "## Channel Status", "## Regeneration Boundaries"),
```

Run `pytest tests/test_wiki.py -q`; expect failures for these headings.

- [ ] **Step 2: Write pre-analysis and cut documentation**

Describe ROOT selector inputs, `h80` output, event lifecycle methods, cut-manager coordination, particle/topology and period-specific cut files, naming convention, and safe extension process. Avoid assigning physics meaning beyond code and verified comments.

- [ ] **Step 3: Write event-selection documentation**

Document `pre_*.root` discovery, `h80` input, required branches (`gammas`, `fcharged_theta`, `RunNumber`, `Polarization`, `Xstrip`), filter `gammas.size() > 1 && fcharged_theta.size() == 1`, `h85` output, vector-preservation setting, output validation, implicit-MT option, atomic directory replacement, and stale-output refusal. Add a focused Mermaid diagram for validation, staging, output validation, atomic replacement, and failure preservation; follow it with the same sequence in text.

- [ ] **Step 4: Write Monte Carlo documentation**

List generator macros from the current directory, channel-to-file mapping through registry, `mc` tree contract, smearing helper, generator invocation pattern, status table, stale-age warning, and exit codes 0/1/2. Explain that staleness warns but does not change completeness exit status.

- [ ] **Step 5: Verify and commit stage 01-03 pages**

```bash
pytest tests/test_wiki.py tests/test_event_selector.py 03_mc_simulation/tests -q
git add tests/test_wiki.py wiki/01-pre-analysis.md wiki/01-detector-cuts.md wiki/02-event-selection.md wiki/03-monte-carlo-simulation.md
git commit -m "docs: document input preparation stages"
```

Expected: selected tests PASS, with ROOT-dependent skips reported rather than hidden.

### Task 5: Document Stage-1 Dataset, Weighting, Training, and Artifacts

**Files:**
- Modify: `wiki/04-bdt-training.md`
- Modify: `wiki/04-dataset-and-features.md`
- Modify: `wiki/04-weighting-and-photon-loss.md`
- Modify: `wiki/04-training-artifacts.md`
- Modify: `tests/test_wiki.py`

**Interfaces:**
- Consumes: `00_common/stage1/*`, `04_bdt_training/beam_spectrum.py`, `photon_loss.py`, `dataset/*`, `training/*`, CLI entry points, versioned `artifacts/stage1/*`, and all BDT tests.
- Produces: precise train-to-runtime contract reused by Stage-1 gate and reconstruction documentation.

- [ ] **Step 1: Add Stage-1 section requirements and run failing tests**

```python
"04-bdt-training.md": ("## Training Pipeline", "## Entry Points", "## Data Flow", "## Verification"),
"04-dataset-and-features.md": ("## Four-Photon Event Contract", "## Feature Schema", "## Dataset Schema", "## Metadata and Reproducibility"),
"04-weighting-and-photon-loss.md": ("## Acceptance Model", "## Beam Reweighting", "## Channel Yields", "## Signal Prior"),
"04-training-artifacts.md": ("## Hyperparameter Search", "## Model Training", "## Runtime Bundle", "## Provenance Validation"),
```

Run `pytest tests/test_wiki.py -q`; expect failures for these headings.

- [ ] **Step 2: Document dataset and feature construction**

Explain signal/background channel choice versus hypothesis choice, identical photon-loss treatment for all classes, exactly-four-observed-photon contract, feature names/count/order from `features.py`, dataset arrays and dtypes from `Stage1Dataset`, metadata, random seeds, and beam-spectrum prerequisite.

- [ ] **Step 3: Document weighting equations and safeguards**

Describe beam-spectrum reweighting, threshold-aware cross-section integration, generated-count denominator, acceptance preservation, eta-to-3pi0 branching relationship, chosen signal prior, normalization to mean event weight one for XGBoost, and Kish effective sample-size diagnostic. Tie every symbol to concrete arrays or dataclasses.

- [ ] **Step 4: Document search, fit, reporting, and runtime artifacts**

Explain grid-search input/output, training split and sample weights, weighted threshold selection, callbacks, metrics/ROC/score plots, and exact bundle filenames: `bdt_stage1.json`, `stage1_threshold.txt`, `stage1_provenance.json`. Include versioned reporting artifacts and distinguish training-only files from runtime-required files. Add a Mermaid diagram from channel ROOT trees and beam spectrum through dataset, search, training, runtime bundle, provenance check, and gate; provide an equivalent artifact table.

- [ ] **Step 5: Verify and commit Stage-1 pages**

```bash
pytest tests/test_wiki.py 00_common/tests/test_stage1_artifacts.py 04_bdt_training/tests tests/test_stage1_contracts.py -q
git add tests/test_wiki.py wiki/04-bdt-training.md wiki/04-dataset-and-features.md wiki/04-weighting-and-photon-loss.md wiki/04-training-artifacts.md
git commit -m "docs: document Stage-1 training"
```

Expected: selected tests PASS.

### Task 6: Document Reconstruction Paths and Kinematic Fit

**Files:**
- Modify: `wiki/05-reconstruction.md`
- Modify: `wiki/05-chi-square-pairing.md`
- Modify: `wiki/05-stage1-gate.md`
- Modify: `wiki/05-kinematic-fit.md`
- Modify: `wiki/05-sidebands-and-two-pion.md`
- Modify: `tests/test_wiki.py`

**Interfaces:**
- Consumes: `05_reconstruction/core/*`, `runtime/*`, reconstruction entry points, `prepare_signal_mc_selected.py`, `validate_kinematic_fit.py`, and reconstruction tests.
- Produces: shared reconstruction decision model, explicit difference between chi-square and BDT paths, fit/output schema, and alternate-path documentation.

- [ ] **Step 1: Add reconstruction section requirements and run failing tests**

```python
"05-reconstruction.md": ("## Shared Reconstruction Core", "## Supported Entry Points", "## Event Flow", "## Output Trees"),
"05-chi-square-pairing.md": ("## Standard Path", "## Pairing Selection", "## Event Guards", "## Output Contract"),
"05-stage1-gate.md": ("## Runtime Bundle", "## Score and Threshold", "## Hypothesis Compatibility", "## Batch Evaluation"),
"05-kinematic-fit.md": ("## Six Constraints", "## Fit Inputs", "## Convergence and Diagnostics", "## Fitted Outputs"),
"05-sidebands-and-two-pion.md": ("## Sideband Reconstruction", "## Signal-MC Adapter", "## Two-Pion Path", "## Boundaries"),
```

Run `pytest tests/test_wiki.py -q`; expect failures for these headings.

- [ ] **Step 2: Write shared reconstruction and chi-square pages**

Document CLI/runtime separation, `EventInput`/configuration/result ownership, ROOT-free event logic, required selected-tree inputs, event guards, hypothesis selection, pairing enumeration and selection, standard path with no model dependency, output tree naming, raw/fitted branch families, and failure semantics. Add a Mermaid decision flow covering guards, optional gate, pairing, cuts, optional 6C fit, and persisted result; describe each branch in prose.

- [ ] **Step 3: Write Stage-1 gate page**

Document default artifact directory, model/threshold/provenance load order, missing-file errors, feature schema reuse, score as signal probability before thresholding, acceptance at threshold, ordered batch answers, and `check_hypothesis` refusal when model and reconstruction final-state hypotheses differ.

- [ ] **Step 4: Write kinematic-fit and alternate-path pages**

Map fit inputs and covariance to the six constraints implemented in `kinematic_fit.py`, convergence fields, raw versus fitted four-vectors, validation tool, sideband entry point, signal-MC selected adapter, and `reconstruct_2pi0.py`. Clearly label paths that do not feed the primary eta-pi0 observable workflow.

- [ ] **Step 5: Verify and commit reconstruction pages**

```bash
pytest tests/test_wiki.py 05_reconstruction/tests -q
git add tests/test_wiki.py wiki/05-reconstruction.md wiki/05-chi-square-pairing.md wiki/05-stage1-gate.md wiki/05-kinematic-fit.md wiki/05-sidebands-and-two-pion.md
git commit -m "docs: document reconstruction paths"
```

Expected: selected tests PASS.

### Task 7: Document Calibration and Observable Extraction

**Files:**
- Modify: `wiki/06-calibration.md`
- Modify: `wiki/07-observable-extraction.md`
- Modify: `wiki/07-beam-asymmetry-estimators.md`
- Modify: `wiki/07-background-correction.md`
- Modify: `wiki/07-systematics-and-outputs.md`
- Modify: `tests/test_wiki.py`

**Interfaces:**
- Consumes: `06_calibration/*`, `config/run_manifest.csv`, `07_observable_extraction/calibration/*`, `core/*`, `io/*`, `plotting/*`, CLI entry point, theory note, and both stage test suites.
- Produces: run-to-exposure lineage, estimator equations, correction/systematics model, public ROOT/PDF schema, and explicit warning/failure rules.

- [ ] **Step 1: Add calibration/observable section requirements and run failing tests**

```python
"06-calibration.md": ("## Run Manifest", "## Strip-Energy Calibration", "## Flux Products", "## QA and Failure Policy"),
"07-observable-extraction.md": ("## Inputs and Preconditions", "## Extraction Workflow", "## Public Products", "## First-Pass and Full Modes"),
"07-beam-asymmetry-estimators.md": ("## Exposure Strata", "## Normalized-Ratio Fit", "## Conditional Likelihood", "## Physical Domain"),
"07-background-correction.md": ("## Mass Regions", "## Sideband Template", "## Background Fraction", "## Corrected Asymmetry"),
"07-systematics-and-outputs.md": ("## Systematic Components", "## Bootstrap by Run", "## Covariance Combination", "## ROOT and Figure Outputs"),
```

Run `pytest tests/test_wiki.py -q`; expect failures for these headings.

- [ ] **Step 2: Write calibration page**

Document manifest row model and CSV source, pre-analysis/flux inputs, run grouping, strip sample statistics, polynomial calibration and monotonicity checks, missing-strip interpolation rules, negative-flux handling, default/custom energy binnings, run/group/strip-exposure CSVs, calibrated ROOT product, QA JSON, progress controls, atomic publication, and which findings warn versus fail. Add a Mermaid flow from manifest, `h80`, and external flux through calibration, QA gates, and published exposure artifacts; provide an input/output table.

- [ ] **Step 3: Write observable workflow and estimator pages**

Document reconstructed-event adapter, calibrated flux exposure adapter, binning, polarization strata, default raw-BDT input, first-pass/full modes, normalized ratio and conditional likelihood equations, vertical/horizontal sign convention, positivity domain, profile errors, and per-bin diagnostic model. Add a Mermaid flow from reconstructed events and calibrated exposures through binning, estimator choice, background correction, systematic covariance, ROOT output, and figures; provide the same stages as an ordered list.

- [ ] **Step 4: Write background, systematics, and output pages**

Document multidimensional mass regions, factorized sideband template, signal-region fraction conversion, correction and uncertainty propagation, signal-leakage validation, polarization-scale component, run bootstrap, covariance combination, randomized-label diagnostic, ROOT objects, covariance matrices, PDFs, diagnostics, and Figure 4 generation.

- [ ] **Step 5: Verify and commit calibration/observable pages**

```bash
pytest tests/test_wiki.py 06_calibration/tests 07_observable_extraction/tests -q
git add tests/test_wiki.py wiki/06-calibration.md wiki/07-observable-extraction.md wiki/07-beam-asymmetry-estimators.md wiki/07-background-correction.md wiki/07-systematics-and-outputs.md
git commit -m "docs: document calibration and observables"
```

Expected: selected tests PASS, with environment-related skips visible.

### Task 8: Write Cross-Cutting Data, Commands, Development, Testing, and Operations Reference

**Files:**
- Modify: `wiki/plotting-and-diagnostics.md`
- Modify: `wiki/data-and-artifacts.md`
- Modify: `wiki/commands-and-configuration.md`
- Modify: `wiki/development.md`
- Modify: `wiki/testing.md`
- Modify: `wiki/troubleshooting.md`
- Modify: `wiki/known-limitations.md`
- Modify: `tests/test_wiki.py`

**Interfaces:**
- Consumes: all stage pages, `scripts/setup.sh`, `pyproject.toml`, `04_bdt_training/requirements.txt`, plotting sources/tests, top-level tests, `.gitignore`, and current tracked artifacts.
- Produces: consolidated reference that stage pages link to instead of duplicating setup, schemas, commands, test policy, and common recovery guidance.

- [ ] **Step 1: Add cross-cutting section requirements and stale-reference scan**

```python
"plotting-and-diagnostics.md": ("## Plot Entry Points", "## Reconstruction Data Adapter", "## Outputs", "## Interpretation Boundaries"),
"data-and-artifacts.md": ("## Artifact Lineage", "## ROOT Trees", "## Training and Calibration Formats", "## Ownership and Persistence"),
"commands-and-configuration.md": ("## Command Matrix", "## Setup Options", "## Stage Options", "## Configuration Sources"),
"development.md": ("## Environment", "## Editable Installation", "## Package Imports", "## Change Workflow"),
"testing.md": ("## Test Layout", "## Focused Tests", "## ROOT-Dependent Tests", "## Full Verification"),
"troubleshooting.md": ("## Setup Failures", "## Missing or Invalid Data", "## Model Compatibility", "## Calibration and Fit Failures"),
"known-limitations.md": ("## Execution Model", "## Environment Dependencies", "## Data Availability", "## Scope Boundaries"),
```

Add:

```python
STALE_REFERENCES = ("graal_pipeline", "06_observable_extraction", "06_plots")


def test_wiki_does_not_document_removed_architecture():
    for source, text in _pages().items():
        for stale in STALE_REFERENCES:
            assert stale not in text, f"{source}: stale reference {stale}"
```

Run `pytest tests/test_wiki.py -q`; expect required-section failures.

- [ ] **Step 2: Write plotting and artifact reference**

Document `plots/dalitz.py`, `fig7_compton_polarization.py`, and `kinfit_resolution.py`; distinguish ROOT-based and uproot/matplotlib paths; list inputs, outputs, truth requirements, and interpretation limits. Build an artifact-lineage Mermaid diagram and equivalent table covering `h80`, `h85`, `mc`, beam-spectrum NPZ, Stage-1 dataset NPZ, model bundle, reconstruction ROOT trees, calibration CSV/JSON/ROOT, observable ROOT/PDF, and ignored `results/` outputs.

- [ ] **Step 3: Write command/configuration and development reference**

Transcribe verified setup and stage commands, important defaults, and configuration ownership. Document Python/PyROOT compatibility, venv with system site packages, dependency installation, editable package mapping, local versus farm data layout, external `flux.root`, import verification, and safe focused-change workflow.

- [ ] **Step 4: Write testing, troubleshooting, and limitations**

Map test directories to responsibilities, explain `--import-mode=importlib`, identify PyROOT-dependent versus numerical tests, and give focused/full commands. Build a symptom/cause/action table from real error boundaries. State factual limitations: manual stage ordering, external ROOT/PyROOT and datasets, no remote data acquisition, unversioned large outputs, fixed primary reaction scope, and no automatic wiki publication.

- [ ] **Step 5: Verify and commit reference pages**

```bash
pytest tests/test_wiki.py plots/tests tests/test_repository_layout.py tests/test_setup_script.py tests/test_packaging.py -q
git add tests/test_wiki.py wiki/plotting-and-diagnostics.md wiki/data-and-artifacts.md wiki/commands-and-configuration.md wiki/development.md wiki/testing.md wiki/troubleshooting.md wiki/known-limitations.md
git commit -m "docs: add project operations reference"
```

Expected: selected tests PASS.

### Task 9: Restore and Test Wiki Synchronization, Then Link README

**Files:**
- Restore/modify: `scripts/sync-wiki.sh`
- Create: `tests/test_wiki_sync.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: complete `wiki/*.md` source set and Git CLI.
- Produces: explicit default GitHub Wiki publication command, locally testable remote override, deterministic `master` publication branch, and repository-to-wiki navigation.

- [ ] **Step 1: Write failing synchronization tests**

Create `tests/test_wiki_sync.py`:

```python
from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess


ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts/sync-wiki.sh"


def _git(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=cwd, text=True, capture_output=True, check=True
    )


def test_sync_script_has_valid_bash_syntax():
    result = subprocess.run(
        ["bash", "-n", str(SCRIPT)], text=True, capture_output=True
    )
    assert result.returncode == 0, result.stderr


def test_sync_rejects_empty_wiki_source_before_remote_changes(tmp_path: Path):
    repo = tmp_path / "repo"
    (repo / "scripts").mkdir(parents=True)
    (repo / "wiki").mkdir()
    shutil.copy2(SCRIPT, repo / "scripts/sync-wiki.sh")
    remote = tmp_path / "wiki.git"
    _git("init", "--bare", str(remote), cwd=tmp_path)
    env = os.environ.copy()
    env["WIKI_REMOTE"] = str(remote)
    result = subprocess.run(
        ["bash", str(repo / "scripts/sync-wiki.sh")],
        cwd=repo,
        env=env,
        text=True,
        capture_output=True,
    )
    assert result.returncode != 0
    assert "no Markdown pages" in result.stderr
    assert not (remote / "refs/heads/master").exists()


def test_sync_publishes_exact_page_set_to_empty_local_remote(tmp_path: Path):
    remote = tmp_path / "wiki.git"
    _git("init", "--bare", str(remote), cwd=tmp_path)
    env = os.environ.copy()
    env.update(
        WIKI_REMOTE=str(remote),
        GIT_AUTHOR_NAME="Wiki Test",
        GIT_AUTHOR_EMAIL="wiki@example.invalid",
        GIT_COMMITTER_NAME="Wiki Test",
        GIT_COMMITTER_EMAIL="wiki@example.invalid",
    )
    subprocess.run(
        ["bash", str(SCRIPT)], cwd=ROOT, env=env, check=True,
        text=True, capture_output=True,
    )
    checkout = tmp_path / "checkout"
    _git("clone", "--branch", "master", str(remote), str(checkout), cwd=tmp_path)
    expected = {path.name for path in (ROOT / "wiki").glob("*.md")}
    actual = {path.name for path in checkout.glob("*.md")}
    assert actual == expected
```

Run `pytest tests/test_wiki_sync.py -q`; expect failure because the script is absent.

- [ ] **Step 2: Restore and harden `scripts/sync-wiki.sh`**

Restore the prior clone/copy/commit/push flow, then make these exact compatibility changes:

```bash
WIKI_REMOTE="${WIKI_REMOTE:-https://github.com/AntoninoFulci/GRAAL_Analysis.wiki.git}"

shopt -s nullglob
WIKI_PAGES=("${WIKI_SRC}"/*.md)
if [[ ${#WIKI_PAGES[@]} -eq 0 ]]; then
    echo "ERROR: no Markdown pages found in ${WIKI_SRC}" >&2
    exit 1
fi
```

After clone or initialization, run `git branch -M master`. Copy with `cp "${WIKI_PAGES[@]}" .`. Preserve fail-loud clone diagnostics, replacement of stale remote pages, no-op detection, commit message `docs: sync wiki from main repo`, and `git push -u origin master`.

- [ ] **Step 3: Run synchronization tests twice**

```bash
pytest tests/test_wiki_sync.py -q
bash -n scripts/sync-wiki.sh
```

Expected: PASS. Tests use only local temporary bare repositories; no network remote is contacted.

- [ ] **Step 4: Add concise README wiki link**

Add a `Documentation` section after the project overview or setup summary:

```markdown
## Documentation

See the [GitHub Wiki](https://github.com/AntoninoFulci/GRAAL_Analysis/wiki)
for the architecture, scientific workflow, stage guides, data contracts,
commands, testing strategy, troubleshooting, and known limitations.
```

Do not reintroduce removed orchestrator commands or duplicate wiki content.

- [ ] **Step 5: Verify and commit publication integration**

```bash
pytest tests/test_wiki.py tests/test_wiki_sync.py tests/test_setup_script.py -q
git diff --check -- README.md scripts/sync-wiki.sh tests/test_wiki_sync.py
git add README.md scripts/sync-wiki.sh tests/test_wiki_sync.py
git commit -m "docs: restore wiki publication workflow"
```

Expected: tests PASS and diff check emits no output.

### Task 10: Perform Full Consistency and Regression Verification

**Files:**
- Modify only if verification finds an error: `wiki/*.md`, `tests/test_wiki.py`, `tests/test_wiki_sync.py`, `README.md`, `scripts/sync-wiki.sh`

**Interfaces:**
- Consumes: complete wiki, tests, current source tree, and approved design spec.
- Produces: evidence that navigation, documentation claims, synchronization, and existing project behavior remain valid.

- [ ] **Step 1: Run documentation gates**

```bash
pytest tests/test_wiki.py tests/test_wiki_sync.py -q
bash -n scripts/sync-wiki.sh
rg -n "\b(TODO|TBD|FIXME)\b|graal_pipeline|06_observable_extraction|06_plots" wiki README.md
```

Expected: pytest PASS; Bash syntax PASS; `rg` exits 1 with no matches.

- [ ] **Step 2: Check documented source paths**

Extract every backticked repository path ending in `.py`, `.sh`, `.toml`, `.csv`, `.C`, `.h`, or `.cpp` from the wiki and verify it exists in the current working tree. Fix typos in wiki text; do not recreate obsolete source paths.

Run this read-only checker:

```bash
python - <<'PY'
import re
from pathlib import Path

root = Path.cwd()
missing = []
for page in sorted((root / "wiki").glob("*.md")):
    text = page.read_text(encoding="utf-8")
    for raw in re.findall(r"`([^`]+\.(?:py|sh|toml|csv|C|h|cpp))`", text):
        if "/" in raw and not (root / raw).exists():
            missing.append(f"{page.name}: {raw}")
if missing:
    raise SystemExit("Missing documented paths:\n" + "\n".join(missing))
print("All documented source paths exist.")
PY
```

Expected: `All documented source paths exist.`

- [ ] **Step 3: Run focused domain suites**

```bash
pytest -q \
  tests/test_repository_layout.py \
  tests/test_setup_script.py \
  tests/test_packaging.py \
  tests/test_stage1_contracts.py \
  00_common/tests \
  03_mc_simulation/tests \
  04_bdt_training/tests \
  05_reconstruction/tests \
  06_calibration/tests \
  07_observable_extraction/tests \
  plots/tests
```

Expected: PASS, with any environment-dependent skips listed explicitly.

- [ ] **Step 4: Run full regression suite**

```bash
pytest -q
```

Expected: PASS. If collection fails solely because PyROOT or another declared scientific dependency is unavailable, record exact import error and preserve results from documentation and dependency-free suites; do not weaken tests.

- [ ] **Step 5: Review diff boundaries and formatting**

```bash
git diff --check
git status --short
git diff -- README.md scripts/sync-wiki.sh tests/test_wiki.py tests/test_wiki_sync.py wiki
```

Confirm only documentation-related paths from this plan were changed by implementation, aside from pre-existing user changes. Confirm no generated ROOT, NPZ, PDF, PNG, cache, or graph artifact was added.

- [ ] **Step 6: Commit verification fixes if needed**

If Steps 1-5 required documentation or test corrections:

```bash
git add README.md scripts/sync-wiki.sh tests/test_wiki.py tests/test_wiki_sync.py wiki
git commit -m "docs: finalize wiki verification"
```

If no corrections were required, do not create an empty commit.

---

## Final Handoff Evidence

Report:

- page count and main navigation groups;
- diagrams created and where they live;
- synchronization script behavior and local integration-test result;
- focused and full pytest results, including exact skip/failure reasons;
- `git diff --check` result;
- confirmation that no remote wiki push occurred;
- any residual risk caused by unavailable external data or PyROOT environment.
