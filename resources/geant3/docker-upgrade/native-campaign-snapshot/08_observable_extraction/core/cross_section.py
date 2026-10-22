"""Linear detector-response inference of unpolarized cross sections.

Observed signal yields are R @ L @ (sigma + sign P a cos(2 phi)).
Sigma and the polarized amplitude a are fitted together; unequal H/V
luminosities must not be cancelled by summing raw counts. Phi is integrated
over each truth cell. The supplied response must describe the production
distribution within each cell, including any unbinned variables.

This is a Gaussian binned estimator, not a low-count Poisson interval method.
No regularization, positivity clipping, or acceptance-hole extrapolation is
silently applied. Errors are first-order conditional errors.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from observable_extraction.core.systematics import validate_covariance


def checked_edges(values, name):
    edges = np.asarray(values, dtype=float)
    if (
        edges.ndim != 1
        or len(edges) < 2
        or not np.all(np.isfinite(edges))
        or np.any(np.diff(edges) <= 0)
    ):
        raise ValueError(f"{name} must be finite strictly increasing edges")
    return edges


def cross_section_basis(luminosity, polarization, phi_edges, state):
    """Truth-cell expectation per μb; luminosity includes external BR [μb⁻¹]."""
    lumi = np.asarray(luminosity, dtype=float)
    pol = np.asarray(polarization, dtype=float)
    edges = checked_edges(phi_edges, "phi")
    if not np.isclose(edges[0], 0, atol=1e-12) or not np.isclose(
        edges[-1], 2 * np.pi, atol=1e-12
    ):
        raise ValueError("phi edges must cover [0, 2pi]")
    if (
        lumi.ndim != 1
        or not len(lumi)
        or pol.shape != lumi.shape
        or not np.all(np.isfinite(lumi))
        or np.any(lumi < 0)
        or not np.all(np.isfinite(pol))
        or np.any((pol < 0) | (pol > 1))
    ):
        raise ValueError("invalid luminosity or polarization")
    if state not in (1, 2):
        raise ValueError("state must be pipeline POL1=vertical or POL2=horizontal")
    fraction = np.diff(edges) / (2 * np.pi)
    harmonic = np.diff(np.sin(2 * edges)) / (4 * np.pi)
    n, p = len(lumi), len(fraction)
    basis = np.zeros((n * p, 2 * n))
    for k in range(n):
        basis[k * p : (k + 1) * p, k] = lumi[k] * fraction
        basis[k * p : (k + 1) * p, n + k] = (
            lumi[k] * pol[k] * harmonic * (1 if state == 1 else -1)
        )
    return basis


def design_matrix(response, luminosity, polarization, phi_edges, state):
    basis = cross_section_basis(luminosity, polarization, phi_edges, state)
    response = np.asarray(response, dtype=float)
    if (
        response.shape != (len(basis), len(basis))
        or not np.all(np.isfinite(response))
        or np.any(response < 0)
        or np.any(response.sum(axis=0) > 1 + 1e-12)
    ):
        raise ValueError("invalid detector response")
    return response @ basis


@dataclass(frozen=True)
class CrossSectionFit:
    coefficients: np.ndarray
    covariance: np.ndarray
    estimator: np.ndarray
    normal_inverse: np.ndarray
    weighted_residual: np.ndarray
    chi2: float
    dof: int
    condition: float


def fit_cross_sections(yields, yield_covariance, design):
    """Unregularized GLS with SVD rank check; signed net yields are retained."""
    y = np.asarray(yields, dtype=float)
    a = np.asarray(design, dtype=float)
    if (
        y.ndim != 1
        or not len(y)
        or a.ndim != 2
        or a.shape[0] != len(y)
        or not a.shape[1]
        or not np.all(np.isfinite(y))
        or not np.all(np.isfinite(a))
    ):
        raise ValueError("invalid yields/design dimensions or nonfinite values")
    covariance = validate_covariance(yield_covariance, size=len(y))
    try:
        chol = np.linalg.cholesky(covariance)
    except np.linalg.LinAlgError as exc:
        raise ValueError("yield covariance must be positive definite") from exc
    whitened = np.linalg.solve(chol, a)
    u, singular, vt = np.linalg.svd(whitened, full_matrices=False)
    tolerance = np.finfo(float).eps * max(a.shape) * singular[0] if len(singular) else 0
    if (
        len(singular) < a.shape[1]
        or np.count_nonzero(singular > tolerance) != a.shape[1]
    ):
        raise ValueError(
            "rank-deficient response: cross section/polarized amplitude not identifiable"
        )
    inverse = (vt.T / singular) @ u.T
    estimator = np.linalg.solve(chol.T, inverse.T).T
    coefficients = estimator @ y
    normal_inverse = (vt.T / singular**2) @ vt
    residual = y - a @ coefficients
    white_residual = np.linalg.solve(chol, residual)
    return CrossSectionFit(
        coefficients,
        normal_inverse,
        estimator,
        normal_inverse,
        np.linalg.solve(chol.T, white_residual),
        float(white_residual @ white_residual),
        len(y) - a.shape[1],
        float(singular[0] / singular[-1]),
    )


def design_shift(fit, delta_design):
    """Derivative of GLS coefficients with fixed data covariance (includes residual term)."""
    delta = np.asarray(delta_design, dtype=float)
    if delta.shape != (fit.estimator.shape[1], len(fit.coefficients)) or not np.all(
        np.isfinite(delta)
    ):
        raise ValueError("invalid design perturbation")
    return (
        fit.normal_inverse @ delta.T @ fit.weighted_residual
        - fit.estimator @ delta @ fit.coefficients
    )


def response_uncertainty(fit, column_covariances, blocks):
    """Propagate one shared MC response across all blocks using it, only once.

    Each block is (observation slice, truth basis). Different independent MC
    samples require separate calls; reusing one sample across periods/H/V
    requires all its blocks in the same call.
    """
    cov = np.asarray(column_covariances, dtype=float)
    if cov.ndim != 3 or cov.shape[0] != cov.shape[1] or cov.shape[1] != cov.shape[2]:
        raise ValueError("invalid response covariance shape")
    n, parameters = cov.shape[0], len(fit.coefficients)
    result = np.zeros((parameters, parameters))
    for true in range(n):
        jacobian = np.zeros((parameters, n))
        for rows, basis in blocks:
            if basis.shape != (n, parameters) or fit.estimator[:, rows].shape[1] != n:
                raise ValueError("response block dimensions mismatch")
            jacobian += np.outer(
                fit.normal_inverse @ basis[true], fit.weighted_residual[rows]
            ) - fit.estimator[:, rows] * (basis[true] @ fit.coefficients)
        result += jacobian @ validate_covariance(cov[true], size=n) @ jacobian.T
    return validate_covariance(result, size=parameters)


def differential_transform(n_energy, mass_edges_gev):
    """Convert cross section integrated in each mass bin to μb/MeV."""
    edges = checked_edges(mass_edges_gev, "mass")
    if type(n_energy) is not int or n_energy < 1:
        raise ValueError("n_energy must be positive")
    return np.diag(np.tile(1 / (1000 * np.diff(edges)), n_energy))


def harmonic_design(moments, luminosity, polarization):
    """Design from event-level MC harmonics, including fitted truth guards.

    Luminosities/polarizations are ordered vertical then horizontal. The
    response remains conditional on the energy/phase-space distribution
    within each truth-energy bin. All truth coefficients, including guards,
    are fitted; reconstructed and true domains need not have equal size.
    """
    moments = np.asarray(moments, dtype=float)
    luminosity, polarization = (
        np.asarray(luminosity, dtype=float),
        np.asarray(polarization, dtype=float),
    )
    if (
        moments.ndim != 3
        or moments.shape[1] != 2
        or not moments.shape[0]
        or not moments.shape[2]
    ):
        raise ValueError("invalid harmonic response dimensions")
    nt, _, nr = moments.shape
    if luminosity.shape != (2, nt) or polarization.shape != (2, nt):
        raise ValueError("harmonic luminosity/polarization dimensions differ")
    if any(not np.isfinite(a).all() for a in (moments, luminosity, polarization)):
        raise ValueError("nonfinite harmonic response")
    if np.any(luminosity < 0) or np.any((polarization < 0) | (polarization > 1)):
        raise ValueError("invalid luminosity/polarization")
    if (
        np.any(moments[:, 0] < 0)
        or np.any(moments[:, 0].sum(axis=1) > 1 + 1e-12)
        or np.any(np.abs(moments[:, 1]) > moments[:, 0] + 1e-12)
    ):
        raise ValueError("unphysical harmonic response moments")
    design = np.zeros((2 * nr, 2 * nt))
    for state, sign in enumerate((1, -1)):
        rows = slice(state * nr, (state + 1) * nr)
        design[rows, :nt] = moments[:, 0].T * luminosity[state]
        design[rows, nt:] = moments[:, 1].T * (
            sign * luminosity[state] * polarization[state]
        )
    return design


def harmonic_mc_covariance(fit, moment_covariance, luminosity, polarization):
    """Propagate the same generated sample jointly through both beam states."""
    cov = np.asarray(moment_covariance, dtype=float)
    luminosity, polarization = (
        np.asarray(luminosity, dtype=float),
        np.asarray(polarization, dtype=float),
    )
    if cov.ndim != 3 or cov.shape[1] != cov.shape[2] or cov.shape[1] % 2:
        raise ValueError("invalid harmonic covariance dimensions")
    nt, nr = len(cov), cov.shape[1] // 2
    if (
        luminosity.shape != (2, nt)
        or polarization.shape != (2, nt)
        or fit.estimator.shape != (2 * nt, 2 * nr)
    ):
        raise ValueError("harmonic fit/covariance dimensions differ")
    result = np.zeros((2 * nt, 2 * nt))
    for energy in range(nt):
        jacobian = np.zeros((2 * nt, 2 * nr))
        for state, sign in enumerate((1, -1)):
            rows = slice(state * nr, (state + 1) * nr)
            for moment, factor in enumerate(
                (
                    luminosity[state, energy],
                    sign * luminosity[state, energy] * polarization[state, energy],
                )
            ):
                parameter = energy + moment * nt
                columns = slice(moment * nr, (moment + 1) * nr)
                jacobian[:, columns] += factor * (
                    np.outer(
                        fit.normal_inverse[:, parameter], fit.weighted_residual[rows]
                    )
                    - fit.estimator[:, rows] * fit.coefficients[parameter]
                )
        result += jacobian @ validate_covariance(cov[energy], size=2 * nr) @ jacobian.T
    return validate_covariance(result, size=2 * nt)


def weighted_harmonic_mc_covariance(fit, moment_covariance):
    """Propagate run-masked luminosity moments, jointly across beam states.

    Moment axes are truth energy, harmonic, concatenated observed states/cells.
    Each pair of moments is already a pair of columns of the design matrix.
    """
    cov = np.asarray(moment_covariance, dtype=float)
    nt = len(cov)
    nobs = fit.estimator.shape[1]
    if cov.shape != (nt, 2 * nobs, 2 * nobs) or fit.estimator.shape[0] != 2 * nt:
        raise ValueError("weighted harmonic fit/covariance dimensions differ")
    result = np.zeros((2 * nt, 2 * nt))
    for energy in range(nt):
        jacobian = np.concatenate(
            [
                np.outer(fit.normal_inverse[:, parameter], fit.weighted_residual)
                - fit.estimator * fit.coefficients[parameter]
                for parameter in (energy, nt + energy)
            ],
            axis=1,
        )
        result += (
            jacobian @ validate_covariance(cov[energy], size=2 * nobs) @ jacobian.T
        )
    return validate_covariance(result, size=2 * nt)
