"""Reproducible evidence for strip-index identity across calibrated runs.

This checks the software mapping, not undocumented detector wiring changes.
Energy axes are deliberately permitted to vary between both runs and states.
"""
from __future__ import annotations

from collections import defaultdict
from hashlib import sha256
from pathlib import Path

import numpy as np

from calibration.run_manifest import validate_manifest
from flux_studies.calibrated_data import STATES


def _fingerprint(path):
    path = Path(path)
    digest = sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return dict(path=str(path.resolve()), sha256=digest.hexdigest())


def _keys(source):
    result = defaultdict(list)
    for key in source.keys(recursive=False):
        result[key.rsplit(';', 1)[0]].append(key)
    return result


def audit_native_strips(manifest, calibrated_flux, raw_flux, *, runs=None):
    """Check each available calibrated histogram against the original strip file.

    The calibration writer copies ``max(0, raw_bin)`` to the same bin number;
    this exact identity is checked along with original 0..128 strip edges and
    calibration-profile centers 1..128. Missing calibrated spectra are recorded
    separately, since they cannot establish or invalidate this mapping.
    """
    import uproot
    selected = None if runs is None else set(runs)
    rows = [row for row in validate_manifest(Path(manifest))
            if selected is None or row.run_number in selected]
    periods, failures, unavailable = {}, [], []
    axes_by_period = defaultdict(list)
    with uproot.open(calibrated_flux) as calibrated, uproot.open(raw_flux) as raw:
        calibrated_keys, raw_keys = _keys(calibrated), _keys(raw)
        for row in rows:
            summary = periods.setdefault(row.source_period, dict(
                histograms_checked=0, content_mismatches=0, raw_axis_mismatches=0,
                calibration_profile_mismatches=0, negative_raw_bins_clamped=0,
                max_content_difference=0., runs_checked=[]))
            for state in STATES.values():
                name = f'run{row.run_number}_{state}'
                if not calibrated_keys[name]:
                    unavailable.append(name)
                    continue
                summary['histograms_checked'] += 1
                summary['runs_checked'].append(row.run_number)
                problems = []
                if len(calibrated_keys[name]) != 1 or len(raw_keys[name]) != 1:
                    failures.append(dict(histogram=name, reasons=['missing_or_duplicate_ROOT_key']))
                    continue
                values, edges = calibrated[name].to_numpy(flow=False)
                raw_values, raw_edges = raw[name].to_numpy(flow=False)
                if (values.shape != (128,) or edges.shape != (129,)
                        or not np.all(np.isfinite(edges)) or np.any(np.diff(edges) <= 0)
                        or not np.all(np.isfinite(values)) or np.any(values < 0)):
                    problems.append('invalid_calibrated_histogram')
                else:
                    axes_by_period[row.source_period].append(edges)
                if (raw_values.shape != (128,) or not np.all(np.isfinite(raw_values))
                        or raw_edges.shape != (129,)
                        or not np.allclose(raw_edges, np.arange(129), rtol=0, atol=1e-6)):
                    summary['raw_axis_mismatches'] += 1
                    problems.append('invalid_raw_strip_histogram')
                if values.shape == raw_values.shape == (128,):
                    expected = np.maximum(raw_values, 0.)
                    summary['negative_raw_bins_clamped'] += int(np.count_nonzero(raw_values < 0))
                    difference = float(np.max(np.abs(values - expected)))
                    summary['max_content_difference'] = max(summary['max_content_difference'], difference)
                    if not np.array_equal(values, expected):
                        summary['content_mismatches'] += 1
                        problems.append('strip_content_identity_failed')
                profile_name = f'calibration/{name}_profile'
                try:
                    profile_edges = calibrated[profile_name].axis().edges()
                    if (profile_edges.shape != (129,) or not np.array_equal(
                            profile_edges, np.arange(129) + .5)):
                        raise ValueError('profile strip centers differ')
                except (KeyError, ValueError, AttributeError):
                    summary['calibration_profile_mismatches'] += 1
                    problems.append('missing_or_invalid_independent_strip_calibration_profile')
                if problems:
                    failures.append(dict(histogram=name, reasons=problems))
    for period, summary in periods.items():
        summary['runs_checked'] = sorted(set(summary['runs_checked']))
        axes = axes_by_period[period]
        summary['unique_energy_axes'] = len({np.asarray(axis).tobytes() for axis in axes})
        summary['max_energy_edge_span_gev'] = float(np.max(np.ptp(axes, axis=0))) if axes else None
    source_root = Path(__file__).resolve().parents[1]
    writer = source_root / '06_calibration/build_strip_energy_flux.py'
    preanalysis = source_root / '01_pre_analysis/PreAnalysis.C'
    checked = sum(item['histograms_checked'] for item in periods.values())
    return dict(
        status='failed' if failures else ('verified' if checked else 'unvalidated'),
        scope='software strip-index mapping for available calibrated histograms',
        index_contract='array[i] = ROOT bin i+1 = xstrip i+1; no cross-period donor pooling',
        calibration_provenance=(
            'build_strip_energy_flux: read_calibration_cells uses h80 Xstrip and beam.E(); '
            '_fit_calibration_group fits energy versus strip; write_calibrated_flux_root '
            'copies max(0, raw bin content) without moving bins'),
        source_mapping_evidence=[
            dict(**_fingerprint(preanalysis), symbol='PreAnalysis: tagger_strip = Xstrip[0]'),
            dict(**_fingerprint(writer), symbol='read_calibration_cells; _fit_calibration_group; '
                 'write_calibrated_flux_root; read_flux_histograms')],
        limitations=['Software evidence does not independently certify historical hardware wiring.',
                     'Independent calibration metadata is for observable mapping, never target model features.',
                     'Missing calibrated spectra have no validated native mapping in this audit.'],
        inputs={name: _fingerprint(path) for name, path in
                [('manifest', manifest), ('calibrated_flux', calibrated_flux), ('raw_flux', raw_flux)]},
        periods=periods, failures=failures, unavailable_calibrated_histograms=unavailable)
