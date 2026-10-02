"""Reconstructed charge-+1 N*(1535) strong amplitude with VMD and pi-pi-N.

The VMD-corrected six-channel WT kernel receives the integrated three-body
correction once. All energies and masses are in GeV; kernels and amplitudes
are in GeV^-1.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from graal_theory.amplitudes import _reduced_t_core
from graal_theory.amplitudes.nstar1535_pipi_n import pipi_n_kernel_correction
from graal_theory.amplitudes.nstar1535_reduced import (
    ReducedTParameters,
    loop_functions,
)
from graal_theory.amplitudes.nstar1535_vmd import VectorMasses, vmd_kernel


def reconstructed_full_kernel(
    w_gev: float, parameters: ReducedTParameters, masses: VectorMasses,
) -> NDArray[np.complex128]:
    """Return the VMD kernel plus one pi-pi-N correction, in GeV^-1.

    Use final-fit parameters for the reconstructed full variant. The
    three-body correction follows the intermediate variant's charged-pion
    and average proton/neutron mass convention.
    """
    w = _reduced_t_core.validated_energy(w_gev, parameters)
    pion = parameters.meson_masses_gev[1]
    nucleon = (parameters.baryon_masses_gev[0] + parameters.baryon_masses_gev[1])/2
    return (vmd_kernel(w, parameters, masses)
            + pipi_n_kernel_correction(w, pion, nucleon))


def reconstructed_full_tmatrix(
    w_gev: float, parameters: ReducedTParameters, masses: VectorMasses,
) -> NDArray[np.complex128]:
    """Solve (I - VG)T = V with the shared numerical guards, in GeV^-1."""
    w = _reduced_t_core.validated_energy(w_gev, parameters)
    return _reduced_t_core.solve_tmatrix(
        reconstructed_full_kernel(w, parameters, masses),
        loop_functions(w, parameters),
    )
