from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest
from scipy.special import xlogy

import fit_sigma
from contracts import PolarizationContractError
from fit_evidence import FIT_EVIDENCE_FILENAMES
from response_uncertainty import ResponsePropagationResult
from sigma_fit import (
    JointSigmaFitResult,
    _row_order,
    _sigma_bin_key,
    canonical_count_row_key,
)
from fit_sigma import main, publish_fit_release


def test_fit_cli_usage_error_writes_nothing(tmp_path):
    assert main([]) == 2
    assert list(tmp_path.iterdir()) == []


def test_make_target_uses_supported_python_and_explicit_s4_inputs():
    makefile = Path(__file__).resolve().parents[2] / "Makefile"
    recipe = makefile.read_text(encoding="utf-8").split("fit-sigma:", 1)[1]

    assert "$(PYTHON) 08_polarization/fit_sigma.py" in recipe
    assert "--acceptance-handoff $(FIT_ACCEPTANCE_HANDOFF)" in recipe
    assert "--reco-inventory $(FIT_RECO_INVENTORY)" in recipe
    assert "--fit-release-id $(FIT_RELEASE_ID)" in recipe


def test_fit_cli_uses_only_explicit_canonical_authority_paths(
    cli_problem, monkeypatch
):
    paths, authority, _output_root, _replica_order = cli_problem
    calls = {}
    monkeypatch.chdir(paths["root"])

    def load(**kwargs):
        calls["load"] = kwargs
        return authority

    def publish(**kwargs):
        calls["publish"] = kwargs

    monkeypatch.setattr(fit_sigma, "load_count_authority", load)
    monkeypatch.setattr(fit_sigma, "publish_fit_release", publish)
    monkeypatch.setattr(fit_sigma, "_producer_commit", lambda _root: "a" * 40)

    assert main(
        [
            "--acceptance-handoff",
            paths["acceptance_qa"].relative_to(paths["root"]).as_posix(),
            "--reco-inventory",
            paths["inventory"].relative_to(paths["root"]).as_posix(),
            "--config",
            "config/physics/polarization_v1.json",
            "--fit-release-id",
            "fit-test",
            "--output-root",
            "results/physics/polarization_fits",
        ]
    ) == 0
    assert calls["load"]["gate0_handoff_path"] == "results/observable_runs/HANDOFF.json"
    assert calls["load"]["fit_release_id"] == "fit-test"
    assert calls["publish"]["authority"] is authority


def _count_test_module():
    path = Path(__file__).with_name("test_azimuth_counts.py")
    spec = importlib.util.spec_from_file_location("task4_cli_count_tests", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def cli_problem(response_fixture, monkeypatch):
    module = _count_test_module()
    paths = module.count_authority_repo.__wrapped__(response_fixture)
    authority = module._load_count_authority(paths)
    counts = module._project(module._event_sample(paths), authority)
    bin_keys = tuple(
        _sigma_bin_key(key, index)
        for key in authority.response.keys
        for index in range(len(authority.response.mass_edges[key]) - 1)
    )
    dimension = len(bin_keys)
    nominal_rows = tuple(
        sorted(
            (row for row in counts.rows if row.replica_id == 0),
            key=_row_order,
        )
    )

    rng = np.random.default_rng(1701)
    centered = rng.normal(size=(32, dimension))
    centered -= np.mean(centered, axis=0)
    orthonormal, _ = np.linalg.qr(centered)
    variances = np.linspace(0.1, 0.2, dimension)
    replica_vectors = orthonormal * np.sqrt(31.0 * variances)
    statistical_covariance = np.cov(replica_vectors, rowvar=False, ddof=1)
    nominal_sigma = np.linspace(-0.2, 0.2, dimension)

    def result(replica_id, sigma=nominal_sigma):
        observed = np.asarray(
            [row.observed_count for row in nominal_rows], dtype=float
        )
        expected = observed + 2.0
        residuals = (observed - expected) / np.sqrt(expected)
        contributions = 2.0 * (
            xlogy(observed, observed / expected) - (observed - expected)
        )
        return JointSigmaFitResult(
            bin_keys,
            tuple(f"{item}|log_yield" for item in bin_keys),
            tuple(canonical_count_row_key(row) for row in nominal_rows),
            np.asarray(sigma, dtype=float),
            np.log(np.linspace(15.0, 25.0, dimension)),
            statistical_covariance,
            expected,
            residuals,
            contributions,
            float(np.sum(contributions)),
            len(expected) - 2 * dimension,
            True,
            2 * dimension,
            replica_id,
        )

    nominal = result(0)
    replica_order = []

    def fit_core(_counts, _response, *, config, replica_id=0):
        replica_order.append(replica_id)
        if replica_id == 0:
            return nominal
        return result(replica_id, replica_vectors[replica_id - 1])

    monkeypatch.setattr(fit_sigma, "build_azimuth_counts", lambda **_kw: counts)
    monkeypatch.setattr(fit_sigma, "fit_sigma_forward_folded", lambda **_kw: nominal)
    monkeypatch.setattr(fit_sigma, "_fit_sigma_forward_folded_core", fit_core)
    monkeypatch.setattr(
        fit_sigma,
        "bootstrap_sigma_covariance",
        lambda values, *args, **kwargs: np.cov(values, rowvar=False, ddof=1),
    )
    monkeypatch.setattr(
        fit_sigma,
        "propagate_response_covariance",
        lambda *args, **kwargs: ResponsePropagationResult(
            np.zeros((dimension, dimension)), (), (), True
        ),
    )
    output_root = paths["root"] / "results/physics/polarization_fits"
    return paths, authority, output_root, replica_order


def test_fit_publication_is_exact_atomic_triplet_and_runs_replicas_in_order(
    cli_problem,
):
    paths, authority, output_root, replica_order = cli_problem

    evidence = publish_fit_release(
        authority=authority,
        output_root=output_root,
        producer_commit="a" * 40,
    )

    assert {item.name for item in evidence.directory.iterdir()} == FIT_EVIDENCE_FILENAMES
    assert replica_order == list(range(33))
    assert not list(output_root.glob(".fit-test.staging-*"))


def test_fit_publication_never_overwrites_existing_release(cli_problem):
    _paths, authority, output_root, _replica_order = cli_problem
    publish_fit_release(
        authority=authority, output_root=output_root, producer_commit="a" * 40
    )
    before = {
        item.name: item.read_bytes() for item in (output_root / "fit-test").iterdir()
    }

    with pytest.raises(PolarizationContractError, match="overwrite"):
        publish_fit_release(
            authority=authority,
            output_root=output_root,
            producer_commit="a" * 40,
        )

    assert before == {
        item.name: item.read_bytes() for item in (output_root / "fit-test").iterdir()
    }


def test_fit_publication_removes_staging_after_independent_validation_failure(
    cli_problem, monkeypatch
):
    _paths, authority, output_root, _replica_order = cli_problem

    def reject(*_args, **_kwargs):
        raise PolarizationContractError("independent rejection")

    monkeypatch.setattr(fit_sigma, "validate_fit_evidence", reject)
    with pytest.raises(PolarizationContractError, match="independent rejection"):
        publish_fit_release(
            authority=authority,
            output_root=output_root,
            producer_commit="a" * 40,
        )

    assert not (output_root / "fit-test").exists()
    assert not list(output_root.glob(".fit-test.staging-*"))


def test_fit_publication_rejects_release_id_path_traversal(cli_problem):
    paths, _authority, output_root, _replica_order = cli_problem
    bad = fit_sigma.load_count_authority(
        repository_root=paths["root"],
        config_path="config/physics/polarization_v1.json",
        gate0_handoff_path="results/observable_runs/HANDOFF.json",
        n2_inventory_path="results/reconstruction/inventory.json",
        acceptance_handoff_path=(
            "results/physics/normalization/handoffs/n3-test/acceptance_qa.json"
        ),
        fit_release_id="../escape",
        bin_set_id="figure4-v1",
    )

    with pytest.raises(PolarizationContractError, match="release ID"):
        publish_fit_release(
            authority=bad,
            output_root=output_root,
            producer_commit="a" * 40,
        )
    assert not (paths["root"] / "results/physics/escape").exists()
