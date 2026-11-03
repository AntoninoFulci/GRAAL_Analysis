"""The energy audit must use the same frozen policy as event selection."""
from dataclasses import fields
from pathlib import Path

import numpy as np
import pytest

from calibration import run_quality
from observable_extraction import beam_asymmetry, workflow
from observable_extraction.core.models import FluxExposure
from observable_extraction.core import periods
from observable_extraction.extraction import ExtractionBundle
from observable_extraction.io.reconstructed_events import EventArrays


@pytest.mark.parametrize("policy_in_metadata", [False, True])
@pytest.mark.parametrize("default_policy", ["missing", "different"])
def test_workflow_energy_audit_preserves_explicit_policy(
    tmp_path, monkeypatch, policy_in_metadata, default_policy
):
    policy_path = Path(__file__).resolve().parents[2] / "config/support/run_quality_exclusions.json"
    policy = run_quality.load_run_quality(policy_path)
    monkeypatch.setattr(run_quality, "DEFAULT_RUN_QUALITY_PATH", tmp_path / "missing.json")
    if default_policy == "different":
        monkeypatch.setattr(periods, "load_run_quality", lambda: {"excluded_runs": []})
    values = {field.name: np.zeros(4) for field in fields(EventArrays)}
    values.update(run_number=np.array([811, 811, 1322, 1322]),
                  polarization=np.array([1, 2, 1, 2]), xstrip=np.full(4, 17),
                  beam_energy_gev=np.full(4, 1.15))
    events = EventArrays(**values)
    exposures = {(run, 17): FluxExposure(run, 17, 1.15, 1., 1., .2, .6, .6)
                 for run in (811, 1322)}
    args = beam_asymmetry.build_parser().parse_args([
        "--raw-bdt", str(tmp_path / "bdt.root"),
        "--raw", str(tmp_path / "absent.root"),
        "--run-quality", str(policy_path), "--output-dir", str(tmp_path / "output"),
    ])
    selected = []

    def no_fits(**kwargs):
        selected.extend(kwargs["events"].run_number.tolist())
        return ExtractionBundle((), ())

    monkeypatch.setattr(workflow, "extract_sample", no_fits)
    monkeypatch.setattr(workflow, "write_root_output", lambda *_: None)
    metadata = {"run_quality": policy} if policy_in_metadata else {}
    payload = workflow._run_single(
        args, prepared=({(args.raw_bdt, "reco_eta_pi0_bdt"): events}, exposures),
        metadata=metadata, period="1998_uv", campaign="policy-regression",
    )
    assert selected == [811, 811]
    counts = payload.extraction_metadata["energy_bins"][0]["samples"]["raw_bdt"]
    assert counts["input"] == 4
    assert counts["selected"] == 2
    assert counts["quality_excluded"] == 2
    assert counts["quality_excluded_runs"] == [1322]
