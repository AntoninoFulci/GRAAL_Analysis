"""Raw-mass Gaussian candle: fixed 50% signal probability, never a data quantile."""

from dataclasses import dataclass, field
import json
import math

import numpy as np
from scipy.optimize import minimize

from graal_common.physics.channels import M_ETA, M_PI0


_RADIUS_SQUARED = 2. * math.log(2.)
_SHAPE_NAMES = ("eta_center_gev", "pi0_center_gev", "eta_sigma_gev", "pi0_sigma_gev", "correlation")
_PARAMETER_NAMES = _SHAPE_NAMES + ("signal_yield_in_window", "pedestal_yield_in_window")
_FIT_BOUNDS = dict(center_offset_half_widths=[-1., 1.], sigma_half_widths=[.04, 1.],
                   correlation=[-.95, .95], signal_fraction=[0., 1.])
_SHAPE_FIT_BOUNDS = np.array([_FIT_BOUNDS["center_offset_half_widths"]] * 2
                             + [np.log(_FIT_BOUNDS["sigma_half_widths"])] * 2
                             + [np.arctanh(_FIT_BOUNDS["correlation"])])


def _peak_at_boundary(shape):
    """Apply the optimizer-coordinate boundary margin to fits and saved audits."""
    distance = np.minimum(shape - _SHAPE_FIT_BOUNDS[:, 0], _SHAPE_FIT_BOUNDS[:, 1] - shape)
    return bool(np.any(distance < 1e-4))


def _mass_arrays(eta_mass, pi0_mass):
    eta, pi0 = np.asarray(eta_mass, dtype=float), np.asarray(pi0_mass, dtype=float)
    if eta.ndim != 1 or eta.shape != pi0.shape:
        raise ValueError("raw mass arrays must have the same one-dimensional shape")
    return eta, pi0


@dataclass(frozen=True)
class GaussianCandle:
    """An immutable ellipse with inclusive squared Mahalanobis radius 2 ln(2).

    The probability refers to the Gaussian component integrated over the whole
    mass plane. Neither the observed fraction nor background containment is 50%.
    Fit audit is stored as immutable JSON; ``to_dict`` returns an independent copy.
    """

    eta_center_gev: float
    pi0_center_gev: float
    eta_sigma_gev: float
    pi0_sigma_gev: float
    correlation: float
    fit_audit_json: str | None = field(default=None, repr=False)
    radius_squared: float = field(default=_RADIUS_SQUARED, init=False)

    def __post_init__(self):
        for name in _SHAPE_NAMES:
            value = getattr(self, name)
            if isinstance(value, (bool, str)) or not np.isscalar(value) or not np.isfinite(value):
                raise ValueError(f"{name} must be finite numeric")
            object.__setattr__(self, name, float(value))
        if self.eta_sigma_gev <= 0 or self.pi0_sigma_gev <= 0:
            raise ValueError("Gaussian sigmas must be positive")
        if abs(self.correlation) >= 1:
            raise ValueError("Gaussian correlation must lie strictly between -1 and 1")
        try:
            covariance = self.covariance_gev2
        except OverflowError as exc:
            raise ValueError("Gaussian covariance must be finite") from exc
        if not np.isfinite(covariance).all() or np.linalg.det(covariance) <= 0:
            raise ValueError("Gaussian covariance must be finite and positive definite")
        if self.fit_audit_json is not None:
            try:
                audit = json.loads(self.fit_audit_json)
                _validate_audit(audit, self)
                normalized = json.dumps(audit, allow_nan=False, sort_keys=True, separators=(",", ":"))
            except (TypeError, KeyError, json.JSONDecodeError) as exc:
                raise ValueError("invalid Gaussian fit audit") from exc
            object.__setattr__(self, "fit_audit_json", normalized)

    @property
    def covariance_gev2(self):
        cross = self.correlation * self.eta_sigma_gev * self.pi0_sigma_gev
        return np.array([[self.eta_sigma_gev ** 2, cross], [cross, self.pi0_sigma_gev ** 2]])

    @property
    def fit_window_gev(self):
        if self.fit_audit_json is None:
            return None
        return tuple(tuple(bounds) for bounds in json.loads(self.fit_audit_json)["fit_window_gev"])

    def mask(self, eta_mass, pi0_mass):
        eta, pi0 = _mass_arrays(eta_mass, pi0_mass)
        finite = np.isfinite(eta) & np.isfinite(pi0)
        result = np.zeros(eta.shape, dtype=bool)
        with np.errstate(over="ignore", invalid="ignore"):
            x = (eta[finite] - self.eta_center_gev) / self.eta_sigma_gev
            y = (pi0[finite] - self.pi0_center_gev) / self.pi0_sigma_gev
            # Cholesky form avoids cancellation for strongly correlated masses.
            distance = x * x + ((y - self.correlation * x) ** 2 / (1 - self.correlation ** 2))
        result[finite] = distance <= self.radius_squared + 64 * np.finfo(float).eps
        return result

    def to_dict(self):
        return dict(schema=1, axes=["eta_mass", "pi0_mass"], units="GeV", boundary="include",
                    radius_squared=self.radius_squared,
                    **{name: getattr(self, name) for name in _SHAPE_NAMES},
                    fit=None if self.fit_audit_json is None else json.loads(self.fit_audit_json))

    @classmethod
    def from_dict(cls, value):
        fields = {"schema", "axes", "units", "boundary", "radius_squared", "fit", *_SHAPE_NAMES}
        if not isinstance(value, dict) or set(value) != fields:
            raise ValueError(f"Gaussian definition requires exactly {sorted(fields)}")
        if type(value["schema"]) is not int or value["schema"] != 1:
            raise ValueError("unsupported Gaussian candle schema")
        if (value["axes"] != ["eta_mass", "pi0_mass"] or value["units"] != "GeV"
                or value["boundary"] != "include" or value["radius_squared"] != _RADIUS_SQUARED):
            raise ValueError("Gaussian candle requires raw masses in GeV and the inclusive 50% contour")
        try:
            audit = None if value["fit"] is None else json.dumps(value["fit"], allow_nan=False)
            return cls(*(value[name] for name in _SHAPE_NAMES), fit_audit_json=audit)
        except (TypeError, OverflowError) as exc:
            raise ValueError("invalid Gaussian definition") from exc


def _validate_audit(audit, candle):
    fields = {"fit_model", "method", "status", "optimizer_message", "fit_window_gev",
              "bins_per_axis", "quadrature_order", "input_count", "finite_count", "fit_count",
              "parameter_names", "parameters", "parameter_errors", "parameter_covariance",
              "covariance_method", "pedestal_at_boundary", "poisson_deviance", "fit_bounds"}
    if not isinstance(audit, dict) or set(audit) != fields:
        raise ValueError("invalid Gaussian fit audit fields")
    if (audit["fit_model"] != "correlated_gaussian_plus_constant"
            or audit["method"] != "binned_poisson_profile_total_yield"
            or audit["status"] != "converged" or audit["parameter_names"] != list(_PARAMETER_NAMES)
            or audit["covariance_method"] != "inverse_expected_poisson_information"):
        raise ValueError("unsupported Gaussian fit model or status")
    arrays = [np.asarray(audit[name]) for name in (
        "parameters", "parameter_errors", "parameter_covariance", "fit_window_gev")]
    if any(array.dtype.kind not in "if" for array in arrays):
        raise ValueError("Gaussian audit parameters must be numeric")
    params, errors, covariance, window = arrays
    if (params.shape != (7,) or errors.shape != (7,) or covariance.shape != (7, 7)
            or window.shape != (2, 2) or not np.isfinite(window).all()
            or not np.all(window[:, 0] < window[:, 1]) or not np.isfinite(params).all()
            or not np.isfinite(errors).all() or not np.isfinite(covariance).all()
            or not np.all(errors > 0) or not np.all(params[5:] >= 0)
            or not np.allclose(covariance, covariance.T, rtol=1e-10, atol=0)
            or not np.allclose(errors ** 2, np.diag(covariance), rtol=1e-10, atol=0)
            or not np.array_equal(params[:5], [getattr(candle, name) for name in _SHAPE_NAMES])):
        raise ValueError("invalid Gaussian fit parameters or covariance")
    try:
        np.linalg.cholesky(covariance)
    except np.linalg.LinAlgError as exc:
        raise ValueError("Gaussian fit covariance must be positive definite") from exc
    widths = np.diff(window, axis=1).ravel() / 2
    if (not np.allclose(window.mean(axis=1), [M_ETA, M_PI0], rtol=0, atol=1e-14)
            or not np.isclose(*widths, rtol=1e-12, atol=0)
            or audit["fit_bounds"] != _FIT_BOUNDS
            or audit["bins_per_axis"] != 40 or audit["quadrature_order"] != 6
            or type(audit["pedestal_at_boundary"]) is not bool
            or type(audit["poisson_deviance"]) not in (float, int)
            or audit["poisson_deviance"] < 0
            or not isinstance(audit["optimizer_message"], str)
            or not audit["optimizer_message"].strip()):
        raise ValueError("invalid Gaussian fit window or method metadata")
    for name in ("input_count", "finite_count", "fit_count", "bins_per_axis", "quadrature_order"):
        if type(audit[name]) is not int or audit[name] <= 0:
            raise ValueError("invalid Gaussian fit counts")
    if not audit["fit_count"] <= audit["finite_count"] <= audit["input_count"]:
        raise ValueError("inconsistent Gaussian fit counts")
    if not np.isclose(params[5:].sum(), audit["fit_count"], rtol=1e-12, atol=0):
        raise ValueError("inconsistent Gaussian fitted yield")
    shape = np.r_[(params[:2] - [M_ETA, M_PI0]) / widths,
                  np.log(params[2:4] / widths), np.arctanh(params[4])]
    if _peak_at_boundary(shape):
        raise ValueError("Gaussian fitted parameters violate fit bounds or boundary policy")
    fraction = params[5] / audit["fit_count"]
    if (audit["fit_count"] < 100 or fraction < .01
            or params[5] < 5 * errors[5] or np.any(errors[2:4] > .5 * params[2:4])):
        raise ValueError("Gaussian fit audit does not describe a sufficiently resolved peak")
    if audit["pedestal_at_boundary"] != bool(fraction >= 1 - 1e-6):
        raise ValueError("inconsistent Gaussian pedestal boundary status")
    # Also rejects NaN/Infinity anywhere in the nested audit.
    json.dumps(audit, allow_nan=False)


def fit_gaussian_candle(eta_mass, pi0_mass, *, half_width_gev=.05):
    """Fit a correlated Gaussian peak plus uniform pedestal to raw masses.

    Use a fixed nominal-mass ± half-width window and 40×40 Poisson bins,
    integrating each bin with 6×6 Gauss-Legendre quadrature. The signal density
    is normalized inside the window; its fitted widths define the *untruncated*
    Gaussian ellipse. Total expected yield is analytically profiled at the
    observed count. At least 100 in-window events and a resolved, >5-sigma peak
    are required. Peak shape boundaries or singular information fail explicitly.
    A zero pedestal is allowed; its reported Wald error is a local curvature
    scale, not a two-sided confidence interval at the physical boundary.
    """
    eta, pi0 = _mass_arrays(eta_mass, pi0_mass)
    if not np.isfinite(half_width_gev) or half_width_gev <= 0:
        raise ValueError("Gaussian fit half width must be finite and positive")
    finite = np.isfinite(eta) & np.isfinite(pi0)
    nominal = np.array([M_ETA, M_PI0])
    masses = (np.column_stack((eta[finite], pi0[finite])) - nominal) / half_width_gev
    masses = masses[np.all(np.abs(masses) <= 1, axis=1)]
    count = len(masses)
    if count < 100:
        raise ValueError("Gaussian fit requires at least 100 finite events in the fit window")
    if np.linalg.eigvalsh(np.cov(masses.T)).min() <= 1e-8:
        raise ValueError("Gaussian fit sample is degenerate")
    bins, order = 40, 6
    edges = np.linspace(-1., 1., bins + 1)
    observed = np.histogram2d(*masses.T, bins=(edges, edges))[0].ravel()
    nodes, weights = np.polynomial.legendre.leggauss(order)
    points = (edges[:-1, None] + edges[1:, None]) / 2 + nodes / bins
    x = points[:, None, :, None]
    y = points[None, :, None, :]
    integration_weights = weights[:, None] * weights[None, :] / bins ** 2

    def probabilities(shape):
        sx, sy = np.exp(shape[2:4])
        rho = np.tanh(shape[4])
        u, v = (x - shape[0]) / sx, (y - shape[1]) / sy
        density = np.exp(-.5 * (u * u + (v - rho * u) ** 2 / (1 - rho * rho)))
        integrated = np.sum(density * integration_weights, axis=(-2, -1)).ravel()
        return integrated / integrated.sum()

    uniform = np.full(bins * bins, 1. / bins ** 2)

    def objective(p):
        probability = p[5] * probabilities(p[:5]) + (1 - p[5]) * uniform
        return -np.dot(observed / count, np.log(np.maximum(probability, 1e-300)))

    bounds = [*_SHAPE_FIT_BOUNDS.tolist(), _FIT_BOUNDS["signal_fraction"]]
    median = np.median(masses, axis=0)
    scale = np.clip(np.std(masses, axis=0), .08, .6)
    starts = [np.r_[median, np.log(scale), 0., .7],
              np.r_[median, np.log(scale / 2), 0., .5]]
    fits = [minimize(objective, start, method="L-BFGS-B", bounds=bounds,
                     options={"ftol": 1e-13, "gtol": 1e-7, "maxiter": 1000, "maxls": 40})
            for start in starts]
    converged = [fit for fit in fits if fit.success and np.isfinite(fit.fun)]
    if not converged:
        raise ValueError("Gaussian mass fit did not converge")
    fit = min(converged, key=lambda item: item.fun)
    p = fit.x
    if _peak_at_boundary(p[:5]):
        raise ValueError("Gaussian mass fit reached a peak parameter boundary")
    if p[5] < .01:
        raise ValueError("Gaussian peak is not identifiable above pedestal")
    # Expected Poisson information for shape and two independently variable
    # yields. Differentiate in dimensionless coordinates for stable conditioning.
    signal = probabilities(p[:5])
    expected = count * (p[5] * signal + (1 - p[5]) * uniform)
    derivatives = []
    step = 1e-5
    for index in range(5):
        delta = np.zeros(5)
        delta[index] = step
        derivatives.append(count * p[5] * (probabilities(p[:5] + delta)
                                          - probabilities(p[:5] - delta)) / (2 * step))
    jacobian = np.column_stack([*derivatives, count * signal, count * uniform])
    information = jacobian.T @ (jacobian / np.maximum(expected[:, None], 1e-300))
    information_scale = np.sqrt(np.diag(information))
    scaled_information = information / np.outer(information_scale, information_scale)
    if not np.isfinite(scaled_information).all() or np.linalg.cond(scaled_information) > 1e10:
        raise ValueError("Gaussian fit information is singular or unidentifiable")
    sx, sy = np.exp(p[2:4]) * half_width_gev
    rho = np.tanh(p[4])
    transform = np.array([half_width_gev, half_width_gev, sx, sy, 1 - rho * rho, count, count])
    transform = transform / information_scale
    covariance = np.linalg.inv(scaled_information) * np.outer(transform, transform)
    covariance = (covariance + covariance.T) / 2
    try:
        np.linalg.cholesky(covariance)
    except np.linalg.LinAlgError as exc:
        raise ValueError("Gaussian fit covariance is not positive definite") from exc
    errors = np.sqrt(np.diag(covariance))
    if (not np.isfinite(errors).all()
            or count * p[5] < 5 * errors[5] or errors[2] > .5 * sx or errors[3] > .5 * sy):
        raise ValueError("Gaussian peak is insufficiently resolved above pedestal")
    centers = nominal + half_width_gev * p[:2]
    parameters = [*centers, sx, sy, rho, count * p[5], count * (1 - p[5])]
    occupied = observed > 0
    deviance = 2 * (np.sum(expected - observed)
                    + np.sum(observed[occupied] * np.log(observed[occupied] / expected[occupied])))
    audit = dict(fit_model="correlated_gaussian_plus_constant",
                 method="binned_poisson_profile_total_yield", status="converged",
                 optimizer_message=str(fit.message),
                 fit_window_gev=np.column_stack((nominal - half_width_gev, nominal + half_width_gev)).tolist(),
                 bins_per_axis=bins, quadrature_order=order, input_count=len(eta),
                 finite_count=int(finite.sum()), fit_count=count,
                 parameter_names=list(_PARAMETER_NAMES), parameters=list(map(float, parameters)),
                 parameter_errors=errors.tolist(), parameter_covariance=covariance.tolist(),
                 covariance_method="inverse_expected_poisson_information", pedestal_at_boundary=bool(p[5] >= 1 - 1e-6),
                 poisson_deviance=float(deviance),
                 fit_bounds=_FIT_BOUNDS)
    return GaussianCandle(*parameters[:5], fit_audit_json=json.dumps(audit, allow_nan=False))
