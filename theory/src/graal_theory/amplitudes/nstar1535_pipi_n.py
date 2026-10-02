"""Intermediate charge-+1 N*(1535) strong amplitude with pi-pi-N absorption.

P73 Eq. (6) corrects the six-channel WT kernel once, without an explicit
three-body channel. Vector-meson exchange is absent, so this is not the
published full model. All energies and masses are in GeV.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from graal_theory.amplitudes import _reduced_t_core
from graal_theory.amplitudes.nstar1535_reduced import (
    ReducedTParameters,
    loop_functions,
    wt_kernel,
)
from graal_theory.amplitudes.pipi_n import pipi_n_loop, pipi_n_potentials


def pipi_n_kernel_correction(
    w_gev: float, pion_mass_gev: float, nucleon_mass_gev: float,
) -> NDArray[np.complex128]:
    """P73 Eq. (6) pion-nucleon block correction, in GeV^-1.

    The vertices use ordinary products, not complex conjugates. Only the
    (pi0_p, pi_plus_n) block receives the integrated three-body correction.
    """
    v11, v31 = pipi_n_potentials(w_gev, pion_mass_gev)
    g = pipi_n_loop(w_gev, pion_mass_gev, nucleon_mass_gev)
    a = -np.sqrt(2)*v31/3 - v11/(3*np.sqrt(2))
    b = (v31-v11)/3
    d = -v31/(3*np.sqrt(2)) - np.sqrt(2)*v11/3
    delta = np.zeros((6, 6), dtype=np.complex128)
    delta[:2, :2] = g*np.array([
        [a*a+b*b, a*b+b*d], [a*b+b*d, b*b+d*d],
    ])
    return delta


def pipi_n_tmatrix(
    w_gev: float, parameters: ReducedTParameters,
) -> NDArray[np.complex128]:
    """Solve the intermediate six-channel (I - VG)T = V amplitude.

    Load the separate final-fit parameters for the intended intermediate
    variant. The three-body loop uses the charged-pion mass and averaged
    proton/neutron mass as an implementation convention; physical channel
    masses remain in the two-body loops.
    """
    w = _reduced_t_core.validated_energy(w_gev, parameters)
    m = parameters.meson_masses_gev[1]
    nucleon = (parameters.baryon_masses_gev[0]+parameters.baryon_masses_gev[1])/2
    v = wt_kernel(w, parameters) + pipi_n_kernel_correction(w, m, nucleon)
    return _reduced_t_core.solve_tmatrix(v, loop_functions(w, parameters))
