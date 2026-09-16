"""ROOT IO for the two-meson reconstruction: chain, branches, event loop, write.

Event decisions live in event_logic. This module moves data in and out of ROOT,
applies the optional event gate, and counts rejected events.

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

Two cuts are applied after the pairing, also to both runs. An event where
either reconstructed meson carries more energy than the tagged beam photon is
thrown away. When the fit is disabled, the missing mass of the two-meson system
must sit within a window of the recoil partner's mass (RecoConfig.partner_mass /
missing_mass_window): the reaction recoils against a single partner, so the
contamination that does not is what pulls the reconstructed meson peak high.
Both decisions are in event_logic, so the chi2 run and the BDT run lose the
same events and the gate stays the only difference between them.
"""
from __future__ import annotations

import os
from array import array
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

import numpy as np
import ROOT

from graal_common.physics import pairing as pr
from graal_common.io import trees
from reconstruction.core import reco_physics as rp
from reconstruction.core.event_logic import (
    EventInput,
    ReconstructedEvent,
    RejectionReason,
    reconstruct_event,
)
from reconstruction.core.kinematic_fit import (
    PROTON_TARGET_REACTION,
    FitCovariance,
    FitReactionModel,
    fit_event,
)


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


AUTO_TREE = trees.AUTO


@dataclass
class RecoConfig:
    input_dir: Path
    output_file: Path
    input_tree: str = AUTO_TREE
    output_tree: str = "reco"
    chi2_cut: float = 10.0
    # Recoil partner of the eta-pi0 system, and the half-width of the window on
    # its missing mass. The cut centres the reconstructed eta; a window of None
    # or <= 0 disables it. See reco_physics.passes_missing_mass.
    partner_mass: float = rp.M_PROTON
    missing_mass_window: float | None = 0.06
    # Kinematic fit. When on, its confidence-level cut replaces the missing-mass
    # cut (the fit's 4-momentum constraint subsumes it); when off, the
    # missing-mass cut above applies. See kinematic_fit.
    do_fit: bool = True
    fit_cl: float = 0.01
    fit_cov: FitCovariance = field(default_factory=FitCovariance)
    fit_reaction: FitReactionModel = PROTON_TARGET_REACTION


def _as_array(v) -> np.ndarray:
    """TLorentzVector -> (4,) [px, py, pz, E]."""
    return np.array([v.Px(), v.Py(), v.Pz(), v.E()], dtype=np.float64)


def _resolve_tree(probe, requested: str, filename: str) -> str:
    """Which tree to read out of the preselected files, and say which."""
    keys = [k.GetName() for k in probe.GetListOfKeys()]
    name = trees.resolve(keys, requested, filename)
    if requested == trees.AUTO:
        print(f"Input tree: {name} (auto-detected)")
    return name


def _build_chain(input_dir: Path, input_tree: str) -> ROOT.TChain:
    if not input_dir.is_dir():
        raise FileNotFoundError(f"input directory not found: {input_dir}")

    root_files = sorted(f for f in os.listdir(input_dir) if f.endswith(".root"))
    if not root_files:
        raise FileNotFoundError(f"no .root files in {input_dir}")

    print(f"Found {len(root_files)} ROOT files")

    # Fail loud if the tree is not there, naming what we did find.
    probe = ROOT.TFile.Open(str(input_dir / root_files[0]))
    if not probe or probe.IsZombie():
        raise RuntimeError(f"cannot open {input_dir / root_files[0]}")
    try:
        tree_name = _resolve_tree(probe, input_tree, root_files[0])
    finally:
        probe.Close()

    chain = ROOT.TChain(tree_name)
    for f in root_files:
        chain.Add(str(input_dir / f))
    return chain


def run_reconstruction(
    cfg: RecoConfig,
    channel: rp.Channel,
    gate: Gate | None = None,
) -> int:
    """Reconstruct one channel. Returns the number of events written."""
    chain = _build_chain(Path(cfg.input_dir), cfg.input_tree)
    n_entries = chain.GetEntries()
    print(f"Total events in chain: {n_entries}")

    cfg.output_file.parent.mkdir(parents=True, exist_ok=True)
    fout = ROOT.TFile(str(cfg.output_file), "RECREATE")
    tout = ROOT.TTree(cfg.output_tree, cfg.output_tree)

    chi2 = array("f", [0.0])
    heavy_mass = array("f", [0.0])
    light_mass = array("f", [0.0])
    run_number = array("i", [0])
    polarization = array("i", [0])
    xstrip = array("f", [0.0])

    beam = ROOT.TLorentzVector()
    target = ROOT.TLorentzVector(0.0, 0.0, 0.0, cfg.partner_mass)  # partner at rest
    proton = ROOT.TLorentzVector()
    neutron = ROOT.TLorentzVector()
    heavy = ROOT.TLorentzVector()
    heavy_g1 = ROOT.TLorentzVector()
    heavy_g2 = ROOT.TLorentzVector()
    light = ROOT.TLorentzVector()
    light_g1 = ROOT.TLorentzVector()
    light_g2 = ROOT.TLorentzVector()
    missing = ROOT.TLorentzVector()

    eta_fit = ROOT.TLorentzVector()
    pi0_fit = ROOT.TLorentzVector()
    proton_fit = ROOT.TLorentzVector()
    eta_fit_g1 = ROOT.TLorentzVector()
    eta_fit_g2 = ROOT.TLorentzVector()
    pi0_fit_g1 = ROOT.TLorentzVector()
    pi0_fit_g2 = ROOT.TLorentzVector()
    fit_chi2 = array("f", [0.0])
    fit_ndf = array("i", [0])
    fit_conv = array("i", [0])

    H, L = channel.heavy_label, channel.light_label

    tout.Branch("chi2", chi2, "chi2/F")
    tout.Branch(f"{H}_mass", heavy_mass, f"{H}_mass/F")
    tout.Branch(f"{L}_mass", light_mass, f"{L}_mass/F")
    tout.Branch("RunNumber", run_number, "RunNumber/I")
    tout.Branch("Polarization", polarization, "Polarization/I")
    tout.Branch("Xstrip", xstrip, "Xstrip/F")

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

    if cfg.do_fit:
        tout.Branch("eta_fit", "TLorentzVector", eta_fit)
        tout.Branch("pi0_fit", "TLorentzVector", pi0_fit)
        tout.Branch("proton_fit", "TLorentzVector", proton_fit)
        tout.Branch("eta_fit_gamma1", "TLorentzVector", eta_fit_g1)
        tout.Branch("eta_fit_gamma2", "TLorentzVector", eta_fit_g2)
        tout.Branch("pi0_fit_gamma1", "TLorentzVector", pi0_fit_g1)
        tout.Branch("pi0_fit_gamma2", "TLorentzVector", pi0_fit_g2)
        tout.Branch("fit_chi2", fit_chi2, "fit_chi2/F")
        tout.Branch("fit_ndf", fit_ndf, "fit_ndf/I")
        tout.Branch("fit_converged", fit_conv, "fit_converged/I")

    n_gated_out = 0
    n_no_proton = 0
    n_impossible = 0
    n_missing_cut = 0
    n_fit_cut = 0
    print("Starting event loop...")

    def _reconstruct_and_fill(event: EventInput) -> None:
        """Reconstruct one gate-accepted event and write it when retained."""
        nonlocal n_impossible, n_missing_cut, n_fit_cut

        decision = reconstruct_event(
            event,
            channel,
            cfg,
            pairing_fn=pr.best_pairing,
            fit_fn=fit_event,
        )
        if decision is RejectionReason.CHI_SQUARE:
            return
        if decision is RejectionReason.IMPOSSIBLE_ENERGY:
            n_impossible += 1
            return
        if decision is RejectionReason.MISSING_MASS:
            n_missing_cut += 1
            return
        if decision is RejectionReason.FIT:
            n_fit_cut += 1
            return

        reconstructed: ReconstructedEvent = decision
        raw_photons = reconstructed.photons

        beam.SetPxPyPzE(*reconstructed.beam)
        proton.SetPxPyPzE(*reconstructed.proton)
        neutron.SetPxPyPzE(*reconstructed.neutron)
        heavy_g1.SetPxPyPzE(*raw_photons[0])
        heavy_g2.SetPxPyPzE(*raw_photons[1])
        light_g1.SetPxPyPzE(*raw_photons[2])
        light_g2.SetPxPyPzE(*raw_photons[3])
        heavy.SetPxPyPzE(*reconstructed.heavy)
        light.SetPxPyPzE(*reconstructed.light)
        missing.SetPxPyPzE(*reconstructed.missing)

        if cfg.do_fit:
            fitted_photons = reconstructed.fitted_photons
            eta_fit_g1.SetPxPyPzE(*fitted_photons[0])
            eta_fit_g2.SetPxPyPzE(*fitted_photons[1])
            pi0_fit_g1.SetPxPyPzE(*fitted_photons[2])
            pi0_fit_g2.SetPxPyPzE(*fitted_photons[3])
            eta_fit.SetPxPyPzE(*reconstructed.fitted_heavy)
            pi0_fit.SetPxPyPzE(*reconstructed.fitted_light)
            proton_fit.SetPxPyPzE(*reconstructed.fitted_proton)
            fit_chi2[0] = reconstructed.fit_chi2
            fit_ndf[0] = reconstructed.fit_ndf
            fit_conv[0] = 1

        chi2[0] = reconstructed.chi2
        heavy_mass[0] = reconstructed.heavy_mass
        light_mass[0] = reconstructed.light_mass
        run_number[0] = reconstructed.run_number
        polarization[0] = reconstructed.polarization
        xstrip[0] = reconstructed.strip
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
                np.stack([event.photons for event in buf]),
                np.stack([event.proton for event in buf]),
                np.stack([event.beam for event in buf]),
            )
            n_gated_out += int(len(buf) - np.count_nonzero(accepted))
            keep = accepted

        for ok, event in zip(keep, buf):
            if ok:
                _reconstruct_and_fill(event)

        buf.clear()

    pending: list[EventInput] = []

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

        pending.append(
            EventInput(
                photons=photons,
                proton=proton_v,
                neutron=neutron_v,
                beam=beam_v,
                run_number=int(chain.RunNumber),
                polarization=int(chain.Polarization),
                strip=float(chain.Xstrip),
            )
        )
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
    print(f"Cut (meson energy above the beam): {n_impossible}")
    if cfg.do_fit:
        print(f"Cut (fit CL < {cfg.fit_cl}): {n_fit_cut}")
    elif cfg.missing_mass_window and cfg.missing_mass_window > 0:
        print(f"Cut (missing mass off partner {cfg.partner_mass:.3f} "
              f"by >= {cfg.missing_mass_window}): {n_missing_cut}")
    print(f"Events written: {n_written}")
    print("====================================")

    return n_written
