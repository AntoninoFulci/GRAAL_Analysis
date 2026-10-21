"""Real missing-calibration geometry, masked validation and paired Sigma sensitivity."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from pathlib import Path
import sys
import numpy as np

from calibration.run_manifest import validate_manifest
from calibration.run_quality import DEFAULT_RUN_QUALITY_PATH, load_run_quality
from flux_studies.audit_flux import audit_flux
from flux_studies.calibrated_data import count_h80, load_calibrated_dataset
from flux_studies.neighbor_validation import evaluate_neighbors, predict_missing_neighbors
from flux_studies.realistic_gaps import gap_inventory, realistic_split, recovery_targets
from flux_studies.reporting import publish_output, write_json, write_csv
from flux_studies.study_calibrated_neighbors import _write_benchmark

CANDIDATE_METHODS = ('linear', 'extra_trees_hybrid', 'kernel_ridge_hybrid')


def restrict_test_states(study, masks):
    """Score exactly the missing-state pattern while all target states stay hidden."""
    keys = {(r['period'], r['run'], r['state']) for r in masks}
    result = dict(study)
    result['predictions'] = [p for p in study['predictions']
                            if p['role'] != 'test' or (p['period'], p['run'], p['state']) in keys]
    result['requested_test_states'] = len(keys)
    result['test_masks'] = masks
    return result


def require_mask_coverage(predictions, masks):
    available = {(p['period'], p['run'], p['state']) for p in predictions
                 if p['role'] == 'test' and p['method'] == 'linear'}
    requested = {(p['period'], p['run'], p['state']) for p in masks}
    if requested - available:
        raise ValueError(f'unpredicted closure masks: {sorted(requested - available)}')


def candidate_support(predictions, validation, records, *, targets, methods=CANDIDATE_METHODS, native=False):
    """Report support diagnostics; no guessed physical adoption tolerance."""
    result = []
    positions = {(r['period'], r['run']): r['position'] for r in [*records, *targets]}
    def offsets(row):
        position = positions[(row['period'], row['run'])]
        left, right = [positions[(row['period'], run)] for run in row['donors']]
        return (position - left, right - position)
    for row in predictions:
        if row['method'] not in methods:
            continue
        group = [p for p in validation if p['role'] == 'test' and p['method'] == row['method']
                 and p['period'] == row['period'] and p['state'] == row['state']]
        train = [r for r in records if r['period'] == row['period'] and r['state'] == row['state']]
        gaps = [p['gap'] for p in group]
        counts = [r['count'] for r in train]
        geometry = offsets(row) in {offsets(p) for p in group}
        count_support = bool(counts and min(counts) <= row['count'] <= max(counts))
        result.append(dict(run=row['run'], period=row['period'], state=row['state'], method=row['method'],
                           gap=row['gap'], validation_n=len(group),
                           donor_offsets=offsets(row),
                           validation_gap_min=min(gaps) if gaps else None,
                           validation_gap_max=max(gaps) if gaps else None,
                           gap_within_validation_support=geometry,
                           count_within_training_range=count_support,
                           supported=geometry and count_support,
                           status='experimental_candidate' if geometry and count_support else 'unsupported_candidate',
                           production_adopted=False,
                           blockers=['no_independent_confirmation', 'flux_uncertainty_not_calibrated',
                                     'missing_state_energy_calibration_requires_separate_validation' if native
                                     else 'native_strip_axis_not_established_for_missing_state']
                                    + ([] if geometry else ['outside_validated_gap_support'])
                                    + ([] if count_support else ['outside_training_count_range'])))
    return result


def _plot_candidates(directory, inventory, predictions, edges):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages
    from flux_studies.neighbor_plots import _save
    periods = sorted({r['period'] for r in inventory['missing']})
    fig, ax = plt.subplots(figsize=(11, 5))
    bottom = np.zeros(len(periods))
    for status in sorted(inventory['summary']['statuses']):
        counts = Counter(r['period'] for r in inventory['missing'] if r['status'] == status)
        values = [counts[p] for p in periods]
        ax.bar(periods, values, bottom=bottom, label=status)
        bottom += values
    ax.set(ylabel='Missing calibrated states', title='Global inventory; candidates require local h80 counts and two clean donors')
    ax.tick_params(axis='x', rotation=45)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(directory / 'gap_inventory.png', dpi=130)
    plt.close(fig)
    energy = (edges[:-1] + edges[1:]) / 2
    groups = defaultdict(list)
    for p in predictions:
        if p['method'] in CANDIDATE_METHODS:
            groups[(p['period'], p['run'], p['state'])].append(p)
    with PdfPages(directory / 'missing_candidates.pdf') as pdf:
        for (period, run, state), rows in sorted(groups.items()):
            fig, axes = plt.subplots(2, 1, figsize=(10, 7), sharex=True)
            for row in rows:
                values = row['estimate']
                axes[0].step(energy, values, where='mid', label=row['method'])
                if values.sum() > 0:
                    axes[1].step(energy, values / values.sum(), where='mid', label=row['method'])
            axes[0].set(ylabel='Photon flux / common energy bin')
            axes[1].set(xlabel='Photon energy [GeV]', ylabel='Unit-area shape')
            for ax in axes:
                ax.legend(); ax.grid(alpha=.2)
            fig.suptitle(f'{period} run {run} {state} | donors {rows[0]["donors"]}\n'
                         'EXPERIMENTAL CANDIDATE — measured truth unavailable; no validated uncertainty')
            _save(pdf, fig)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=Path('config/run_manifest.csv'))
    parser.add_argument('--raw-flux', type=Path, default=Path('data/00_external/flux.root'))
    parser.add_argument('--calibrated-flux', type=Path, required=True)
    parser.add_argument('--h80', type=Path, action='append', required=True)
    parser.add_argument('--reco-uv', type=Path, required=True)
    parser.add_argument('--reco-vis', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--seed', type=int, default=142)
    args = parser.parse_args(argv)
    try:
        inputs = [args.manifest, args.raw_flux, args.calibrated_flux, *args.h80,
                  args.reco_uv, args.reco_vis, DEFAULT_RUN_QUALITY_PATH]
        with publish_output(args.output_dir, inputs) as directory:
            print('Counting inclusive events and inventorying actual calibrated gaps...', flush=True)
            counts, sources = count_h80(args.h80)
            dataset = load_calibrated_dataset(args.manifest, args.calibrated_flux, counts)
            quality = load_run_quality()
            audit = audit_flux(manifest=args.manifest, raw_flux=args.raw_flux, calibrated_flux=args.calibrated_flux)
            inventory = gap_inventory(validate_manifest(args.manifest), audit, counts, dataset['records'],
                                      excluded_runs={r['run'] for r in quality['excluded_runs']})
            design = realistic_split(dataset['records'], inventory['patterns'], seed=args.seed)
            write_json(directory / 'gap_inventory.json', inventory)
            write_csv(directory / 'missing_states.csv', inventory['missing'])
            write_json(directory / 'realistic_design.json', design)
            print(f'Clean spectra: {len(dataset["records"])}; inventory: {inventory["summary"]}', flush=True)
            print(f'Masked test states: {len(design["test_masks"])}', flush=True)
            from threadpoolctl import threadpool_limits
            with threadpool_limits(limits=1):
                study = evaluate_neighbors(dataset['records'], block_size=1, seed=args.seed,
                                           models=('extra_trees', 'kernel_ridge'),
                                           split_plan=design['split_plan'])
                study = restrict_test_states(study, design['test_masks'])
                study['block_size'] = 'realistic'
                targets = recovery_targets(inventory, excluded_runs={
                    r['run'] for r in dataset['run_quality']['excluded_runs']})
                candidates = predict_missing_neighbors(dataset['records'], targets,
                                                       models=('extra_trees', 'kernel_ridge'), seed=args.seed)
            print('Running paired observable closure with frozen selections...', flush=True)
            require_mask_coverage(study['predictions'], design['test_masks'])
            from flux_studies.flux_observable_closure import run_observable_closure
            closure = run_observable_closure(
                [p for p in study['predictions'] if p['role'] == 'test' and p['method'] in CANDIDATE_METHODS],
                common_edges_by_period={r['period']: dataset['energy_edges'] for r in dataset['records']},
                flux_path=args.calibrated_flux, manifest_path=args.manifest,
                reco_paths={'uv': args.reco_uv, 'vis': args.reco_vis}, output_dir=directory / 'closure')
            support = candidate_support(candidates['predictions'], study['predictions'], dataset['records'], targets=targets)
            supported = {(r['period'], r['run'], r['state'], r['method']) for r in support
                         if r['status'] == 'experimental_candidate'}
            published = [p for p in candidates['predictions']
                         if (p['period'], p['run'], p['state'], p['method']) in supported]
            write_json(directory / 'candidate_support.json', support)
            write_json(directory / 'candidate_fits.json', candidates['fits'])
            write_csv(directory / 'candidate_predictions.csv',
                      [{k: v for k, v in p.items() if k not in ('estimate', 'lower68', 'upper68', 'lower95', 'upper95')}
                       for p in published])
            np.savez_compressed(directory / 'candidate_spectra.npz', energy_edges=dataset['energy_edges'],
                                estimate=np.array([p['estimate'] for p in published]).reshape(-1, 128))
            write_json(directory / 'candidate_exclusions.json', candidates['exclusions'])
            write_json(directory / 'adoption_gate.json', dict(status='not_adopted',
                       reasons=['development_data_reused', 'flux_covariance_and_coverage_unvalidated',
                                'no_physical_tolerance_defined', 'native_strip_axes_needed_for_missing_states'],
                       candidate_methods_published=len(published), candidate_methods_rejected=len(support)-len(published),
                       run_quality=quality,
                       observable_closure_status=closure.get('status', 'see_closure_report')))
            print('Writing measured-versus-predicted overlays and diagnostic plots...', flush=True)
            _write_benchmark(directory, dataset, [study], sources=sources)
            _plot_candidates(directory, inventory, published, dataset['energy_edges'])
        print(f'Output: {args.output_dir}', flush=True)
        return 0
    except (ValueError, OSError, KeyError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
