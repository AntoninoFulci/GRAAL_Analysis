"""Sideband studies and background correction orchestration."""
from __future__ import annotations

from dataclasses import replace
from typing import Sequence

import numpy as np

from graal_common.physics.channels import ETA_PI0_HYP, M_ETA, M_PI0, M_PROTON
from observable_extraction.extraction import extract_sample
from observable_extraction.core.binning import PHI_EDGES_RAD
from observable_extraction.core.background import (
    BackgroundEstimate, Region, SidebandWindows, classify_region,
    correct_sigma_with_uncertainty, factorized_sideband_template,
    fit_background_fraction, fraction_in_mask, validate_signal_leakage,
)
from observable_extraction.io.root_output import OutputPoint


SIDEBAND_TREE = "reco_eta_pi0_bdt_sideband"
SIDEBAND_WINDOWS = SidebandWindows(
    eta_center=M_ETA,
    eta_half_width=ETA_PI0_HYP.heavy_window,
    pi0_center=M_PI0,
    pi0_half_width=ETA_PI0_HYP.light_window,
    missing_center=M_PROTON,
    missing_half_width=0.06,
)


def _apply_background_correction(
    points: Sequence[OutputPoint],
    fractions_by_energy: dict[int, BackgroundEstimate],
    background_by_bin: dict[tuple[str, int, int], object],
) -> list[OutputPoint]:
    """Correct Sigma while retaining observed value and propagated uncertainty."""
    corrected_points: list[OutputPoint] = []
    for output in points:
        point = output.point
        fraction = fractions_by_energy.get(point.energy_bin)
        background = background_by_bin.get(
            (output.estimator, point.pair, point.energy_bin, point.mass_bin)
        )
        if background is None:
            background = background_by_bin.get(
                (point.pair, point.energy_bin, point.mass_bin)
            )
        if fraction is None or background is None:
            corrected_points.append(output)
            continue
        observed_error = 0.5 * (point.stat_low + point.stat_high)
        background_error = 0.5 * (
            background.point.stat_low + background.point.stat_high
        )
        sigma, error = correct_sigma_with_uncertainty(
            sigma_observed=point.sigma,
            observed_error=observed_error,
            background_fraction=fraction.fraction,
            fraction_error=fraction.error,
            sigma_background=background.point.sigma,
            background_error=background_error,
        )
        corrected_points.append(
            replace(
                output,
                point=replace(point, sigma=sigma, stat_low=error, stat_high=error),
                sigma_uncorrected=point.sigma,
                background_fraction=fraction.fraction,
                uncertainty_kind="background_propagated_unclassified",
            )
        )
    return corrected_points


def _sideband_regions(events) -> np.ndarray:
    return np.array(
        [
            classify_region(
                eta_mass=float(eta_mass),
                pi0_mass=float(pi0_mass),
                missing_mass=float(missing_mass),
                windows=SIDEBAND_WINDOWS,
            )
            for eta_mass, pi0_mass, missing_mass in zip(
                events.eta_mass_gev,
                events.pi0_mass_gev,
                events.missing_mass_gev,
            )
        ],
        dtype=object,
    )


def _mass_pulls(events) -> np.ndarray:
    return np.column_stack(
        (
            (events.eta_mass_gev - SIDEBAND_WINDOWS.eta_center)
            / SIDEBAND_WINDOWS.eta_half_width,
            (events.pi0_mass_gev - SIDEBAND_WINDOWS.pi0_center)
            / SIDEBAND_WINDOWS.pi0_half_width,
            (events.missing_mass_gev - SIDEBAND_WINDOWS.missing_center)
            / SIDEBAND_WINDOWS.missing_half_width,
        )
    )


def _estimate_background_fractions(
    broad_events,
    signal_mc,
    energy_edges: np.ndarray,
) -> tuple[dict[int, BackgroundEstimate], float]:
    """Fit broad 3D mass mixtures, then project fractions into signal cube."""
    broad_regions = _sideband_regions(broad_events)
    signal_regions = _sideband_regions(signal_mc)
    leakage = validate_signal_leakage(signal_regions, maximum=0.05)
    broad_pulls = _mass_pulls(broad_events)
    signal_pulls = _mass_pulls(signal_mc)
    histogram_edges = [np.linspace(-4.0, 4.0, 9)] * 3
    centers = 0.5 * (histogram_edges[0][:-1] + histogram_edges[0][1:])
    signal_cube = (
        (np.abs(centers[:, None, None]) < 1.0)
        & (np.abs(centers[None, :, None]) < 1.0)
        & (np.abs(centers[None, None, :]) < 1.0)
    )
    estimates: dict[int, BackgroundEstimate] = {}
    for energy_bin, (energy_low, energy_high) in enumerate(
        zip(energy_edges[:-1], energy_edges[1:])
    ):
        last = energy_bin == len(energy_edges) - 2
        broad_energy = (broad_events.beam_energy_gev >= energy_low) & (
            (broad_events.beam_energy_gev < energy_high)
            | (last & (broad_events.beam_energy_gev <= energy_high))
        )
        signal_energy = (signal_mc.beam_energy_gev >= energy_low) & (
            (signal_mc.beam_energy_gev < energy_high)
            | (last & (signal_mc.beam_energy_gev <= energy_high))
        )
        hard = broad_energy & (broad_regions == Region.HARD_SIDEBAND)
        if not np.any(broad_energy) or not np.any(signal_energy) or not np.any(hard):
            continue
        data_hist, _ = np.histogramdd(
            broad_pulls[broad_energy], bins=histogram_edges
        )
        signal_hist, _ = np.histogramdd(
            signal_pulls[signal_energy], bins=histogram_edges
        )
        hard_hist, _ = np.histogramdd(broad_pulls[hard], bins=histogram_edges)
        if data_hist.sum() <= 0.0 or signal_hist.sum() <= 0.0 or hard_hist.sum() <= 0.0:
            continue
        signal_template = signal_hist + 0.5
        signal_template /= signal_template.sum()
        background_template = factorized_sideband_template(hard_hist)
        broad_fit = fit_background_fraction(
            data_hist,
            signal_template,
            background_template,
        )
        fraction = fraction_in_mask(
            broad_fit.fraction,
            signal_template,
            background_template,
            signal_cube,
        )
        low = fraction_in_mask(
            max(0.0, broad_fit.fraction - broad_fit.error),
            signal_template,
            background_template,
            signal_cube,
        )
        high = fraction_in_mask(
            min(1.0, broad_fit.fraction + broad_fit.error),
            signal_template,
            background_template,
            signal_cube,
        )
        estimates[energy_bin] = BackgroundEstimate(
            fraction=min(fraction, 1.0 - 1e-12),
            error=0.5 * abs(high - low),
            nll=broad_fit.nll,
            converged=broad_fit.converged,
        )
    return estimates, leakage


def _background_asymmetries(
    broad_events,
    exposures,
    estimator: str,
    energy_edges: np.ndarray,
    phi_edges: np.ndarray = PHI_EDGES_RAD,
    selected_phi_bins: dict | None = None,
    workers: int = 1,
) -> dict[tuple[str, str, int, int], OutputPoint]:
    regions = _sideband_regions(broad_events)
    hard_events = broad_events.take(regions == Region.HARD_SIDEBAND)
    if len(hard_events) == 0:
        return {}
    bundle = extract_sample(
        sample_name="hard_sideband",
        events=hard_events,
        exposures=exposures,
        estimator=estimator,
        retain_ratio_objects=False,
        energy_edges=energy_edges,
        phi_edges=phi_edges,
        workers=workers,
        **({"selected_phi_bins": selected_phi_bins} if selected_phi_bins is not None else {}),
    )
    return {
        (
            item.estimator,
            item.point.pair,
            item.point.energy_bin,
            item.point.mass_bin,
        ): item
        for item in bundle.points
    }
