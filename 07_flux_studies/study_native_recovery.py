"""Local native-strip grid search, correlated uncertainty and recovery benefit."""
from __future__ import annotations

import argparse
import json
import platform
from pathlib import Path
import sys
import time

import numpy as np

from calibration.run_quality import DEFAULT_RUN_QUALITY_PATH
from flux_studies.calibrated_data import load_calibrated_dataset
from flux_studies.flux_uncertainty import neighbor_replicas, closure_replicas
from flux_studies.neighbor_validation import evaluate_neighbors, predict_missing_neighbors
from flux_studies.reporting import publish_output, write_json, write_csv
from flux_studies.strip_audit import audit_native_strips
from flux_studies.study_calibrated_neighbors import _write_benchmark
from flux_studies.study_realistic_gaps import restrict_test_states, require_mask_coverage
from flux_studies.study_realistic_gaps import candidate_support

FAMILIES = ('ridge', 'kernel_ridge', 'extra_trees', 'mlp', 'cnn1d')
METHODS = ('linear', 'extra_trees_hybrid', 'kernel_ridge_hybrid', 'mlp_hybrid', 'cnn1d_hybrid')


def load_cached_counts(path):
    """Validate the previously scanned inclusive cache against local h80 identity."""
    import uproot
    cache = json.loads(Path(path).read_text())
    counts = {}
    for row in cache['counts']:
        if any(isinstance(row[k], bool) or not isinstance(row[k], int) or row[k] <= 0 for k in ('run', 'count')):
            raise ValueError('inclusive run and event counts must be positive integers')
        key = (int(row['run']), row['state'])
        if key in counts or row['state'] not in ('POL1', 'POL2', 'BREM') or row['count'] <= 0:
            raise ValueError('invalid or duplicate inclusive count cache entry')
        counts[key] = int(row['count'])
    uuids = set()
    for source in cache['sources']:
        with uproot.open(source['path']) as f:
            uuid = str(f.file.uuid)
            if uuid != source['uuid'] or int(f['h80'].num_entries) != source['entries'] or uuid in uuids:
                raise ValueError('inclusive cache h80 provenance mismatch')
            uuids.add(uuid)
    if sum(counts.values()) != sum(s['entries'] for s in cache['sources']):
        raise ValueError('inclusive count cache does not cover all h80 entries')
    return counts, cache['sources']


def _uncertainty_plots(directory, uncertainty, study):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages
    from flux_studies.neighbor_plots import _save
    keys, draws = uncertainty['keys'], uncertainty['draws']
    rows = uncertainty['target_summary']
    with PdfPages(directory / 'flux_uncertainty.pdf') as pdf:
        for period in sorted(study['splits']):
            fig, axes = plt.subplots(1, 3, figsize=(15, 4))
            for j, method in enumerate(METHODS):
                group = [r for r in rows if r['period'] == period and r['method'] == method]
                if not group:
                    continue
                axes[0].plot([r['run'] for r in group], [r['valid_replicas'] for r in group], '.', label=method)
                for level, marker in ((68, 'x'), (95, 'o')):
                    for ax, field in ((axes[1], 'coverage'), (axes[2], 'integral_covered')):
                        values = [r[f'{field}{level}'] for r in group if r[f'{field}{level}'] is not None]
                        if values:
                            ax.scatter(j, np.mean(values), marker=marker)
            axes[0].set(xlabel='Run', ylabel='Valid replicas / requested', title=f"Requested: {uncertainty['requested_replicas']}")
            axes[0].legend(fontsize=6)
            for ax, title in zip(axes[1:], ('Marginal strip coverage', 'Integral coverage')):
                ax.set_xticks(range(len(METHODS)), METHODS, rotation=50, ha='right', fontsize=7)
                ax.set(ylim=(0, 1.05), title=title)
                for level in (.68, .95):
                    ax.axhline(level, color='gray', ls='--', lw=.7)
            fig.suptitle(f'{period}: exploratory block + validation-residual uncertainty\nx: 68%; o: 95%; correlated targets, no independent coverage certification')
            _save(pdf, fig, directory / f'uncertainty_{period}.png')
            for method in METHODS:
                indices = [i for i, k in enumerate(keys) if k['period'] == period and k['method'] == method]
                if not indices:
                    continue
                integrals = draws[:, indices].sum(axis=2)
                valid = np.all(np.isfinite(integrals), axis=1)
                fig, axes = plt.subplots(1, 2, figsize=(11, 4))
                if valid.sum() >= 2:
                    cov = np.atleast_2d(np.cov(integrals[valid], rowvar=False))
                    std = np.sqrt(np.maximum(np.diag(cov), 0.))
                    corr = np.divide(cov, np.outer(std, std), out=np.zeros_like(cov), where=np.outer(std, std) > 0)
                    im = axes[0].imshow(corr, vmin=-1, vmax=1, cmap='RdBu_r', origin='lower')
                    fig.colorbar(im, ax=axes[0], label='Correlation')
                else:
                    axes[0].text(.5, .5, 'Insufficient jointly valid replicas', ha='center')
                axes[0].set(title=f'Integral correlations: {int(valid.sum())} complete draws', xlabel='Masked spectrum', ylabel='Masked spectrum')
                i = indices[len(indices)//2]
                sample = draws[:, i]
                ok = np.isfinite(sample).all(axis=1)
                if ok.sum() >= 2:
                    p = next(p for p in study['predictions'] if all(p[k] == v for k, v in keys[i].items()))
                    lo, hi = np.quantile(sample[ok], [.025, .975], axis=0)
                    axes[1].fill_between(np.arange(1, 129), lo, hi, alpha=.25, label='Exploratory 95%')
                    axes[1].plot(np.arange(1, 129), p['truth'], color='black', label='Measured')
                    axes[1].plot(np.arange(1, 129), p['estimate'], label='Reconstructed')
                    axes[1].legend(fontsize=7)
                axes[1].set(xlabel='Native strip', ylabel='Flux', title=f"Run {keys[i]['run']} {keys[i]['state']}")
                fig.suptitle(f'{period} {method}: aligned full-spectrum draws')
                _save(pdf, fig)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=Path('config/run_manifest.csv'))
    parser.add_argument('--raw-flux', type=Path, default=Path('data/00_external/flux.root'))
    parser.add_argument('--calibrated-flux', type=Path, default=Path('data/00_external/flux_calibrated.root'))
    parser.add_argument('--counts-cache', type=Path, default=Path('results/calibrated-neighbor-inputs-20261019/h80_counts.json'))
    parser.add_argument('--reference-study', type=Path, default=Path('results/realistic-flux-closure-20261019'))
    parser.add_argument('--run-quality', type=Path, default=DEFAULT_RUN_QUALITY_PATH)
    parser.add_argument('--reco-uv', type=Path, default=Path('results/uv/reco/reco_eta_pi0_bdt.root'))
    parser.add_argument('--reco-vis', type=Path, default=Path('results/vis/reco/reco_eta_pi0_bdt.root'))
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--replicas', type=int, default=64)
    parser.add_argument('--seed', type=int, default=142)
    args = parser.parse_args(argv)
    if args.replicas < 2:
        parser.error('--replicas must be >=2')
    counts, sources = load_cached_counts(args.counts_cache)
    design_path = args.reference_study / 'realistic_design.json'
    inventory_path = args.reference_study / 'gap_inventory.json'
    design = json.loads(design_path.read_text())
    inventory = json.loads(inventory_path.read_text())
    inputs = [args.manifest, args.raw_flux, args.calibrated_flux, args.counts_cache,
              design_path, inventory_path, args.reco_uv, args.reco_vis, args.run_quality,
              *[Path(s['path']) for s in sources]]
    started = time.monotonic()
    with publish_output(args.output_dir, inputs) as directory:
        print('Auditing native strip identity...', flush=True)
        dataset = load_calibrated_dataset(args.manifest, args.calibrated_flux, counts,
                                          representation='native_strip', run_quality_path=args.run_quality)
        audit = audit_native_strips(args.manifest, args.calibrated_flux, args.raw_flux,
                                   runs={r['run'] for r in dataset['records']})
        write_json(directory / 'strip_audit.json', audit)
        if audit['status'] != 'verified':
            raise ValueError('native strip mapping audit failed')
        write_json(directory / 'realistic_design.json', design)
        from threadpoolctl import threadpool_limits
        with threadpool_limits(limits=1):
            print(f"Grid searches: {len(dataset['records'])} spectra, {FAMILIES}", flush=True)
            study = evaluate_neighbors(dataset['records'], block_size=3, seed=args.seed,
                                       models=FAMILIES, split_plan=design['split_plan'])
            study = restrict_test_states(study, design['test_masks'])
            study['block_size'] = 'native_realistic'
            require_mask_coverage(study['predictions'], design['test_masks'])
            print('Writing full measured/predicted spectra and grid diagnostics...', flush=True)
            _write_benchmark(directory, dataset, [study], sources=sources)
            print(f'Generating {args.replicas} synchronized bootstrap/residual replicas...', flush=True)
            uncertainty = neighbor_replicas(dataset['records'], study, methods=METHODS,
                                           n_replicas=args.replicas, seed=args.seed+1000)
            np.savez_compressed(directory / 'flux_replicas.npz', draws=uncertainty['draws'],
                                model_draws=uncertainty['model_draws'])
            write_json(directory / 'flux_uncertainty.json', {k: v for k, v in uncertainty.items()
                                                           if k not in ('draws', 'model_draws')})
            _uncertainty_plots(directory, uncertainty, study)
            print('Propagating flux replicas and comparing recovery against oracle and discarded runs...', flush=True)
            from flux_studies.flux_observable_closure import run_observable_closure
            closure = run_observable_closure(
                [p for p in study['predictions'] if p['role'] == 'test' and p['method'] in METHODS],
                common_edges_by_period={}, representation='native_strip',
                flux_path=args.calibrated_flux, manifest_path=args.manifest,
                reco_paths={'uv': args.reco_uv, 'vis': args.reco_vis}, output_dir=directory / 'closure',
                methods=METHODS, flux_replicas=closure_replicas(uncertainty), flux_replica_count=args.replicas,
                run_quality_path=args.run_quality)
            print('Fitting experimental missing-state candidates in native strips...', flush=True)
            targets = [{k: r[k] for k in ('run', 'state', 'period', 'group', 'position', 'count')}
                       for r in inventory['missing'] if r['status'] == 'candidate']
            for target in targets:
                target['group'] = tuple(target['group'])
            candidates = predict_missing_neighbors(dataset['records'], targets,
                                                   models=tuple(f for f in FAMILIES if f != 'ridge'), seed=args.seed)
            write_json(directory / 'candidate_fits.json', candidates['fits'])
            support = candidate_support(candidates['predictions'], study['predictions'], dataset['records'],
                                        targets=targets, methods=METHODS, native=True)
            supported = {(r['run'], r['state'], r['method']) for r in support if r['supported']}
            attempted = [p for p in candidates['predictions'] if p['method'] in METHODS]
            published = [p for p in attempted if (p['run'], p['state'], p['method']) in supported]
            missing_reasons = {(r['run'], r['state']): r.get('missing_reason', 'missing_calibrated')
                               for r in inventory['missing']}
            for p in attempted:
                p['missing_reason'] = missing_reasons[p['run'], p['state']]
                p['supported'] = (p['run'], p['state'], p['method']) in supported
            write_csv(directory / 'candidate_attempts.csv', [{k: v for k, v in p.items() if k not in
                      ('estimate', 'lower68', 'upper68', 'lower95', 'upper95')} for p in attempted])
            np.savez_compressed(directory / 'candidate_attempt_spectra.npz', strip_indices=np.arange(1, 129),
                                estimate=np.array([p['estimate'] for p in attempted]).reshape(-1, 128))
            write_json(directory / 'candidate_support.json', support)
            write_json(directory / 'candidate_exclusions.json', candidates['exclusions'])
            write_csv(directory / 'candidate_predictions.csv', [{k: v for k, v in p.items() if k not in
                      ('estimate', 'lower68', 'upper68', 'lower95', 'upper95')} for p in published])
            np.savez_compressed(directory / 'candidate_spectra.npz', strip_indices=np.arange(1, 129),
                                estimate=np.array([p['estimate'] for p in published]).reshape(-1, 128))
        import torch, sklearn, uproot
        write_json(directory / 'execution.json', dict(elapsed_seconds=time.monotonic()-started,
                   command=sys.argv, python=sys.version, platform=platform.platform(),
                   versions=dict(torch=torch.__version__, numpy=np.__version__, sklearn=sklearn.__version__, uproot=uproot.__version__),
                   methods=METHODS, replicas=args.replicas, seed=args.seed,
                   split_definition='frozen geometry from supplied reference-study; block_size does not override explicit split',
                   reference_study=str(args.reference_study), run_quality=dataset['run_quality']))
        write_json(directory / 'adoption_gate.json', dict(status='not_adopted',
                   reason='development study: independent bias/coverage and missing-state energy calibration still unvalidated',
                   acceptance_by_period=[dict(period=p['period'], **p['acceptance']) for p in closure['periods']]))
    print(f'Published {args.output_dir}', flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
