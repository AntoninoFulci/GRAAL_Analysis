"""Bin integration of exact Delta-EM interference matrices."""

from __future__ import annotations

from dataclasses import dataclass, field, replace

import numpy as np
from numpy.typing import NDArray

from .beam_asymmetry import _HORIZONTAL, _VERTICAL, fit_binned_asymmetry
from .constants import GEV2_TO_MICROBARN
from .figure4_integration import PAIR_DAUGHTERS, convergence_reasons
from .kinematics import invariant_mass, s_from_lab_photon_energy
from .models.delta_em_basis import delta_em_event_basis
from .phase_space import SobolConfig, sample_three_body_mass_window
from .photon_flux import FluxSpectrum, group_flux_by_energy
from .quadratic_moments import QuadraticMoments, azimuth_state_moments, quadratic_moments


@dataclass(frozen=True)
class BinPrediction:
    numerator: float
    denominator: float
    intrinsic_sigma: float
    ratio_sigma: float | None
    energy_rule: str

    @property
    def sigma(self) -> float:
        return self.intrinsic_sigma if self.energy_rule == "uniform" else float(self.ratio_sigma)


@dataclass(frozen=True)
class BasisBinMoment:
    pair: str
    energy_range_gev: tuple[float, float]
    mass_range_gev: tuple[float, float]
    energy_rule: str
    numerator: NDArray[np.complex128]
    denominator: NDArray[np.complex128]
    state_phi: NDArray[np.complex128] | None
    flux_vertical: float | None
    flux_horizontal: float | None
    polarization_vertical: float | None
    polarization_horizontal: float | None
    source_used_denominator: NDArray[np.complex128]
    energy_nodes_gev: NDArray[np.float64]
    status: str
    reason: str | None = None
    model_fingerprint: str | None = None
    anchor_g1: float | None = None
    anchor_g2: float | None = None
    proton_mass_gev: float | None = None
    mass_numerator: NDArray[np.complex128] | None = None
    accessible_energy_gev: tuple[float, float] | None = None
    accessible_mass_gev: tuple[float, float] | None = None
    vertical_normalization: NDArray[np.complex128] | None = None
    horizontal_normalization: NDArray[np.complex128] | None = None

    def polarized_normalizations(self, coefficients) -> tuple[float, float]:
        if self.status != "calculated" or self.vertical_normalization is None \
                or self.horizontal_normalization is None:
            raise ValueError("polarized normalizations unavailable")
        c = np.asarray(coefficients, dtype=np.float64)
        if c.shape != (3,) or not np.isfinite(c).all():
            raise ValueError("coefficients must be finite three-vector")
        return (float(np.real(c @ self.vertical_normalization @ c)),
                float(np.real(c @ self.horizontal_normalization @ c)))

    def weighted_mass_gev(self, coefficients) -> float:
        denominator = self.evaluate(coefficients).denominator
        if self.mass_numerator is None:
            raise ValueError("mass numerator unavailable")
        c = np.asarray(coefficients, dtype=np.float64)
        result = float(np.real(c @ self.mass_numerator @ c)/denominator)
        if not np.isfinite(result):
            raise ValueError("weighted mass must be finite")
        return result

    def source_used_extension_fraction(self, coefficients) -> float:
        denominator = self.evaluate(coefficients).denominator
        c = np.asarray(coefficients, dtype=np.float64)
        fraction = float(np.real(c @ self.source_used_denominator @ c)/denominator)
        if not np.isfinite(fraction) or not -1e-12 <= fraction <= 1+1e-12:
            raise ValueError("source-used denominator fraction outside [0,1]")
        return float(np.clip(fraction, 0., 1.))

    def evaluate(self, coefficients) -> BinPrediction:
        if self.status != "calculated":
            raise ValueError(f"cannot evaluate {self.status} basis bin: {self.reason}")
        n, d, intrinsic = QuadraticMoments(self.numerator, self.denominator).evaluate(coefficients)
        ratio = None
        if self.energy_rule == "native_flux":
            c = np.asarray(coefficients, dtype=np.float64)
            counts = np.real(np.einsum("a,spab,b->sp", c, self.state_phi, c))
            if not np.isfinite(counts).all() or np.any(counts < -1e-12):
                raise ValueError("native expected counts must be finite and nonnegative")
            counts = np.maximum(counts, 0.)
            ratio = fit_binned_asymmetry(counts[0], counts[1], self.flux_vertical,
                                         self.flux_horizontal, self.polarization_vertical,
                                         self.polarization_horizontal,
                                         np.linspace(0., 2*np.pi, 13))
        return BinPrediction(n, d, intrinsic, ratio, self.energy_rule)


@dataclass(frozen=True)
class BasisBinCertificate:
    moment: BasisBinMoment
    status: str
    reason: tuple[str, ...]
    numerical_error_bound: float
    matrix_covariance: NDArray[np.float64] | None
    checks: tuple[BasisBinMoment, ...]
    replica_count: int
    fit_precision_limit: float | None
    reference_deltas: dict[str, dict[str, float]] = field(default_factory=dict)

    def predict(self, coefficients) -> BinPrediction:
        if self.status != "calculated":
            raise ValueError(f"uncertified basis bin: {self.reason}")
        estimate = self.moment.evaluate(coefficients)
        bound = _prediction_bound(estimate, self.checks, self.replica_count, coefficients)
        limit = self.fit_precision_limit if self.fit_precision_limit is not None else .01
        if not np.isfinite(bound) or bound > limit:
            raise ValueError(f"basis prediction numerical error {bound} exceeds {limit}")
        return estimate


def _prediction_bound(estimate, checks, replica_count, coefficients) -> float:
    base, energy, sobol, direct, *replicas = checks
    values = [item.evaluate(coefficients).sigma for item in checks]
    replica_values = np.asarray(values[4:], dtype=np.float64)
    replica_se = float(np.std(replica_values, ddof=1)/np.sqrt(replica_count))
    return max(replica_se, abs(values[1]-values[0]), abs(values[2]-values[0]),
               abs(values[3]-values[0]), abs(estimate.sigma-values[0]))


def _matrix_vector(moment: BasisBinMoment) -> NDArray[np.float64]:
    parts = [moment.numerator.ravel(), moment.denominator.ravel()]
    if moment.vertical_normalization is not None:
        parts.extend((moment.vertical_normalization.ravel(),
                      moment.horizontal_normalization.ravel()))
    if moment.mass_numerator is not None:
        parts.append(moment.mass_numerator.ravel())
    if moment.state_phi is not None:
        parts.append(moment.state_phi.ravel())
    values = np.concatenate(parts)
    return np.concatenate((values.real, values.imag))


def _relative(left: float, right: float) -> float:
    return abs(left-right)/max(abs(left), abs(right), 1e-30)


def _state_norm(moment: BasisBinMoment, coefficients) -> tuple[float, float]:
    if moment.state_phi is None:
        return moment.polarized_normalizations(coefficients)
    c = np.asarray(coefficients, dtype=np.float64)
    counts = np.real(np.einsum("a,spab,b->sp", c, moment.state_phi, c))
    return (float(np.sum(counts[0])/moment.flux_vertical),
            float(np.sum(counts[1])/moment.flux_horizontal))


def certify_basis_bin(model, pair: str, energy_range_gev: tuple[float, float],
                      mass_range_gev: tuple[float, float], *, energy_rule: str,
                      energy_order: int, sobol_power: int,
                      replica_seeds: tuple[int, ...],
                      flux_spectrum: FluxSpectrum | None = None,
                      data_stat_error: float | None = None) -> BasisBinCertificate:
    """Precompute fixed checks, then gate sourced and off-source contractions."""
    if (not isinstance(replica_seeds, tuple) or len(replica_seeds) < 8
            or len(set(replica_seeds)) != len(replica_seeds)
            or any(type(seed) is not int or seed < 0 for seed in replica_seeds)):
        raise ValueError("certification requires eight distinct nonnegative replica seeds")
    if energy_rule == "native_flux":
        if data_stat_error is None or not np.isfinite(data_stat_error) or data_stat_error <= 0:
            raise ValueError("native certification requires positive data_stat_error")
        precision_limit = min(.01, .2*data_stat_error)
    else:
        precision_limit = None
    def integrate(order: int, sobol: SobolConfig, candidate=model):
        return integrate_basis_bin(candidate, pair, energy_range_gev, mass_range_gev,
                                   energy_rule=energy_rule, energy_order=order,
                                   sobol=sobol, flux_spectrum=flux_spectrum)
    base = integrate(energy_order, SobolConfig(sobol_power))
    if base.status != "calculated":
        return BasisBinCertificate(base, base.status, (base.reason or base.status,),
                                   float("nan"), None, (), 0, precision_limit)
    energy = integrate(2*energy_order, SobolConfig(sobol_power))
    sobol = integrate(energy_order, SobolConfig(sobol_power+1))
    replicas = tuple(integrate(energy_order, SobolConfig(sobol_power, scramble=True, seed=seed))
                     for seed in replica_seeds)
    direct_model = replace(model, strong_grid=None) if getattr(model, "strong_grid", None) is not None else model
    direct = integrate(energy_order, SobolConfig(sobol_power), direct_model) if direct_model is not model else base
    checks = (base, energy, sobol, direct, *replicas)
    failures = tuple(item.reason or item.status for item in checks if item.status != "calculated")
    if any(item.model_fingerprint != base.model_fingerprint for item in (energy, sobol, *replicas)):
        failures += ("model_fingerprint",)
    if failures:
        return BasisBinCertificate(base, "masked_nonconverged", failures,
                                   float("nan"), None, checks, len(replicas), precision_limit)
    replica_vectors = np.stack([_matrix_vector(item) for item in replicas])
    covariance = np.atleast_2d(np.cov(replica_vectors, rowvar=False, ddof=1))/len(replicas)
    covariance.setflags(write=False)
    mean = replace(base,
                   numerator=np.mean([item.numerator for item in replicas], axis=0),
                   denominator=np.mean([item.denominator for item in replicas], axis=0),
                   vertical_normalization=np.mean([item.vertical_normalization for item in replicas], axis=0),
                   horizontal_normalization=np.mean([item.horizontal_normalization for item in replicas], axis=0),
                   mass_numerator=np.mean([item.mass_numerator for item in replicas], axis=0),
                   source_used_denominator=np.mean([item.source_used_denominator for item in replicas], axis=0),
                   state_phi=(np.mean([item.state_phi for item in replicas], axis=0)
                              if base.state_phi is not None else None))
    for matrix in (mean.numerator, mean.denominator, mean.vertical_normalization,
                   mean.horizontal_normalization, mean.mass_numerator,
                   mean.source_used_denominator, mean.state_phi):
        if matrix is not None:
            matrix.setflags(write=False)
    reasons = []
    worst = 0.
    reference_deltas = {}
    for label, coefficients in (("source", (1., 0., 0.)),
                                ("plus", (1., .04, -.03)),
                                ("minus", (1., -.06, .05))):
        prediction = mean.evaluate(coefficients)
        b, e, s, d = (item.evaluate(coefficients) for item in checks[:4])
        reference_deltas[label] = {
            f"{name}_{quantity}": float(getattr(candidate, quantity)-getattr(b, quantity))
            for name, candidate in (("energy", e), ("sobol", s), ("grid_direct", d))
            for quantity in ("numerator", "denominator", "sigma")
        }
        replica_values = np.array([item.evaluate(coefficients).sigma for item in replicas])
        replica_se = float(np.std(replica_values, ddof=1)/np.sqrt(len(replicas)))
        bv, bh = _state_norm(base, coefficients)
        ev, eh = _state_norm(energy, coefficients)
        sv, sh = _state_norm(sobol, coefficients)
        gates = convergence_reasons(
            sigma=prediction.sigma,
            energy_delta_sigma=abs(e.sigma-b.sigma),
            energy_vertical_relative=_relative(ev, bv),
            energy_horizontal_relative=_relative(eh, bh),
            sobol_delta_sigma=abs(s.sigma-b.sigma),
            sobol_total_relative=_relative(s.denominator, b.denominator),
            sobol_vertical_relative=_relative(sv, bv),
            sobol_horizontal_relative=_relative(sh, bh),
            replica_se=replica_se,
            grid_direct_delta_sigma=abs(d.sigma-b.sigma),
            populated=True,
        )
        reasons.extend(gates)
        bound = _prediction_bound(prediction, checks, len(replicas), coefficients)
        worst = max(worst, bound)
        if precision_limit is not None and bound > precision_limit:
            reasons.append("fit_precision")
    # Entry-wise checks prevent a cancellation at the source vector from hiding
    # a numerically unstable off-source amplitude direction.
    denominator_scale = max(np.max(np.abs(base.denominator)), 1e-30)
    for label, candidate, threshold in (("energy_matrix", energy, .01),
                                        ("sobol_matrix", sobol, .03),
                                        ("grid_matrix", direct, .002)):
        delta = max(np.max(np.abs(candidate.numerator-base.numerator)),
                    np.max(np.abs(candidate.denominator-base.denominator)))/denominator_scale
        if base.mass_numerator is not None:
            mass_scale = max(np.max(np.abs(base.mass_numerator)), 1e-30)
            delta = max(delta,
                        np.max(np.abs(candidate.mass_numerator-base.mass_numerator))/mass_scale)
        for field in ("vertical_normalization", "horizontal_normalization"):
            original = getattr(base, field)
            updated = getattr(candidate, field)
            if original is not None:
                delta = max(delta, np.max(np.abs(updated-original))/denominator_scale)
        if base.state_phi is not None:
            state_scale = max(np.max(np.abs(base.state_phi)), 1e-30)
            delta = max(delta, np.max(np.abs(candidate.state_phi-base.state_phi))/state_scale)
        if delta > threshold:
            reasons.append(label)
    replica_n = np.std(np.stack([item.numerator for item in replicas]), axis=0, ddof=1)/np.sqrt(len(replicas))
    replica_d = np.std(np.stack([item.denominator for item in replicas]), axis=0, ddof=1)/np.sqrt(len(replicas))
    replica_matrix = max(np.max(np.abs(replica_n)), np.max(np.abs(replica_d)))/denominator_scale
    if base.mass_numerator is not None:
        replica_mass = np.std(np.stack([item.mass_numerator for item in replicas]), axis=0,
                              ddof=1)/np.sqrt(len(replicas))
        replica_matrix = max(replica_matrix,
                             np.max(np.abs(replica_mass))/max(np.max(np.abs(base.mass_numerator)), 1e-30))
    for field in ("vertical_normalization", "horizontal_normalization"):
        original = getattr(base, field)
        if original is not None:
            replica_norm = np.std(np.stack([getattr(item, field) for item in replicas]),
                                  axis=0, ddof=1)/np.sqrt(len(replicas))
            replica_matrix = max(replica_matrix,
                                 np.max(np.abs(replica_norm))/denominator_scale)
    if base.state_phi is not None:
        replica_state = np.std(np.stack([item.state_phi for item in replicas]), axis=0, ddof=1)/np.sqrt(len(replicas))
        replica_matrix = max(replica_matrix,
                             np.max(np.abs(replica_state))/max(np.max(np.abs(base.state_phi)), 1e-30))
    if replica_matrix > .01:
        reasons.append("replica_matrix")
    unique = tuple(dict.fromkeys(reasons))
    return BasisBinCertificate(mean, "masked_nonconverged" if unique else "calculated",
                               unique, worst, covariance, checks, len(replicas), precision_limit,
                               reference_deltas)


def _zero_matrix() -> NDArray[np.complex128]:
    return np.zeros((3, 3), dtype=np.complex128)


def integrate_basis_bin(model, pair: str, energy_range_gev: tuple[float, float],
                        mass_range_gev: tuple[float, float], *, energy_rule: str,
                        energy_order: int, sobol: SobolConfig,
                        flux_spectrum: FluxSpectrum | None = None) -> BasisBinMoment:
    """Integrate raw Hermitian matrices over one exact mass/energy window."""
    if pair not in PAIR_DAUGHTERS:
        raise ValueError(f"unknown pair: {pair}")
    if energy_rule not in ("uniform", "native_flux") or (flux_spectrum is None) != (energy_rule == "uniform"):
        raise ValueError("uniform and native-flux energy weights must not mix")
    if not isinstance(energy_order, int) or isinstance(energy_order, bool) or energy_order < 1:
        raise ValueError("energy_order must be a positive integer")
    if not isinstance(sobol, SobolConfig):
        raise ValueError("sobol requires SobolConfig")
    bounds = (*energy_range_gev, *mass_range_gev)
    if len(bounds) != 4 or not np.isfinite(bounds).all() or bounds[0] <= 0 \
            or bounds[0] >= bounds[1] or bounds[2] >= bounds[3]:
        raise ValueError("energy and mass bounds must be finite and increasing")
    e_low, e_high, m_low, m_high = map(float, bounds)
    masses = model.masses
    proton = model.parameters.proton_mass_gev
    daughters = PAIR_DAUGHTERS[pair]
    spectator = next(index for index in range(3) if index not in daughters)
    mass_low = max(m_low, masses[daughters[0]]+masses[daughters[1]])
    mass_high = min(m_high, np.sqrt(s_from_lab_photon_energy(e_high, proton))-masses[spectator])
    onset = ((mass_low+masses[spectator])**2-proton**2)/(2*proton)
    energy_low = max(e_low, onset)
    numerator, denominator, source_used, mass_numerator, vertical_norm, horizontal_norm = (
        _zero_matrix(), _zero_matrix(), _zero_matrix(), _zero_matrix(),
        _zero_matrix(), _zero_matrix())
    state_phi = np.zeros((2, 12, 3, 3), dtype=np.complex128) if energy_rule == "native_flux" else None
    anchor = None
    def result(status, reason, energies=(), fingerprint=None, flux=None):
        for matrix in (numerator, denominator, source_used, mass_numerator,
                       vertical_norm, horizontal_norm, state_phi):
            if matrix is not None:
                matrix.setflags(write=False)
        nodes = np.asarray(energies, dtype=np.float64)
        nodes.setflags(write=False)
        if flux is None:
            fv = fh = pv = ph = None
        else:
            fv, fh, pv, ph = flux
        return BasisBinMoment(pair, (e_low, e_high), (m_low, m_high), energy_rule,
                              numerator, denominator, state_phi, fv, fh, pv, ph,
                              source_used, nodes, status, reason, fingerprint,
                              None if anchor is None else anchor[0],
                              None if anchor is None else anchor[1], proton,
                              mass_numerator,
                              (energy_low, e_high) if mass_low < mass_high and energy_low < e_high else None,
                              (mass_low, mass_high) if mass_low < mass_high and energy_low < e_high else None,
                              vertical_norm, horizontal_norm)
    if mass_low >= mass_high or energy_low >= e_high:
        return result("masked_kinematic", "no accessible energy-mass intersection")
    if energy_rule == "uniform":
        nodes, legendre = np.polynomial.legendre.leggauss(energy_order)
        energies = (energy_low+e_high)/2 + (e_high-energy_low)*nodes/2
        weights = legendre*(e_high-energy_low)/(2*(e_high-e_low))
        flux_summary = None
    else:
        if flux_spectrum.energy_range_gev != (e_low, e_high):
            raise ValueError("native flux energy range must equal bin range")
        eligible = tuple(node for node in flux_spectrum.exposures if energy_low <= node.energy_gev < e_high)
        if not eligible:
            return result("masked_nonconverged", "no measured flux above mass onset")
        grouped = group_flux_by_energy(replace(flux_spectrum,
                                               energy_range_gev=(energy_low, e_high),
                                               exposures=eligible), energy_order)
        if not grouped:
            raise ValueError("native flux has no energy nodes")
        energies = np.array([node.energy_gev for node in grouped])
        total_v = sum(node.flux_vertical for node in flux_spectrum.exposures)
        total_h = sum(node.flux_horizontal for node in flux_spectrum.exposures)
        total = total_v+total_h
        weights = np.array([(node.flux_vertical+node.flux_horizontal)/total for node in grouped])
        flux_summary = (total_v, total_h,
                        sum(node.flux_vertical*node.polarization_vertical for node in flux_spectrum.exposures)/total_v,
                        sum(node.flux_horizontal*node.polarization_horizontal for node in flux_spectrum.exposures)/total_h)
    fingerprint = None
    for index, (energy, energy_weight) in enumerate(zip(energies, weights)):
        if energy < energy_low:
            continue
        s = s_from_lab_photon_energy(float(energy), proton)
        sample = sample_three_body_mass_window(float(np.sqrt(s)), masses, daughters,
                                                (m_low, m_high), sobol,
                                                reduce_global_azimuth=True)
        if sample is None:
            continue
        eta_p_mass = invariant_mass(sample.momenta[:, 0]+sample.momenta[:, 2])
        if np.any(eta_p_mass > 1.80):
            return result("masked_unsupported_domain", "M(eta p) exceeds 1.80 GeV", energies)
        pair_momentum = sample.momenta[:, daughters[0]]+sample.momenta[:, daughters[1]]
        phi = np.arctan2(pair_momentum[:, 2], pair_momentum[:, 1])
        pair_mass = invariant_mass(pair_momentum)
        normalization = GEV2_TO_MICROBARN*4*proton**2/(2*(s-proton**2)*len(phi))
        measure = normalization*sample.weights_gev2
        vertical = delta_em_event_basis(model, sample, _VERTICAL)
        horizontal = delta_em_event_basis(model, sample, _HORIZONTAL)
        vertical.validate_model(model)
        horizontal.validate_model(model)
        candidate_anchor = (getattr(vertical, "anchor_g1", None),
                            getattr(vertical, "anchor_g2", None))
        if (candidate_anchor != (getattr(horizontal, "anchor_g1", None),
                                 getattr(horizontal, "anchor_g2", None))
                or (anchor is not None and anchor != candidate_anchor)):
            raise ValueError("H/V or energy-node EM source anchor mismatch")
        anchor = candidate_anchor
        if getattr(vertical, "fingerprint", None) != getattr(horizontal, "fingerprint", None):
            raise ValueError("H/V basis model fingerprint mismatch")
        if fingerprint is None:
            fingerprint = getattr(vertical, "fingerprint", None)
        elif fingerprint != getattr(vertical, "fingerprint", None):
            raise ValueError("basis model fingerprint changed across energy nodes")
        q = quadratic_moments(vertical.matrices, horizontal.matrices, phi, measure)
        numerator += energy_weight*q.numerator
        denominator += energy_weight*q.denominator
        vertical_norm += energy_weight*q.vertical
        horizontal_norm += energy_weight*q.horizontal
        mass_numerator += energy_weight*quadratic_moments(
            vertical.matrices, horizontal.matrices, phi,
            measure*pair_mass).denominator
        extended = eta_p_mass > 1.60
        if np.any(extended):
            source_used += energy_weight*quadratic_moments(
                vertical.matrices[:, extended], horizontal.matrices[:, extended],
                phi[extended], measure[extended]).denominator
        if energy_rule == "native_flux":
            node = grouped[index]
            state = azimuth_state_moments(vertical.matrices, horizontal.matrices,
                                          phi, measure, node.polarization_vertical,
                                          node.polarization_horizontal)
            state_phi[0] += node.flux_vertical*state[0]
            state_phi[1] += node.flux_horizontal*state[1]
    if not np.isfinite(denominator).all() or np.real(denominator[0, 0]) <= 0:
        return result("masked_nonconverged", "zero or nonfinite source normalization", energies)
    return result("calculated", None, energies, fingerprint, flux_summary)
