"""Unweighted physical controls of the selected eta/pi0 candle populations."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping, TYPE_CHECKING
from uuid import uuid4

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from plots.core.kinematics import quality_observables
from plots.quality import fit_mass

if TYPE_CHECKING:
    from observable_extraction.io.reconstructed_events import EventArrays


_SAMPLES = {'raw_bdt': ('Full', 'black'), 'full': ('Full', 'black'),
            'raw_bdt_core': ('Core', 'tab:blue'), 'raw_bdt_tails': ('Tails', 'tab:orange')}
_CONTROLS = {
    'eta_mass_gev': (r'Raw $M(\eta)$ [GeV]', (.45, .65)),
    'pi0_mass_gev': (r'Raw $M(\pi^0)$ [GeV]', (.05, .22)),
    'theta_missing_proton_deg': (r'$\theta_{missing}-\theta_{proton}$ [deg]', (-10., 10.)),
    'coplanarity_deg': (r'wrap($\phi_p-\phi_{\eta+\pi^0}-180^\circ$) [deg]', (-10., 10.)),
    'missing_mass_gev': (r'Signed $M(beam+target-\eta-\pi^0)$ [GeV]', (.8, 1.1)),
}
_FIT_WINDOWS = {'eta_mass_gev': (.50, .60), 'pi0_mass_gev': (.10, .17)}
_ANGLES = ('proton_theta_deg', 'theta_missing_proton_deg', 'coplanarity_deg')


def candle_quality_observables(events: EventArrays) -> dict[str, np.ndarray]:
    """Reuse the raw-vector adapter; undefined angles do not remove any row.

    Missing raw vectors and nonfinite vector components are explicit errors,
    as in the existing reconstruction quality adapter. Candidate mass NaNs
    remain independent of the vector controls and are audited per observable.
    """
    vectors = {}
    for name in ('proton', 'missing', 'beam', 'target', 'eta', 'pi0'):
        value = getattr(events, name, None)
        if value is None:
            raise ValueError(f'candle quality requires raw {name} four-vectors')
        value = np.asarray(value, dtype=float)
        if value.shape != (len(events), 4):
            raise ValueError(f'raw {name} must have shape (event_count, 4)')
        if not np.isfinite(value).all():
            raise ValueError(f'non-finite raw {name} four-vector in candle quality')
        vectors[name] = value
    result = {key: np.empty(len(events)) for key in (*_ANGLES, 'missing_mass_gev')}
    for index in range(len(events)):
        row = quality_observables(**{name: value[index] for name, value in vectors.items()})
        for name, value in row.items():
            result[name][index] = value
    for name in ('eta_mass_gev', 'pi0_mass_gev'):
        value = np.asarray(getattr(events, name), dtype=float)
        if value.shape != (len(events),):
            raise ValueError(f'{name} must have shape (event_count,)')
        result[name] = value
    result['beam_energy_gev'] = vectors['beam'][:, 3]
    return result


def _edges(arrays, default, bins=100):
    """Common plotting edges expand to include every finite value, without cuts."""
    low, high = default
    for values in arrays:
        finite = values[np.isfinite(values)]
        if finite.size:
            low = min(low, float(finite.min()))
            high = max(high, float(finite.max()))
    return np.linspace(low, high, bins + 1)


def _mass_fit(values, window):
    # Share the established diagnostic ROOT fit; do not refit the selection
    # ellipse or interpret the core/tail truncated shape as detector resolution.
    import ROOT
    ROOT.gROOT.SetBatch(True)
    histogram = ROOT.TH1D(f'candle_quality_{uuid4().hex}', '', 100, *window)
    histogram.SetDirectory(0)
    for value in values[np.isfinite(values)]:
        histogram.Fill(float(value))
    result = fit_mass(histogram, window)
    result['interpretation'] = 'diagnostic shape width; selected/truncated sample, not detector resolution or efficiency'
    return result


def _histogram(values, edges):
    finite = np.isfinite(values)
    counts, _ = np.histogram(values[finite], edges)
    total = int(finite.sum())
    density = counts / (total * np.diff(edges)) if total else np.zeros(len(counts))
    return dict(finite_count=total, nonfinite_count=int((~finite).sum()),
                counts=counts.tolist(), density=density.tolist())


def _save(figure, path):
    try:
        figure.savefig(path, format='pdf', bbox_inches='tight')
    finally:
        plt.close(figure)


def write_candle_quality_report(output_dir: Path, samples: Mapping[str, EventArrays]) -> dict:
    """Write six PDFs and a JSON count audit, with no weights or extra cuts.

    Samples may contain raw_bdt (or full), raw_bdt_core and raw_bdt_tails.
    Full overlaps core/tails: these descriptive distributions are not an
    independent-sample significance test. The PDF axes include every finite
    value; density uses each observable's finite count, documented in JSON.
    """
    if not samples or set(samples) - set(_SAMPLES):
        raise ValueError('quality samples must be full/raw_bdt, raw_bdt_core, raw_bdt_tails')
    if 'raw_bdt' in samples and 'full' in samples:
        raise ValueError('provide only one full sample: raw_bdt or full')
    values = {name: candle_quality_observables(events) for name, events in samples.items()}
    edges = {key: _edges([row[key] for row in values.values()], default)
             for key, (_, default) in _CONTROLS.items()}
    theta_edges = _edges([row['proton_theta_deg'] for row in values.values()], (0., 40.), 50)
    energy_edges = _edges([row['beam_energy_gev'] for row in values.values()], (.9, 1.55), 50)
    report = {
        'schema': 1, 'channel': 'eta_pi0', 'additional_plot_cuts': [],
        'weights': 'unit event counts; no flux, acceptance or efficiency correction',
        'normalization': 'counts / (finite count for this observable * bin width or bin area); empty densities are zero',
        'sample_dependence': 'full overlaps core and tails; no independent-sample inference',
        'nonfinite_vector_policy': 'reject report explicitly, never silently remove events',
        'undefined_direction_policy': 'zero momentum: undefined theta; zero transverse momentum: undefined phi; omit only affected angle and count it',
        'definitions': {
            'eta_mass_gev': 'raw eta_mass branch', 'pi0_mass_gev': 'raw pi0_mass branch',
            'theta_missing_proton_deg': 'theta(raw missing branch)-theta(measured proton), degrees',
            'coplanarity_deg': 'wrap(phi(measured proton)-phi(eta+pi0)-180 deg) in [-180,180)',
            'missing_mass_gev': 'signed sqrt((beam+target-eta-pi0)^2), TLorentzVector.M convention; not measured recoil mass',
            'beam_energy_vs_proton_theta': 'measured proton theta [deg], raw beam energy [GeV]',
        },
        'histogram_edges': {key: value.tolist() for key, value in edges.items()},
        'beam_energy_vs_proton_theta_edges': {'theta_deg': theta_edges.tolist(), 'energy_gev': energy_edges.tolist()},
        'samples': {}, 'pdf_files': [],
    }
    maps = {}
    for name, row in values.items():
        valid = np.isfinite(row['proton_theta_deg']) & np.isfinite(row['beam_energy_gev'])
        counts, _, _ = np.histogram2d(row['proton_theta_deg'][valid], row['beam_energy_gev'][valid],
                                       bins=(theta_edges, energy_edges))
        total = int(valid.sum())
        area = np.diff(theta_edges)[:, None] * np.diff(energy_edges)[None, :]
        density = counts / (total * area) if total else np.zeros_like(counts)
        maps[name] = (counts, density)
        report['samples'][name] = {
            'label': _SAMPLES[name][0], 'event_count': len(samples[name]),
            'undefined_angles': {key: int((~np.isfinite(row[key])).sum()) for key in _ANGLES},
            'histograms': {key: _histogram(row[key], edge) for key, edge in edges.items()},
            'mass_fits': {key: _mass_fit(row[key], window) for key, window in _FIT_WINDOWS.items()},
            'beam_energy_vs_proton_theta': dict(finite_count=total, nonfinite_count=int((~valid).sum()),
                                                counts=counts.astype(int).tolist(), density=density.tolist()),
        }
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    for key, (label, _) in _CONTROLS.items():
        figure, axes = plt.subplots(1, 2, figsize=(12., 4.7), constrained_layout=True)
        for name, sample in report['samples'].items():
            histogram = sample['histograms'][key]
            legend = f"{sample['label']}: N={sample['event_count']}, finite={histogram['finite_count']}"
            for axis, column in zip(axes, ('counts', 'density')):
                axis.stairs(histogram[column], edges[key], label=legend, color=_SAMPLES[name][1])
        for axis, title, ylabel in zip(axes, ('Raw counts', 'Unit-area comparison'), ('Events / bin', 'Probability density')):
            axis.set(xlabel=label, ylabel=ylabel, title=title)
            axis.legend(fontsize=8)
            axis.grid(alpha=.2)
        figure.suptitle('Selected raw eta/pi0: full / core / tails')
        if key in _FIT_WINDOWS:
            notes = []
            for sample in report['samples'].values():
                fit = sample['mass_fits'][key]
                detail = (f"mean={fit['mean_gev']:.4f}, sigma={fit['sigma_gev']:.4f} GeV"
                          if fit['status'] == 'ok' else fit['status'])
                notes.append(f"{sample['label']}: {detail}")
            axes[1].text(.02, .03, 'Diagnostic Gaussian fit (selected shape)\n' + '\n'.join(notes),
                         transform=axes[1].transAxes, fontsize=8, va='bottom',
                         bbox=dict(facecolor='white', alpha=.85, edgecolor='0.8'))
        filename = f'quality_{key}.pdf'
        _save(figure, output_dir / filename)
        report['pdf_files'].append(filename)
    figure, axes = plt.subplots(2, len(samples), figsize=(5. * len(samples), 8.),
                                constrained_layout=True, squeeze=False)
    for index, name in enumerate(samples):
        sample = report['samples'][name]
        for row_index, mode in enumerate(('Raw counts', 'Unit-area density')):
            maximum = max(float(value[row_index].max()) for value in maps.values())
            artist = axes[row_index, index].pcolormesh(theta_edges, energy_edges, maps[name][row_index].T,
                                                      vmin=0., vmax=maximum or 1., shading='auto', rasterized=True)
            axes[row_index, index].set(xlabel=r'Measured proton $\theta$ [deg]', ylabel='Beam energy [GeV]',
                                      title=f"{sample['label']}: N={sample['event_count']}, finite={sample['beam_energy_vs_proton_theta']['finite_count']}\n{mode}")
            figure.colorbar(artist, ax=axes[row_index, index], label='Events / bin' if row_index == 0 else 'Probability / (deg GeV)')
    filename = 'quality_beam_energy_vs_proton_theta.pdf'
    _save(figure, output_dir / filename)
    report['pdf_files'].append(filename)
    (output_dir / 'quality_audit.json').write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + '\n')
    return report
