"""ROOT IO for the two-meson reconstruction: chain, branches, event loop, write.

The physics lives in reco_physics. This module only moves data in and out of
ROOT and applies the optional event gate.

Event requirements, applied identically to the chi2 run and the BDT-gated run,
before either the gate or the chi2 pairing run:
  - at least 4 reconstructed photons (the combination table only ever
    references photons 0-3);
  - exactly 1 reconstructed proton. The reaction is gamma p -> p eta pi0: the
    recoil is a proton. Events without exactly one proton are skipped, not
    padded with a fictitious (0,0,0,0) proton -- a zero proton fakes a missing
    mass of ~1.87 GeV (a real proton gives ~0.75 GeV) and a stage-1 BDT score
    from a region of feature space the model never saw in training, which used
    to make the BDT run silently drop every such event while the chi2 run kept
    them. Skipping both runs at the source keeps the two samples identical
    except for the gate, which is the entire point of the comparison.
"""
from __future__ import annotations

import os
from array import array
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import numpy as np
import ROOT

from analysis import reco_physics as rp


# How many events to hold before asking the gate about them. A gate asked one
# event at a time spends nearly all its time on per-call overhead rather than on
# the question; asked in bulk it is ~300x faster. 20000 events is a few MB of
# buffer and already well into the flat part of that curve.
_GATE_CHUNK = 20000


class Gate(Protocol):
    """An event filter applied before the chi2 pairing, asked in bulk."""

    def accepts_many(
        self, photons: np.ndarray, protons: np.ndarray, beams: np.ndarray
    ) -> np.ndarray:
        """photons: (N,4,4); protons, beams: (N,4) — all [px, py, pz, E].

        Returns an (N,) bool array, one answer per event, True to keep.
        """
        ...


@dataclass
class RecoConfig:
    input_dir: Path
    output_file: Path
    input_tree: str = "h85"
    output_tree: str = "reco"
    chi2_cut: float = 10.0


def _as_array(v) -> np.ndarray:
    """TLorentzVector -> (4,) [px, py, pz, E]."""
    return np.array([v.Px(), v.Py(), v.Pz(), v.E()], dtype=np.float64)


def _build_chain(input_dir: Path, input_tree: str) -> ROOT.TChain:
    if not input_dir.is_dir():
        raise FileNotFoundError(f"input directory not found: {input_dir}")

    root_files = sorted(f for f in os.listdir(input_dir) if f.endswith(".root"))
    if not root_files:
        raise FileNotFoundError(f"no .root files in {input_dir}")

    print(f"Found {len(root_files)} ROOT files")

    # Fail loud if the tree is not the one we expect, naming what we did find.
    probe = ROOT.TFile.Open(str(input_dir / root_files[0]))
    if not probe or probe.IsZombie():
        raise RuntimeError(f"cannot open {input_dir / root_files[0]}")
    if not probe.Get(input_tree):
        keys = [k.GetName() for k in probe.GetListOfKeys()]
        probe.Close()
        raise RuntimeError(
            f"tree '{input_tree}' not found in {root_files[0]}; found: {keys}"
        )
    probe.Close()

    chain = ROOT.TChain(input_tree)
    for f in root_files:
        chain.Add(str(input_dir / f))
    return chain


def run_reconstruction(
    cfg: RecoConfig,
    channel: rp.Channel,
    gate: Gate | None = None,
) -> int:
    """Reconstruct one channel. Returns the number of events written."""
    if not channel.combinations_file.exists():
        raise FileNotFoundError(
            f"combinations table not found: {channel.combinations_file}"
        )
    combinations = np.loadtxt(channel.combinations_file)

    chain = _build_chain(Path(cfg.input_dir), cfg.input_tree)
    n_entries = chain.GetEntries()
    print(f"Total events in chain: {n_entries}")

    cfg.output_file.parent.mkdir(parents=True, exist_ok=True)
    fout = ROOT.TFile(str(cfg.output_file), "RECREATE")
    tout = ROOT.TTree(cfg.output_tree, cfg.output_tree)

    chi2 = array("f", [0.0])
    heavy_mass = array("f", [0.0])
    light_mass = array("f", [0.0])

    beam = ROOT.TLorentzVector()
    target = ROOT.TLorentzVector(0.0, 0.0, 0.0, rp.M_PROTON)  # proton at rest
    proton = ROOT.TLorentzVector()
    neutron = ROOT.TLorentzVector()
    heavy = ROOT.TLorentzVector()
    heavy_g1 = ROOT.TLorentzVector()
    heavy_g2 = ROOT.TLorentzVector()
    light = ROOT.TLorentzVector()
    light_g1 = ROOT.TLorentzVector()
    light_g2 = ROOT.TLorentzVector()
    missing = ROOT.TLorentzVector()

    H, L = channel.heavy_label, channel.light_label

    tout.Branch("chi2", chi2, "chi2/F")
    tout.Branch(f"{H}_mass", heavy_mass, f"{H}_mass/F")
    tout.Branch(f"{L}_mass", light_mass, f"{L}_mass/F")

    tout.Branch("beam", "TLorentzVector", beam)
    tout.Branch("target", "TLorentzVector", target)
    tout.Branch("proton", "TLorentzVector", proton)
    tout.Branch("neutron", "TLorentzVector", neutron)
    tout.Branch(H, "TLorentzVector", heavy)
    tout.Branch(f"{H}_gamma1", "TLorentzVector", heavy_g1)
    tout.Branch(f"{H}_gamma2", "TLorentzVector", heavy_g2)
    tout.Branch(L, "TLorentzVector", light)
    tout.Branch(f"{L}_gamma1", "TLorentzVector", light_g1)
    tout.Branch(f"{L}_gamma2", "TLorentzVector", light_g2)
    tout.Branch("missing", "TLorentzVector", missing)

    n_gated_out = 0
    n_no_proton = 0
    print("Starting event loop...")

    def _reconstruct_and_fill(photons, proton_v, neutron_v, beam_v) -> None:
        """chi2-pair one accepted event and write it. Identical for both runs."""
        idx, chi2_val = rp.best_combination(photons, combinations)
        chi2[0] = chi2_val
        if chi2_val >= cfg.chi2_cut:
            return

        heavy_idx, light_idx = rp.assign_pairs(combinations[idx], channel)

        beam.SetPxPyPzE(*beam_v)
        proton.SetPxPyPzE(*proton_v)
        neutron.SetPxPyPzE(*neutron_v)

        hg1, hg2 = photons[heavy_idx[0]], photons[heavy_idx[1]]
        lg1, lg2 = photons[light_idx[0]], photons[light_idx[1]]

        heavy_g1.SetPxPyPzE(*hg1)
        heavy_g2.SetPxPyPzE(*hg2)
        light_g1.SetPxPyPzE(*lg1)
        light_g2.SetPxPyPzE(*lg2)
        heavy.SetPxPyPzE(*(hg1 + hg2))
        light.SetPxPyPzE(*(lg1 + lg2))

        missing_v = (beam + target) - (heavy + light)
        missing.SetPxPyPzE(
            missing_v.Px(), missing_v.Py(), missing_v.Pz(), missing_v.E()
        )

        heavy_mass[0] = heavy.M()
        light_mass[0] = light.M()

        tout.Fill()

    def _flush(buf: list) -> None:
        """Ask the gate about a whole buffer, then reconstruct what it keeps.

        Buffering only changes WHEN the gate is asked, never which events reach
        it: the guards above have already run on every event, in order, so the
        chi2 run and the BDT run still see the identical set.
        """
        nonlocal n_gated_out
        if not buf:
            return

        if gate is None:
            keep = [True] * len(buf)
        else:
            accepted = gate.accepts_many(
                np.stack([b[0] for b in buf]),
                np.stack([b[1] for b in buf]),
                np.stack([b[3] for b in buf]),
            )
            n_gated_out += int(len(buf) - np.count_nonzero(accepted))
            keep = accepted

        for ok, event in zip(keep, buf):
            if ok:
                _reconstruct_and_fill(*event)

        buf.clear()

    pending: list = []

    for iev in range(n_entries):
        chain.GetEntry(iev)

        if iev % 100000 == 0:
            print(f"Event {iev}/{n_entries}")

        # The combination table only ever references photons 0-3.
        if chain.gammas.size() < 4:
            continue

        # Require exactly one reconstructed proton (the recoil in gamma p ->
        # p eta pi0). Applied before the gate and before the chi2 so the chi2
        # run and the BDT run see the identical event set. See module
        # docstring for why a fictitious zero-proton is not used instead.
        if chain.protons.size() != 1:
            n_no_proton += 1
            continue

        photons = np.vstack([_as_array(chain.gammas[k]) for k in range(4)])

        proton_v = _as_array(chain.protons[0])
        neutron_v = (
            _as_array(chain.neutrons[0]) if chain.neutrons.size() == 1 else np.zeros(4)
        )
        beam_v = np.array([0.0, 0.0, chain.beam.E(), chain.beam.E()])

        pending.append((photons, proton_v, neutron_v, beam_v))
        if len(pending) >= _GATE_CHUNK:
            _flush(pending)

    _flush(pending)

    fout.cd()
    tout.Write("", ROOT.TObject.kOverwrite)  # reuse the key, avoid extra ;N cycles
    n_written = tout.GetEntries()
    fout.Close()

    print("====================================")
    print(f"Created file  : {cfg.output_file}")
    print(f"Tree          : {cfg.output_tree}")
    print(f"Skipped (not exactly 1 proton): {n_no_proton}")
    if gate is not None:
        print(f"Rejected by gate: {n_gated_out}")
    print(f"Events written: {n_written}")
    print("====================================")

    return n_written
