import json
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


def test_agents_protects_untracked_user_data_from_unapproved_mutation():
    text = read("AGENTS.md").lower()
    assert "raw/local inputs" in text
    assert "working data" in text
    assert "cache" in text
    assert "virtual environments" in text
    assert "must not delete or overwrite" in text
    assert "without explicit authorization" in text


def test_requirements_include_scipy_and_pytest():
    requirements = {
        line.split("=", 1)[0].split(">", 1)[0].strip()
        for line in read("requirements-dev.txt").splitlines()
        if line and not line.startswith("#")
    }
    assert {"scipy", "pytest"} <= requirements


def test_graphify_is_pinned_and_maintenance_uses_the_project_interpreter():
    """A user-global Graphify executable would make clone bootstrap non-portable."""
    assert "graphifyy==0.9.7" in read("requirements-graphify.txt")
    makefile = read("Makefile")
    assert "GRAPHIFY ?= $(PYTHON) -m graphify" in makefile
    assert "requirements-graphify.txt" in makefile.split("setup:", 1)[1].split("\n\n", 1)[0]


def test_graphify_disambiguates_repeated_document_headings():
    """Published graph labels must identify which document owns a generic heading."""
    graph = json.loads(read("graphify-out/graph.json"))
    expected = {
        "readme_graal_analysis": "GRAAL Analysis Repository README",
        "wiki_home_graal_analysis": "GRAAL Analysis Wiki Home",
        "wiki_sidebar_graal_analysis": "GRAAL Analysis Wiki Navigation",
        "docs_superpowers_plans_2026_09_08_observable_run_database_global_constraints": "Observable-run Database Global Constraints",
        "wiki_strip_energy_flux_implementation_plan_global_constraints": "Strip-energy Flux Global Constraints",
        "docs_superpowers_plans_2026_09_09_two_person_ai_handoff_global_constraints": "Two-Person AI Handoff Global Constraints",
    }
    actual = {
        node["id"]: node["label"]
        for node in graph["nodes"]
        if node["id"] in expected
    }
    assert actual == expected
    assert len(set(actual.values())) == len(actual)

    community_labels = json.loads(read("graphify-out/.graphify_labels.json"))
    duplicates = {
        label
        for label in community_labels.values()
        if list(community_labels.values()).count(label) > 1
    }
    assert not duplicates, f"duplicate published Graphify community labels: {duplicates}"


def test_makefile_exposes_required_targets():
    makefile = read("Makefile")
    required = {
        "help", "setup", "syntax", "test-root-free", "test",
        "validate-manifest", "observable-runs", "graph-update",
        "artifact-inventory", "verify",
    }
    declared = set(re.findall(r"^([a-z][a-z0-9-]*):", makefile, re.MULTILINE))
    assert required <= declared


def test_verify_uses_saved_inventory_without_regenerating_it():
    """Verification must fail on drift, not replace the provenance it is checking."""
    makefile = read("Makefile")
    target = makefile.split("verify:", 1)[1]
    header, _, recipe = target.partition("\n")
    assert "artifact-inventory" not in header
    assert "--verify --inventory ARTIFACTS.json" in recipe


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
    assert "08_polarization/tests" in recipe
    assert "--ignore=08_polarization/tests/test_figure4_end_to_end.py" in recipe
    assert "--ignore=08_polarization/tests/test_root_events_integration.py" in recipe


def test_default_test_discovery_includes_person2_polarization():
    assert '"08_polarization/tests"' in read("pyproject.toml")


def test_polarization_diagnostics_do_not_share_immutable_s6_directory():
    text = read("docs/physics/polarization.md")
    assert "--output-dir results/diagnostics/polarization/figure4_comparison" in text
    assert "--output-dir results/physics/polarization/figure4_comparison" not in text


def test_testing_docs_name_top_level_pyroot_plot_module():
    text = read("wiki/testing.md")
    assert "06_plots/dalitz.py" in text


def test_two_person_physics_roadmap_has_only_two_owners_and_defined_handoffs():
    """Catch an added owner or a missing artifact handoff in the physics plan."""
    text = read("docs/collaboration/two-person-physics-roadmap.md")
    assert len(re.findall(r"^## Primary ownership: ", text, re.MULTILINE)) == 2
    expected_acceptance = {
        "results/physics/normalization/handoffs/<acceptance_release_id>/acceptance_v1.csv",
        "results/physics/normalization/handoffs/<acceptance_release_id>/acceptance_phi_response_v1.csv",
        "results/physics/normalization/handoffs/<acceptance_release_id>/acceptance_qa.json",
    }
    expected_polarization = {
        "results/physics/polarization/sigma_v1.csv",
        "results/physics/polarization/sigma_covariance.npz",
        "results/physics/polarization/polarization_qa.json",
    }
    handoff_section = text.split("### Handoff Person 1 → Person 2", 1)[1]
    handoff_block = re.search(r"```text\n(.*?)\n```", handoff_section, re.DOTALL)
    assert handoff_block is not None
    assert set(handoff_block.group(1).splitlines()) == expected_acceptance
    assert expected_polarization <= set(text.splitlines())

    plan = read("docs/superpowers/plans/2026-09-09-two-person-ai-handoff.md")
    plan_block = re.search(
        r"handoff (?:filenames|paths):\n\n```text\n(.*?)\n```", plan, re.DOTALL
    )
    assert plan_block is not None
    plan_acceptance = {
        line
        for line in plan_block.group(1).splitlines()
        if line.startswith("results/physics/normalization/")
    }
    assert plan_acceptance == expected_acceptance

    deprecated_acceptance = {
        "results/physics/normalization/acceptance_v1.csv",
        "results/physics/normalization/acceptance_qa.json",
    }
    assert all(path not in text for path in deprecated_acceptance)
    assert all(path not in plan for path in deprecated_acceptance)
    assert "D2/neutron work is deferred" in text
    assert "eta-prime work is deferred" in text


def test_shared_docs_publish_exact_s4_and_s6_triplets():
    roadmap = read("docs/collaboration/two-person-physics-roadmap.md")
    polarization = read("docs/physics/polarization.md")
    expected_s4 = {
        "results/physics/polarization_fits/<fit_release_id>/azimuth_counts_v1.csv",
        "results/physics/polarization_fits/<fit_release_id>/sigma_fit_v1.csv",
        "results/physics/polarization_fits/<fit_release_id>/sigma_fit_qa.json",
    }
    expected_s6 = {
        "results/physics/polarization/sigma_v1.csv",
        "results/physics/polarization/sigma_covariance.npz",
        "results/physics/polarization/polarization_qa.json",
    }
    for text in (roadmap, polarization):
        assert expected_s4 <= set(text.splitlines())
        assert expected_s6 <= set(text.splitlines())
        assert "azimuth_counts_v1.csv" in text
        assert "immutable" in text.lower() or "immutabile" in text.lower()
        assert "no-overwrite" in text.lower()


def test_shared_docs_define_canonical_s4_cli_and_release_edges():
    roadmap = read("docs/collaboration/two-person-physics-roadmap.md")
    polarization = read("docs/physics/polarization.md")
    for text in (roadmap, polarization):
        assert "python 08_polarization/fit_sigma.py" in text
        assert "--acceptance-handoff results/physics/normalization/handoffs/<acceptance_release_id>/acceptance_qa.json" in text
        assert "--reco-inventory results/reconstruction/inventory.json" in text
        assert "--config config/physics/polarization_v1.json" in text
        assert "--fit-release-id <fit_release_id>" in text
        assert "--output-root results/physics/polarization_fits" in text
        assert "N2 -> S4" in text
        assert "N3 -> S4" in text
        assert "N3 -> S6" in text
        assert "N4 -/-> S4" in text


def test_shared_docs_fail_closed_on_wrong_handoffs_and_require_joint_review():
    roadmap = read("docs/collaboration/two-person-physics-roadmap.md")
    polarization = read("docs/physics/polarization.md")
    artifact_policy = read("docs/artifact-policy.md")
    combined = "\n".join((roadmap, polarization, artifact_policy)).lower()
    assert "wrong-directory" in combined
    assert "incomplete triplet" in combined
    assert "legacy path" in combined
    assert "canonical repository-relative posix" in combined
    assert "two-owner approval" in combined
    assert "response_application=forward_folded" in combined
    assert "c_response" in combined
    assert "full replay" in combined
