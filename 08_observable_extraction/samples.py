"""Supported reconstructed samples and their persisted tree contracts."""

from dataclasses import dataclass


@dataclass(frozen=True)
class SampleInput:
    tree: str
    requires_bdt: bool


SAMPLES = {
    "raw": SampleInput("reco_eta_pi0_chi2", False),
    "raw_bdt": SampleInput("reco_eta_pi0_bdt", True),
}
