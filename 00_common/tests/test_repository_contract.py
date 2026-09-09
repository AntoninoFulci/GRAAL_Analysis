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


def test_testing_docs_name_top_level_pyroot_plot_module():
    text = read("wiki/testing.md")
    assert "06_plots/dalitz.py" in text
