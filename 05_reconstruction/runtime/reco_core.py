"""ROOT IO for the two-meson reconstruction: chain, branches, event loop, write.

Event decisions live in event_logic. This module moves data in and out of ROOT,
applies the optional event gate, and counts rejected events.

Event requirements, applied identically to the chi2 run and the BDT-gated run,
before either the gate or the chi2 pairing run:
  - at least 4 reconstructed photons (pairing uses photons 0-3);
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
thrown away. The missing mass of the two-meson system
must sit within a window of the recoil partner's mass (RecoConfig.partner_mass /
missing_mass_window): the reaction recoils against a single partner, so the
contamination that does not is what pulls the reconstructed meson peak high.
Both decisions are in event_logic, so the chi2 run and the BDT run lose the
same events and the gate stays the only difference between them.
"""
from __future__ import annotations

import os
import json
import subprocess
import sys
from array import array
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import numpy as np
import ROOT

from graal_common.physics import pairing as pr
from graal_common.io import trees
from graal_common.io.raw_tracks import has_raw_tracks, snapshot_raw_tracks, RawTrackWriter
from reconstruction.runtime.provenance import (
    KEY, acquisition_counts, file_identities, input_run_states, stage1_domain,
)
from reconstruction.core import reco_physics as rp
from reconstruction.core.event_logic import (
    EventInput,
    ReconstructedEvent,
    RejectionReason,
    reconstruct_event,
)


# How many events to hold before asking the gate about them. A gate asked one
# event at a time spends nearly all its time on per-call overhead rather than on
# the question; asked in bulk it is ~300x faster. 20000 events is a few MB of
# buffer and already well into the flat part of that curve.
_GATE_CHUNK = 20000


class Gate(Protocol):
    """An event filter applied before the chi2 pairing, asked in bulk."""

    threshold: float

    def scores_many(
        self, photons: np.ndarray, protons: np.ndarray, beams: np.ndarray
    ) -> np.ndarray:
        """photons: (N,4,4); protons, beams: (N,4) — all [px, py, pz, E].

        Returns an (N,) signal-probability array.
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
    energy_range_gev: tuple[float, float] | None = None
    model_dir: Path | None = None
    beam_profile: str | None = None
    workers: int = 1


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


def _build_chain(input_dir: Path, input_tree: str, *, files=None) -> ROOT.TChain:
    if not input_dir.is_dir():
        raise FileNotFoundError(f"input directory not found: {input_dir}")

    root_files = (sorted(f for f in os.listdir(input_dir) if f.endswith(".root"))
                  if files is None else list(files))
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
    metadata_states = set()
    input_file_entries = []
    acquisition_states = []
    for f in root_files:
        probe = ROOT.TFile.Open(str(input_dir / f))
        if not probe or probe.IsZombie():
            raise RuntimeError(f"cannot open {input_dir / f}")
        try:
            tree = probe.Get(tree_name)
            if not tree:
                raise RuntimeError(f"tree '{tree_name}' not found in {input_dir / f}")
            metadata_states.add(has_raw_tracks(tree, str(input_dir / f)))
            input_file_entries.append((str((input_dir / f).resolve()), int(tree.GetEntries())))
            acquisition_states.extend(input_run_states(probe))
        finally:
            probe.Close()
        chain.Add(str(input_dir / f))
    if len(metadata_states) != 1:
        raise ValueError("mixed raw-track metadata: regenerate legacy inputs or process them separately")
    chain.raw_track_metadata_available = metadata_states.pop()
    chain.input_file_entries = input_file_entries
    chain.input_run_states = acquisition_states
    return chain


def _snapshot_inputs(cfg: RecoConfig) -> dict:
    """Capture one authoritative provenance snapshot before dispatching work."""
    # Snapshot executable inputs before processing; later edits must not relabel this run.
    import graal_common
    import reconstruction
    sources = []
    for package in (reconstruction, graal_common):
        base = Path(package.__file__).resolve().parent
        files = tuple(p for p in base.rglob("*.py") if "tests" not in p.relative_to(base).parts)
        if not files or Path(package.__file__).resolve() not in files:
            raise ValueError(f"source inventory is empty or incomplete: {base}")
        sources.extend(files)
    source_files = file_identities(sources)
    # Only a source checkout has a meaningful repository revision. Installed
    # modules are identified by the actual files above, never sibling stage dirs.
    repo = Path(reconstruction.__file__).resolve().parent.parent
    revision = "unknown"
    if (repo / "pyproject.toml").is_file() and (repo / ".git").exists():
        result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo,
                                capture_output=True, text=True, check=False)
        if result.returncode == 0:
            revision = result.stdout.strip()
    model_inputs = file_identities(cfg.model_dir / name for name in
        ("bdt_stage1.json", "stage1_threshold.txt", "stage1_provenance.json")) if cfg.model_dir else []
    return {"source_revision": revision, "source_files": source_files,
            "model_inputs": model_inputs,
            "inputs": file_identities(Path(cfg.input_dir).glob("*.root")),
            "command": list(sys.argv)}


def run_reconstruction(
    cfg: RecoConfig,
    channel: rp.Channel,
    gate: Gate | None = None,
) -> int:
    """Reconstruct in input order; each process owns its ROOT files and buffers.

    ``workers=1`` keeps the serial path. More workers split sorted files into
    contiguous entry ranges and atomically publish their ordered merge.
    """
    if isinstance(cfg.workers, bool) or not isinstance(cfg.workers, int) or cfg.workers <= 0:
        raise ValueError("workers must be a positive integer")
    if cfg.energy_range_gev is not None:
        low, high = cfg.energy_range_gev
        if not np.isfinite((low, high)).all() or high <= low:
            raise ValueError("reconstruction energy range must be finite and increasing")
    if cfg.workers > 1:
        from reconstruction.runtime.parallel import run_parallel_reconstruction
        return run_parallel_reconstruction(cfg, channel, gate)
    return _run_serial(cfg, channel, gate)


def _run_serial(cfg, channel, gate=None, *, input_files=None, entry_range=None,
                snapshot=None, include_acquisition_counts=True) -> int:
    snapshot = _snapshot_inputs(cfg) if snapshot is None else snapshot
    chain = (_build_chain(Path(cfg.input_dir), cfg.input_tree) if input_files is None
             else _build_chain(Path(cfg.input_dir), cfg.input_tree, files=input_files))
    n_entries = chain.GetEntries()
    start, stop = (0, n_entries) if entry_range is None else entry_range
    counts = acquisition_counts(getattr(chain, "input_run_states", ())
                                if include_acquisition_counts else ())
    print(f"Total events in chain: {n_entries}")

    cfg.output_file.parent.mkdir(parents=True, exist_ok=True)
    fout = ROOT.TFile(str(cfg.output_file), "RECREATE")
    tout = ROOT.TTree(cfg.output_tree, cfg.output_tree)
    raw_track_writer = (RawTrackWriter(tout)
                        if getattr(chain, "raw_track_metadata_available", False) else None)

    chi2 = array("f", [0.0])
    heavy_mass = array("f", [0.0])
    light_mass = array("f", [0.0])
    run_number = array("i", [0])
    polarization = array("i", [0])
    xstrip = array("f", [0.0])
    n_photons_input = array("i", [0])
    bdt_score = array("f", [float("nan")])

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

    H, L = channel.heavy_label, channel.light_label

    tout.Branch("chi2", chi2, "chi2/F")
    tout.Branch(f"{H}_mass", heavy_mass, f"{H}_mass/F")
    tout.Branch(f"{L}_mass", light_mass, f"{L}_mass/F")
    tout.Branch("RunNumber", run_number, "RunNumber/I")
    tout.Branch("Polarization", polarization, "Polarization/I")
    tout.Branch("Xstrip", xstrip, "Xstrip/F")
    tout.Branch("n_photons_input", n_photons_input, "n_photons_input/I")
    if gate is not None:
        tout.Branch("bdt_score", bdt_score, "bdt_score/F")

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
    n_impossible = 0
    n_missing_cut = 0
    n_outside_energy = 0
    print("Starting event loop...")

    def _reconstruct_and_fill(
        event: EventInput, score: float | None = None, raw_tracks=None
    ) -> None:
        """Reconstruct one gate-accepted event and write it when retained."""
        nonlocal n_impossible, n_missing_cut

        decision = reconstruct_event(
            event,
            channel,
            cfg,
            pairing_fn=pr.best_pairing,
        )
        if isinstance(decision, RejectionReason):
            counts[(event.run_number, event.polarization)][decision.value] += 1
            if decision is RejectionReason.IMPOSSIBLE_ENERGY:
                n_impossible += 1
            elif decision is RejectionReason.MISSING_MASS:
                n_missing_cut += 1
            return

        counts[(event.run_number, event.polarization)]["written"] += 1
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

        chi2[0] = reconstructed.chi2
        heavy_mass[0] = reconstructed.heavy_mass
        light_mass[0] = reconstructed.light_mass
        run_number[0] = reconstructed.run_number
        polarization[0] = reconstructed.polarization
        xstrip[0] = reconstructed.strip
        n_photons_input[0] = event.n_photons_input
        if score is not None:
            bdt_score[0] = score
        if raw_track_writer is not None:
            raw_track_writer.assign(raw_tracks)
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
            scores: list[float | None] | np.ndarray = [None] * len(buf)
        else:
            scores = gate.scores_many(
                np.stack([event.photons for event, _ in buf]),
                np.stack([event.proton for event, _ in buf]),
                np.stack([event.beam for event, _ in buf]),
            )
            accepted = scores >= gate.threshold
            n_gated_out += int(len(buf) - np.count_nonzero(accepted))
            keep = accepted

        for ok, (event, raw_tracks), score in zip(keep, buf, scores):
            if ok:
                _reconstruct_and_fill(event, score, raw_tracks)
            else:
                counts[(event.run_number, event.polarization)]["bdt_gate"] += 1

        buf.clear()

    pending: list[tuple[EventInput, dict | None]] = []

    for iev in range(start, stop):
        chain.GetEntry(iev)
        counter = counts[(int(chain.RunNumber), int(chain.Polarization))]
        counter["input"] += 1

        if iev % 100000 == 0:
            print(f"Event {iev}/{n_entries}")

        if cfg.energy_range_gev is not None:
            low, high = cfg.energy_range_gev
            energy = float(chain.beam.E())
            if energy < low or energy > high:
                n_outside_energy += 1
                counter["outside_energy"] += 1
                continue

        # Pairing uses the first four reconstructed photons.
        if chain.gammas.size() < 4:
            counter["fewer_than_four_photons"] += 1
            continue

        # Require exactly one reconstructed proton (the recoil in gamma p ->
        # p eta pi0). Applied before the gate and before the chi2 so the chi2
        # run and the BDT run see the identical event set. See module
        # docstring for why a fictitious zero-proton is not used instead.
        if chain.protons.size() != 1:
            n_no_proton += 1
            counter["not_one_proton"] += 1
            continue

        photons = np.vstack([_as_array(chain.gammas[k]) for k in range(4)])

        proton_v = _as_array(chain.protons[0])
        neutron_v = (
            _as_array(chain.neutrons[0]) if chain.neutrons.size() == 1 else np.zeros(4)
        )
        beam_v = np.array([0.0, 0.0, chain.beam.E(), chain.beam.E()])

        pending.append(
            (EventInput(
                photons=photons,
                proton=proton_v,
                neutron=neutron_v,
                beam=beam_v,
                run_number=int(chain.RunNumber),
                polarization=int(chain.Polarization),
                strip=float(chain.Xstrip),
                n_photons_input=int(chain.gammas.size()),
            ), snapshot_raw_tracks(chain) if raw_track_writer is not None else None)
        )
        if len(pending) >= _GATE_CHUNK:
            _flush(pending)

    _flush(pending)

    fout.cd()
    tout.Write("", ROOT.TObject.kOverwrite)  # reuse the key, avoid extra ;N cycles
    n_written = tout.GetEntries()
    metadata = {
        "schema": 2, "selection_algorithm": "pairing_missing_mass", "channel": channel.name,
        "input_tree": getattr(chain, "GetName", lambda: cfg.input_tree)(),
        "output_tree": cfg.output_tree,
        "raw_track_metadata": {"available": raw_track_writer is not None,
                               "cut": "disabled_pending_definition"},
        **snapshot,
        "versions": {"python": sys.version, "numpy": np.__version__},
        "selection": {
            "chi2_cut": cfg.chi2_cut, "chi2_resolution_relative": rp.CHI2_RESOLUTION,
            "missing_mass_window_gev": cfg.missing_mass_window,
            "partner_mass_gev": cfg.partner_mass,
            "energy_range_gev": cfg.energy_range_gev,
            "photons": "first_four_of_at_least_four", "protons": "exactly_one",
            "bdt_threshold": gate.threshold if gate is not None else None,
        },
        "beam_profile": cfg.beam_profile,
        "bdt_domain": stage1_domain(gate),
        "counts_by_run_state": [dict(run=run, polarization=pol, **counter)
                                for (run, pol), counter in sorted(counts.items())],
    }
    ROOT.TNamed(KEY, json.dumps(metadata, sort_keys=True)).Write()
    fout.Close()

    print("====================================")
    print(f"Created file  : {cfg.output_file}")
    print(f"Tree          : {cfg.output_tree}")
    print(f"Skipped (outside beam profile): {n_outside_energy}")
    print(f"Skipped (not exactly 1 proton): {n_no_proton}")
    if gate is not None:
        print(f"Rejected by gate: {n_gated_out}")
    print(f"Cut (meson energy above the beam): {n_impossible}")
    if cfg.missing_mass_window and cfg.missing_mass_window > 0:
        print(f"Cut (missing mass off partner {cfg.partner_mass:.3f} "
              f"by >= {cfg.missing_mass_window}): {n_missing_cut}")
    print(f"Events written: {n_written}")
    print("====================================")

    return n_written
