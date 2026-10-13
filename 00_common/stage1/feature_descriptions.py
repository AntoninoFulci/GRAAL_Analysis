"""Diagnostic definitions of the Stage-1 columns, in the shared feature order.

Natural units c=1. Windows are fixed before looking at any dataset; they are
not cuts. Values outside the windows remain in explicit under/overflow bins.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from graal_common.physics.channels import CHI2_RESOLUTION, ETA_PI0_HYP, Hypothesis
from graal_common.physics.pairing import PAIR_IDX
from graal_common.stage1.features import feature_names


@dataclass(frozen=True)
class FeatureDefinition:
    name: str
    formula: str
    unit: str
    kind: str
    family: str
    domain: str
    edges: tuple[float, ...]


def feature_definitions(hypothesis: Hypothesis = ETA_PI0_HYP) -> tuple[FeatureDefinition, ...]:
    """Describe every column without changing how any feature is computed."""
    def window(low, high, bins=60):
        edges = np.linspace(low, high, bins + 1)
        # Physical upper endpoints (+1 for cosines) belong to the last bin.
        edges[-1] = np.nextafter(edges[-1], np.inf)
        return tuple(edges)

    masses = window(0, 1.6)
    energies = window(0, 1.6)
    cosines = window(-1, 1)
    specs = []

    def add(formula, unit, family, domain, edges, kind='continuous'):
        specs.append((formula, unit, kind, family, domain, edges))

    for i, j in PAIR_IDX:
        add(f'sqrt(max((g{i} + g{j})^2, 0))', 'GeV', 'photon pair masses',
            '[0, infinity)', masses)
    for label, mass, half_window in (
        (hypothesis.light_label, hypothesis.light_mass, hypothesis.light_window),
        (hypothesis.heavy_label, hypothesis.heavy_mass, hypothesis.heavy_window),
    ):
        add(f'sum over 6 pairs: abs(m_gg - m_{label}) < {half_window:g}; '
            f'm_{label}={mass:g} GeV', 'count', 'mass pole counts',
            'integers 0..6', tuple(np.arange(-.5, 7., 1.)), 'discrete')
    add('min over 3 disjoint pairings and 2 assignments: '
        f'((m_heavy_pair - {hypothesis.heavy_mass:g}) / '
        f'({CHI2_RESOLUTION:g} * {hypothesis.heavy_mass:g}))^2 + '
        f'((m_light_pair - {hypothesis.light_mass:g}) / '
        f'({CHI2_RESOLUTION:g} * {hypothesis.light_mass:g}))^2',
        '1', 'pairing', '[0, infinity)',
        tuple(np.concatenate(([0.], np.geomspace(1.e-4, 1.e4, 65)))))
    add('sqrt(max(q^2, 0)), q = beam + target - proton; '
        'NOT recoil beam + target - eta - pi0', 'GeV', 'missing kinematics',
        '[0, infinity)', masses)
    add('q_E, q = beam + target - proton', 'GeV', 'missing kinematics',
        'real', window(-1.6, 2.4))
    add('q_pz, q = beam + target - proton', 'GeV', 'missing kinematics',
        'real', window(-2.4, 2.4))
    add('sqrt(q_px^2 + q_py^2), q = beam + target - proton', 'GeV',
        'missing kinematics', '[0, infinity)', energies)
    add('sum_i E_gamma_i', 'GeV', 'photon energy', '[0, infinity)', window(0, 2.4))
    add('beam_E (stored, including smearing)', 'GeV', 'beam energy',
        '[0, infinity)', window(0, 1.6))
    add('max_i E_gamma_i', 'GeV', 'photon energy', '[0, infinity)', energies)
    add('min_i E_gamma_i', 'GeV', 'photon energy', '[0, infinity)', energies)
    add('sqrt(mean_i((E_gamma_i - mean_j(E_gamma_j))^2))', 'GeV',
        'photon energy', '[0, infinity)', energies)
    add('sum over 6 pairs: acos(clip(p_i dot p_j / max(|p_i||p_j|, 1e-9), -1, 1))',
        'rad', 'photon angles', '[0, 6*pi]', window(0, 6 * np.pi))
    add('min over 6 m_gg', 'GeV', 'photon pair masses', '[0, infinity)', masses)
    add('max over 6 m_gg', 'GeV', 'photon pair masses', '[0, infinity)', masses)
    add('sum_i sqrt(px_gamma_i^2 + py_gamma_i^2) (scalar sum, NOT vector norm)',
        'GeV', 'photon momentum', '[0, infinity)', window(0, 2.4))
    add('sqrt(px_proton^2 + py_proton^2 + pz_proton^2)', 'GeV', 'proton',
        '[0, infinity)', window(0, 2.4))
    add('pz_proton / |p_proton|; 0 when |p_proton|=0', '1', 'proton',
        '[-1, 1]', cosines)
    add('abs(E1 - E2)/(E1 + E2) for heavy candidate of chi2-best pairing; '
        '0 when E1 + E2 <= 0', '1', 'meson candidates', '[0, 1]', window(0, 1))
    add('cos(lab opening angle) = clip(p_heavy dot p_light / '
        'max(|p_heavy||p_light|, 1e-9), -1, 1); chi2-best pairing',
        '1', 'meson candidates', '[-1, 1]', cosines)
    return tuple(FeatureDefinition(name, *spec) for name, spec in
                 zip(feature_names(hypothesis), specs, strict=True))
