"""Conditional publication-bin polarized moments for Ajaka Figure 4."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Mapping

import numpy as np
from numpy.typing import NDArray

from .beam_asymmetry import _HORIZONTAL, _VERTICAL
from .constants import GEV2_TO_MICROBARN
from .kinematics import invariant_mass, s_from_lab_photon_energy
from .phase_space import SobolConfig, sample_three_body_mass_window


PAIR_DAUGHTERS = {"p_pi0": (2, 1), "p_eta": (2, 0), "eta_pi0": (0, 1)}


def project_polarized_moments(phi, vertical, horizontal, weights) -> tuple[float, float]:
    phi, vertical, horizontal, weights = (
        np.asarray(value, dtype=np.float64) for value in (phi, vertical, horizontal, weights))
    if (phi.ndim != 1 or any(value.shape != phi.shape for value in
                             (vertical, horizontal, weights))
            or any(not np.all(np.isfinite(value)) for value in
                   (phi, vertical, horizontal, weights))
            or np.any(vertical < 0) or np.any(horizontal < 0) or np.any(weights < 0)):
        raise ValueError("polarized moments require matching finite nonnegative weights")
    numerator = float(np.sum(2*np.cos(2*phi)*(vertical-horizontal)*weights))
    denominator = float(np.sum((vertical+horizontal)*weights))
    return numerator, denominator


def project_azimuth_averaged_moments(
        phi, vertical_amplitude, horizontal_amplitude, weights) -> tuple[float, float]:
    """Integrate the redundant global rotation exactly using H/V interference."""
    angle = np.asarray(phi, dtype=np.float64)
    vertical = np.asarray(vertical_amplitude, dtype=np.complex128)
    horizontal = np.asarray(horizontal_amplitude, dtype=np.complex128)
    measure = np.asarray(weights, dtype=np.float64)
    if (angle.ndim != 1 or measure.shape != angle.shape
            or vertical.shape != (len(angle), 2, 2)
            or horizontal.shape != vertical.shape):
        raise ValueError("azimuth average requires matching (N,2,2) amplitudes")
    if (not np.all(np.isfinite(angle)) or not np.all(np.isfinite(measure))
            or np.any(measure < 0) or not np.all(np.isfinite(vertical))
            or not np.all(np.isfinite(horizontal))):
        raise ValueError("azimuth average requires finite amplitudes and measure")
    v = np.sum(abs(vertical)**2, axis=(1, 2))/2
    h = np.sum(abs(horizontal)**2, axis=(1, 2))/2
    interference = np.real(np.sum(np.conj(horizontal)*vertical, axis=(1, 2)))/2
    numerator = float(np.sum(((v-h)*np.cos(2*angle)
                              -2*interference*np.sin(2*angle))*measure))
    denominator = float(np.sum((v+h)*measure))
    return numerator, denominator


@dataclass(frozen=True)
class Figure4BinMoment:
    pair: str
    energy_range_gev: tuple[float, float]
    mass_range_gev: tuple[float, float]
    accessible_energy_gev: tuple[float, float] | None
    accessible_mass_gev: tuple[float, float] | None
    energy_nodes_gev: NDArray[np.float64]
    numerator: float
    denominator: float
    vertical_normalization: float
    horizontal_normalization: float
    mass_numerator: float
    source_used_denominator: float
    status: str
    reason: str | None = None

    @property
    def sigma(self) -> float:
        return self.numerator/self.denominator if self.denominator > 0 else float("nan")

    @property
    def weighted_mass_gev(self) -> float:
        return self.mass_numerator/self.denominator if self.denominator > 0 else float("nan")

    @property
    def source_used_extension_fraction(self) -> float:
        return self.source_used_denominator/self.denominator if self.denominator > 0 else float("nan")


@dataclass(frozen=True)
class Figure4CertifiedBin:
    moment: Figure4BinMoment
    status: str
    reason: tuple[str, ...]
    numerical_error_bound: float
    error_components: dict[str, float]

    @property
    def sigma(self) -> float:
        return self.moment.sigma


@dataclass(frozen=True)
class Figure4PanelResult:
    pair: str
    energy_range_gev: tuple[float, float]
    mass_edges_gev: NDArray[np.float64]
    bins: tuple[Figure4CertifiedBin, ...]
    covariance: NDArray[np.float64]
    energy_order: int
    sobol_power: int
    replica_seeds: tuple[int, ...]
    mode: str
    denominator_replica_se: float = float("nan")
    vertical_replica_se: float = float("nan")
    horizontal_replica_se: float = float("nan")


def covariance_from_replicates(sigma_by_replica: NDArray[np.float64]) -> NDArray[np.float64]:
    """Covariance of independent replica means, preserving cross-bin terms."""
    values = np.asarray(sigma_by_replica, dtype=np.float64)
    if (values.ndim != 2 or values.shape[0] < 8 or values.shape[1] < 1
            or not np.all(np.isfinite(values))):
        raise ValueError("covariance requires at least eight complete finite replicas")
    return np.atleast_2d(np.cov(values, rowvar=False, ddof=1))/len(values)


def convergence_reasons(*, sigma: float, energy_delta_sigma: float,
                        energy_vertical_relative: float, energy_horizontal_relative: float,
                        sobol_delta_sigma: float, sobol_total_relative: float,
                        sobol_vertical_relative: float, sobol_horizontal_relative: float,
                        replica_se: float, grid_direct_delta_sigma: float,
                        populated: bool) -> tuple[str, ...]:
    """Apply fixed design gates without treating absent checks as passing."""
    checks = {
        "energy_sigma": (energy_delta_sigma, .005, False),
        "energy_vertical": (energy_vertical_relative, .01, True),
        "energy_horizontal": (energy_horizontal_relative, .01, True),
        "sobol_sigma": (sobol_delta_sigma, .01, False),
        "sobol_total": (sobol_total_relative, .01, True),
        "sobol_vertical": (sobol_vertical_relative, .03, True),
        "sobol_horizontal": (sobol_horizontal_relative, .03, True),
        "replica_se": (replica_se, .01, False),
        "grid_direct_sigma": (grid_direct_delta_sigma, .002, False),
    }
    reasons = []
    if not np.isfinite(sigma) or abs(sigma) > 1+1e-12:
        reasons.append("sigma_range")
    for name, (value, limit, strict) in checks.items():
        if name in ("sobol_vertical", "sobol_horizontal") and not populated:
            continue
        if not np.isfinite(value):
            reasons.append(name+"_not_completed")
        elif (abs(value) >= limit if strict else abs(value) > limit):
            reasons.append(name)
    return tuple(reasons)


def predict_figure4_bin(model, pair: str, energy_range_gev: tuple[float, float],
                        mass_range_gev: tuple[float, float], *, energy_order: int,
                        sobol: SobolConfig) -> Figure4BinMoment:
    if pair not in PAIR_DAUGHTERS:
        raise ValueError(f"unknown pair: {pair}")
    try:
        e_low, e_high = map(float, energy_range_gev)
        m_low, m_high = map(float, mass_range_gev)
    except (TypeError, ValueError) as exc:
        raise ValueError("energy and mass ranges require two finite bounds") from exc
    if (not all(np.isfinite(v) for v in (e_low, e_high, m_low, m_high))
            or e_low <= 0 or e_low >= e_high or m_low >= m_high):
        raise ValueError("energy and mass ranges must increase")
    if isinstance(energy_order, bool) or not isinstance(energy_order, int) or energy_order < 1:
        raise ValueError("energy_order must be a positive integer")
    if not isinstance(sobol, SobolConfig):
        raise ValueError("sobol requires SobolConfig")
    masses = model.masses
    proton = model.parameters.proton_mass_gev
    daughters = PAIR_DAUGHTERS[pair]
    spectator = next(index for index in range(3) if index not in daughters)
    mass_low = max(m_low, masses[daughters[0]]+masses[daughters[1]])
    mass_high = min(m_high, np.sqrt(s_from_lab_photon_energy(e_high, proton))-masses[spectator])
    onset = ((mass_low+masses[spectator])**2-proton**2)/(2*proton)
    energy_low = max(e_low, onset)
    def masked(status, reason):
        return Figure4BinMoment(pair, (e_low, e_high), (m_low, m_high), None, None,
                                np.empty(0), 0., 0., 0., 0., 0., 0., status, reason)
    if mass_low >= mass_high or energy_low >= e_high:
        return masked("masked_kinematic", "no accessible energy-mass intersection")

    nodes, legendre_weights = np.polynomial.legendre.leggauss(energy_order)
    energies = (energy_low+e_high)/2 + (e_high-energy_low)*nodes/2
    energy_weights = legendre_weights*(e_high-energy_low)/(2*(e_high-e_low))
    numerator = denominator = vertical_sum = horizontal_sum = mass_sum = extension_sum = 0.
    for energy, energy_weight in zip(energies, energy_weights):
        s = s_from_lab_photon_energy(float(energy), proton)
        sample = sample_three_body_mass_window(float(np.sqrt(s)), masses, daughters,
                                                (m_low, m_high), sobol,
                                                reduce_global_azimuth=callable(
                                                    getattr(model, "amplitude", None)))
        if sample is None:
            continue
        eta_p_mass = invariant_mass(sample.momenta[:, 0]+sample.momenta[:, 2])
        if np.any(eta_p_mass > 1.80):
            return masked("masked_unsupported_domain", "M(eta p) exceeds 1.80 GeV")
        momentum = sample.momenta[:, daughters[0]]+sample.momenta[:, daughters[1]]
        phi = np.arctan2(momentum[:, 2], momentum[:, 1])
        mass = invariant_mass(momentum)
        matrices = None
        if callable(getattr(model, "amplitude", None)):
            matrices = tuple(np.asarray(model.amplitude(sample, epsilon), dtype=np.complex128)
                             for epsilon in (_VERTICAL, _HORIZONTAL))
            if any(matrix.shape != (len(mass), 2, 2) or not np.all(np.isfinite(matrix))
                   for matrix in matrices):
                raise ValueError(f"invalid polarized amplitude at E_gamma={energy:.12g} GeV")
            vertical, horizontal = (np.sum(abs(matrix)**2, axis=(1, 2))/2
                                    for matrix in matrices)
        else:
            vertical, horizontal = (np.asarray(model.polarized_matrix_element_squared(sample, epsilon),
                                                    dtype=np.float64) for epsilon in (_VERTICAL, _HORIZONTAL))
        if (vertical.shape != mass.shape or horizontal.shape != mass.shape
                or not np.all(np.isfinite(vertical)) or not np.all(np.isfinite(horizontal))
                or np.any(vertical < 0) or np.any(horizontal < 0)):
            raise ValueError(f"invalid polarized weight at E_gamma={energy:.12g} GeV")
        normalization = (GEV2_TO_MICROBARN*4*proton**2
                         /(2*(s-proton**2)*len(mass)))
        weights = energy_weight*normalization*sample.weights_gev2
        node_n, node_d = (project_azimuth_averaged_moments(
            phi, matrices[0], matrices[1], weights) if matrices is not None else
            project_polarized_moments(phi, vertical, horizontal, weights))
        if matrices is not None:
            # The same exact global-angle average makes H and V
            # normalizations equal, while their cos(2phi) contrast survives.
            node_v = node_h = node_d/2
        else:
            node_v = float(np.sum(vertical*weights))
            node_h = float(np.sum(horizontal*weights))
        numerator += node_n
        denominator += node_d
        vertical_sum += node_v
        horizontal_sum += node_h
        mass_sum += float(np.sum(mass*(vertical+horizontal)*weights))
        extension_sum += float(np.sum((vertical+horizontal)*weights*(eta_p_mass > 1.60)))
    if denominator <= 0 or not np.isfinite(denominator):
        return masked("masked_nonconverged", "zero or nonfinite polarized normalization")
    return Figure4BinMoment(pair, (e_low, e_high), (m_low, m_high),
                            (energy_low, e_high), (mass_low, mass_high), energies,
                            numerator, denominator, vertical_sum, horizontal_sum,
                            mass_sum, extension_sum, "calculated")


def _panel_edges(edges) -> NDArray[np.float64]:
    value = np.asarray(edges, dtype=np.float64)
    if (value.ndim != 1 or len(value) < 2 or not np.all(np.isfinite(value))
            or np.any(np.diff(value) <= 0)):
        raise ValueError("mass edges must be finite and increasing")
    return value


def _failure_moment(model, pair, energy_range, mass_range, reason):
    daughters = PAIR_DAUGHTERS[pair]
    spectator = next(index for index in range(3) if index not in daughters)
    proton = model.parameters.proton_mass_gev
    mass_low = max(mass_range[0], sum(model.masses[index] for index in daughters))
    mass_high = min(mass_range[1],
                    np.sqrt(s_from_lab_photon_energy(energy_range[1], proton))-model.masses[spectator])
    onset = ((mass_low+model.masses[spectator])**2-proton**2)/(2*proton)
    energy_low = max(energy_range[0], onset)
    accessible_mass = (mass_low, mass_high) if mass_low < mass_high else None
    accessible_energy = (energy_low, energy_range[1]) if energy_low < energy_range[1] else None
    return Figure4BinMoment(pair, tuple(energy_range), tuple(mass_range),
                            accessible_energy, accessible_mass,
                            np.empty(0), 0., 0., 0., 0., 0., 0.,
                            "masked_nonconverged", reason)


def _safe_predict(model, pair, energy_range, mass_range, energy_order, sobol):
    try:
        return predict_figure4_bin(model, pair, energy_range, mass_range,
                                   energy_order=energy_order, sobol=sobol)
    except ValueError as exc:
        return _failure_moment(model, pair, energy_range, mass_range,
                               f"inner_quadrature_or_input: {exc}")


def _validate_panel_input(pair, energy_range):
    if pair not in PAIR_DAUGHTERS:
        raise ValueError(f"unknown pair: {pair}")
    if (len(energy_range) != 2 or not np.all(np.isfinite(energy_range))
            or energy_range[0] <= 0 or energy_range[0] >= energy_range[1]):
        raise ValueError("energy range must have finite positive increasing bounds")


def integrate_figure4_panel(model, pair: str, energy_range_gev: tuple[float, float],
                            mass_edges_gev, *, energy_order: int,
                            sobol: SobolConfig) -> Figure4PanelResult:
    """Calculate raw moments; accessible bins remain uncertified masks."""
    _validate_panel_input(pair, energy_range_gev)
    edges = _panel_edges(mass_edges_gev)
    bins = []
    for lower, upper in zip(edges[:-1], edges[1:]):
        moment = _safe_predict(model, pair, energy_range_gev, (float(lower), float(upper)),
                               energy_order, sobol)
        status = moment.status if moment.status != "calculated" else "masked_nonconverged"
        reason = ((moment.reason,) if moment.reason else ("not_completed",))
        bins.append(Figure4CertifiedBin(moment, status, reason, float("nan"), {}))
    return Figure4PanelResult(pair, tuple(energy_range_gev), edges.copy(),
        tuple(bins), np.full((len(bins), len(bins)), np.nan), energy_order,
        sobol.power, (), "grid" if getattr(model, "strong_grid", None) is not None else "direct")


def _relative_difference(left: float, right: float) -> float:
    return abs(left-right)/max(abs(left), abs(right), 1e-30)


def _replica_mean(moments: tuple[Figure4BinMoment, ...]) -> Figure4BinMoment:
    first = moments[0]
    names = ("numerator", "denominator", "vertical_normalization",
             "horizontal_normalization", "mass_numerator", "source_used_denominator")
    averages = {name: float(np.mean([getattr(moment, name) for moment in moments]))
                for name in names}
    return replace(first, **averages)


def certify_figure4_panel(model, pair: str, energy_range_gev: tuple[float, float],
                          mass_edges_gev, *, energy_order: int, sobol_power: int,
                          replica_seeds: tuple[int, ...] = tuple(range(2026, 2034))) -> Figure4PanelResult:
    """Apply every fixed numerical gate to each conditional nominal bin."""
    if (not isinstance(replica_seeds, tuple) or len(replica_seeds) < 8
            or len(set(replica_seeds)) != len(replica_seeds)
            or any(type(seed) is not int or seed < 0 for seed in replica_seeds)):
        raise ValueError("certification requires at least eight distinct nonnegative replica seeds")
    _validate_panel_input(pair, energy_range_gev)
    edges = _panel_edges(mass_edges_gev)
    base_config = SobolConfig(sobol_power)
    finer_config = SobolConfig(sobol_power+1)
    raw = []
    for lower, upper in zip(edges[:-1], edges[1:]):
        interval = (float(lower), float(upper))
        base = _safe_predict(model, pair, energy_range_gev, interval, energy_order, base_config)
        if base.status != "calculated":
            raw.append((base, None, None, (), None))
            continue
        energy = _safe_predict(model, pair, energy_range_gev, interval,
                               2*energy_order, base_config)
        sobol = _safe_predict(model, pair, energy_range_gev, interval,
                              energy_order, finer_config)
        replicas = tuple(_safe_predict(model, pair, energy_range_gev, interval,
            energy_order, SobolConfig(sobol_power, scramble=True, seed=seed))
            for seed in replica_seeds)
        if getattr(model, "strong_grid", None) is not None:
            direct_model = replace(model, strong_grid=None)
            direct = _safe_predict(direct_model, pair, energy_range_gev,
                                   interval, energy_order, base_config)
        else:
            direct = base
        raw.append((base, energy, sobol, replicas, direct))

    covariance = np.full((len(raw), len(raw)), np.nan)
    valid = [index for index, (base, energy, sobol, replicas, direct) in enumerate(raw)
             if (base.status == energy.status == sobol.status == direct.status == "calculated"
                 and all(replica.status == "calculated" for replica in replicas))]
    if valid:
        replica_sigmas = np.array([[raw[index][3][replica].sigma for index in valid]
                                   for replica in range(len(replica_seeds))])
        covariance[np.ix_(valid, valid)] = covariance_from_replicates(replica_sigmas)

    total = sum(item[0].denominator for item in raw if item[0].status == "calculated")
    certified = []
    for index, (base, energy, sobol, replicas, direct) in enumerate(raw):
        if base.status == "masked_kinematic":
            certified.append(Figure4CertifiedBin(base, base.status,
                (base.reason or "kinematic",), float("nan"), {}))
            continue
        if index not in valid:
            failures = [moment.reason for moment in (base, energy, sobol, direct, *replicas)
                        if moment is not None and moment.status != "calculated"]
            certified.append(Figure4CertifiedBin(base, "masked_nonconverged",
                tuple(failures) or ("not_completed",), float("nan"), {}))
            continue
        mean = _replica_mean(replicas)
        se = float(np.sqrt(max(covariance[index, index], 0.)))
        deltas = {
            "energy_delta_sigma": abs(energy.sigma-base.sigma),
            "energy_vertical_relative": _relative_difference(
                energy.vertical_normalization, base.vertical_normalization),
            "energy_horizontal_relative": _relative_difference(
                energy.horizontal_normalization, base.horizontal_normalization),
            "sobol_delta_sigma": abs(sobol.sigma-base.sigma),
            "sobol_total_relative": _relative_difference(
                sobol.denominator, base.denominator),
            "sobol_vertical_relative": _relative_difference(
                sobol.vertical_normalization, base.vertical_normalization),
            "sobol_horizontal_relative": _relative_difference(
                sobol.horizontal_normalization, base.horizontal_normalization),
            "replica_se": se,
            "grid_direct_delta_sigma": abs(direct.sigma-base.sigma),
        }
        reasons = convergence_reasons(sigma=mean.sigma,
            populated=base.denominator >= 1e-4*total, **deltas)
        error = max(se, deltas["energy_delta_sigma"],
                    deltas["sobol_delta_sigma"], deltas["grid_direct_delta_sigma"])
        certified.append(Figure4CertifiedBin(mean,
            "masked_nonconverged" if reasons else "calculated", reasons,
            error, deltas))
    accessible = [index for index, (base, _, _, _, _) in enumerate(raw)
                  if base.status != "masked_kinematic"]
    norm_errors = [float("nan")]*3
    if accessible and all(index in valid for index in accessible):
        for k, field in enumerate(("denominator", "vertical_normalization",
                                   "horizontal_normalization")):
            totals = [sum(getattr(raw[index][3][replica], field)
                          for index in accessible)
                      for replica in range(len(replica_seeds))]
            norm_errors[k] = float(np.std(totals, ddof=1)/np.sqrt(len(totals)))
    return Figure4PanelResult(pair, tuple(energy_range_gev), edges.copy(),
        tuple(certified), covariance, energy_order, sobol_power, replica_seeds,
        "grid" if getattr(model, "strong_grid", None) is not None else "direct",
        *norm_errors)


def apply_pair_total_gate(
        panels: Mapping[tuple[int, str], Figure4PanelResult]
) -> dict[tuple[int, str], Figure4PanelResult]:
    """Require three pair projections to give the same polarized totals."""
    checked = dict(panels)
    pairs = ("p_pi0", "p_eta", "eta_pi0")
    for energy in range(4):
        keys = [(energy, pair) for pair in pairs]
        if any(key not in checked for key in keys):
            continue
        group = [checked[key] for key in keys]
        if any(any(item.status not in ("calculated", "masked_kinematic")
                   for item in panel.bins) for panel in group):
            continue
        mismatch = False
        for field, se_field in (("denominator", "denominator_replica_se"),
                                ("vertical_normalization", "vertical_replica_se"),
                                ("horizontal_normalization", "horizontal_replica_se")):
            totals = [sum(getattr(item.moment, field) for item in panel.bins
                          if item.status == "calculated") for panel in group]
            errors = [getattr(panel, se_field) for panel in group]
            for i in range(3):
                for j in range(i+1, 3):
                    combined_se = (np.hypot(errors[i], errors[j])
                                   if np.isfinite(errors[i]) and np.isfinite(errors[j]) else 0.)
                    if abs(totals[i]-totals[j]) > max(.01*max(totals[i], totals[j]),
                                                       3*combined_se):
                        mismatch = True
        if mismatch:
            for key, panel in zip(keys, group):
                bins = tuple(replace(item, status="masked_nonconverged",
                            reason=item.reason+("pair_total_mismatch",))
                             if item.status == "calculated" else item
                             for item in panel.bins)
                checked[key] = replace(panel, bins=bins)
    return checked
