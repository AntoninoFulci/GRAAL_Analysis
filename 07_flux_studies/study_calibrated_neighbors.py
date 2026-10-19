"""Benchmark calibrated flux reconstruction; no production replacement."""
from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path
import sys
import numpy as np

from flux_studies.calibrated_data import count_h80, load_calibrated_dataset
from flux_studies.neighbor_validation import evaluate_neighbors
from flux_studies.reporting import publish_output, write_json, write_csv

ASSUMPTIONS = {
    'evaluation_scope': 'development holdouts on previously inspected periods; not independent confirmation',
    'run_duration_minutes': 15,
    'timing_source': 'user assumption; timestamps unavailable',
    'order': 'ordinal position in full manifest period, sorted by run number',
    'compatibility': 'within-period apparatus, trigger, prescale, dead time, background and inclusive response assumed stable',
    'normalization': 'inclusive h80 event count per run and polarization state',
    'h80_convention': 'all entries in supplied h80; upstream no-tagger selection depends on source campaign',
    'status': 'exploratory benchmark; synthetic flux not adopted in production',
    'intervals': 'validation-only empirical residual bands; no guaranteed coverage or cross-run independence',
    'features': 'left/right flux per event (128 each), interpolation (128), two assumed distances, relative position',
    'energy_grid': '128 equal bins from 0.5 to 2.0 GeV; piecewise-constant conservative rebinning',
}


def _summary(study):
    groups = defaultdict(list)
    for p in study['predictions']:
        if p['role'] == 'test':
            groups[(p['period'], p['state'], p['method'])].append(p)
    metrics = []
    for (period, state, method), rows in sorted(groups.items()):
        row = dict(period=period, state=state, method=method, n=len(rows))
        for name in ('relative_integral_error', 'relative_l1', 'shape_l1', 'coverage68', 'coverage95',
                     'integral_covered68', 'integral_covered95'):
            values = [r[name] for r in rows if r.get(name) is not None]
            row[name + '_n'] = len(values)
            row[name + '_mean'] = float(np.mean(values)) if values else None
            row[name + '_median'] = float(np.median(values)) if values else None
        metrics.append(row)
    paired = defaultdict(dict)
    for p in study['predictions']:
        if p['role'] == 'test' and p['method'] in ('linear', 'ridge') and p['relative_l1'] is not None:
            paired[(p['period'], p['run'], p['state'])][p['method']] = p['relative_l1']
    pairs = [p for p in paired.values() if len(p) == 2]
    by_method = defaultdict(dict)
    for p in study['predictions']:
        if p['role'] == 'test' and p.get('relative_l1') is not None:
            by_method[p['method']][(p['period'], p['run'], p['state'])] = p
    comparisons = []
    for method, targets in sorted(by_method.items()):
        if method == 'linear':
            continue
        references = ['linear']
        if '_default' not in method:
            default = method.replace('_hybrid', '_default_hybrid') if method.endswith('_hybrid') else method + '_default'
            if default in by_method:
                references.append(default)
        for reference in references:
            common = sorted(targets.keys() & by_method[reference].keys())
            if not common:
                continue
            actual = np.array([targets[k]['relative_l1'] for k in common])
            baseline = np.array([by_method[reference][k]['relative_l1'] for k in common])
            comparisons.append(dict(method=method, reference=reference, n=len(common),
                                    method_better_fraction=float(np.mean(actual < baseline)),
                                    method_mean_relative_l1=float(actual.mean()),
                                    reference_mean_relative_l1=float(baseline.mean()),
                                    method_median_relative_l1=float(np.median(actual)),
                                    reference_median_relative_l1=float(np.median(baseline))))
    return dict(block_size=study['block_size'], status=study['status'], metrics=metrics,
                comparisons=comparisons,
                paired=dict(n=len(pairs),
                            ridge_better_fraction=float(np.mean([p['ridge'] < p['linear'] for p in pairs])) if pairs else None,
                            linear_mean_relative_l1=float(np.mean([p['linear'] for p in pairs])) if pairs else None,
                            ridge_mean_relative_l1=float(np.mean([p['ridge'] for p in pairs])) if pairs else None),
                exclusions=study['exclusions'])


def publish_benchmark(output, dataset, studies, *, sources, inputs):
    with publish_output(Path(output), inputs) as directory:
        _write_benchmark(directory, dataset, studies, sources=sources)


def _write_benchmark(directory, dataset, studies, *, sources):
    from flux_studies.neighbor_plots import plot_benchmark
    arrays = ('truth', 'estimate', 'lower68', 'upper68', 'lower95', 'upper95')
    assumptions = dict(ASSUMPTIONS)
    native = dataset.get('representation') == 'native_strip'
    if native:
        assumptions['energy_grid'] = 'Native xstrip indices 1..128; independent energy calibration retained separately'
        write_json(directory / 'native_calibration_axes.json', [
            {k: r[k] for k in ('run', 'state', 'period', 'calibration_edges', 'axis_source')}
            for r in dataset['records']])
    write_json(directory / 'summary.json', dict(assumptions=assumptions, sources=sources,
                                                   run_quality=dataset.get('run_quality'),
                                                   data_exclusions=dataset['exclusions'],
                                                   extra_h80_runs=dataset.get('extra_h80_runs', []),
                                                   studies=[_summary(s) for s in studies]))
    write_csv(directory / 'counts.csv', [dict(run=r['run'], state=r['state'], period=r['period'],
                                                 count=r['count'], position_minutes_assumed=r['position'])
                                            for r in dataset['records']])
    for study in studies:
        folder = directory / f'block_{study["block_size"]}'
        folder.mkdir()
        write_json(folder / 'splits.json', study['splits'])
        write_json(folder / 'fits.json', study['fits'])
        write_csv(folder / 'predictions.csv', [{k: v for k, v in p.items() if k not in arrays}
                                                  for p in study['predictions']])
        predictions = study['predictions']
        coordinates = {'strip_edges': np.arange(.5, 129.5)} if native else {'energy_edges': dataset['energy_edges']}
        np.savez_compressed(folder / 'spectra.npz', **coordinates,
                                **{name: np.array([p[name] if p[name] is not None else np.full(128, np.nan)
                                                   for p in predictions]) for name in arrays})
        plot_benchmark(folder, dataset, study)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=Path('config/run_manifest.csv'))
    parser.add_argument('--calibrated-flux', type=Path, required=True)
    parser.add_argument('--representation', choices=('common_energy', 'native_strip'), default='common_energy')
    parser.add_argument('--raw-flux', type=Path, default=Path('data/00_external/flux.root'),
                        help='Original strip flux used by the mandatory native-strip identity audit')
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument('--h80', type=Path, action='append')
    source_group.add_argument('--counts-cache', type=Path)
    parser.add_argument('--run-quality', type=Path)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--block-size', type=int, action='append')
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--models', nargs='+', choices=('ridge', 'kernel_ridge', 'extra_trees', 'mlp', 'cnn1d'),
                        default=['ridge', 'kernel_ridge', 'extra_trees'])
    args = parser.parse_args(argv)
    try:
        if args.output_dir.exists():
            raise FileExistsError(f'output already exists: {args.output_dir}')
        print('Checking input identities...', flush=True)
        from calibration.run_quality import DEFAULT_RUN_QUALITY_PATH
        if args.counts_cache:
            from flux_studies.study_native_recovery import load_cached_counts
            cached_counts, cached_sources = load_cached_counts(args.counts_cache)
            source_paths = [Path(s['path']) for s in cached_sources]
        else:
            source_paths = args.h80
        inputs = [args.manifest, args.calibrated_flux, *source_paths,
                  args.run_quality or DEFAULT_RUN_QUALITY_PATH, args.counts_cache]
        if args.representation == 'native_strip':
            inputs.append(args.raw_flux)
        with publish_output(args.output_dir, inputs) as directory:
            print('Counting inclusive h80 run/state events...', flush=True)
            counts, sources = ((cached_counts, cached_sources) if args.counts_cache else count_h80(args.h80))
            quality_kwargs = {'run_quality_path': args.run_quality} if args.run_quality else {}
            if args.representation == 'native_strip':
                from flux_studies.strip_audit import audit_native_strips
                dataset = load_calibrated_dataset(args.manifest, args.calibrated_flux, counts,
                                                  representation='native_strip', **quality_kwargs)
                audit = audit_native_strips(args.manifest, args.calibrated_flux, args.raw_flux,
                                            runs={r['run'] for r in dataset['records']})
                write_json(directory / 'strip_audit.json', audit)
                if audit['status'] != 'verified':
                    raise ValueError('native strip mapping audit failed')
            else:
                dataset = load_calibrated_dataset(args.manifest, args.calibrated_flux, counts, **quality_kwargs)
            print(f'Usable calibrated spectra: {len(dataset["records"])}', flush=True)
            studies = []
            from threadpoolctl import threadpool_limits
            with threadpool_limits(limits=1):
                for block_size in dict.fromkeys(args.block_size or [1, 3]):
                    print(f'Fitting block size {block_size}...', flush=True)
                    study = evaluate_neighbors(dataset['records'], block_size=block_size, seed=args.seed,
                                               models=tuple(args.models),
                                               split_runs_by_period=dataset.get('split_runs_by_period'))
                    studies.append(study)
                    print(_summary(study)['paired'], flush=True)
            print('Writing complete overlays and diagnostics...', flush=True)
            _write_benchmark(directory, dataset, studies, sources=sources)
        print(f'Output: {args.output_dir}', flush=True)
        return 0
    except (ValueError, OSError, KeyError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
