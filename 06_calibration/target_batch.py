"""Resumable raw-h70 target campaign with isolated failures and bounded workers.

Run shards are immutable and fingerprinted. A failed run gets an empty archive,
CSV status and warning, never a fabricated vertex or a period-average weight.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict
from datetime import datetime, timezone
import fcntl
import hashlib
from importlib.metadata import version
import json
import logging
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time
import traceback
from zipfile import ZipFile, ZIP_DEFLATED

import numpy as np
import uproot

from graal_common.io.filesystem import atomic_output_directory
from plots.target_vertex import analyze, OUTPUT_TYPES
if __package__:
    from .run_manifest import validate_manifest
    from .target_database import _analyze_run, _write_tables, _geant4_candidates, _sha256
    from .target_periods import aggregate_periods
    from .target_archive import write_run, finish_archive, render_periods
else:
    from run_manifest import validate_manifest
    from target_database import _analyze_run, _write_tables, _geant4_candidates, _sha256
    from target_periods import aggregate_periods
    from target_archive import write_run, finish_archive, render_periods

LOG = logging.getLogger(__name__)


def _json(path, value):
    path = Path(path)
    temporary = path.with_name('.'+path.name+'.tmp')
    with temporary.open('w') as stream:
        stream.write(json.dumps(value, indent=2, allow_nan=False)+'\n')
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def source_hashes():
    root = Path(__file__).resolve().parents[1]
    names = ['06_calibration/'+name for name in (
        'target_batch.py', 'target_database.py', 'target_fit.py', 'target_edges.py', 'target_periods.py',
        'target_archive.py', 'run_manifest.py')]
    names += ['plots/target_vertex.py', 'plots/core/vertex.py', '00_common/io/filesystem.py']
    return {name: _sha256(root/name) for name in names}


def _input_identity(path):
    try:
        stat = path.stat()
        return dict(path=str(path), size_bytes=stat.st_size, mtime_ns=stat.st_mtime_ns)
    except FileNotFoundError:
        return dict(path=str(path), missing=True)
    except OSError as exc:
        return dict(path=str(path), stat_error=type(exc).__name__, errno=exc.errno)


def _empty_data():
    return {name: np.empty(0, dtype=dtype) for name, dtype in OUTPUT_TYPES.items()}


def _failed_record(run, raw_events, status, note):
    data = _empty_data()
    record, xyz, mask = _analyze_run(run, data, {'events_read': raw_events}, 0)
    record.update(reconstruction_status=status, reconstruction_note=note)
    return record, xyz, data, mask


def process_run(row, raw_root, shards, bootstrap, code_hashes):
    """Lock each run as well as the controller, including orphaned workers."""
    shards = Path(shards)
    shards.mkdir(parents=True, exist_ok=True)
    run = row['run_number']
    with (shards/f'run_{run}.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        destination = shards/f'run_{run}'
        if destination.is_dir() and not any(destination.iterdir()):
            destination.rmdir()  # Empty reservation left by an interrupted writer.
        for staging in shards.glob(f'.run_{run}.*'):
            if staging.is_dir():
                shutil.rmtree(staging)  # No live worker can own this run's lock.
        return _process_run(row, raw_root, shards, bootstrap, code_hashes)


def _process_run(row, raw_root, shards, bootstrap, code_hashes):
    """Return a verified completed shard; catch run errors, not interrupts."""
    run = row['run_number']
    path = (Path(raw_root)/row['source_file']).resolve()
    raw_identity = _input_identity(path)
    fingerprint = dict(schema=1, catalog_row=row, input=raw_identity,
                       bootstrap=bootstrap, dca_max_cm=.4, code_hashes=code_hashes)
    destination = Path(shards)/f'run_{run}'
    if destination.exists():
        saved = json.loads((destination/'record.json').read_text())
        if saved['fingerprint'] != fingerprint:
            raise ValueError(f'run {run}: resume fingerprint mismatch; use a new campaign')
        if _sha256(destination/'plots.npz') != saved['archive_sha256']:
            raise ValueError(f'run {run}: corrupt completed shard')
        return saved['record'], True
    started = time.monotonic()
    raw_events = None
    counts = {}
    summary = None
    error = None
    with atomic_output_directory(destination, overwrite=False) as out:
        try:
            if 'stat_error' in raw_identity:
                raise OSError(raw_identity['errno'], f"{raw_identity['stat_error']}: cannot stat raw input")
            # Obtain entry count even when chamber branches are absent.
            with uproot.open(path) as source:
                raw_events = int(source['h70'].num_entries)
            with tempfile.TemporaryDirectory(prefix=f'vertex-{run}-', dir=out) as scratch:
                vertex_dir = Path(scratch)/'vertices'
                summary = analyze([path], vertex_dir, plots=False, expected_run=run)
                counts = summary['runs'].get(str(run), {})
                with uproot.open(vertex_dir/'vertices.root') as source:
                    data = source['vertices'].arrays(library='np')
                record, xyz, mask = _analyze_run(run, data, {'events_read': raw_events}, bootstrap)
            if not raw_events:
                status, note = 'empty_input', 'h70 contains no events'
            elif not counts.get('events_with_chamber_tracks', 0):
                status, note = 'no_chamber_tracks', 'No chamber tracks; chambers may be off or unusable'
            elif not counts.get('valid_pairs', 0):
                status, note = 'no_valid_vertices', 'No valid central pair vertex from chamber tracks'
            elif not record['selected_events']:
                status, note = 'no_selected_vertices', 'No exactly-two-charge vertex with DCA <= 4 mm'
            else:
                status = 'completed'
                note = '' if record['length_fit']['status'] == 'approximate' else record['length_fit']['status']
                if record['length_fit'].get('model_check') == 'poor_shape_agreement':
                    note = '; '.join(filter(None, [note, 'poor_shape_agreement']))
            record.update(reconstruction_status=status, reconstruction_note=note)
        except Exception as exc:
            error = traceback.format_exc()
            status = ('missing_input' if isinstance(exc, FileNotFoundError) else
                      'missing_geometry_branches' if 'missing branches' in str(exc) else 'reconstruction_failed')
            record, xyz, data, mask = _failed_record(run, raw_events, status, f'{type(exc).__name__}: {exc}')
        # Inputs changing mid-run invalidate the attempt, including after a read error.
        if _input_identity(path) != raw_identity:
            record, xyz, data, mask = _failed_record(run, raw_events, 'input_changed', 'Raw file changed during processing')
        record.update(catalog={key: row[key] for key in
                              ('target', 'beam_type', 'source_period', 'classification_source')},
                      raw_source_files=[str(path)],
                      raw_input_identity=raw_identity,
                      raw_root_uuid=summary['files'][0]['root_uuid'] if summary else None,
                      events_with_chamber_tracks=counts.get('events_with_chamber_tracks'),
                      elapsed_seconds=time.monotonic()-started)
        with ZipFile(out/'plots.npz', 'w', compression=ZIP_DEFLATED, allowZip64=True) as archive:
            write_run(archive, run, xyz, data, mask, record)
        saved = dict(fingerprint=fingerprint, record=record, vertex_summary=summary,
                     archive_sha256=_sha256(out/'plots.npz'))
        _json(out/'record.json', saved)
        if error:
            (out/'error.log').write_text(error)
    return record, False


def merge_shards(campaign, catalog, rows, *, plots=True):
    """Merge only the declared run set after all its shards have been verified."""
    campaign = Path(campaign)
    catalog = Path(catalog).resolve()
    manifest = json.loads((campaign/'campaign.json').read_text())
    if manifest['catalog_sha256'] != _sha256(catalog):
        raise ValueError('catalog changed during campaign')
    report = dict(schema=2, created_utc=datetime.now(timezone.utc).isoformat(),
                  status='run_and_period_target_campaign', dca_max_cm=.4,
                  coordinate_frame='native_h70_detector', run_archive_units='cm', period_xy_edges_units='mm',
                  selection='status=0, exactly two eligible central charges, finite xyz, 0<=DCA<=0.4 cm; one vertex/event',
                  vertex_campaign=str(campaign), catalog={'path': str(catalog), 'sha256': _sha256(catalog)},
                  code_hashes=manifest['code_hashes'], campaign=manifest, runs={})
    catalog_runs = defaultdict(list)
    for row in validate_manifest(catalog):
        catalog_runs[row.source_period].append(row.run_number)
    with atomic_output_directory(campaign/'products', overwrite=False) as out:
        with ZipFile(out/'run_plots.npz', 'w', compression=ZIP_DEFLATED, allowZip64=True) as archive:
            for row in sorted(rows, key=lambda r: r['run_number']):
                run = str(row['run_number'])
                shard = campaign/'runs'/f'run_{run}'
                saved = json.loads((shard/'record.json').read_text())
                expected = dict(schema=1, catalog_row=row,
                                input=_input_identity((Path(manifest['raw_root'])/row['source_file']).resolve()),
                                bootstrap=manifest['bootstrap'], dca_max_cm=.4, code_hashes=manifest['code_hashes'])
                if saved['fingerprint'] != expected or saved['record']['run'] != int(run):
                    raise ValueError(f'run {run}: changed input or shard identity')
                if _sha256(shard/'plots.npz') != saved['archive_sha256']:
                    raise ValueError(f'run {run}: corrupt archive')
                report['runs'][run] = saved['record']
                with ZipFile(shard/'plots.npz') as source:
                    for name in source.namelist():
                        if not name.startswith(f'run_{run}_') or not name.endswith('.npy'):
                            raise ValueError(f'run {run}: unexpected archive member {name}')
                        with source.open(name) as src, archive.open(name, 'w', force_zip64=True) as dst:
                            shutil.copyfileobj(src, dst)
            report['periods'] = aggregate_periods(report['runs'], catalog_runs)
            exported = finish_archive(archive, report)
        _write_tables(out, report)
        _json(out/'metadata.json', exported)
        _json(out/'geant4_candidates.json', _geant4_candidates(report))
        if plots:
            render_periods(out/'run_plots.npz', report, out)
        _json(out/'checksums.json', {p.name: _sha256(p) for p in sorted(out.iterdir()) if p.is_file()})
    return report


def run_campaign(raw_root, catalog, output, *, workers=4, bootstrap=32, runs=None, plots=True):
    if workers < 1 or bootstrap < 0:
        raise ValueError('workers must be positive and bootstrap nonnegative')
    raw_root, catalog, output = (Path(p).resolve() for p in (raw_root, catalog, output))
    rows = [asdict(row) for row in validate_manifest(catalog)]
    if runs is not None:
        requested = set(runs)
        if requested-set(row['run_number'] for row in rows):
            raise ValueError('requested runs absent from catalog')
        rows = [row for row in rows if row['run_number'] in requested]
    if not rows:
        raise ValueError('empty campaign')
    output.mkdir(parents=True, exist_ok=True)
    with (output/'campaign.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        manifest = dict(schema=1, raw_root=str(raw_root), catalog_sha256=_sha256(catalog),
                        runs=[row['run_number'] for row in rows], bootstrap=bootstrap,
                        plots=plots, code_hashes=source_hashes(),
                        versions={name: version(name) for name in ('numpy', 'scipy', 'uproot', 'awkward', 'matplotlib')},
                        python=sys.version)
        manifest_path = output/'campaign.json'
        if manifest_path.exists():
            if json.loads(manifest_path.read_text()) != manifest:
                raise ValueError('campaign fingerprint mismatch; use a new output directory')
        else:
            _json(manifest_path, manifest)
        if (output/'products').exists():
            if not any((output/'products').iterdir()):
                (output/'products').rmdir()
        for staging in output.glob('.products.*'):
            if staging.is_dir():
                shutil.rmtree(staging)
        if (output/'products').exists():
            for row in rows:
                saved = json.loads((output/'runs'/f"run_{row['run_number']}"/'record.json').read_text())
                current = _input_identity((raw_root/row['source_file']).resolve())
                if saved['fingerprint']['input'] != current:
                    raise ValueError(f"run {row['run_number']}: raw input changed after completion")
            checksums = json.loads((output/'products/checksums.json').read_text())
            if any(_sha256(output/'products'/name) != digest for name, digest in checksums.items()):
                raise ValueError('completed product checksum mismatch')
            LOG.info('Campaign products already complete: %s', output/'products')
            return output/'products'
        (output/'runs').mkdir(exist_ok=True)
        with ProcessPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(process_run, row, raw_root, output/'runs', bootstrap,
                                   manifest['code_hashes']) for row in rows]
            for i, future in enumerate(as_completed(futures), 1):
                record, resumed = future.result()
                status, fit = record['reconstruction_status'], record['length_fit']['status']
                level = (logging.INFO if status == 'completed' and fit == 'approximate'
                         and not record['reconstruction_note'] else logging.WARNING)
                LOG.log(level, '%s/%s run %s: %s; fit=%s; selected=%s; %s%s',
                        i, len(rows), record['run'], status, fit, record['selected_events'],
                        record['reconstruction_note'], '; resumed' if resumed else '')
        merge_shards(output, catalog, rows, plots=plots)
        LOG.info('COMPLETE %s runs: %s', len(rows), output/'products')
    return output/'products'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raw-root', type=Path, required=True)
    parser.add_argument('--catalog', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--workers', type=int, default=4)
    parser.add_argument('--bootstrap', type=int, default=32)
    parser.add_argument('--runs', type=int, nargs='+')
    parser.add_argument('--no-plots', action='store_true')
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s', force=True)
    run_campaign(args.raw_root, args.catalog, args.output, workers=args.workers,
                 bootstrap=args.bootstrap, runs=args.runs, plots=not args.no_plots)


if __name__ == '__main__':
    main()
