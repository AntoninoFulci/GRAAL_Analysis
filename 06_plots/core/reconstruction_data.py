"""ROOT storage adapter for reconstructed plotting data.

This module owns tree access and conversion to detached NumPy arrays. Plot
definitions and rendering remain in :mod:`plots.dalitz`.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import ROOT

from plots.core import kinematics as kin


@dataclass(frozen=True)
class ReconstructionArrays:
    """Arrays required by reconstructed-data plots, independent of ROOT files."""

    mep_meas: np.ndarray
    mpp_meas: np.ndarray
    mep_miss: np.ndarray
    mpp_miss: np.ndarray
    eta_mass: np.ndarray
    pi0_mass: np.ndarray
    eta_mass_raw: np.ndarray
    pi0_mass_raw: np.ndarray
    over_limit: np.ndarray
    eta_over_beam: np.ndarray
    has_fit: bool

    def as_dict(self) -> dict[str, np.ndarray | bool]:
        """Return legacy dictionary shape used by older plotting callers."""
        return {
            "mep_meas": self.mep_meas,
            "mpp_meas": self.mpp_meas,
            "mep_miss": self.mep_miss,
            "mpp_miss": self.mpp_miss,
            "eta_mass": self.eta_mass,
            "pi0_mass": self.pi0_mass,
            "eta_mass_raw": self.eta_mass_raw,
            "pi0_mass_raw": self.pi0_mass_raw,
            "over_limit": self.over_limit,
            "eta_over_beam": self.eta_over_beam,
            "has_fit": self.has_fit,
        }


def as_array(vector) -> np.ndarray:
    """Convert TLorentzVector to ``[px, py, pz, E]``."""
    return np.array(
        [vector.Px(), vector.Py(), vector.Pz(), vector.E()], dtype=np.float64
    )


def open_tree(path: Path, tree_name: str):
    """Open reconstructed ROOT tree, failing loudly when input is unusable."""
    if not path.exists():
        raise FileNotFoundError(f"file ricostruito non trovato: {path}")

    root_file = ROOT.TFile.Open(str(path))
    if not root_file or root_file.IsZombie():
        raise RuntimeError(f"impossibile aprire {path}")

    tree = root_file.Get(tree_name)
    if not tree:
        keys = [key.GetName() for key in root_file.GetListOfKeys()]
        raise RuntimeError(
            f"albero '{tree_name}' non trovato in {path}; trovati: {keys}"
        )

    entry_count = tree.GetEntries()
    if entry_count == 0:
        raise RuntimeError(f"l'albero '{tree_name}' in {path} e' vuoto")

    print(f"  {path.name}: {entry_count} eventi")
    return root_file, tree


def has_fit(tree) -> bool:
    """Return whether tree carries kinematic-fit branches."""
    return "fit_chi2" in {
        branch.GetName() for branch in tree.GetListOfBranches()
    }


def collect(tree) -> ReconstructionArrays:
    """Collect plot inputs in one tree pass and detach them from ROOT."""
    tree_has_fit = has_fit(tree)

    mep_meas, mpp_meas, mep_miss, mpp_miss = [], [], [], []
    eta_m, pi0_m, eta_m_raw, pi0_m_raw = [], [], [], []
    over_limit, eta_over_beam = [], []

    for event in tree:
        eta_raw = as_array(event.eta)
        pi0_raw = as_array(event.pi0)
        eta = as_array(event.eta_fit) if tree_has_fit else eta_raw
        pi0 = as_array(event.pi0_fit) if tree_has_fit else pi0_raw
        proton = as_array(event.proton)
        missing = as_array(event.missing)
        beam = as_array(event.beam)
        target = as_array(event.target)

        mep_meas.append(kin.invariant_mass(eta, proton))
        mpp_meas.append(kin.invariant_mass(pi0, proton))
        mep_miss.append(kin.invariant_mass(eta, missing))
        mpp_miss.append(kin.invariant_mass(pi0, missing))

        eta_m.append(event.eta_fit.M() if tree_has_fit else event.eta_mass)
        pi0_m.append(event.pi0_fit.M() if tree_has_fit else event.pi0_mass)
        eta_m_raw.append(event.eta_mass)
        pi0_m_raw.append(event.pi0_mass)

        limit = kin.dalitz_limit(kin.sqrt_s(beam, target), kin.M_PI0)
        over_limit.append(mep_meas[-1] > limit)
        eta_over_beam.append(eta_raw[3] > beam[3])

    return ReconstructionArrays(
        mep_meas=np.array(mep_meas),
        mpp_meas=np.array(mpp_meas),
        mep_miss=np.array(mep_miss),
        mpp_miss=np.array(mpp_miss),
        eta_mass=np.array(eta_m),
        pi0_mass=np.array(pi0_m),
        eta_mass_raw=np.array(eta_m_raw),
        pi0_mass_raw=np.array(pi0_m_raw),
        over_limit=np.array(over_limit),
        eta_over_beam=np.array(eta_over_beam),
        has_fit=tree_has_fit,
    )


def collect_legacy(tree) -> dict[str, np.ndarray | bool]:
    """Collect data using legacy dictionary result shape."""
    return collect(tree).as_dict()
