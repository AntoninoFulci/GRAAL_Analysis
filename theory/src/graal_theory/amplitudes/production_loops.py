"""Sourced inputs and numerical controls for coherent production loops."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from math import isfinite
from numbers import Integral, Real
from pathlib import Path
from types import MappingProxyType
from typing import Callable, Mapping

import numpy as np
from numpy.polynomial.legendre import leggauss
from numpy.typing import ArrayLike, NDArray

from ..sources import PhysicalParameter, SourceRef, load_source_registry
from ..spin import PAULI
from ..phase_space import ThreeBodySample
from ..kinematics import validate_final_state
from .nstar1535_reduced import CHANNELS, ReducedTParameters, _validated_energy


def _finite_real(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"parameter {name!r} must be a finite real scalar")
    try:
        numeric = float(value)
    except (ValueError, OverflowError):
        raise ValueError(f"parameter {name!r} must be a finite real scalar") from None
    if not isfinite(numeric):
        raise ValueError(f"parameter {name!r} must be a finite real scalar")
    return numeric


@dataclass(frozen=True)
class QuadratureSettings:
    """Validated reproducibility controls, separate from physical provenance."""

    q_order: int = 64
    angle_order: int = 48
    relative_tolerance: float = 1e-5
    absolute_tolerance: float = 1e-10

    def __post_init__(self) -> None:
        for name in ("q_order", "angle_order"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, Integral) or value < 16:
                raise ValueError(f"{name} must be a non-bool integer >=16")
        for name in ("relative_tolerance", "absolute_tolerance"):
            if _finite_real(getattr(self, name), name) <= 0:
                raise ValueError(f"{name} must be positive")


@dataclass(frozen=True)
class ProductionParameters:
    electric_charge: float
    axial_d: float
    axial_f: float
    b6d: float
    b6f: float
    first_loop_cutoff_gev: float
    pion_form_factor_cutoff_gev: float
    rho_form_factor_cutoff_gev: float
    nstar1520_mass_gev: float
    nstar1520_npi_width_gev: float
    f_tilde_nstar_delta_pi: float
    g_tilde_nstar_delta_pi: float
    g1_nstar_per_gev: float
    g2_nstar_per_gev2: float
    g_rho_nstar: float
    sigma_star_mass_gev: float
    sigma_star_width_gev: float
    g_k_sigma_star: complex
    sigma_star_su3_correction: float
    quadrature: QuadratureSettings
    provenance: Mapping[str, PhysicalParameter] = field(repr=False, compare=False)

    def __post_init__(self) -> None:
        # Copy before freezing so retained caller dictionaries cannot mutate it.
        object.__setattr__(self, "provenance", MappingProxyType(dict(self.provenance)))


_SCHEMA = {
    "electric_charge": ("1", "nacher_2001"),
    "axial_d": ("1", "doering_2006_prc"),
    "axial_f": ("1", "doering_2006_prc"),
    "b6d": ("1", "doering_2006_prc"),
    "b6f": ("1", "doering_2006_prc"),
    "first_loop_cutoff_gev": ("GeV", "doering_2006_prc"),
    "pion_form_factor_cutoff_gev": ("GeV", "doering_2006_prc"),
    "rho_form_factor_cutoff_gev": ("GeV", "nacher_2001"),
    "nstar1520_mass_gev": ("GeV", "nacher_2001"),
    "nstar1520_npi_width_gev": ("GeV", "nacher_2001"),
    "f_tilde_nstar_delta_pi": ("1", "nacher_2001"),
    "g_tilde_nstar_delta_pi": ("1", "nacher_2001"),
    "g1_nstar": ("m_N^-1", "nacher_2001"),
    "g2_nstar": ("m_N^-2", "nacher_2001"),
    "g_rho_nstar": ("1", "nacher_2001"),
    "sigma_star_mass_gev": ("GeV", "pdg_2024"),
    "sigma_star_width_gev": ("GeV", "doering_2006_prc"),
    "g_k_sigma_star": ("1", "doering_2006_prc"),
    "sigma_star_su3_correction": ("1", "doering_2006_prc"),
    "proton_mass": ("GeV", "pdg_2024"),
}
_POSITIVE = frozenset({
    "first_loop_cutoff_gev", "pion_form_factor_cutoff_gev",
    "rho_form_factor_cutoff_gev",
    "nstar1520_mass_gev", "sigma_star_mass_gev", "proton_mass",
})
_WIDTHS = frozenset({"nstar1520_npi_width_gev", "sigma_star_width_gev"})


def load_production_parameters(parameter_path: Path, source_path: Path) -> ProductionParameters:
    """Load a closed source-linked record, retaining source units in provenance.

    The proton mass is a sourced conversion input, not a new production field.
    Electromagnetic couplings are returned in GeV^-1 and GeV^-2, matching the
    existing Delta1700Parameters nucleon-mass convention.
    """
    raw = json.loads(parameter_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("production parameters must be an object")
    missing = sorted(_SCHEMA.keys() - raw.keys())
    unexpected = sorted(raw.keys() - _SCHEMA.keys())
    if missing or unexpected:
        raise ValueError(f"production parameter names: missing={missing}, unexpected={unexpected}")
    sources = load_source_registry(source_path)
    provenance = {}
    for name, (unit, source_key) in _SCHEMA.items():
        entry = raw[name]
        if not isinstance(entry, dict) or set(entry) != {"value", "unit", "source_key", "locator"}:
            raise ValueError(f"parameter {name!r} requires value, unit, source_key, locator")
        if entry["unit"] != unit:
            raise ValueError(f"parameter {name!r} requires unit {unit!r}")
        if entry["source_key"] != source_key or source_key not in sources:
            raise ValueError(f"parameter {name!r} requires registered source {source_key!r}")
        locator = entry["locator"]
        if not isinstance(locator, str) or not locator.strip() or "://" in locator:
            raise ValueError(f"parameter {name!r} requires a source locator")
        value = entry["value"]
        if name == "g_k_sigma_star":
            if not isinstance(value, dict) or set(value) != {"real", "imag"}:
                raise ValueError(f"parameter {name!r} requires real and imag components")
            numeric = complex(_finite_real(value["real"], name), _finite_real(value["imag"], name))
        else:
            numeric = _finite_real(value, name)
            if name in _POSITIVE and numeric <= 0:
                raise ValueError(f"parameter {name!r} must be positive")
            if name in _WIDTHS and numeric < 0:
                raise ValueError(f"parameter {name!r} must be nonnegative")
        record = sources[source_key]
        ref = SourceRef(source_key, record.get("doi") or record.get("arxiv"), locator)
        provenance[name] = PhysicalParameter(name, numeric, unit, ref)
    values = {name: parameter.value for name, parameter in provenance.items()}
    proton_mass = values.pop("proton_mass")
    for name, field_name, power in (
        ("g1_nstar", "g1_nstar_per_gev", 1),
        ("g2_nstar", "g2_nstar_per_gev2", 2),
    ):
        try:
            converted = values.pop(name) / proton_mass**power
        except (ZeroDivisionError, OverflowError):
            raise ValueError(f"parameter {name!r} has nonfinite unit conversion") from None
        values[field_name] = _finite_real(converted, name)
    return ProductionParameters(**values, quadrature=QuadratureSettings(), provenance=provenance)


def _real_array(value: ArrayLike, context: str) -> NDArray[np.float64]:
    array = np.asarray(value)
    if array.dtype.kind not in "iuf" or not np.all(np.isfinite(array)):
        raise ValueError(f"{context}: requires finite real values")
    return np.asarray(array, dtype=np.float64)


def pion_monopole(
    momentum_squared_gev2: ArrayLike, pion_mass_gev: float, cutoff_gev: float,
) -> NDArray[np.float64]:
    """NPA 695 (2001), Appendix Eq. (74), with Minkowski p^2 in GeV^2."""
    context = "pion monopole"
    try:
        mass = _finite_real(pion_mass_gev, "pion_mass_gev")
        cutoff = _finite_real(cutoff_gev, "cutoff_gev")
        if mass <= 0 or cutoff <= 0:
            raise ValueError("mass and cutoff must be positive")
        squared = _real_array(momentum_squared_gev2, context)
        denominator = cutoff**2 - squared
        if np.any(denominator == 0):
            raise ValueError("cutoff pole")
        value = (cutoff**2 - mass**2) / denominator
        if not np.all(np.isfinite(value)):
            raise ValueError("nonfinite result")
        return np.asarray(value, dtype=np.float64)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{context}: {exc}") from exc


def _quadrature_value(value, context: str) -> NDArray[np.complex128]:
    try:
        raw = np.asarray(value)
        if raw.dtype.kind not in "iufc":
            raise ValueError("requires numeric, non-bool values")
        array = np.asarray(raw, dtype=np.complex128)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{context}: malformed integrand") from exc
    if not np.all(np.isfinite(array)):
        raise ValueError(f"{context}: nonfinite integrand")
    return array


def _interval(lower, upper, order, context):
    try:
        low, high = _finite_real(lower, "lower"), _finite_real(upper, "upper")
    except ValueError as exc:
        raise ValueError(f"{context}: {exc}") from exc
    if low >= high:
        raise ValueError(f"{context}: integration interval must increase")
    nodes, weights = leggauss(order)
    jacobian = (high - low) / 2
    return low + (nodes + 1)*jacobian, weights*jacobian


def _integrate_orders(integrand, bounds, settings, context):
    if not isinstance(settings, QuadratureSettings):
        raise ValueError(f"{context}: requires QuadratureSettings")
    if not callable(integrand):
        raise ValueError(f"{context}: integrand must be callable")

    def evaluate(multiplier):
        q, qw = _interval(*bounds[:2], multiplier*settings.q_order, context)
        total = None
        shape = None
        if len(bounds) == 2:
            points = ((float(qi),) for qi in q)
            weights = qw
        else:
            x, xw = _interval(*bounds[2:], multiplier*settings.angle_order, context)
            points = ((float(qi), float(xi)) for qi in q for xi in x)
            weights = (weight_q*weight_x for weight_q in qw for weight_x in xw)
        for point, weight in zip(points, weights):
            try:
                value = _quadrature_value(integrand(*point), context)
            except (ValueError, TypeError, ZeroDivisionError, FloatingPointError, OverflowError) as exc:
                raise ValueError(f"{context}: {exc}") from exc
            if total is None:
                shape = value.shape
                total = np.zeros(shape, dtype=np.complex128)
            if value.shape != shape:
                raise ValueError(f"{context}: integrand shape changed")
            total += weight*value
        return _quadrature_value(total, context)

    low, high = evaluate(1), evaluate(2)
    tolerance = settings.absolute_tolerance + settings.relative_tolerance*np.abs(high)
    if np.any(np.abs(high-low) > tolerance):
        raise ValueError(f"{context}: quadrature convergence failure; "
                         f"max difference={np.max(np.abs(high-low)):.6g}")
    return high


def _integrate_complex_1d(integrand, lower, upper, *, settings, context):
    """Direct GL integration; the doubled-order result must agree elementwise."""
    return _integrate_orders(integrand, (lower, upper), settings, context)


def _integrate_complex_2d(
    integrand, q_lower, q_upper, x_lower, x_upper, *, settings, context,
):
    """Tensor GL integration with explicit radial and angular Jacobians."""
    return _integrate_orders(
        integrand, (q_lower, q_upper, x_lower, x_upper), settings, context,
    )


# PRC 73, 045209, Table II; the ordering is the six-channel strong-T ordering.
KR_A = np.array([0, -1, 0, 0, np.sqrt(2/3), 0.0])
KR_B = np.array([0, 0, 0, -1/np.sqrt(2), -1/np.sqrt(6), 0.0])
BBM_A = np.array([1/np.sqrt(2), 1, 1/np.sqrt(6), 0, -np.sqrt(2/3), 0.0])
BBM_B = np.array([0, 0, -np.sqrt(2/3), 1/np.sqrt(2), 1/np.sqrt(6), 1.0])
MESON_CHARGE = np.array([0, -1, 0, -1, -1, 0.0])
for _coefficient in (KR_A, KR_B, BBM_A, BBM_B, MESON_CHARGE):
    _coefficient.setflags(write=False)


def _at_radial_cutoff(root, limit):
    """Allow only roundoff in equivalent kinematic endpoint expressions."""
    return abs(root-limit) <= 32*np.finfo(float).eps*max(1., root, limit)


def _reject_zero_width_intermediate_pole(w, meson, pole, width, limit, context, particle):
    """Preflight a declared resonance pole before GL nodes avoid a split.

    At W=meson+pole the q=0 denominator zero is canceled by the radial q^2
    measure. A nonzero-radius pole has no stable-particle prescription here.
    Consumers own the mass, width and active source/transition; this helper
    neither probes callbacks nor classifies arbitrary numerical landmarks.
    """
    if width != 0 or w <= meson+pole:
        return
    radial_squared = (w*w-(meson+pole)**2)*(w*w-(meson-pole)**2)/(4*w*w)
    radial = np.sqrt(radial_squared)
    if radial < limit or _at_radial_cutoff(radial, limit):
        raise ValueError(f"{context} invariant={w:.12g}GeV: zero-width {particle} "
                         f"intermediate pole at q={radial:.12g}GeV")


def _radial_cut_density(q, numerator, denominator, roots, derivative, limit, context):
    """Regular density for the source's 1/(D+i0), without finite epsilon.

    Subtract each simple real root's residue a/(q-r), integrate its principal
    value analytically, and add -i*pi*F(r)/|D'(r)|. The analytic terms are
    constant densities over [0, limit], so configured/doubled GL checks cover
    their angular integration too. Closed channels have no real roots.
    """
    poles = []
    correction = 0j
    for root in roots:
        if _at_radial_cutoff(root, limit):
            raise ValueError(f"{context}: pole at radial cutoff")
        if not 0 < root < limit:
            continue
        slope = derivative(root)
        if slope == 0 or not np.isfinite(slope):
            raise ValueError(f"{context}: nonsimple physical pole")
        value = _quadrature_value(numerator(root), context)
        residue = value/slope
        poles.append((root, residue))
        correction = (correction + residue*np.log((limit-root)/root)
                      - 1j*np.pi*value/abs(slope))

    def regular(point):
        divisor = denominator(point)
        if divisor == 0:
            raise ValueError(f"{context}: unaccounted propagator pole")
        value = _quadrature_value(numerator(point), context)/divisor
        for root, residue in poles:
            value = value-residue/(point-root)
        return value

    # At an accidentally coincident GL node, evaluate the removable limit.
    nearest = min((abs(q-root) for root, _ in poles), default=np.inf)
    if nearest < 1e-8:
        step = min(1e-5, q/4, (limit-q)/4)
        density = (regular(q-step)+regular(q+step))/2
    else:
        density = regular(q)
    return density + correction/limit


def _polarization(polarization, context):
    try:
        array = np.asarray(polarization)
        if (array.shape != (3,) or array.dtype.kind not in "iufc"
                or not np.all(np.isfinite(array)) or np.linalg.norm(array) == 0
                or abs(array[2]) > 1e-12*np.linalg.norm(array)):
            raise ValueError("requires a finite nonzero Coulomb-transverse three-vector")
        return np.asarray(array, dtype=np.complex128)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{context}: polarization {exc}") from exc


def _eq8_cut_density(q, smooth_numerator, momentum_squared, limit, context):
    """Rationalized q^2 H(q)/(p_on^2-q^2+i0), including closed-channel limits.

    Subtract the full quadratic pole pair, rather than only its positive root,
    to keep both threshold sides smooth at configured orders. The closed
    branch integrates its q=0 boundary term as kappa*atan(limit/kappa).
    """
    h = smooth_numerator(q)
    if momentum_squared > 0:
        pole = np.sqrt(momentum_squared)
        if _at_radial_cutoff(pole, limit):
            raise ValueError(f"{context}: pole at radial cutoff")
        on_shell = momentum_squared*smooth_numerator(pole)
        if abs(q-pole) < 1e-8:
            step = min(1e-5, q/4, (limit-q)/4)
            def regular(r):
                return (r*r*smooth_numerator(r)-on_shell)/(momentum_squared-r*r)
            density = (regular(q-step)+regular(q+step))/2
        else:
            density = (q*q*h-on_shell)/(momentum_squared-q*q)
        analytic = np.log(abs((limit+pole)/(limit-pole)))/(2*pole)
        if pole < limit:
            analytic -= 1j*np.pi/(2*pole)
        return density + on_shell*analytic/limit
    if momentum_squared == 0:
        return -h
    kappa = np.sqrt(-momentum_squared)
    at_zero = smooth_numerator(0.)
    return (-h + momentum_squared*(h-at_zero)/(momentum_squared-q*q)
            + kappa*at_zero*np.arctan(limit/kappa)/limit)


def eta_photoproduction_amplitude(
    sqrt_s: float, polarization: NDArray, production: ProductionParameters,
    strong_parameters: ReducedTParameters, strong_t: Callable[[float], NDArray],
) -> NDArray[np.complex128]:
    """Coherent physical KR + meson-pole pair, PRC73 Eqs. (8)-(9).

    Photon direction is +z, Coulomb gauge. T is evaluated once at sqrt(s),
    never at a loop-dependent energy. The first-loop cutoff does not replace
    the dimensional-regularization scale in the strong amplitude. Each direct
    integral uses principal-value subtraction for the printed +i0, with
    elementwise configured/doubled-order verification and no interpolation.
    """
    context = f"eta photoproduction invariant={sqrt_s!r}GeV"
    if (not isinstance(production, ProductionParameters)
            or not isinstance(strong_parameters, ReducedTParameters)):
        raise ValueError(f"{context}: requires production and strong parameter records")
    try:
        for field in ("electric_charge", "axial_d", "axial_f"):
            _finite_real(getattr(production, field), field)
    except ValueError as exc:
        raise ValueError(f"{context}: {exc}") from exc
    try:
        w = _validated_energy(sqrt_s, strong_parameters)
        if w <= strong_parameters.baryon_masses_gev[0]:
            raise ValueError("invariant must exceed proton mass")
    except (ValueError, TypeError) as exc:
        raise ValueError(f"{context}: invariant {exc}") from exc
    epsilon = _polarization(polarization, context)
    try:
        t = _quadrature_value(strong_t(w), context)
    except (ValueError, TypeError, ZeroDivisionError, FloatingPointError, OverflowError) as exc:
        raise ValueError(f"{context}: strong T {exc}") from exc
    if t.shape != (6, 6):
        raise ValueError(f"{context}: strong T requires shape (6,6)")
    try:
        limit = _finite_real(production.first_loop_cutoff_gev, "first_loop_cutoff_gev")
        if limit <= 0:
            raise ValueError("cutoff must be positive")
    except ValueError as exc:
        raise ValueError(f"{context}: {exc}") from exc
    k = (w*w-strong_parameters.baryon_masses_gev[0]**2)/(2*w)
    sigma_epsilon = np.einsum("i,ijk->jk", epsilon, PAULI)
    result = np.zeros((2, 2), dtype=np.complex128)
    for channel in range(6):
        if ((KR_A[channel] == KR_B[channel] == 0 and MESON_CHARGE[channel] == 0)
                or t[channel, 2] == 0):
            continue
        label = f"{context} channel={CHANNELS[channel]}"
        mass = strong_parameters.meson_masses_gev[channel]
        baryon = strong_parameters.baryon_masses_gev[channel]
        decay = strong_parameters.decay_constants_gev[channel]

        def energies(q):
            return np.sqrt(mass*mass+q*q), np.sqrt(baryon*baryon+q*q)

        momentum_squared = (w*w-(mass+baryon)**2)*(w*w-(mass-baryon)**2)/(4*w*w)
        omega_on = (w*w+mass*mass-baryon*baryon)/(2*w)

        def rational_factor(q):
            omega, energy = energies(q)
            return (omega_on+omega)*(w-omega+energy)/(2*w)

        def kr_smooth_numerator(q):
            omega, energy = energies(q)
            return baryon/(4*np.pi**2*omega*energy)*rational_factor(q)

        kr = _integrate_complex_1d(
            lambda q: _eq8_cut_density(q, kr_smooth_numerator, momentum_squared,
                                        limit, label+" KR"),
            0., limit, settings=production.quadrature, context=label+" KR",
        )

        def mp_smooth_numerator(q, x):
            omega, energy = energies(q)
            shifted = np.sqrt(q*q+k*k-2*q*k*x+mass*mass)
            divisor = ((w-shifted-k-energy)*omega*shifted
                       *(k-omega-shifted)*(k+omega+shifted))
            if divisor == 0:
                raise ValueError(f"{label} MP: meson propagator pole")
            bracket = (k*shifted+(energy-w)*(omega+shifted)+(omega+shifted)**2)
            return q*q*(1-x*x)*bracket/(energy*divisor)*rational_factor(q)

        mp = _integrate_complex_2d(
            lambda q, x: _eq8_cut_density(
                q, lambda r: mp_smooth_numerator(r, x), momentum_squared,
                limit, label+" MP",
            ), 0., limit, -1., 1., settings=production.quadrature, context=label+" MP",
        )
        axial_kr = (KR_A[channel]*(production.axial_d+production.axial_f)
                    + KR_B[channel]*(production.axial_d-production.axial_f))/2
        axial_mp = (BBM_A[channel]*(production.axial_d+production.axial_f)
                    + BBM_B[channel]*(production.axial_d-production.axial_f))/2
        scalar = (np.sqrt(2)*1j*production.electric_charge/decay*t[channel, 2]
                  *(-axial_kr*kr + axial_mp*MESON_CHARGE[channel]*baryon/(8*np.pi**2)*mp))
        result += scalar*sigma_epsilon
    return _quadrature_value(result, context)


def _complex_scalar(value, context):
    array = np.asarray(value)
    if array.shape != () or array.dtype.kind not in "iufc":
        raise ValueError(f"{context}: requires finite complex scalar")
    return np.complex128(_quadrature_value(array, context).item())


def eq26_rescattering_loop(
    sample: ThreeBodySample, event_index: int, channel_index: int,
    source_kernel: Callable[[float, float], NDArray],
    intermediate_propagator: Callable[[complex], complex], transition: complex,
    production: ProductionParameters, strong_parameters: ReducedTParameters,
    context: str,
    *, intermediate_invariant_landmarks_gev: tuple[float, ...] = (),
) -> NDArray[np.complex128]:
    """Shared direct PRC73 Eq. (26), with exact Eq. (27) recoil energies.

    The sample order is (eta, pi0, proton), as in the existing model. The family
    supplies the spin kernel, intermediate propagator, and already-evaluated
    T[i,eta](z); it owns the external z prescription and any resonance width.
    No intermediate width or mass is invented here. The callback receives
    principal sqrt(complex((W-omega)^2-q^2)), including Im(sqrt)>=0 for a
    spacelike invariant. Physical meson-baryon +i0 cuts use direct quadrature
    with the same principal-value subtraction as Eq. (8). If the principal
    sqrt has a branch point inside the radial domain, quadratic maps on
    either side remove its endpoint cusp. The convergence comparison applies
    to their combined integral, retaining the full PV/cut normalization.
    Families can additionally supply an immutable tuple of numerical invariant
    landmarks (thresholds or pole masses). Reachable values become radial
    boundaries. The helper owns the invariant conversion, not resonance physics.
    """
    label = f"{context} Eq26 event={event_index!r} channel={channel_index!r}"
    try:
        if (isinstance(channel_index, (bool, np.bool_))
                or not isinstance(channel_index, Integral) or not 0 <= channel_index < 6):
            raise ValueError("channel index must be an integer in [0,6)")
        if (isinstance(event_index, (bool, np.bool_))
                or not isinstance(event_index, Integral)):
            raise ValueError("event index must be a non-bool integer")
        if not isinstance(sample, ThreeBodySample):
            raise ValueError("requires ThreeBodySample")
        initial = _real_array(sample.initial, label)
        momenta = _real_array(sample.momenta, label)
        if (momenta.ndim != 3 or momenta.shape[1:] != (3, 4)
                or initial.shape != (len(momenta), 4)
                or not 0 <= event_index < len(momenta)):
            raise ValueError("invalid sample shape or event index")
        if np.any(np.abs(initial[event_index, 1:]) > 1e-12):
            raise ValueError("Eq26 sample must be in the overall CM frame")
        expected_masses = (strong_parameters.meson_masses_gev[2],
                           strong_parameters.meson_masses_gev[0],
                           strong_parameters.baryon_masses_gev[0])
        if not np.allclose(sample.masses, expected_masses, rtol=0, atol=1e-12):
            raise ValueError("sample masses must follow (eta,pi0,proton) ordering")
        validate_final_state(initial[event_index], momenta[event_index:event_index+1], sample.masses)
        if initial[event_index, 0] <= sum(sample.masses):
            raise ValueError("invariant below three-body threshold")
        transition_value = _complex_scalar(transition, label+" transition")
        if not callable(source_kernel) or not callable(intermediate_propagator):
            raise ValueError("source and propagator must be callable")
        limit = _finite_real(production.first_loop_cutoff_gev, "first_loop_cutoff_gev")
        if limit <= 0:
            raise ValueError("cutoff must be positive")
        if not isinstance(intermediate_invariant_landmarks_gev, tuple):
            raise ValueError("invariant landmarks require an immutable tuple")
        landmarks = tuple(_finite_real(value, "invariant landmark")
                          for value in intermediate_invariant_landmarks_gev)
        if any(value < 0 for value in landmarks):
            raise ValueError("invariant landmarks must be nonnegative")
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError(f"{label}: {exc}") from exc
    w = float(initial[event_index, 0])
    pion = momenta[event_index, 1]
    pion_magnitude = np.linalg.norm(pion[1:])
    available = w-pion[0]
    mass = strong_parameters.meson_masses_gev[channel_index]
    baryon = strong_parameters.baryon_masses_gev[channel_index]
    label += f"={CHANNELS[channel_index]} invariant={w:.12g}GeV"

    def energies(q, x):
        return (np.sqrt(mass*mass+q*q),
                np.sqrt(baryon*baryon+q*q+pion_magnitude**2+2*q*pion_magnitude*x))

    def numerator(q, x):
        omega, energy = energies(q, x)
        spin = _quadrature_value(source_kernel(q, x), label+" source kernel")
        if spin.shape != (2, 2):
            raise ValueError(f"{label}: source kernel requires shape (2,2)")
        intermediate = np.sqrt(np.complex128((w-omega)**2-q*q))
        prop = _complex_scalar(intermediate_propagator(intermediate), label+" intermediate propagator")
        return transition_value*spin*prop*q*q*baryon/(8*np.pi**2*omega*energy)

    def density(q, x):
        def denominator(r):
            omega, energy = energies(r, x)
            return available-omega-energy

        def derivative(r):
            omega, energy = energies(r, x)
            return -r/omega-(r+pion_magnitude*x)/energy

        # Solving A*omega(q)+q*p_pi*x=B gives all possible radial roots.
        # Check the unsquared equation to reject roots introduced by squaring.
        b = (available**2+mass**2-baryon**2-pion_magnitude**2)/2
        c = available**2-(pion_magnitude*x)**2
        discriminant = (b*pion_magnitude*x)**2-c*(available**2*mass**2-b*b)
        roots = []
        if discriminant >= 0:
            for root in ((-b*pion_magnitude*x-np.sqrt(discriminant))/c,
                         (-b*pion_magnitude*x+np.sqrt(discriminant))/c):
                if root > 0 and abs(denominator(root)) < 1e-10:
                    if not roots or abs(root-roots[0]) > 1e-12:
                        roots.append(root)
        return _radial_cut_density(q, lambda r: numerator(r, x), denominator,
                                   roots, derivative, limit, label)

    branch = (w*w-mass*mass)/(2*w)
    cuts = [0., limit]
    if 0 < branch < limit:
        cuts.append(branch)
    for value in landmarks:
        if w <= value+mass:
            # Omit unreachable values and the removable q=0 endpoint. The
            # addition form avoids a spurious tiny split from subtraction.
            continue
        omega = (w*w+mass*mass-value*value)/(2*w)
        radial_squared = omega*omega-mass*mass
        if omega >= mass and radial_squared > 0:
            radial = np.sqrt(radial_squared)
            if 0 < radial < limit:
                cuts.append(float(radial))
    cuts = sorted(set(cuts))
    if len(cuts) > 2:
        segments = tuple(zip(cuts[:-1], cuts[1:]))
        def mapped_density(u, x):
            total = np.zeros((2, 2), dtype=np.complex128)
            for lower, upper in segments:
                length = upper-lower
                if upper == branch:
                    q, jacobian = upper-length*u*u, 2*length*u
                elif lower == branch:
                    q, jacobian = lower+length*u*u, 2*length*u
                else:
                    q, jacobian = lower+length*u, length
                total += jacobian*density(q, x)
            return total
        # One checked integral compares the configured combined sum with
        # the doubled-order combined sum; no individual segment is accepted.
        return _integrate_complex_2d(mapped_density, 0., 1., -1., 1.,
            settings=production.quadrature, context=label)
    return _integrate_complex_2d(density, 0., limit, -1., 1.,
        settings=production.quadrature, context=label)
