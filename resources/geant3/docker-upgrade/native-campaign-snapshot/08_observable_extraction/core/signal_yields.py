"""Provisional, selection-truncated two-mass signal extraction.

Signal weights separate a double mass peak from a smooth continuum. Optional
one-meson peak components provide a model variation. They do not distinguish physics backgrounds peaking in both masses.
The covariance differentiates both the fitted weights and the same Poisson
counts used to fit them; holding fitted weights fixed underestimates uncertainty.
"""

from __future__ import annotations

import numpy as np
from scipy.optimize import minimize
from scipy.special import ndtr, softmax
from scipy.stats import chi2


class MassModel:
    """Mass components integrated within the actual chi2 mass ellipse.

    Coordinates are (M-M_PDG)/(0.08 M_PDG). A correlated skew-normal peak
    models signal; an exponential density in each mass models the continuum. The optional extended model adds
    single-meson peak components; it is used only as a model variation.
    """

    def __init__(self, bins=24, cut=10.0, quadrature=8, extended=False):
        self.extended = extended
        self.bins, self.cut = bins, cut
        self.edges = np.linspace(-np.sqrt(cut), np.sqrt(cut), bins + 1)
        centers = (self.edges[:-1] + self.edges[1:]) / 2
        nodes, weights = np.polynomial.legendre.leggauss(quadrature)
        delta = np.diff(self.edges)[0] / 2
        axis = centers[:, None] + nodes[None, :] * delta
        self.x = np.broadcast_to(
            axis[:, None, :, None], (bins, bins, quadrature, quadrature)
        ).reshape(bins * bins, -1)
        self.y = np.broadcast_to(
            axis[None, :, None, :], (bins, bins, quadrature, quadrature)
        ).reshape(bins * bins, -1)
        self.integration = np.outer(weights, weights).reshape(-1)[None, :] * (
            self.x**2 + self.y**2 < cut
        )
        self.active = self.integration.sum(axis=1) > 0
        self.initial = np.array(
            [
                -0.1,
                -0.05,
                np.log(0.65),
                np.log(0.95),
                0.05,
                -0.15,
                -0.05,
                2.0,
                0.2,
                0.2,
                -1.0,
                0.1,
            ]
        )
        self.bounds = [
            (-1.2, 1.2),
            (-1.2, 1.2),
            (-1.4, 0.35),
            (-1.0, 0.5),
            (-0.7, 0.7),
            (-6, 6),
            (-6, 6),
            (-7, 7),
            (-7, 7),
            (-7, 7),
            (-8, 8),
            (-8, 8),
        ]

    def components(self, theta):
        mx, my, lx, ly, rho, ax, ay = theta[:7]
        sx, sy = np.exp([lx, ly])
        x, y = (self.x - mx) / sx, (self.y - my) / sy
        gx, gy = (
            np.exp(-0.5 * x * x) / sx * 2 * ndtr(theta[10] * x),
            np.exp(-0.5 * y * y) / sy * 2 * ndtr(theta[11] * y),
        )
        signal = (
            np.exp(-0.5 * (x * x + y * y - 2 * rho * x * y) / (1 - rho * rho))
            / (sx * sy * np.sqrt(1 - rho * rho))
            * 2
            * ndtr(theta[10] * x + theta[11] * y)
        )
        bx, by = (
            np.exp(ax * self.x / np.sqrt(self.cut)),
            np.exp(ay * self.y / np.sqrt(self.cut)),
        )
        columns = [signal, bx * gy, gx * by, bx * by]
        templates = np.stack(
            [(v * self.integration).sum(axis=1) for v in columns], axis=1
        )
        templates /= templates.sum(axis=0)
        if self.extended:
            return templates, softmax(np.r_[theta[7:10], 0.0])
        return templates[:, [0, 3]], softmax(np.r_[theta[7], 0.0])

    def probabilities(self, theta):
        templates, fractions = self.components(theta)
        return templates @ fractions


def _jacobian(function, theta, step=2e-4):
    return np.stack(
        [
            (
                function(theta + np.eye(len(theta))[i] * step)
                - function(theta - np.eye(len(theta))[i] * step)
            )
            / (2 * step)
            for i in range(len(theta))
        ],
        axis=-1,
    )


def signal_weights(templates, probability):
    templates, probability = np.asarray(templates), np.asarray(probability)
    active = probability > 0
    information = templates[active].T @ (templates[active] / probability[active, None])
    if np.linalg.cond(information) > 1e10:
        raise ValueError("mass components cannot be separated")
    weights = np.zeros(len(probability))
    weights[active] = (
        templates[active] @ np.linalg.solve(information, np.eye(templates.shape[1])[0])
    ) / probability[active]
    return weights


def fit_mass_model(model, counts, *, start=None, multistart=True):
    counts = np.asarray(counts, dtype=float)
    if (
        counts.shape != (model.bins**2,)
        or not np.all(np.isfinite(counts))
        or np.any(counts < 0)
        or counts.sum() <= 0
    ):
        raise ValueError("mass histogram must have finite nonnegative nonempty counts")
    if np.any(counts[~model.active]):
        raise ValueError("mass events outside selection ellipse")
    active = model.active
    total = counts.sum()

    def objective(theta):
        probability = model.probabilities(theta)[active]
        return -np.dot(counts[active], np.log(probability)) / total

    starts = [model.initial if start is None else np.asarray(start)]
    free = (
        np.arange(len(model.initial))
        if model.extended
        else np.array([0, 1, 2, 3, 4, 5, 6, 7, 10, 11])
    )

    def expand(z):
        t = starts[0].copy()
        t[free] = z
        return t

    if multistart:
        other = starts[0].copy()
        other[7:10] = [0.5, 0.0, 0.0]
        starts.append(other)
    results = [
        minimize(
            lambda z: objective(expand(z)),
            initial[free],
            method="L-BFGS-B",
            bounds=[model.bounds[i] for i in free],
            options={"ftol": 1e-13, "gtol": 2e-7, "maxiter": 1500, "maxls": 40},
        )
        for initial in starts
    ]
    good = [r for r in results if r.success and np.isfinite(r.fun)]
    if not good:
        raise ValueError(
            "mass fit failed convergence: " + "; ".join(str(r.message) for r in results)
        )
    fit = min(good, key=lambda r: r.fun)
    fit.x = expand(fit.x)
    templates, fractions = model.components(fit.x)
    expected = total * (templates @ fractions)
    occupied = counts > 0
    deviance = 2 * float(
        np.sum(counts[occupied] * np.log(counts[occupied] / expected[occupied]))
    )
    dof = int(active.sum() - 1 - len(free))
    weights = signal_weights(templates, expected / total)
    boundaries = [
        i
        for i, (lo, hi) in enumerate(model.bounds)
        if i in free and min(fit.x[i] - lo, hi - fit.x[i]) < 0.002
    ]
    return {
        "theta": fit.x,
        "free_parameters": free,
        "converged": True,
        "fractions": fractions,
        "expected": expected,
        "counts": counts,
        "signal_yield": float(counts @ weights),
        "weights": weights,
        "deviance": deviance,
        "dof": dof,
        "p_value_asymptotic": float(chi2.sf(deviance, dof)),
        "boundary_parameters": boundaries,
        "n_events": float(total),
    }


def yield_influence(model, fit, cell_counts, *, full_covariance=True):
    """First-order covariance including same-data fitted shape/count correlation.

    Returns factors for C = diag(count_variance) + L @ K @ L.T. K need not be
    positive semidefinite individually: the complete covariance is the Poisson
    influence covariance and is PSD. Empty cells have zero observed information.
    """
    cells = np.asarray(cell_counts, dtype=float)
    if (
        cells.ndim != 2
        or cells.shape[1] != model.bins**2
        or np.any(cells < 0)
        or not np.all(np.isfinite(cells))
    ):
        raise ValueError("cell mass histograms have invalid dimensions/counts")
    if np.any(cells.sum(axis=0) > fit["counts"] + 1e-7):
        raise ValueError("cell histograms must be a disjoint subset of fitted events")
    theta_full = fit["theta"]
    free = fit["free_parameters"]
    theta = theta_full[free]
    pooled = fit["counts"]
    weights = fit["weights"]

    def expand(z):
        t = theta_full.copy()
        t[free] = z
        return t

    active = model.active

    def logp(t):
        return np.log(model.probabilities(expand(t))[active])

    score = _jacobian(logp, theta)

    # Differentiate observed likelihood, not a separate independent calibration.
    def gradient(t):
        return -pooled[active] @ _jacobian(logp, t)

    hessian = _jacobian(gradient, theta, step=5e-4)
    hessian = (hessian + hessian.T) / 2
    eigenvalues = np.linalg.eigvalsh(hessian)
    if eigenvalues[0] <= max(eigenvalues[-1] * 1e-8, 0):
        raise ValueError("nonpositive or unidentified fitted-shape Hessian")
    response = np.zeros((len(pooled), len(theta)))
    response[active] = score @ np.linalg.inv(hessian)

    def weight_function(t):
        templates, fractions = model.components(expand(t))
        return signal_weights(templates, templates @ fractions)

    weight_derivative = _jacobian(weight_function, theta)
    derivative = cells @ weight_derivative
    cross = (cells * weights) @ response
    shape_covariance = response.T @ (pooled[:, None] * response)
    diagonal = cells @ (weights**2)
    factors = np.concatenate([derivative, cross], axis=1)
    identity = np.eye(len(theta))
    kernel = np.block(
        [[shape_covariance, identity], [identity, np.zeros_like(identity)]]
    )
    covariance = (
        (np.diag(diagonal) + factors @ kernel @ factors.T) if full_covariance else None
    )
    return (
        cells @ weights,
        covariance,
        {
            "diagonal": diagonal,
            "factors": factors,
            "kernel": kernel,
            "hessian_eigenvalues": eigenvalues,
        },
    )
