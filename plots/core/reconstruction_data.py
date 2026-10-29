"""ROOT storage adapter for reconstructed plotting data.

This module owns tree access and conversion to detached NumPy arrays. Plot
definitions and rendering remain in :mod:`plots.dalitz`.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

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
    pair_masses_raw: Mapping[str, np.ndarray]
    pair_mass_squared: Mapping[str, Mapping[str, np.ndarray]]
    identity_residual: Mapping[str, np.ndarray]
    beam_energy: np.ndarray
    w: np.ndarray
    run_numbers: np.ndarray | None
    quality: Mapping[str, np.ndarray]

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
        }


def as_array(vector) -> np.ndarray:
    """Convert TLorentzVector to ``[px, py, pz, E]``."""
    return np.array(
        [vector.Px(), vector.Py(), vector.Pz(), vector.E()], dtype=np.float64
    )


def open_tree(path: Path, tree_name: str, *, allow_empty: bool = False):
    """Open reconstructed ROOT tree, failing loudly when input is unusable."""
    if not path.exists():
        raise FileNotFoundError(f"file ricostruito non trovato: {path}")

    root_file = ROOT.TFile.Open(str(path))
    if not root_file or root_file.IsZombie():
        raise RuntimeError(f"impossibile aprire {path}")

    tree = root_file.Get(tree_name)
    if not tree:
        keys = [key.GetName() for key in root_file.GetListOfKeys()]
        root_file.Close()
        raise RuntimeError(
            f"albero '{tree_name}' non trovato in {path}; trovati: {keys}"
        )

    entry_count = tree.GetEntries()
    if entry_count == 0 and not allow_empty:
        root_file.Close()
        raise RuntimeError(f"l'albero '{tree_name}' in {path} e' vuoto")

    print(f"  {path.name}: {entry_count} eventi")
    return root_file, tree


def collect(tree) -> ReconstructionArrays:
    """Collect measured vectors and missing-recoil diagnostics."""
    branches = {branch.GetName() for branch in tree.GetListOfBranches()}
    mep_meas, mpp_meas, mep_miss, mpp_miss = [], [], [], []
    eta_m, pi0_m, eta_m_raw, pi0_m_raw = [], [], [], []
    over_limit, eta_over_beam = [], []
    pair_raw = {name: [] for name in ("p_eta", "p_pi0", "eta_pi0")}
    pair_s = {mode: {name: [] for name in pair_raw} for mode in ("meas", "miss")}
    residual = {mode: [] for mode in pair_s}
    beam_energy, w, runs = [], [], []
    quality = {name: [] for name in ('proton_theta_deg', 'theta_missing_proton_deg',
                                     'coplanarity_deg', 'missing_mass_gev')}

    for event in tree:
        eta = as_array(event.eta)
        pi0 = as_array(event.pi0)
        proton = as_array(event.proton)
        beam = as_array(event.beam)
        target = as_array(event.target)
        missing = as_array(event.missing)
        for name, value in kin.quality_observables(proton, missing, beam, target, eta, pi0).items():
            quality[name].append(value)

        for mode, recoil in (("meas", proton), ("miss", missing)):
            squares = kin.dalitz_invariants(recoil, eta, pi0)
            for name, value in squares.items():
                pair_s[mode][name].append(value)
            residual[mode].append(kin.dalitz_residual(squares, beam + target))
        beam_energy.append(beam[3])
        w.append(kin.sqrt_s(beam, target))
        if "RunNumber" in branches:
            runs.append(int(event.RunNumber))

        mep_meas.append(kin.invariant_mass(eta, proton))
        mpp_meas.append(kin.invariant_mass(pi0, proton))
        mep_miss.append(kin.invariant_mass(eta, missing))
        mpp_miss.append(kin.invariant_mass(pi0, missing))
        pair_raw["p_eta"].append(kin.invariant_mass(proton, eta))
        pair_raw["p_pi0"].append(kin.invariant_mass(proton, pi0))
        pair_raw["eta_pi0"].append(kin.invariant_mass(eta, pi0))

        eta_m.append(event.eta_mass)
        pi0_m.append(event.pi0_mass)
        eta_m_raw.append(event.eta_mass)
        pi0_m_raw.append(event.pi0_mass)

        limit = kin.dalitz_limit(kin.sqrt_s(beam, target), kin.M_PI0)
        over_limit.append(mep_meas[-1] > limit)
        eta_over_beam.append(eta[3] > beam[3])

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
        pair_masses_raw={name: np.array(values) for name, values in pair_raw.items()},
        pair_mass_squared={mode: {name: np.array(values) for name, values in pairs.items()}
                           for mode, pairs in pair_s.items()},
        identity_residual={mode: np.array(values) for mode, values in residual.items()},
        beam_energy=np.array(beam_energy),
        w=np.array(w),
        run_numbers=np.array(runs, dtype=np.int64) if "RunNumber" in branches else None,
        quality={name: np.asarray(values) for name, values in quality.items()},
    )


def collect_legacy(tree) -> dict[str, np.ndarray | bool]:
    """Collect data using legacy dictionary result shape."""
    return collect(tree).as_dict()
