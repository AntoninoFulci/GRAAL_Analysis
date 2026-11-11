"""CSV run/period database, self-contained NPZ plots and GEANT4 proposals.

Physical diameter stays unknown. The historical 5 cm reference is an explicit
assumption; XY is an observed interaction profile, not unfolded photon truth.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from zipfile import ZipFile, ZIP_DEFLATED

import numpy as np
import scipy
import uproot

from graal_common.io.filesystem import atomic_output_directory
if __package__:
    from .target_fit import observed_xy, select_vertices
    from .target_edges import fit_edges
    from .run_manifest import validate_manifest
    from .target_periods import aggregate_periods, exclusion_reason
    from .target_archive import write_run, finish_archive, render_periods, render_archived_run
else:
    from target_fit import observed_xy, select_vertices
    from target_edges import fit_edges
    from run_manifest import validate_manifest
    from target_periods import aggregate_periods, exclusion_reason
    from target_archive import write_run, finish_archive, render_periods, render_archived_run


def _sha256(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b''):
            result.update(chunk)
    return result.hexdigest()


def _analyze_run(run, data, raw_counts, bootstrap):
    mask = select_vertices(data, dca_max_cm=.4)
    xyz = np.column_stack([data[f'{a}_cm'][mask] for a in 'xyz'])
    fit = fit_edges(xyz[:, 2], bootstrap=bootstrap, seed=73+int(run))
    z_inside = np.ones(len(xyz), dtype=bool)
    if fit['length_cm'] is not None:
        z_inside = (xyz[:, 2] >= fit['z_min_cm']) & (xyz[:, 2] <= fit['z_max_cm'])
    spot = observed_xy(xyz[z_inside, :2])
    spot['z_selection'] = 'within fitted cell edges' if fit['length_cm'] is not None else 'no z selection; length unavailable'
    spot['outside_z_selection'] = int((~z_inside).sum())
    variations = {}
    for dca in (.2, .3):
        other = select_vertices(data, dca_max_cm=dca)
        alternate = fit_edges(data['z_cm'][other], seeds=fit.get('edge_seeds_cm'))
        variations[str(dca)] = {k: alternate.get(k) for k in ('length_cm', 'status', 'fit_events', 'model_check')}
    if fit['length_cm'] is not None:
        shifts = [abs(v['length_cm']-fit['length_cm']) for v in variations.values() if v['length_cm'] is not None]
        fit['dca_variation_max_shift_cm'] = max(shifts) if shifts else None
    windows = {}
    for width in (1.2, 2.):
        alternate = fit_edges(xyz[:, 2], halfwidth=width, seeds=fit.get('edge_seeds_cm'))
        windows[str(width)] = {k: alternate.get(k) for k in ('length_cm', 'status', 'halfwidth_effective_cm')}
    if fit['length_cm'] is not None:
        shifts = [abs(v['length_cm']-fit['length_cm']) for v in windows.values() if v['length_cm'] is not None]
        fit['window_variation_max_shift_cm'] = max(shifts) if shifts else None
        fit['robustness_limit_cm'] = .5
        if max(fit.get('dca_variation_max_shift_cm') or 0., max(shifts, default=0.)) > .5:
            fit['status'] = 'unstable_edges'
    record = dict(run=int(run), raw_events=raw_counts['events_read'], saved_pairs=len(data['run']),
                  selected_events=int(mask.sum()), length_fit=fit, observed_xy=spot,
                  dca_variations_cm=variations, window_variations_cm=windows, target_diameter_cm=None,
                  physical_diameter_status='not_identified; illuminated spot is not cell diameter',
                  geant4_ready=False)
    return record, xyz, mask


def _write_csv(path, rows):
    if not rows:
        raise ValueError('cannot write database with no rows')
    with path.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _write_tables(out, report):
    rows = []
    for run, row in report['runs'].items():
        fit, spot, catalog = row['length_fit'], row['observed_xy'], row['catalog']
        center = spot['median_cm'] or [None, None]
        widths = spot['sigma68_cm'] or [None, None]
        flat = dict(run=run, source_period=catalog['source_period'], target=catalog['target'],
                    beam_type=catalog['beam_type'], raw_events=row['raw_events'], saved_pairs=row['saved_pairs'],
                    selected_events=row['selected_events'], dca_max_cm=.4, fit_status=fit['status'])
        flat.update(reconstruction_status=row.get('reconstruction_status', 'completed'),
                    reconstruction_note=row.get('reconstruction_note', ''),
                    events_with_chamber_tracks=row.get('events_with_chamber_tracks'))
        flat.update(length_model=fit.get('model'), model_scope=fit.get('model_scope', 'full_profile'),
                    window_variation_max_shift_cm=fit.get('window_variation_max_shift_cm'),
                    previous_length_cm=row.get('previous_length_cm'),
                    included_in_period=exclusion_reason(row) is None,
                    period_exclusion_reason=exclusion_reason(row) or '',
                    bootstrap_requested=fit.get('bootstrap_requested'),
                    bootstrap_successful=fit.get('bootstrap_successful'))
        for side in ('left', 'right'):
            edge = fit.get('local_edges', {}).get(side, {})
            for key in ('status', 'sigma_cm', 'slope_per_cm', 'background_fraction', 'deviance_per_ndf'):
                flat[f'{side}_{key}'] = edge.get(key)
        for key in ('length_cm', 'length_stat_error_cm', 'center_cm', 'z_min_cm', 'z_max_cm',
                    'effective_sigma_cm', 'background_fraction', 'deviance', 'ndf', 'deviance_per_ndf',
                    'model_check', 'dca_variation_max_shift_cm', 'outside_fit_window'):
            flat['center_z_cm' if key == 'center_cm' else key] = fit.get(key)
        flat.update(target_diameter_cm=None, historical_reference_diameter_cm=5.,
                    physical_diameter_status=row['physical_diameter_status'],
                    spot_x_cm=center[0], spot_y_cm=center[1], spot_sigma68_x_cm=widths[0], spot_sigma68_y_cm=widths[1],
                    illuminated_diameter95_cm=spot['illuminated_diameter95_cm'],
                    xy_events=spot['events'], xy_outside_window=spot['outside_xy_window'],
                    outside_z_selection=spot['outside_z_selection'],
                    raw_source_files=';'.join(row['raw_source_files']),
                    source_campaign=report['vertex_campaign'], plot_archive='run_plots.npz', archive_prefix=f'run_{run}_')
        rows.append(flat)
    _write_csv(out/'target_runs.csv', rows)
    rows = []
    for period, row in report['periods'].items():
        center = row['spot_mean_cm'] or [None, None]
        widths = row['spot_sigma68_cm'] or [None, None]
        rms = row['spot_rms_cm'] or [None, None]
        flat = {key: row[key] for key in ('period', 'n_runs', 'n_processed_runs', 'n_catalog_runs', 'coverage_status',
                 'weighting', 'geometry_status', 'selected_events', 'length_cm', 'length_run_std_cm',
                 'length_stat_error_cm', 'length_span_cm', 'center_z_cm', 'z_min_cm', 'z_max_cm',
                 'target_diameter_cm', 'historical_reference_diameter_cm', 'illuminated_diameter95_cm')}
        for key in ('included_runs', 'excluded_runs', 'missing_runs', 'target_labels', 'beam_labels', 'poor_shape_runs'):
            flat[key] = ';'.join(map(str, row[key]))
        flat.update(spot_mean_x_cm=center[0], spot_mean_y_cm=center[1],
                    spot_sigma68_x_cm=widths[0], spot_sigma68_y_cm=widths[1],
                    spot_rms_x_cm=rms[0], spot_rms_y_cm=rms[1],
                    plot_archive='run_plots.npz', archive_prefix=f'period_{period}_')
        rows.append(flat)
    _write_csv(out/'target_periods.csv', rows)


def _geant4_candidates(report):
    candidates = {}
    for period, row in report['periods'].items():
        available = row['geometry_candidate_available']
        candidates[period] = dict(
            status='diagnostic_approximation_not_applied', weighting=row['weighting'],
            included_runs=row['included_runs'], excluded_runs=row['excluded_runs'],
            coverage_status=row['coverage_status'], missing_runs=row['missing_runs'],
            geometry_status=row['geometry_status'], poor_shape_runs=row['poor_shape_runs'],
            target=dict(length_mm=10*row['length_cm'] if available else None,
                        center_z_mm=10*row['center_z_cm'] if available else None,
                        center_xy_mm=None, diameter_mm=50.,
                        diameter_source='historical_reference_assumption_not_run_measurement',
                        material_label=row['target_labels'][0] if len(row['target_labels']) == 1 else 'UNKNOWN'),
            photon_beam_proxy=dict(kind='equal_run_mean_observed_interaction_xy_not_unfolded_incident_beam',
                                   available=row['n_runs'] > 0,
                                   profile_file='run_plots.npz', archive_prefix=f'period_{period}_',
                                   probability_key=f'period_{period}_xy_probability' if row['n_runs'] > 0 else None,
                                   frame='native_h70_detector', units='mm',
                                   sampling=('select a 2D bin by xy_probability, then sample uniformly within its mm edges'
                                             if row['n_runs'] > 0 else None)),
            limitations=['physical target diameter and xy center not measured',
                         'XY includes resolution and acceptance; equal-run average is not flux/exposure weighted',
                         'length is average of model-dependent run estimates; incompatible lengths are not exported'])
    return dict(schema=2, periods=candidates)


def build_database(campaign, output, *, bootstrap=32, plots=True, catalog=None):
    campaign, output = Path(campaign).resolve(), Path(output).resolve()
    metadata_path, vertices_path = campaign/'summary.json', campaign/'vertices.root'
    metadata = json.loads(metadata_path.read_text())
    if bootstrap < 0:
        raise ValueError('bootstrap must be nonnegative')
    if (metadata.get('schema') != 1 or metadata.get('diagnostic') != 'central_pair_target_vertex'
            or metadata.get('units') != 'cm, native h70 detector frame; no alignment shift'):
        raise ValueError('unsupported vertex campaign or coordinate units')
    if catalog is None:
        raise ValueError('catalog required for period aggregation')
    catalog = Path(catalog).resolve()
    catalog_hash = _sha256(catalog)
    catalog_rows = {str(row.run_number): row for row in validate_manifest(catalog)}
    if set(metadata['runs']) - set(catalog_rows):
        raise ValueError('vertex runs missing from catalog')
    catalog_runs = defaultdict(list)
    for row in catalog_rows.values():
        catalog_runs[row.source_period].append(row.run_number)
    source_hashes = {p.name: _sha256(p) for p in (metadata_path, vertices_path)}
    report = dict(schema=2, created_utc=datetime.now(timezone.utc).isoformat(),
                  status='diagnostic_run_and_period_database', dca_max_cm=.4,
                  coordinate_frame='native_h70_detector', run_archive_units='cm', period_xy_edges_units='mm',
                  selection='status=0, exactly two eligible central charges, finite xyz, 0<=DCA<=0.4 cm; one vertex/event',
                  vertex_campaign=str(campaign), source_hashes=source_hashes, raw_input_files=metadata['files'],
                  code_hashes={name: _sha256(Path(__file__).with_name(name)) for name in
                               ('target_database.py', 'target_fit.py', 'target_edges.py', 'target_periods.py', 'target_archive.py')},
                  versions={'python':sys.version, 'numpy':np.__version__, 'scipy':scipy.__version__, 'uproot':uproot.__version__},
                  historical_reference={'target_diameter_cm':5.,
                      'source':'docs/reference/fortran/prog/laggen/include/lagtarg.inc: TRADIUS=2.5 cm',
                      'status':'reference_not_per_run_measurement'},
                  catalog={'path':str(catalog), 'sha256':catalog_hash}, runs={})
    source_paths = {entry['index']: entry['path'] for entry in metadata['files']}
    with atomic_output_directory(output, overwrite=False) as out:
        with ZipFile(out/'run_plots.npz', 'w', compression=ZIP_DEFLATED, allowZip64=True) as archive:
            with uproot.open(vertices_path) as handle:
                tree = handle['vertices']
                names = ['run', 'source_file', 'source_entry', 'n_charged', 'status', 'dca_cm', 'x_cm', 'y_cm', 'z_cm']
                if set(names)-set(tree.keys()):
                    raise ValueError('missing vertex branches')
                actual_runs = {str(int(run)) for run in np.unique(tree['run'].array(library='np'))}
                if actual_runs-set(metadata['runs']):
                    raise ValueError('vertex tree/manifest run coverage mismatch')
                for run, raw_counts in sorted(metadata['runs'].items(), key=lambda item:int(item[0])):
                    if not run.isdecimal() or int(run) <= 0:
                        raise ValueError('invalid run identity')
                    data = tree.arrays(names, cut=f'run == {int(run)}', library='np')
                    record, xyz, mask = _analyze_run(run, data, raw_counts, bootstrap)
                    row = catalog_rows[run]
                    record['catalog'] = {name:getattr(row,name) for name in
                                         ('target', 'beam_type', 'source_period', 'classification_source')}
                    record['raw_source_files'] = [source_paths[int(i)] for i in np.unique(data['source_file'])]
                    report['runs'][run] = record
                    write_run(archive, run, xyz, data, mask, record)
                    # Only small fit/profile products are retained across runs.
                    del data, xyz, mask
            report['periods'] = aggregate_periods(report['runs'], catalog_runs)
            export_metadata = finish_archive(archive, report)
        if (any(_sha256(campaign/name) != value for name,value in source_hashes.items())
                or _sha256(catalog) != catalog_hash):
            raise ValueError('input campaign or catalog changed during fit')
        _write_tables(out, report)
        (out/'geant4_candidates.json').write_text(json.dumps(_geant4_candidates(report), indent=2, allow_nan=False)+'\n')
        (out/'metadata.json').write_text(json.dumps(export_metadata, indent=2, allow_nan=False)+'\n')
        if plots:
            render_periods(out/'run_plots.npz', report, out)
    return report


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] == 'plot-run':
        parser = argparse.ArgumentParser(description='Regenerate a run figure from the self-contained NPZ archive.')
        parser.add_argument('archive', type=Path)
        parser.add_argument('--run', type=int, required=True)
        parser.add_argument('--output', type=Path, required=True, help='New output directory')
        args = parser.parse_args(argv[1:])
        print(render_archived_run(args.archive, args.run, args.output).resolve())
        return
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('vertex_campaign', type=Path)
    parser.add_argument('--output', type=Path, required=True, help='New directory; existing output is never replaced')
    parser.add_argument('--catalog', type=Path, required=True)
    parser.add_argument('--bootstrap', type=int, default=32)
    parser.add_argument('--no-plots', action='store_true')
    args = parser.parse_args(argv)
    report = build_database(args.vertex_campaign, args.output, bootstrap=args.bootstrap,
                            plots=not args.no_plots, catalog=args.catalog)
    for period, row in report['periods'].items():
        print(f"{period}: {row['n_runs']}/{row['n_catalog_runs']} runs, mean length={row['length_cm']} cm")
    print(args.output.resolve())


if __name__ == '__main__':
    main()
