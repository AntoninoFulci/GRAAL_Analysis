"""Complete held-out spectrum atlases and diagnostics for neighbor benchmarks."""
from __future__ import annotations

from collections import defaultdict
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

from flux_studies.reporting import write_json

COLORS = dict(nearest='#777777', linear_unscaled='#8e44ad', linear='#d97706', extra_trees_hybrid='#1261a0')
LABELS = dict(nearest='Nearest / events', linear_unscaled='Interpolation without counts',
              linear='Two neighbors / events', extra_trees_hybrid='Extra Trees hybrid / events')


def _save(pdf, fig, png=None):
    fig.tight_layout(rect=(0, 0, 1, .95))
    pdf.savefig(fig)
    if png is not None:
        fig.savefig(png, dpi=130)
    plt.close(fig)


FAMILY_LABELS = {'ridge': 'Ridge', 'kernel_ridge': 'Kernel Ridge', 'extra_trees': 'Extra Trees',
                 'mlp': 'PyTorch MLP', 'cnn1d': 'PyTorch CNN 1D'}


def _overlay(rows, energy, xlabel=r'$E_\gamma$ [GeV]'):
    first = rows[0]
    truth = first['truth']
    families = [f for f in FAMILY_LABELS if any(r['method'] in (f, f + '_hybrid') for r in rows)] or ['ridge']
    if len(families) == 1:
        fig, grid = plt.subplots(2, 2, figsize=(12, 8), sharex=True)
        columns = [list(grid.flat)]
    else:
        fig, grid = plt.subplots(4, len(families), figsize=(6 * len(families), 13), sharex=True, squeeze=False)
        columns = [list(grid[:, i]) for i in range(len(families))]
    for family, axes in zip(families, columns, strict=True):
        axes[0].step(energy, truth, where='mid', color='black', label='Measured truth', linewidth=1.4)
        if truth.sum() > 0:
            axes[1].step(energy, truth / truth.sum(), where='mid', color='black', label='Measured truth')
        for row in rows:
            method = row['method']
            if method not in ('linear', family, family + '_hybrid'):
                continue
            color = '#d97706' if method == 'linear' else '#16803c' if method.endswith('_hybrid') else '#1261a0'
            label = 'Two neighbors / events' if method == 'linear' else FAMILY_LABELS[family] + (' hybrid' if method.endswith('_hybrid') else ' direct')
            style = '--' if method.endswith('_hybrid') else '-'
            values = row['estimate']
            axes[0].step(energy, values, where='mid', color=color, linestyle=style, label=label)
            for level, alpha in ((95, .07), (68, .13)):
                if row.get(f'lower{level}') is not None:
                    axes[0].fill_between(energy, row[f'lower{level}'], row[f'upper{level}'], step='mid', color=color, alpha=alpha)
            if values.sum() > 0:
                axes[1].step(energy, values / values.sum(), where='mid', color=color, linestyle=style, label=label)
            ratio = np.divide(values, truth, out=np.full_like(values, np.nan), where=truth > 0)
            axes[2].plot(energy, ratio, color=color, linestyle=style, linewidth=1)
            if truth.sum() > 0:
                axes[3].plot(energy, (values - truth) / truth.sum(), color=color, linestyle=style)
        axes[0].set(ylabel='Photon flux / bin', title=FAMILY_LABELS[family] + ': direct vs hybrid; 68/95% bands')
        axes[1].set(ylabel='Fraction / bin', title='Unit-area shape')
        axes[2].axhline(1, color='black', linewidth=.6)
        axes[2].set(ylabel='Prediction / truth (truth > 0)', xlabel=xlabel)
        axes[3].axhline(0, color='black', linewidth=.6)
        axes[3].set(ylabel='Residual / true integral', xlabel=xlabel)
        for ax in axes[:2]:
            ax.legend(fontsize=7)
        for ax in axes:
            ax.grid(alpha=.15)
    fig.suptitle(f"{first['period']} | run {first['run']} | {first['state']} | DEVELOPMENT HOLDOUT\n"
                 f"Donors {first['donors']} | {first['count']:,} h80 events | assumed gap {first['gap']:.0f} min")
    return fig


def plot_benchmark(directory, dataset, study):
    directory.mkdir(exist_ok=True)
    native = dataset.get('representation') == 'native_strip'
    edges = np.arange(.5, 129.5) if native else dataset['energy_edges']
    xlabel = 'Native tagger strip (xstrip)' if native else r'$E_\gamma$ [GeV]'
    energy = (edges[:-1] + edges[1:]) / 2
    test = [p for p in study['predictions'] if p['role'] == 'test']
    by_target = defaultdict(list)
    for p in test:
        by_target[(p['period'], p['run'], p['state'])].append(p)
    atlas_index = []
    for period in sorted({key[0] for key in by_target}):
        filename = f'overlays_{period}.pdf'
        targets = sorted(k for k in by_target if k[0] == period)
        ranked = sorted(targets, key=lambda k: next((p['relative_l1'] or 0 for p in by_target[k]
                                                    if p['method'] == 'linear'), 0))
        selected = {ranked[len(ranked)//2]: 'median', ranked[-1]: 'largest_error'} if ranked else {}
        with PdfPages(directory / filename) as pdf:
            for page, key in enumerate(targets, 1):
                rows = by_target[key]
                png = directory / f'example_{period}_{selected[key]}.png' if key in selected else None
                _save(pdf, _overlay(rows, energy, xlabel), png)
                atlas_index.append(dict(period=period, run=key[1], state=key[2], atlas=filename, page=page))
    write_json(directory / 'overlay_index.json', atlas_index)

    with PdfPages(directory / 'diagnostics.pdf') as pdf:
        for period in sorted(study['splits']):
            fig, axes = plt.subplots(1, 3, figsize=(15, 4))
            for state in ('POL1', 'POL2', 'BREM'):
                rows = [r for r in dataset['records'] if r['period'] == period and r['state'] == state]
                axes[0].scatter([r['count'] for r in rows], [r['values'].sum() for r in rows], s=9, label=state)
                axes[1].plot([r['run'] for r in rows], [r['values'].sum()/r['count'] for r in rows], '.', label=state)
            for role, y in [('train', 0), ('validation', 1), ('test', 2)]:
                runs = [r['run'] for r in study['splits'][period] if r['role'] == role]
                axes[2].scatter(runs, [y]*len(runs), s=12, label=role)
            axes[0].set(xlabel='Inclusive h80 events', ylabel='Measured photon flux', xscale='log', yscale='log')
            axes[1].set(xlabel='Run', ylabel='Measured flux / h80 event', yscale='log')
            axes[2].set(xlabel='Run', yticks=[0, 1, 2], yticklabels=['train', 'interval calibration', 'test'])
            for ax in axes[:2]:
                ax.legend(fontsize=8)
            fig.suptitle(f'{period}: normalization and split | {study["block_size"]}-run masking blocks')
            _save(pdf, fig, directory / f'normalization_{period}.png')

        fig, axes = plt.subplots(2, 2, figsize=(12, 9))
        for index, method in enumerate(COLORS):
            rows = [p for p in test if p['method'] == method]
            if not rows:
                continue
            color = COLORS[method]
            axes[0, 0].scatter([p['true_integral'] for p in rows], [p['predicted_integral'] for p in rows],
                               s=12, alpha=.55, color=color, label=f'{LABELS[method]} (n={len(rows)})')
            for ax, metric in [(axes[0, 1], 'relative_integral_error'), (axes[1, 0], 'shape_l1')]:
                values = [p[metric] for p in rows if p[metric] is not None]
                if values:
                    ax.boxplot([values], positions=[index], widths=.6, showfliers=True,
                               medianprops={'color': color})
            coverage = [p.get('coverage95') for p in rows if p.get('coverage95') is not None]
            if coverage:
                axes[1, 1].scatter(index, np.mean(coverage), color=color, marker='o')
            coverage68 = [p.get('coverage68') for p in rows if p.get('coverage68') is not None]
            if coverage68:
                axes[1, 1].scatter(index, np.mean(coverage68), color=color, marker='x')
        positive = [p['true_integral'] for p in test if p['true_integral'] > 0]
        if positive:
            axes[0, 0].plot([min(positive), max(positive)], [min(positive), max(positive)], 'k--', linewidth=.7)
        axes[0, 0].set(xscale='log', yscale='log', xlabel='True integral', ylabel='Predicted integral')
        axes[0, 0].legend(fontsize=7)
        axes[0, 1].set(ylabel='Relative integral error')
        axes[0, 1].set_yscale('symlog', linthresh=.1)
        axes[0, 1].axhline(0, color='gray', linewidth=.7)
        axes[1, 0].set(ylabel='Shape L1 (0 = exact, 2 = disjoint)')
        axes[1, 0].set_yscale('symlog', linthresh=.1)
        axes[1, 1].set(ylabel='Active-bin marginal coverage', ylim=(0, 1.05), title='o: 95%; x: 68%; empirical bands')
        for y in (.68, .95):
            axes[1, 1].axhline(y, color='gray', linestyle='--', linewidth=.7)
        for ax in (axes[0, 1], axes[1, 0], axes[1, 1]):
            ax.set_xticks(range(len(COLORS)), ['Nearest', 'Unscaled', 'Linear', 'Trees hybrid'], rotation=15)
        fig.suptitle(f'Development held-out performance | block size {study["block_size"]}')
        _save(pdf, fig, directory / 'performance.png')

        fig, axes = plt.subplots(1, 3, figsize=(15, 4))
        paired = []
        for rows in by_target.values():
            methods = {p['method']: p for p in rows}
            if all(m in methods and methods[m]['relative_l1'] is not None for m in ('linear', 'extra_trees_hybrid')):
                paired.append(methods)
        if paired:
            linear = [r['linear']['relative_l1'] for r in paired]
            ridge = [r['extra_trees_hybrid']['relative_l1'] for r in paired]
            axes[0].scatter(linear, ridge, s=13, alpha=.65)
            maximum = max(linear + ridge)
            axes[0].plot([0, maximum], [0, maximum], 'k--', linewidth=.7)
        axes[0].set(xlabel='Interpolation relative L1', ylabel='Extra Trees hybrid relative L1', title=f'Paired test targets: {len(paired)}')
        axes[0].set_xscale('symlog', linthresh=.1)
        axes[0].set_yscale('symlog', linthresh=.1)
        for method in ('linear', 'extra_trees_hybrid'):
            rows = [p for p in test if p['method'] == method and p['relative_l1'] is not None]
            axes[1].scatter([p['count'] for p in rows], [p['relative_l1'] for p in rows],
                            s=12, alpha=.6, color=COLORS[method], label=method)
            axes[2].scatter([p['gap'] for p in rows], [p['relative_l1'] for p in rows],
                            s=12, alpha=.6, color=COLORS[method], label=method)
        axes[1].set(xlabel='Target h80 events', xscale='log', ylabel='Relative L1 error')
        axes[2].set(xlabel='Assumed donor separation [min]', ylabel='Relative L1 error')
        axes[1].set_yscale('symlog', linthresh=.1)
        axes[2].set_yscale('symlog', linthresh=.1)
        axes[1].legend(); axes[2].legend()
        fig.suptitle('Paired comparison and robustness')
        _save(pdf, fig, directory / 'paired_errors.png')

        for period in sorted(study['splits']):
            for state in ('POL1', 'POL2', 'BREM'):
                fig, axes = plt.subplots(2, 2, figsize=(12, 7), sharex='col')
                has_rows = False
                for col, method in enumerate(('linear', 'extra_trees_hybrid')):
                    rows = sorted([p for p in test if p['period'] == period and p['state'] == state
                                   and p['method'] == method and p['true_integral'] > 0], key=lambda p: p['run'])
                    if not rows:
                        continue
                    has_rows = True
                    residuals = np.array([(p['estimate']-p['truth'])/p['true_integral'] for p in rows])
                    limit = max(float(np.max(np.abs(residuals))), 1e-12)
                    im = axes[0, col].imshow(residuals, origin='lower', aspect='auto', cmap='RdBu_r',
                                             vmin=-limit, vmax=limit,
                                             extent=(edges[0], edges[-1], -.5, len(rows)-.5))
                    axes[0, col].set(title=LABELS[method], ylabel='Test run (sorted)')
                    ticks = np.unique(np.linspace(0, len(rows)-1, min(6, len(rows)), dtype=int))
                    axes[0, col].set_yticks(ticks, [str(rows[i]['run']) for i in ticks])
                    fig.colorbar(im, ax=axes[0, col], label='Residual / true integral')
                    axes[1, col].plot(energy, residuals.mean(axis=0), color=COLORS[method])
                    axes[1, col].axhline(0, color='gray', linewidth=.7)
                    axes[1, col].set(xlabel=xlabel, ylabel='Mean relative spectral residual')
                if has_rows:
                    fig.suptitle(f'{period} {state}: test spectral bias')
                    _save(pdf, fig)
                else:
                    plt.close(fig)

        fig, axes = plt.subplots(1, 2, figsize=(12, 4))
        for fit in study['fits']:
            candidates = fit.get('models', {}).get('extra_trees', {}).get('candidates', [])
            if candidates:
                axes[0].plot(range(len(candidates)), [c['hybrid']['relative_l1'] for c in candidates],
                             '.-', label=f'{fit["group"][0]} {fit["group"][-1]}')
        axes[0].set(xlabel='Extra Trees grid candidate', ylabel='Inner hold-out relative L1', title='Training-only model selection')
        if axes[0].lines:
            axes[0].legend(fontsize=7)
        for method in ('linear', 'extra_trees_hybrid'):
            errors = []
            for role in ('train', 'validation', 'test'):
                values = [p['relative_l1'] for p in study['predictions'] if p['method'] == method
                          and p['role'] == role and p['relative_l1'] is not None]
                errors.append(float(np.mean(values)) if values else np.nan)
            axes[1].plot(['train*', 'validation', 'test'], errors, '.-', color=COLORS[method], label=method)
        axes[1].set(ylabel='Mean relative L1', title='*ML train error is in-sample')
        axes[1].legend()
        fig.suptitle('Fit diagnostics; development holdout never used for parameter selection')
        _save(pdf, fig, directory / 'training.png')
    if any(fit.get('models') for fit in study['fits']):
        _model_diagnostics(directory, study)


def _model_diagnostics(directory, study):
    """Show every grid trial and matched default-vs-tuned comparisons."""
    test = [p for p in study['predictions'] if p['role'] == 'test']
    families = [f for f in FAMILY_LABELS if any(p['method'] == f for p in test)]
    methods = ['linear', *[m for f in families for m in (f, f + '_hybrid')]]
    short = lambda method: 'Linear' if method == 'linear' else method.replace('kernel_ridge', 'Kernel').replace('extra_trees', 'Trees').replace('ridge', 'Ridge').replace('_hybrid', ' hybrid')
    with PdfPages(directory / 'model_comparison.pdf') as pdf:
        fig, axes = plt.subplots(1, 3, figsize=(18, 5))
        for ax, metric, title in zip(axes, ('relative_l1', 'relative_integral_error', 'shape_l1'),
                                     ('Spectrum relative L1', 'Absolute relative integral error', 'Unit-area shape L1'), strict=True):
            labels = []
            for index, method in enumerate(methods):
                values = [abs(p[metric]) for p in test if p['method'] == method and p.get(metric) is not None]
                labels.append(f'{short(method)}\nn={len(values)}')
                if values:
                    ax.boxplot([values], positions=[index], widths=.6)
            ax.set_xticks(range(len(methods)), labels, rotation=60, ha='right', fontsize=8)
            ax.set(title=title, ylabel='Error (lower is better)', yscale='symlog')
            ax.set_yscale('symlog', linthresh=.03)
            ax.grid(axis='y', alpha=.2)
        fig.suptitle(f'All tuned models and hybrids | block {study["block_size"]} | DEVELOPMENT HOLDOUT')
        _save(pdf, fig, directory / 'all_models.png')

        if families:
            fig, axes = plt.subplots(2, len(families), figsize=(6 * len(families), 8), squeeze=False)
            for col, family in enumerate(families):
                for row, hybrid in enumerate((False, True)):
                    suffix = '_hybrid' if hybrid else ''
                    tuned_name, default_name = family + suffix, family + '_default' + suffix
                    key = lambda p: (p['period'], p['run'], p['state'])
                    tuned = {key(p): p for p in test if p['method'] == tuned_name and p.get('relative_l1') is not None}
                    default = {key(p): p for p in test if p['method'] == default_name and p.get('relative_l1') is not None}
                    common = sorted(tuned.keys() & default.keys())
                    x = [default[k]['relative_l1'] for k in common]
                    y = [tuned[k]['relative_l1'] for k in common]
                    ax = axes[row, col]
                    ax.scatter(x, y, s=12, alpha=.6)
                    if common:
                        upper = max(x + y)
                        ax.plot([0, upper], [0, upper], 'k--', linewidth=.7)
                    ax.set(title=f'{FAMILY_LABELS[family]} {"hybrid" if hybrid else "direct"}; n={len(common)}',
                           xlabel='Default relative L1', ylabel='Grid-selected relative L1')
                    ax.set_xscale('symlog', linthresh=.03)
                    ax.set_yscale('symlog', linthresh=.03)
                    ax.grid(alpha=.15)
            fig.suptitle('Does parameter tuning help? Below diagonal = tuned improves\nMatched development holdouts; selection used training folds only')
            _save(pdf, fig, directory / 'default_vs_tuned.png')

        fig, axes = plt.subplots(1, 2, figsize=(14, 5))
        for i, method in enumerate(methods):
            rows = [p for p in test if p['method'] == method]
            for ax, prefix in zip(axes, ('coverage', 'integral_covered'), strict=True):
                for level, marker in ((68, 'x'), (95, 'o')):
                    values = [float(p[f'{prefix}{level}']) for p in rows if p.get(f'{prefix}{level}') is not None]
                    if values:
                        ax.scatter(i, np.mean(values), marker=marker, color='#1261a0')
        for ax, title in zip(axes, ('Active-bin marginal coverage', 'Integral coverage'), strict=True):
            ax.set(ylim=(0, 1.05), title=title, ylabel='Empirical coverage')
            ax.set_xticks(range(len(methods)), [short(m) for m in methods], rotation=45, ha='right')
            for level in (.68, .95):
                ax.axhline(level, linestyle='--', color='gray', linewidth=.7)
        fig.suptitle('Validation-calibrated empirical bands | x: 68%, o: 95% | no coverage guarantee')
        _save(pdf, fig, directory / 'all_model_coverage.png')

    with PdfPages(directory / 'grid_search.pdf') as pdf:
        for fit in study['fits']:
            models = fit.get('models', {})
            if not models:
                continue
            fig, axes = plt.subplots(len(models), 2, figsize=(12, 4 * len(models)), squeeze=False)
            for row_index, (family, record) in enumerate(models.items()):
                candidates = record['candidates']
                for col, kind in enumerate(('direct', 'hybrid')):
                    ax = axes[row_index, col]
                    valid = [c for c in candidates if c[kind].get('relative_l1') is not None]
                    if not valid:
                        ax.text(.5, .5, 'No usable inner validation targets', ha='center')
                        continue
                    names = sorted(valid[0]['parameters'])
                    if len(names) == 1:
                        name = names[0]
                        ordered = sorted(valid, key=lambda c: c['parameters'][name])
                        ax.plot([c['parameters'][name] for c in ordered], [c[kind]['relative_l1'] for c in ordered], '.-')
                        ax.set(xscale='log', xlabel=name, ylabel='Inner validation relative L1')
                        selected = record['selected'][kind]
                        if selected:
                            choice = next(c for c in valid if c['parameters'] == selected)
                            ax.scatter([selected[name]], [choice[kind]['relative_l1']], marker='*', color='red', s=110)
                    else:
                        yname, xname = names[:2]
                        ys = sorted({c['parameters'][yname] for c in valid})
                        xs = sorted({c['parameters'][xname] for c in valid})
                        matrix = np.full((len(ys), len(xs)), np.nan)
                        for candidate in valid:
                            matrix[ys.index(candidate['parameters'][yname]), xs.index(candidate['parameters'][xname])] = candidate[kind]['relative_l1']
                        image = ax.imshow(matrix, origin='lower', aspect='auto', cmap='viridis_r')
                        ax.set_xticks(range(len(xs)), [str(x) for x in xs])
                        ax.set_yticks(range(len(ys)), [str(y) for y in ys])
                        ax.set(xlabel=xname, ylabel=yname)
                        for (iy, ix), value in np.ndenumerate(matrix):
                            if np.isfinite(value):
                                color = 'black' if image.norm(value) < .45 else 'white'
                                ax.text(ix, iy, f'{value:.3g}', ha='center', va='center', color=color, fontsize=9)
                        selected = record['selected'][kind]
                        if selected:
                            ax.scatter(xs.index(selected[xname]) + .3, ys.index(selected[yname]) + .3,
                                       marker='*', color='red', s=130)
                        fig.colorbar(image, ax=ax, label='Inner validation relative L1')
                    ax.set_title(f'{FAMILY_LABELS[family]} {kind}; red star = selected')
            fig.suptitle(f'{fit["group"][0]} {fit["group"][-1]} | training-only grid | block {study["block_size"]}')
            _save(pdf, fig, directory / f'grid_{fit["group"][0]}_{fit["group"][-1]}.png')
