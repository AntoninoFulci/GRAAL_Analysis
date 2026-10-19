"""Energy-view diagnostics after native predictions; axes never enter fitting."""
from collections import defaultdict
from pathlib import Path
import csv
import json

import numpy as np


def clustered_coverage_intervals(rows, clusters, *, seed=142, resamples=4000):
    """Descriptive confidence intervals resampling whole assumed donor clusters.

    The input rows contain one target spectrum each. Correlated strips are
    already summarized within each row. Too few clusters remain unvalidated;
    no additional independence is manufactured by counting strips as trials.
    """
    rng = np.random.default_rng(seed)
    groups = defaultdict(list)
    for row in rows:
        groups[row['period'], row['state'], row['method']].append(row)
    result = []
    for (period, state, method), group in sorted(groups.items()):
        summary = dict(period=period, state=state, method=method, requested_targets=len(group),
                       interpretation='Assumes independent central donor/masking clusters; excludes shared fitted-model and residual-pool dependence. Conditional development diagnostic only.')
        for metric in ('coverage68', 'coverage95', 'integral_covered68', 'integral_covered95'):
            blocks = defaultdict(list)
            for row in group:
                if row[metric] is not None:
                    blocks[clusters[period][row['run']]].append(float(row[metric]))
            arrays = list(blocks.values())
            n = sum(map(len, arrays))
            observed = sum(map(sum, arrays))/n if n else None
            ci = None
            boundary = observed in (0., 1.)
            constant = bool(arrays) and np.ptp([np.mean(a) for a in arrays]) < 1e-15
            if len(arrays) >= 5 and not constant:
                choices = rng.integers(0, len(arrays), (resamples, len(arrays)))
                sums, sizes = np.array(list(map(sum, arrays))), np.array(list(map(len, arrays)))
                rates = sums[choices].sum(axis=1)/sizes[choices].sum(axis=1)
                ci = np.quantile(rates, [.025, .975]).tolist()
            nominal = .68 if metric.endswith('68') else .95
            summary[metric] = dict(observed=observed, evaluable_targets=n, donor_clusters=len(arrays),
                                   interval95=ci, nominal=nominal,
                                   nominal_inside_interval=None if ci is None else ci[0] <= nominal <= ci[1],
                                   status=('conditional_diagnostic' if ci is not None else
                                           'boundary_uninformative' if boundary and len(arrays) >= 5 else
                                           'constant_cluster_coverage' if constant and len(arrays) >= 5 else 'insufficient_clusters'))
        result.append(summary)
    return result


def plot_published_energy_views(directory):
    """Render already-frozen held-out predictions using independent target axes."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages
    from flux_studies.neighbor_plots import _save
    directory = Path(directory)
    calibration = json.loads((directory / 'native_calibration_axes.json').read_text())
    axes_by_key = {(r['period'], r['run'], r['state']): np.asarray(r['calibration_edges']) for r in calibration}
    blocks = sorted(directory.glob('block_*'))
    if len(blocks) != 1:
        raise ValueError('native diagnostics require exactly one benchmark block directory')
    block = blocks[0]
    with (block / 'predictions.csv').open() as stream:
        metadata = list(csv.DictReader(stream))
    with np.load(block / 'spectra.npz') as archive:
        arrays = dict(archive)
    if (directory / 'flux_uncertainty.json').exists():
        from flux_studies.flux_uncertainty import _clusters
        from flux_studies.reporting import write_json
        uncertainty = json.loads((directory / 'flux_uncertainty.json').read_text())
        splits = json.loads((block / 'splits.json').read_text())
        clusters = {}
        for period, assignments in splits.items():
            central = [dict(run=int(p['run']), donors=json.loads(p['donors'])) for p in metadata
                       if p['role'] == 'test' and p['period'] == period and p['method'] == 'linear']
            clusters[period] = _clusters(central, {a['run']: a['block'] for a in assignments})
        write_json(directory / 'coverage_cluster_intervals.json',
                   clustered_coverage_intervals(uncertainty['target_summary'], clusters))
    by_target = defaultdict(list)
    methods = ('linear', 'extra_trees_hybrid', 'kernel_ridge_hybrid', 'mlp_hybrid', 'cnn1d_hybrid')
    for i, p in enumerate(metadata):
        if p['role'] == 'test' and p['method'] in methods:
            by_target[p['period'], int(p['run']), p['state']].append((i, p))
    with PdfPages(directory / 'energy_overlays.pdf') as pdf:
        for key, rows in sorted(by_target.items()):
            edges = axes_by_key[key]
            centers = .5 * (edges[1:] + edges[:-1])
            truth = arrays['truth'][rows[0][0]]
            fig, axes = plt.subplots(2, 1, figsize=(11, 7), sharex=True)
            axes[0].stairs(truth, edges, color='black', lw=1.5, label='Measured')
            for i, p in rows:
                values = arrays['estimate'][i]
                axes[0].stairs(values, edges, label=p['method'], lw=.9)
                axes[1].plot(centers, np.divide(values, truth, out=np.full(128, np.nan), where=truth > 0), lw=.8)
            axes[0].set(ylabel='Flux / native strip bin')
            axes[0].legend(fontsize=8)
            axes[1].axhline(1, color='black', lw=.7)
            axes[1].set(xlabel='Photon energy [GeV], independent target calibration', ylabel='Predicted / measured')
            for ax in axes:
                ax.grid(alpha=.2)
            fig.suptitle(f'{key[0]} run {key[1]} {key[2]}\nNative predictions; energy axis applied only after fitting')
            _save(pdf, fig)
    fits = json.loads((block / 'fits.json').read_text())
    with PdfPages(directory / 'neural_learning.pdf') as pdf:
        for fit in fits:
            fig, axes = plt.subplots(2, 2, figsize=(12, 8))
            for column, family in enumerate(('mlp', 'cnn1d')):
                metadata = fit['models'].get(family, {})
                diagnostic = metadata.get('fit_diagnostics', {}).get(family + '_hybrid')
                if diagnostic is None:
                    for ax in axes[:, column]:
                        ax.text(.5, .5, f'{family}: fit unavailable\nInsufficient training or family not requested',
                                transform=ax.transAxes, ha='center', va='center')
                        ax.set_axis_off()
                    continue
                for member in diagnostic['initializations']:
                    loss = member['loss_history']
                    axes[0, column].plot(np.arange(1, len(loss)+1), loss, label=f"seed {member['seed']}")
                axes[0, column].set(xlabel='Epoch', ylabel='Training KL divergence', title=f'{family}: selected full-training fit')
                axes[0, column].legend(fontsize=7)
                for i, candidate in enumerate(metadata['candidates']):
                    error = candidate['hybrid']['relative_l1']
                    final_losses = [m['final_loss'] for fold in candidate['folds']
                                    if fold.get('fit_diagnostics') for m in fold['fit_diagnostics']['initializations']]
                    axes[1, column].scatter(i, error, color='tab:orange', label='Inner held-out L1' if i == 0 else None)
                    if final_losses:
                        axes[1, column].scatter(i, np.mean(final_losses), color='tab:blue', marker='x', label='Mean training KL' if i == 0 else None)
                axes[1, column].set_xticks(range(len(metadata['candidates'])),
                    [f"width={c['parameters']['width']}\nweight decay={c['parameters']['weight_decay']:g}"
                     for c in metadata['candidates']], fontsize=7)
                axes[1, column].set(ylabel='Different losses, shown separately', title='Grid: training fit and held-out error')
                axes[1, column].legend(fontsize=7)
            fig.suptitle(f"{fit['group'][0]} {fit['group'][-1]}: neural convergence and grid diagnostics\nTraining KL and held-out L1 are different metrics; compare candidates within each metric")
            _save(pdf, fig)
    if not (directory / 'candidate_predictions.csv').exists():
        return
    attempts = (directory / 'candidate_attempts.csv').exists()
    with (directory / ('candidate_attempts.csv' if attempts else 'candidate_predictions.csv')).open() as stream:
        candidate_rows = list(csv.DictReader(stream))
    with np.load(directory / ('candidate_attempt_spectra.npz' if attempts else 'candidate_spectra.npz')) as archive:
        candidate_values = archive['estimate']
    grouped = defaultdict(list)
    for i, row in enumerate(candidate_rows):
        grouped[row['period'], int(row['run']), row['state']].append((i, row))
    with PdfPages(directory / 'missing_native_candidates.pdf') as pdf:
        for key, rows in sorted(grouped.items()):
            fig, axes = plt.subplots(2, 1, figsize=(11, 7), sharex=True)
            for i, row in rows:
                value = candidate_values[i]
                axes[0].plot(np.arange(1, 129), value, label=row['method'])
                axes[1].plot(np.arange(1, 129), value / value.sum())
            axes[0].set(ylabel='Flux / native strip')
            axes[0].legend(fontsize=8)
            axes[1].set(xlabel='Native tagger strip', ylabel='Normalized shape')
            support = ('; OUTSIDE validated support' if any(row.get('supported') == 'False' for _, row in rows) else '')
            reason = rows[0][1].get('missing_reason', 'missing_calibrated')
            fig.suptitle(f'{key[0]} run {key[1]} {key[2]}: {reason}{support}\nExperimental candidate: measured reference unavailable; no production adoption', fontsize=11)
            _save(pdf, fig)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    plot_published_energy_views(parser.parse_args().directory)
