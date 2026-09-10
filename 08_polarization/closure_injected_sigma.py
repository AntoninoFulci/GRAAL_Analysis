"""Injected-asymmetry closure and controlled orientation-sign test."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import sys

import numpy as np

from contracts import PolarizationContractError, load_json
from sigma_fit import fit_sigma_binned


@dataclass(frozen=True)
class ClosureResult:
    injected_sigma: float
    fitted_mean: float
    bias: float
    pull_mean: float
    pull_width: float
    experiments: int
    bias_threshold: float
    pull_mean_threshold: float
    pull_width_tolerance: float
    sign_check_passed: bool
    valid: bool


def _closure_design(injected_sigma: float) -> tuple[dict[str, np.ndarray], np.ndarray]:
    phi_state = (np.arange(16, dtype=float) + 0.5) * np.pi / 16.0
    phi = np.concatenate((phi_state, phi_state))
    sign = np.concatenate((-np.ones(16), np.ones(16)))
    polarization = np.concatenate((np.full(16, 0.74), np.full(16, 0.66)))
    acceptance = np.concatenate(
        (
            0.28 + 0.58 * np.sin(phi_state + 0.11) ** 2,
            0.32 + 0.52 * np.cos(phi_state - 0.19) ** 2,
        )
    )
    exposure = np.concatenate((np.full(16, 1.15), np.full(16, 0.87)))
    state_scale = np.where(sign < 0.0, 6000.0, 5200.0)
    expected = (
        exposure
        * acceptance
        * state_scale
        * (1.0 + sign * polarization * injected_sigma * np.cos(2.0 * phi))
    )
    design = {
        "phi": phi,
        "orientation_sign": sign,
        "polarization": polarization,
        "acceptance": acceptance,
        "exposure": exposure,
    }
    return design, expected


def run_injected_closure(
    injected_sigma: float,
    *,
    seed: int = 1701,
    experiments: int = 50,
    bias_threshold: float = 0.02,
    pull_mean_threshold: float = 0.2,
    pull_width_tolerance: float = 0.2,
) -> ClosureResult:
    """Run deterministic Poisson ensemble and Asimov sign inversion."""
    injected = float(injected_sigma)
    if not np.isfinite(injected) or not -1.0 <= injected <= 1.0:
        raise PolarizationContractError("injected Sigma must lie in [-1, 1]")
    if isinstance(experiments, bool) or not isinstance(experiments, int) or experiments < 2:
        raise PolarizationContractError("closure experiments must be an integer >= 2")
    thresholds = (bias_threshold, pull_mean_threshold, pull_width_tolerance)
    if any(not np.isfinite(value) or value < 0.0 for value in thresholds):
        raise PolarizationContractError("closure thresholds must be finite and nonnegative")
    design, expected = _closure_design(injected)
    rng = np.random.default_rng(seed)
    estimates = []
    pulls = []
    for _ in range(experiments):
        observed = rng.poisson(expected)
        fit = fit_sigma_binned(**design, observed=observed)
        estimates.append(fit.sigma)
        pulls.append((fit.sigma - injected) / fit.stat_uncertainty)
    fitted_mean = float(np.mean(estimates))
    bias = fitted_mean - injected
    pull_mean = float(np.mean(pulls))
    pull_width = float(np.std(pulls, ddof=1))
    asimov = fit_sigma_binned(**design, observed=expected)
    swapped_design = dict(design)
    swapped_design["orientation_sign"] = -design["orientation_sign"]
    swapped = fit_sigma_binned(**swapped_design, observed=expected)
    sign_check_passed = abs(swapped.sigma + asimov.sigma) <= 5e-6
    valid = (
        abs(bias) <= bias_threshold
        and abs(pull_mean) <= pull_mean_threshold
        and abs(pull_width - 1.0) <= pull_width_tolerance
        and sign_check_passed
    )
    return ClosureResult(
        injected_sigma=injected,
        fitted_mean=fitted_mean,
        bias=bias,
        pull_mean=pull_mean,
        pull_width=pull_width,
        experiments=experiments,
        bias_threshold=float(bias_threshold),
        pull_mean_threshold=float(pull_mean_threshold),
        pull_width_tolerance=float(pull_width_tolerance),
        sign_check_passed=sign_check_passed,
        valid=valid,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--require-sign-check", action="store_true")
    parser.add_argument(
        "--injected", type=float, nargs="*", default=[-0.6, -0.2, 0.0, 0.3, 0.7]
    )
    args = parser.parse_args(argv)
    try:
        config = load_json(args.config)
        closure = config.get("closure")
        if not isinstance(closure, dict):
            raise PolarizationContractError("config closure must be a JSON object")
        results = [
            run_injected_closure(
                injected,
                seed=int(closure["random_seed"]),
                bias_threshold=float(closure["bias_absolute_max"]),
                pull_mean_threshold=float(closure["pull_mean_absolute_max"]),
                pull_width_tolerance=float(closure["pull_width_tolerance"]),
            )
            for injected in args.injected
        ]
    except (KeyError, TypeError, ValueError, PolarizationContractError) as exc:
        print(f"Injected Sigma closure failed: {exc}", file=sys.stderr)
        return 1
    if args.require_sign_check and any(not result.sign_check_passed for result in results):
        print("Injected Sigma closure failed: orientation sign check", file=sys.stderr)
        return 1
    invalid = [result for result in results if not result.valid]
    for result in results:
        print(
            f"Sigma={result.injected_sigma:+.3f} bias={result.bias:+.5f} "
            f"pull={result.pull_mean:+.3f}+/-{result.pull_width:.3f} "
            f"sign={result.sign_check_passed} valid={result.valid}"
        )
    return 1 if invalid else 0


if __name__ == "__main__":
    raise SystemExit(main())
