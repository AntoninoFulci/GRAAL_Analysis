"""Tabulated Compton beam polarization with covariance propagation."""

from __future__ import annotations

from pathlib import Path
from typing import Mapping

import numpy as np

from contracts import PolarizationContractError, load_json, validate_source


class PolarizationCurve:
    """Piecewise-linear `P(Egamma)` with covariance on tabulated nodes."""

    def __init__(self, energies_mev, values, covariance) -> None:
        self.energies_mev = np.asarray(energies_mev, dtype=float)
        self.values = np.asarray(values, dtype=float)
        self.covariance = np.asarray(covariance, dtype=float)
        self._validate()

    def _validate(self) -> None:
        energies = self.energies_mev
        values = self.values
        covariance = self.covariance
        if energies.ndim != 1 or energies.size < 2:
            raise PolarizationContractError("Compton curve requires at least two energy nodes")
        if values.shape != energies.shape:
            raise PolarizationContractError("Compton values must match energy-node shape")
        if not np.all(np.isfinite(energies)) or not np.all(np.isfinite(values)):
            raise PolarizationContractError("Compton curve values must be finite")
        if not np.all(np.diff(energies) > 0.0):
            raise PolarizationContractError("Compton energies must be strictly increasing")
        if np.any((values < 0.0) | (values > 1.0)):
            raise PolarizationContractError("Compton polarization must stay in physical range [0,1]")
        expected_shape = (energies.size, energies.size)
        if covariance.shape != expected_shape:
            raise PolarizationContractError(
                f"Compton covariance shape must be {expected_shape}"
            )
        if not np.all(np.isfinite(covariance)):
            raise PolarizationContractError("Compton covariance must be finite")
        if not np.allclose(covariance, covariance.T, rtol=1e-12, atol=1e-14):
            raise PolarizationContractError("Compton covariance must be symmetric")
        scale = max(1.0, float(np.max(np.abs(covariance))))
        if float(np.min(np.linalg.eigvalsh(covariance))) < -1e-12 * scale:
            raise PolarizationContractError("Compton covariance must be positive semidefinite")

    def _weights_at(self, energy_mev: float) -> np.ndarray:
        energy = float(energy_mev)
        if not np.isfinite(energy):
            raise PolarizationContractError("Compton evaluation energy must be finite")
        low = float(self.energies_mev[0])
        high = float(self.energies_mev[-1])
        if energy < low or energy > high:
            raise PolarizationContractError(
                f"Compton extrapolation forbidden outside [{low}, {high}] MeV"
            )
        if energy == high:
            weights = np.zeros(self.energies_mev.size)
            weights[-1] = 1.0
            return weights
        right = int(np.searchsorted(self.energies_mev, energy, side="right"))
        left = max(0, right - 1)
        right = min(right, self.energies_mev.size - 1)
        if left == right:
            weights = np.zeros(self.energies_mev.size)
            weights[left] = 1.0
            return weights
        fraction = (energy - self.energies_mev[left]) / (
            self.energies_mev[right] - self.energies_mev[left]
        )
        weights = np.zeros(self.energies_mev.size)
        weights[left] = 1.0 - fraction
        weights[right] = fraction
        return weights

    def _evaluate_weights(self, weights: np.ndarray) -> tuple[float, float]:
        value = float(weights @ self.values)
        variance = float(weights @ self.covariance @ weights)
        return value, max(0.0, variance)

    def evaluate(self, energy_mev: float) -> tuple[float, float]:
        """Return interpolated polarization and variance at one energy."""
        return self._evaluate_weights(self._weights_at(energy_mev))

    def bin_average(self, low_mev: float, high_mev: float) -> tuple[float, float]:
        """Return uniform-energy average and propagated variance for one bin."""
        low = float(low_mev)
        high = float(high_mev)
        if not np.isfinite(low) or not np.isfinite(high) or high <= low:
            raise PolarizationContractError("Compton averaging bin must have positive width")
        # Endpoint calls enforce no extrapolation. Internal knots make trapezoidal
        # integration exact for each piecewise-linear basis function.
        self._weights_at(low)
        self._weights_at(high)
        points = [low]
        points.extend(float(value) for value in self.energies_mev if low < value < high)
        points.append(high)
        integral_weights = np.zeros(self.energies_mev.size)
        for left, right in zip(points, points[1:]):
            width = right - left
            integral_weights += 0.5 * width * (
                self._weights_at(left) + self._weights_at(right)
            )
        return self._evaluate_weights(integral_weights / (high - low))


def load_period_curves(
    config_path: Path,
    repository_root: Path,
) -> dict[str, PolarizationCurve]:
    """Load authority-approved period curves from configuration."""
    config = load_json(config_path)
    section = config.get("compton_polarization")
    if not isinstance(section, Mapping):
        raise PolarizationContractError(
            "config compton_polarization must be a JSON object"
        )
    if section.get("status") != "ready":
        raise PolarizationContractError(
            "Compton polarization is blocked; authoritative period source missing"
        )
    periods = section.get("periods")
    if not isinstance(periods, list) or not periods:
        raise PolarizationContractError("Compton polarization requires period curves")
    curves: dict[str, PolarizationCurve] = {}
    for raw in periods:
        if not isinstance(raw, Mapping):
            raise PolarizationContractError("Compton period must be a JSON object")
        name = raw.get("source_period")
        if not isinstance(name, str) or not name.strip() or name in curves:
            raise PolarizationContractError("Compton source_period must be unique and non-empty")
        source = raw.get("source")
        if not isinstance(source, Mapping):
            raise PolarizationContractError(f"Compton period {name} requires source provenance")
        validate_source(source, repository_root)
        try:
            curves[name] = PolarizationCurve(
                raw["energies_mev"], raw["polarization"], raw["covariance"]
            )
        except KeyError as exc:
            raise PolarizationContractError(
                f"Compton period {name} missing field: {exc.args[0]}"
            ) from exc
    return curves
