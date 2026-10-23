"""Diagnostic endpoint-aware phase-space map for Figure 4 raw moments.

This trial changes sampling coordinates with an exact Jacobian. It changes
no amplitudes, physics parameters, numerical gates, or production sampler.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import tempfile
from time import monotonic

import numpy as np
from scipy.stats import qmc

from graal_theory.cli import _figure4_model
from graal_theory import figure4_integration, phase_space
from graal_theory.figure4_integration import _safe_predict
from graal_theory.kinematics import invariant_mass, validate_final_state
from graal_theory.phase_space import SobolConfig, ThreeBodySample


REFERENCES = Path(__file__).resolve().parents[1]/"references"
CONTROLS = {
    "lower": ((1.10, 1.20), (1.52, 1.56)),
    "upper": ((1.40, 1.50), (1.60, 1.64)),
}


def endpoint_map(points):
    """Cluster mass and both polar coordinates at both physical endpoints."""
    raw = np.asarray(points, dtype=float)
    if (raw.ndim != 2 or raw.shape[1] != 4 or not np.isfinite(raw).all()
            or np.any((raw < 0) | (raw > 1))):
        raise ValueError("endpoint map requires finite (N,4) unit-cube points")
    mapped = raw.copy()
    mapped[:, :3] = (1-np.cos(np.pi*raw[:, :3]))/2
    jacobian = np.prod(np.pi/2*np.sin(np.pi*raw[:, :3]), axis=1)
    return mapped, jacobian


def mapped_sample(sqrt_s, masses, pair, mass_range_gev, config,
                  *, reduce_global_azimuth=False):
    """Experimental counterpart of the established conditional sampler."""
    baseline = phase_space.sample_three_body_mass_window(
        sqrt_s, masses, pair, mass_range_gev, config,
        reduce_global_azimuth=reduce_global_azimuth)
    if baseline is None or not reduce_global_azimuth:
        return baseline
    spectator = next(index for index in range(3) if index not in pair)
    permutation = (*pair, spectator)
    ordered_masses = tuple(masses[index] for index in permutation)
    low = max(mass_range_gev[0], ordered_masses[0]+ordered_masses[1])
    high = min(mass_range_gev[1], sqrt_s-ordered_masses[2])
    raw = qmc.Sobol(d=4, scramble=config.scramble,
                    seed=config.seed).random_base2(config.power)
    mapped, jacobian = endpoint_map(raw)
    points = np.column_stack((mapped[:, 0], mapped[:, 1],
                              np.zeros(len(mapped)), mapped[:, 2], mapped[:, 3]))
    ordered = phase_space._sample_ordered(sqrt_s, ordered_masses, config,
                                          points, low**2, high**2)
    momenta = ordered.momenta[:, np.argsort(permutation), :].copy()
    canonical_s12 = invariant_mass(momenta[:, 0]+momenta[:, 1])**2
    validate_final_state(ordered.initial, momenta, masses, atol=1e-12)
    return ThreeBodySample(ordered.initial, momenta,
                           ordered.weights_gev2*jacobian, masses,
                           canonical_s12, config)


def probe(control: str) -> dict:
    energy, mass = CONTROLS[control]
    model = _figure4_model(REFERENCES, "grid", 64, 48)
    start = monotonic()
    rows = []
    original = figure4_integration.sample_three_body_mass_window
    figure4_integration.sample_three_body_mass_window = mapped_sample
    try:
        for power in (5, 6, 7, 8):
            moment = _safe_predict(model, "p_eta", energy, mass, 4,
                                   SobolConfig(power))
            rows.append({
                "power": power,
                "status": moment.status,
                "reason": moment.reason,
                "sigma": moment.sigma if moment.denominator > 0 else None,
                "numerator": moment.numerator,
                "denominator": moment.denominator,
                "vertical_normalization": moment.vertical_normalization,
                "horizontal_normalization": moment.horizontal_normalization,
            })
    finally:
        figure4_integration.sample_three_body_mass_window = original
    return {
        "purpose": "endpoint_map_diagnostic_only",
        "control": control,
        "pair": "p_eta",
        "energy_range_gev": energy,
        "mass_range_gev": mass,
        "energy_order": 4,
        "q_order": 64,
        "angle_order": 48,
        "mode": "grid",
        "powers": rows,
        "elapsed_seconds": monotonic()-start,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--control", choices=tuple(CONTROLS), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.output.exists():
        parser.error(f"output already exists: {args.output}")
    print(f"Endpoint-map diagnostic: {args.control}, p5..p8", flush=True)
    result = probe(args.control)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=args.output.parent,
                                     prefix=".figure4-endpoint-", suffix=".json",
                                     delete=False) as stream:
        temp = Path(stream.name)
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write("\n")
    os.replace(temp, args.output)
    complete = all(row["status"] == "calculated" for row in result["powers"])
    print(f"Saved {args.output}: {'calculated' if complete else 'masked'}, "
          f"{result['elapsed_seconds']:.1f} s", flush=True)
    return 0 if complete else 2


if __name__ == "__main__":
    raise SystemExit(main())
