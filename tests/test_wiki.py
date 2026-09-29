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

REQUIRED_SECTIONS = {
    "Home.md": (
        "## Choose Your Path",
        "## Pipeline at a Glance",
        "## Documentation Map",
    ),
    "getting-started.md": (
        "## Requirements",
        "## Local Setup",
        "## Farm Setup",
        "## Verify the Installation",
    ),
    "architecture.md": (
        "## System Context",
        "## End-to-End Flow",
        "## Package Boundaries",
        "## External Boundaries",
    ),
    "workflow.md": (
        "## Execution Model",
        "## Main Data Flow",
        "## Training Branch",
        "## Calibration Branch",
        "## Reuse and Failure Boundaries",
    ),
    "repository-structure.md": (
        "## Top-Level Layout",
        "## Package Name Mapping",
        "## Generated and External Data",
    ),
    "architecture-decisions.md": (
        "## Shared Contracts",
        "## ROOT-Free Cores",
        "## Explicit Artifacts",
        "## Fail-Loud Boundaries",
    ),
    "scientific-foundations.md": (
        "## Reaction and Final State",
        "## Analysis Hypotheses",
        "## Reconstruction Comparison",
        "## Measured Observable",
    ),
    "physics-channels.md": (
        "## Channel Registry",
        "## Signal and Background Roles",
        "## Thresholds and Cross Sections",
        "## Adding a Channel",
    ),
    "photon-pairing.md": (
        "## Pairing Space",
        "## Heavy and Light Mesons",
        "## Chi-Square Definition",
        "## Shared Contract",
    ),
    "compton-beam-and-polarization.md": (
        "## GRAAL Beam",
        "## Compton Edge",
        "## Polarization Transfer",
        "## Figure 7 Reproduction",
    ),
    "01-pre-analysis.md": (
        "## Purpose",
        "## Input and Output Trees",
        "## Processing Lifecycle",
        "## Implementation Map",
    ),
    "01-detector-cuts.md": (
        "## Cut Manager",
        "## Cut Families",
        "## Run-Period Variants",
        "## Extension Rules",
    ),
    "02-event-selection.md": (
        "## Selection Contract",
        "## Required Branches",
        "## Atomic Output",
        "## Failure Behavior",
    ),
    "03-monte-carlo-simulation.md": (
        "## Generator Set",
        "## ROOT Output Contract",
        "## Channel Status",
        "## Regeneration Boundaries",
    ),
}


def _pages() -> dict[str, str]:
    return {
        path.name: path.read_text(encoding="utf-8")
        for path in WIKI.glob("*.md")
    }


def _internal_page(target: str) -> str | None:
    clean = target.split("#", 1)[0].split("?", 1)[0]
    if not clean or "://" in clean or clean.startswith("../"):
        return None
    name = Path(clean).name
    return name if name.endswith(".md") else f"{name}.md"


def test_wiki_contains_exactly_the_supported_pages():
    assert set(_pages()) == EXPECTED_PAGES


def test_sidebar_lists_every_public_page_once():
    pages = _pages()
    assert "_Sidebar.md" in pages, "missing wiki/_Sidebar.md"
    targets = [
        page
        for raw in LINK.findall(pages["_Sidebar.md"])
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
    path = WIKI / source
    assert path.is_file(), f"missing {path.relative_to(ROOT)}"
    assert not PLACEHOLDER.search(path.read_text(encoding="utf-8")), source


def test_mermaid_blocks_are_closed():
    for source, text in _pages().items():
        starts = text.count("```mermaid")
        closed = len(
            re.findall(r"```mermaid\n.*?\n```", text, flags=re.DOTALL)
        )
        assert closed == starts, source


@pytest.mark.parametrize("source,headings", sorted(REQUIRED_SECTIONS.items()))
def test_pages_contain_required_sections(
    source: str, headings: tuple[str, ...]
):
    text = (WIKI / source).read_text(encoding="utf-8")
    for heading in headings:
        assert heading in text, f"{source}: missing {heading}"
