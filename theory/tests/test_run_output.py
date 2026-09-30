import json
from pathlib import Path

import numpy as np
import pytest

from graal_theory.convergence import compare_resolutions
from graal_theory.models.eta_pi0_p import EtaPi0PModel
from graal_theory.observables import HistogramSpec, predict_energy
from graal_theory.phase_space import SobolConfig
from graal_theory.run_output import MANIFEST_KEYS, RunBundle, write_run_bundle
from graal_theory.sources import load_source_registry


REFERENCES = Path(__file__).resolve().parents[1] / "references"


@pytest.fixture(scope="module")
def bundle():
    model = EtaPi0PModel.from_files(REFERENCES / "central_parameters.json", REFERENCES / "sources.json")
    low = predict_energy(1.2, model, SobolConfig(power=6), HistogramSpec(bins=4))
    high = predict_energy(1.2, model, SobolConfig(power=7), HistogramSpec(bins=4))
    return RunBundle(
        model=model,
        predictions=(high,),
        convergence=(compare_resolutions(low, high),),
        source_registry=load_source_registry(REFERENCES / "sources.json"),
    )


def test_failed_bundle_write_preserves_existing_destination(tmp_path, monkeypatch, bundle):
    destination = tmp_path / "run"
    destination.mkdir()
    (destination / "sentinel").write_text("old")

    def fail_save(*args, **kwargs):
        raise OSError("boom")

    monkeypatch.setattr(np, "savez_compressed", fail_save)
    with pytest.raises(OSError, match="boom"):
        write_run_bundle(destination, bundle, replace=True)
    assert (destination / "sentinel").read_text() == "old"


def test_bundle_writes_closed_partial_manifest_and_arrays(tmp_path, bundle):
    destination = tmp_path / "run"
    write_run_bundle(destination, bundle)
    manifest = json.loads((destination / "manifest.json").read_text())
    assert set(manifest) == MANIFEST_KEYS
    assert manifest["scope"] == "partial:delta1700_eta_delta_tree_eq43"
    assert manifest["validation_state"] == "pending"
    with np.load(destination / "results.npz") as arrays:
        assert arrays["photon_energy_gev"].tolist() == [1.2]
        assert "eta_p_density_0" in arrays
