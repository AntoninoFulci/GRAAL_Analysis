"""Executable S3 checks for reaction-plane periodicity and degeneracy."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

import numpy as np

from angles import reaction_plane_phi
from contracts import PolarizationContractError, load_json


def _validate_config(config_path: Path) -> None:
    config = load_json(config_path)
    angle = config.get("angle")
    if not isinstance(angle, dict):
        raise PolarizationContractError("config angle must be a JSON object")
    expected_keys = {
        "observable", "period_radians", "range_radians", "reference_axis_lab",
        "reaction_momentum", "degenerate_plane_policy", "tolerance",
    }
    if set(angle) != expected_keys:
        raise PolarizationContractError("config angle keys are not canonical")
    if (
        angle.get("observable") != "reaction_plane_phi"
        or angle.get("period_radians") != np.pi
        or angle.get("range_radians") != [0.0, np.pi]
        or angle.get("reference_axis_lab") != [1.0, 0.0, 0.0]
        or angle.get("reaction_momentum") != "proton"
        or angle.get("degenerate_plane_policy") != "invalid"
        or isinstance(angle.get("tolerance"), bool)
        or not isinstance(angle.get("tolerance"), (int, float))
        or not np.isfinite(angle["tolerance"])
        or angle["tolerance"] <= 0.0
    ):
        raise PolarizationContractError("config angle convention is not canonical")


def run_periodicity_checks() -> None:
    beam = np.array([0.0, 0.0, 1.0])
    reference = np.array([1.0, 0.0, 0.0])
    for angle in (0.0, 0.2, np.pi / 2.0, np.pi - 1e-9):
        momentum = np.array([np.cos(angle), np.sin(angle), 0.4])
        nominal = reaction_plane_phi(beam, reference, momentum)
        reversed_axis = reaction_plane_phi(beam, reference, -momentum)
        if not nominal.valid or not reversed_axis.valid:
            raise PolarizationContractError("synthetic nondegenerate plane marked invalid")
        if not np.isclose(nominal.value, reversed_axis.value, rtol=0.0, atol=1e-12):
            raise PolarizationContractError("phi is not periodic under plane-axis reversal")
    epsilon = 1e-9
    left = reaction_plane_phi(
        beam, reference, [np.cos(-epsilon), np.sin(-epsilon), 0.0]
    )
    right = reaction_plane_phi(
        beam, reference, [np.cos(epsilon), np.sin(epsilon), 0.0]
    )
    if not np.isclose(
        np.cos(2.0 * left.value), np.cos(2.0 * right.value), rtol=0.0, atol=1e-14
    ):
        raise PolarizationContractError("cos(2phi) is discontinuous at 0/pi")
    degenerate = reaction_plane_phi(beam, reference, beam)
    if degenerate.valid or not np.isnan(degenerate.value):
        raise PolarizationContractError("degenerate reaction plane was not marked invalid")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        _validate_config(args.config)
        run_periodicity_checks()
    except (PolarizationContractError, TypeError, ValueError) as exc:
        print(f"Phi periodicity validation failed: {exc}", file=sys.stderr)
        return 1
    print("Phi periodicity validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
