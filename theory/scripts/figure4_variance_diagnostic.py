"""Record event-level Figure 4 integrands without changing the production model.

Nested prefixes reuse already evaluated amplitudes. Family allocations include
interference and can be negative; they are not separate physical cross sections.
Marginal quartiles localize drift, not independent errors or Sobol indices.
No output of this diagnostic certifies convergence.
"""

from __future__ import annotations

import argparse
from contextlib import nullcontext
from functools import partial
import hashlib
import importlib.util
import json
from pathlib import Path
import platform
import subprocess
import sys
from time import monotonic
from unittest.mock import patch

import numpy as np
import scipy
from scipy.stats import qmc

import graal_theory
from graal_theory import figure4_integration
from graal_theory.beam_asymmetry import _HORIZONTAL, _VERTICAL
from graal_theory.cli import _figure4_model
from graal_theory.constants import GEV2_TO_MICROBARN
from graal_theory.figure4_integration import PAIR_DAUGHTERS, predict_figure4_bin
from graal_theory.kinematics import invariant_mass
from graal_theory.phase_space import SobolConfig, sample_three_body_mass_window


THEORY = Path(__file__).resolve().parents[1]
COORDINATES = ("pair_mass_squared", "spectator_cos_theta", "daughter_rest_cos_theta",
               "daughter_rest_azimuth")


def allocate_moments(phi, vertical, horizontal, weights):
    """Allocate each bilinear equally to its two whole-amplitude families."""
    v_total, h_total = vertical.sum(axis=0), horizontal.sum(axis=0)
    v = np.real(np.sum(np.conj(vertical)*v_total, axis=(-2, -1)))/2
    h = np.real(np.sum(np.conj(horizontal)*h_total, axis=(-2, -1)))/2
    cross = np.real(np.sum(np.conj(horizontal)*v_total
                           + np.conj(h_total)*vertical, axis=(-2, -1)))/4
    return (((v-h)*np.cos(2*phi)-2*cross*np.sin(2*phi))*weights,
            (v+h)*weights)


class _RecordingModel:
    def __init__(self, model):
        self.model = model
        self.masses, self.parameters = model.masses, model.parameters
        self.nodes = []

    def amplitude(self, sample, epsilon):
        families = self.model.family_amplitudes(sample, epsilon)
        matrices = np.stack(tuple(families.values()))
        if np.array_equal(epsilon, _VERTICAL):
            self.nodes.append({"sample": sample, "names": tuple(families), "v": matrices})
        elif np.array_equal(epsilon, _HORIZONTAL):
            if not self.nodes or self.nodes[-1]["sample"] is not sample:
                raise ValueError("diagnostic requires paired H/V on the same sample")
            if tuple(families) != self.nodes[-1]["names"]:
                raise ValueError("H/V family order mismatch")
            self.nodes[-1]["h"] = matrices
        else:
            raise ValueError("unexpected diagnostic polarization")
        return np.add.reduce(matrices)


def diagnose_bin(model, pair, energy, mass, *, energy_order, sobol,
                 sampler=None, coordinate_names=COORDINATES):
    """Single-process diagnostic; a candidate sampler is scoped to this call."""
    start = monotonic()
    recorder = _RecordingModel(model)
    context = (patch.object(figure4_integration, "sample_three_body_mass_window", sampler)
               if sampler is not None else nullcontext())
    with context:
        moment = predict_figure4_bin(recorder, pair, energy, mass,
                                     energy_order=energy_order, sobol=sobol)
    sample_window = sample_three_body_mass_window if sampler is None else sampler
    if moment.status != "calculated":
        raise ValueError(f"diagnostic unavailable: {moment.status}: {moment.reason}")
    if len(recorder.nodes) != energy_order:
        raise ValueError("diagnostic requires all energy nodes")
    low, high = moment.accessible_energy_gev
    _, legendre = np.polynomial.legendre.leggauss(energy_order)
    energy_weights = legendre*(high-low)/(2*(energy[1]-energy[0]))
    daughters = PAIR_DAUGHTERS[pair]
    proton = model.parameters.proton_mass_gev
    count = 2**sobol.power
    # Same four unit-cube coordinates as the unchanged production sampler.
    coordinates = qmc.Sobol(d=4, scramble=sobol.scramble,
                            seed=sobol.seed).random_base2(sobol.power)
    records = {name: [] for name in (
        "momenta", "measure", "vertical_amplitudes", "horizontal_amplitudes",
        "family_numerator", "family_denominator", "numerator", "denominator",
        "phase_space_denominator", "pair_mass", "eta_p_mass")}
    names = recorder.nodes[0]["names"]
    for node, energy_weight in zip(recorder.nodes, energy_weights):
        sample = node["sample"]
        if node["names"] != names:
            raise ValueError("family order changed across energy nodes")
        # Check actual kinematics/weights, not merely Sobol coordinate nesting.
        for power in range(4, sobol.power):
            prefix = sample_window(sample.initial[0, 0], model.masses,
                daughters, mass, SobolConfig(power, scramble=sobol.scramble, seed=sobol.seed),
                reduce_global_azimuth=True)
            n = 2**power
            if (prefix is None or not np.array_equal(prefix.momenta, sample.momenta[:n])
                    or not np.array_equal(prefix.weights_gev2, sample.weights_gev2[:n])):
                raise ValueError("production sampler no longer has exact nested prefixes")
        pair_momentum = sample.momenta[:, daughters[0]]+sample.momenta[:, daughters[1]]
        phi = np.arctan2(pair_momentum[:, 2], pair_momentum[:, 1])
        s = sample.initial[0, 0]**2
        measure = (energy_weight*GEV2_TO_MICROBARN*4*proton**2
                   /(2*(s-proton**2)*count)*sample.weights_gev2)
        fn, fd = allocate_moments(phi, node["v"], node["h"], measure)
        values = dict(momenta=sample.momenta, measure=measure,
            vertical_amplitudes=node["v"], horizontal_amplitudes=node["h"],
            family_numerator=fn.T, family_denominator=fd.T,
            numerator=fn.sum(0), denominator=fd.sum(0),
            phase_space_denominator=2*measure, pair_mass=invariant_mass(pair_momentum),
            eta_p_mass=invariant_mass(sample.momenta[:, 0]+sample.momenta[:, 2]))
        for name, value in values.items():
            records[name].append(value)
    arrays = {name: np.stack(value) for name, value in records.items()}
    arrays["coordinates"] = coordinates
    arrays["energy_nodes_gev"] = moment.energy_nodes_gev
    # Independent production projection remains the authority for N and D.
    np.testing.assert_allclose([arrays["numerator"].sum(), arrays["denominator"].sum()],
        [moment.numerator, moment.denominator], rtol=1e-12, atol=1e-12)
    if (any(not np.isfinite(value).all() for value in arrays.values())
            or np.any(arrays["denominator"] < 0)):
        raise ValueError("invalid event diagnostic weights")

    rows = []
    quartiles = np.minimum((4*coordinates).astype(int), 3)
    for power in range(4, sobol.power+1):
        n = 2**power
        scale = count/n
        row = {"power": power, "families": {}, "marginals": {}}
        for field in ("numerator", "denominator"):
            values = arrays[field][:, :n]*scale
            row[field] = float(values.sum())
            row["families"][field] = (arrays["family_"+field][:, :n]*scale).sum((0, 1)).tolist()
            for index, name in enumerate(coordinate_names):
                row["marginals"].setdefault(name, {})[field] = [
                    float(values[:, quartiles[:n, index] == q].sum()) for q in range(4)]
        row["sigma"] = row["numerator"]/row["denominator"] if row["denominator"] > 0 else None
        row["phase_space_denominator"] = float(arrays["phase_space_denominator"][:, :n].sum()*scale)
        rows.append(row)
    refinements = []
    for before, after in zip(rows, rows[1:]):
        refinement = {"powers": [before["power"], after["power"]],
            "numerator_delta": after["numerator"]-before["numerator"],
            "denominator_delta": after["denominator"]-before["denominator"],
            "marginal_drift": {}, "family_drift": {}}
        for field in ("numerator", "denominator"):
            refinement["family_drift"][field] = (np.array(after["families"][field])
                - np.array(before["families"][field])).tolist()
            for name in coordinate_names:
                refinement["marginal_drift"].setdefault(name, {})[field] = (
                    np.array(after["marginals"][name][field])
                    - np.array(before["marginals"][name][field])).tolist()
        refinements.append(refinement)
    largest = np.argsort(arrays["denominator"].ravel())[-10:][::-1]
    top = []
    for index in largest:
        node, event = np.unravel_index(index, arrays["denominator"].shape)
        top.append({"energy_node": int(node), "event": int(event),
            "denominator_fraction": float(arrays["denominator"][node, event]/moment.denominator),
            "coordinates": coordinates[event].tolist(),
            "pair_mass_gev": float(arrays["pair_mass"][node, event]),
            "eta_p_mass_gev": float(arrays["eta_p_mass"][node, event])})
    report = {"purpose": "event_variance_diagnostic_only", "pair": pair,
        "energy_range_gev": list(energy), "mass_range_gev": list(mass),
        "energy_order": energy_order, "sobol_power": sobol.power,
        "scramble": sobol.scramble, "seed": sobol.seed, "family_names": list(names),
        "coordinate_names": list(coordinate_names), "resolutions": rows,
        "refinements": refinements, "largest_denominator_events": top,
        "elapsed_seconds": monotonic()-start,
        "limitations": "No convergence certificate. Signed family allocations include interference. "
                        "Quartiles are separate marginals, not additive across coordinates. "
                        "Nested prefixes are correlated, not independent replicas."}
    return report, arrays


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pair", choices=tuple(PAIR_DAUGHTERS), default="eta_pi0")
    parser.add_argument("--energy", type=float, nargs=2, default=(1.1, 1.2))
    parser.add_argument("--mass", type=float, nargs=2, required=True)
    parser.add_argument("--power", type=int, default=5)
    parser.add_argument("--energy-order", type=int, default=1)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--mode", choices=("direct", "grid"), default="direct")
    parser.add_argument("--sampler", choices=("standard", "delta-helicity"), default="standard")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    # This recorder retains full amplitudes: bound memory before evaluation.
    if not 4 <= args.power <= 12 or not 1 <= args.energy_order <= 16:
        parser.error("diagnostic requires power 4..12 and energy order 1..16")
    config = SobolConfig(args.power, scramble=args.seed is not None, seed=args.seed)
    package_path = Path(graal_theory.__file__).resolve().parent
    if package_path != (THEORY/"src/graal_theory").resolve():
        raise ValueError("graal_theory loaded from another checkout; use PYTHONPATH=theory/src")
    args.output.mkdir(parents=True, exist_ok=False)
    files = sorted((THEORY/"src").rglob("*.py"))+sorted((THEORY/"references").glob("*.json"))
    files.append(Path(__file__).resolve())
    joint_path = THEORY/"scripts/figure4_joint_map_probe.py"
    if args.sampler == "delta-helicity":
        files.append(joint_path)
    provenance = {"command": sys.argv if argv is None else argv,
        "python": sys.version, "numpy": np.__version__, "scipy": scipy.__version__,
        "platform": platform.platform(), "mode": args.mode, "q_order": 64, "angle_order": 48,
        "package_path": str(package_path),
        "sampler": args.sampler,
        "git_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=THEORY, text=True).strip(),
        "sha256": {str(p.relative_to(THEORY)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}}
    (args.output/"provenance.json").write_text(json.dumps(provenance, indent=2)+"\n")
    print(f"Diagnostic only: {args.pair}, p4..p{args.power}, n={args.energy_order}, "
          f"{args.mode}, {args.sampler}", flush=True)
    start = monotonic()
    try:
        model = _figure4_model(THEORY/"references", args.mode, 64, 48)
        sampler, coordinate_names = None, COORDINATES
        sampling = {"name": args.sampler}
        if args.sampler == "delta-helicity":
            spec = importlib.util.spec_from_file_location("figure4_joint_map_probe", joint_path)
            joint = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(joint)
            tree = model.parameters.tree
            sampler = partial(joint.sample_delta_helicity,
                resonance_mass=tree.delta_mass_gev, resonance_width=tree.delta_width_gev)
            coordinate_names = joint.COORDINATES
            sampling.update(resonance_mass_gev=tree.delta_mass_gev,
                            resonance_width_gev=tree.delta_width_gev)
        report, arrays = diagnose_bin(model, args.pair, tuple(args.energy), tuple(args.mass),
            energy_order=args.energy_order, sobol=config, sampler=sampler,
            coordinate_names=coordinate_names)
        report["sampler"] = sampling
        report["total_elapsed_seconds"] = monotonic()-start
        np.savez_compressed(args.output/"events.npz", **arrays)
        report["events_sha256"] = hashlib.sha256((args.output/"events.npz").read_bytes()).hexdigest()
        (args.output/"report.json").write_text(json.dumps(report, indent=2, allow_nan=False)+"\n")
        (args.output/"COMPLETE").write_text("diagnostic only; no convergence certification\n")
    except Exception as exc:
        (args.output/"failure.json").write_text(json.dumps({"type": type(exc).__name__, "error": str(exc)})+"\n")
        raise
    print(f"Saved {args.output}; {report['total_elapsed_seconds']:.1f} s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
