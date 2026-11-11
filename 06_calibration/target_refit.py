"""Refit archived selected vertices with local edges; rebuild period products.

No raw reconstruction or scientific input is overwritten. Failed reconstruction
rows retain their original status. Immutable run shards allow safe resumption.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from contextlib import contextmanager
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
import fcntl
import json
import logging
from pathlib import Path
import shutil
import sys
from zipfile import ZipFile, ZIP_DEFLATED

import numpy as np
import scipy
from graal_common.io.filesystem import atomic_output_directory
if __package__:
    from .target_database import _analyze_run, _sha256, _write_tables, _geant4_candidates
    from .target_archive import write_run, finish_archive, render_periods
    from .target_periods import aggregate_periods
    from .run_manifest import validate_manifest
    from .target_batch import _json, source_hashes
    from .target_fit import observed_xy
else:
    from target_database import _analyze_run, _sha256, _write_tables, _geant4_candidates
    from target_archive import write_run, finish_archive, render_periods
    from target_periods import aggregate_periods
    from run_manifest import validate_manifest
    from target_batch import _json, source_hashes
    from target_fit import observed_xy

LOG=logging.getLogger(__name__)
_SOURCE=None
_METADATA=None


def _init_worker(archive):
    global _SOURCE, _METADATA
    _SOURCE=np.load(archive,allow_pickle=False)
    _METADATA=json.loads(_SOURCE['metadata_json'].item())


def _read_data(archive, run, row):
    prefix=f'run_{run}_'
    xyz=archive[prefix+'xyz_cm']
    if xyz.ndim!=2 or xyz.shape[1]!=3 or not np.isfinite(xyz).all():
        raise ValueError(f'run {run}: invalid xyz archive shape or values')
    n=len(xyz)
    if n!=row['selected_events']:
        raise ValueError(f'run {run}: selected event count mismatch')
    data={key:archive[prefix+key] for key in ('dca_cm','source_file','source_entry')}
    if any(value.shape!=(n,) for value in data.values()):
        raise ValueError(f'run {run}: inconsistent event-array lengths')
    if not np.isfinite(data['dca_cm']).all() or np.any((data['dca_cm']<0)|(data['dca_cm']>.4)):
        raise ValueError(f'run {run}: selected DCA contract violated')
    if any(not np.issubdtype(data[key].dtype,np.integer) for key in ('source_file','source_entry')):
        raise ValueError(f'run {run}: invalid event identifiers')
    data.update(run=np.full(n,int(run),dtype=np.int64),status=np.zeros(n,dtype=np.int64),
                n_charged=np.full(n,2,dtype=np.int64),**{f'{axis}_cm':xyz[:,i] for i,axis in enumerate('xyz')})
    # Reject corrupted or duplicated provenance before the fit-error boundary.
    identities=np.column_stack([data['source_file'],data['source_entry']])
    if len(np.unique(identities,axis=0))!=n:
        raise ValueError(f'run {run}: duplicated selected event identity')
    return data,xyz


def _refit_one(run, shards, bootstrap, fingerprint):
    destination=Path(shards)/f'run_{run}'
    with destination.with_suffix('.lock').open('w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if destination.is_dir() and not any(destination.iterdir()):
            destination.rmdir()
        for pending in destination.parent.glob(f'.run_{run}.*'):
            if pending.is_dir():shutil.rmtree(pending)
        if destination.exists():
            saved=json.loads((destination/'record.json').read_text())
            if saved['fingerprint']!=fingerprint or _sha256(destination/'plots.npz')!=saved['archive_sha256']:
                raise ValueError(f'run {run}: refit resume fingerprint/checksum mismatch')
            return run,saved['record']['length_fit']['status'],True
        previous=_METADATA['runs'][run]
        data,xyz=_read_data(_SOURCE,run,previous)
        try:
            fresh,_,mask=_analyze_run(run,data,{'events_read':previous['raw_events']},bootstrap)
        except Exception as exc:
            empty={k:v[:0] for k,v in data.items()}
            fresh,_,_=_analyze_run(run,empty,{'events_read':previous['raw_events']},0)
            fresh['length_fit'].update(status='fit_failed',note=f'{type(exc).__name__}: {exc}')
            counts=np.histogram(xyz[:,2],fresh['length_fit']['edges_cm'])[0]
            fresh['length_fit'].update(input_events=len(xyz),fit_events=int(counts.sum()),
                                       outside_fit_window=int(len(xyz)-counts.sum()),counts=counts.tolist())
            fresh['observed_xy']={**observed_xy(xyz[:,:2]),'outside_z_selection':0,
                                  'z_selection':'no z selection; local edge fit failed'}
            fresh['dca_variations_cm']={}
            fresh['window_variations_cm']={}
            fresh['selected_events']=len(xyz)
            mask=np.ones(len(xyz),dtype=bool)
            LOG.warning('run %s fit failed: %s',run,exc)
        record={**previous,**fresh}
        record['saved_pairs']=previous['saved_pairs']
        record['previous_length_cm']=previous['length_fit'].get('length_cm')
        record['previous_fit_status']=previous['length_fit']['status']
        record['refit_status']=fresh['length_fit']['status']
        if previous.get('reconstruction_status','completed')=='completed':
            notes=[]
            if record['length_fit']['status']!='approximate':notes.append(record['length_fit']['status'])
            if record['length_fit'].get('model_check')=='poor_shape_agreement':notes.append('poor_shape_agreement')
            record['reconstruction_note']='; '.join(notes)
        with atomic_output_directory(destination,overwrite=False) as out:
            with ZipFile(out/'plots.npz','w',compression=ZIP_DEFLATED,allowZip64=True) as archive:
                write_run(archive,run,xyz,data,mask,record)
            _json(out/'record.json',dict(record=record,fingerprint=fingerprint,
                                       archive_sha256=_sha256(out/'plots.npz')))
        return run,record['length_fit']['status'],False


@contextmanager
def _output_lock(output):
    output=Path(output).resolve()
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.with_name('.'+output.name+'.lock').open('w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if output.is_dir() and not any(output.iterdir()):
            output.rmdir()
        for staging in output.parent.glob('.'+output.name+'.*'):
            if staging.is_dir():shutil.rmtree(staging)
        yield output


def refit_archive(archive, catalog, output, *, work, workers=8, bootstrap=32):
    with _output_lock(output) as output:
        return _refit_archive(archive,catalog,output,work=work,workers=workers,bootstrap=bootstrap)


def _refit_archive(archive, catalog, output, *, work, workers=8, bootstrap=32):
    archive,catalog,output,work=(Path(p).resolve() for p in (archive,catalog,output,work))
    if workers<1 or bootstrap<0:
        raise ValueError('invalid worker or bootstrap count')
    if output.exists():raise FileExistsError(output)
    catalog_rows=validate_manifest(catalog)
    expected_hashes=json.loads((archive.parent/'checksums.json').read_text())
    archive_hash=_sha256(archive)
    if archive_hash!=expected_hashes[archive.name]:raise ValueError('source archive checksum mismatch')
    with np.load(archive,allow_pickle=False) as source:
        upstream=json.loads(source['metadata_json'].item())
    if upstream.get('schema')!=2 or upstream.get('dca_max_cm')!=.4 or upstream.get('coordinate_frame')!='native_h70_detector':
        raise ValueError('unsupported selected-vertex archive contract')
    if set(upstream['runs'])!={str(row.run_number) for row in catalog_rows}:
        raise ValueError('source/catalog run coverage mismatch')
    if upstream['catalog']['sha256']!=_sha256(catalog):raise ValueError('source/catalog hash mismatch')
    for row in catalog_rows:
        source_row=upstream['runs'][str(row.run_number)]
        if source_row['run']!=row.run_number or any(source_row['catalog'][k]!=getattr(row,k) for k in ('source_period','target','beam_type')):
            raise ValueError('source/catalog run identity mismatch')
    hashes={**source_hashes(), '06_calibration/target_refit.py':_sha256(Path(__file__))}
    fingerprint=dict(schema=1,archive_sha256=archive_hash,catalog_sha256=_sha256(catalog),
                     bootstrap=bootstrap,code_hashes=hashes,
                     versions=dict(python=sys.version,numpy=np.__version__,scipy=scipy.__version__))
    work.mkdir(parents=True,exist_ok=True)
    with (work/'refit.lock').open('w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        manifest=work/'manifest.json'
        if manifest.exists() and json.loads(manifest.read_text())!=fingerprint:
            raise ValueError('refit campaign changed; use new work directory')
        _json(manifest,fingerprint)
        shards=work/'runs';shards.mkdir(exist_ok=True)
        runs=sorted(upstream['runs'],key=int)
        with ProcessPoolExecutor(max_workers=workers,initializer=_init_worker,initargs=(archive,)) as pool:
            jobs=[pool.submit(_refit_one,run,shards,bootstrap,fingerprint) for run in runs]
            for count,future in enumerate(as_completed(jobs),1):
                run,status,resumed=future.result()
                LOG.log(logging.INFO if status=='approximate' else logging.WARNING,
                        '%s/%s run %s: %s%s',count,len(runs),run,status,'; resumed' if resumed else '')
        report=dict(schema=2,estimator_revision=2,status='local_edge_run_and_period_conditions',
                    created_utc=datetime.now(timezone.utc).isoformat(),dca_max_cm=.4,
                    coordinate_frame='native_h70_detector',run_archive_units='cm',period_xy_edges_units='mm',
                    selection=upstream['selection'],vertex_campaign=str(archive),
                    code_hashes=hashes,catalog={'path':str(catalog),'sha256':fingerprint['catalog_sha256']},
                    versions=fingerprint['versions'],
                    input_archive={'path':str(archive),'sha256':archive_hash},
                    upstream_provenance={k:v for k,v in upstream.items() if k not in ('runs','periods')},
                    method='independent local edges; run-specific seeds; equal-run period means; XY rebuilt inside new fitted edges',
                    robustness='DCA 2/3/4 mm and local halfwindows 1.2/1.6/2.0 cm; >0.5 cm length sensitivity excluded',
                    runs={})
        catalog_runs=defaultdict(list)
        for row in catalog_rows:catalog_runs[row.source_period].append(row.run_number)
        with atomic_output_directory(output,overwrite=False) as out:
            with ZipFile(out/'run_plots.npz','w',compression=ZIP_DEFLATED,allowZip64=True) as combined:
                for run in runs:
                    shard=shards/f'run_{run}'
                    saved=json.loads((shard/'record.json').read_text())
                    if saved['fingerprint']!=fingerprint or _sha256(shard/'plots.npz')!=saved['archive_sha256']:
                        raise ValueError(f'run {run}: changed shard')
                    report['runs'][run]=saved['record']
                    with ZipFile(shard/'plots.npz') as source:
                        for name in source.namelist():
                            if not name.startswith(f'run_{run}_') or not name.endswith('.npy'):
                                raise ValueError('unexpected shard member')
                            with source.open(name) as src,combined.open(name,'w',force_zip64=True) as dst:
                                shutil.copyfileobj(src,dst)
                report['periods']=aggregate_periods(report['runs'],catalog_runs)
                metadata=finish_archive(combined,report)
            _write_tables(out,report)
            _json(out/'metadata.json',metadata)
            _json(out/'geant4_candidates.json',_geant4_candidates(report))
            render_periods(out/'run_plots.npz',report,out)
            if _sha256(archive)!=archive_hash or _sha256(catalog)!=fingerprint['catalog_sha256']:
                raise ValueError('source input changed during refit')
            _json(out/'checksums.json',{p.name:_sha256(p) for p in sorted(out.iterdir()) if p.is_file()})
        LOG.info('COMPLETE %s runs, %s periods: %s',len(runs),len(report['periods']),output)
    return report



def reaggregate_products(archive, catalog, output):
    with _output_lock(output) as output:
        return _reaggregate_products(archive,catalog,output)


def _reaggregate_products(archive, catalog, output):
    """Apply period eligibility to immutable run fits without rerunning them."""
    archive,catalog,output=(Path(p).resolve() for p in (archive,catalog,output))
    checks=json.loads((archive.parent/'checksums.json').read_text())
    source_hash=_sha256(archive)
    if source_hash!=checks[archive.name]:raise ValueError('source archive checksum mismatch')
    catalog_hash=_sha256(catalog)
    catalog_runs=defaultdict(list)
    catalog_rows=validate_manifest(catalog)
    for row in catalog_rows:catalog_runs[row.source_period].append(row.run_number)
    with np.load(archive,allow_pickle=False) as arrays:
        report=json.loads(arrays['metadata_json'].item())
        if report['catalog']['sha256']!=catalog_hash or set(report['runs'])!={str(r.run_number) for r in catalog_rows}:
            raise ValueError('catalog differs from input products')
        report['fit_code_hashes']=report.get('fit_code_hashes',report['code_hashes'])
        report['code_hashes']={**source_hashes(),'06_calibration/target_refit.py':_sha256(Path(__file__))}
        report['aggregation_input']={'path':str(archive),'sha256':source_hash}
        report['aggregation_created_utc']=datetime.now(timezone.utc).isoformat()
        report['period_eligibility']='valid nominal fit and XY; at least one valid DCA variation and one valid window variation with different effective width; failed checks remain explicit'
        for run,row in report['runs'].items():
            prefix=f'run_{run}_'
            for key,suffix in [('edges_cm','z_edges_cm'),('counts','z_counts'),('expected_counts','z_expected_counts')]:
                values=arrays[prefix+suffix]
                row['length_fit'][key]=([float(v) if np.isfinite(v) else None for v in values]
                                        if len(values) else None)
            for key,suffix in [('x_edges_cm','x_edges_cm'),('y_edges_cm','y_edges_cm'),('counts','xy_counts')]:
                row['observed_xy'][key]=arrays[prefix+suffix].tolist()
        report['periods']=aggregate_periods(report['runs'],catalog_runs)
    with atomic_output_directory(output,overwrite=False) as out:
        with ZipFile(archive) as source,ZipFile(out/'run_plots.npz','w',compression=ZIP_DEFLATED,allowZip64=True) as destination:
            for name in source.namelist():
                if name.startswith('run_') and name.endswith('.npy'):
                    with source.open(name) as src,destination.open(name,'w',force_zip64=True) as dst:
                        shutil.copyfileobj(src,dst)
            metadata=finish_archive(destination,report)
        _write_tables(out,report)
        _json(out/'metadata.json',metadata)
        _json(out/'geant4_candidates.json',_geant4_candidates(report))
        render_periods(out/'run_plots.npz',report,out)
        if _sha256(archive)!=source_hash or _sha256(catalog)!=catalog_hash:
            raise ValueError('input changed during period aggregation')
        _json(out/'checksums.json',{p.name:_sha256(p) for p in sorted(out.iterdir()) if p.is_file()})
    LOG.info('COMPLETE period aggregation: %s',output)
    return report

def main(argv=None):
    argv=sys.argv[1:] if argv is None else argv
    if argv and argv[0]=='aggregate':
        parser=argparse.ArgumentParser(description='Rebuild periods from verified immutable run fits')
        parser.add_argument('archive',type=Path)
        parser.add_argument('--catalog',type=Path,required=True)
        parser.add_argument('--output',type=Path,required=True)
        args=parser.parse_args(argv[1:])
        logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s',force=True)
        reaggregate_products(args.archive,args.catalog,args.output)
        return
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive',type=Path)
    parser.add_argument('--catalog',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--work',type=Path,required=True)
    parser.add_argument('--workers',type=int,default=8)
    parser.add_argument('--bootstrap',type=int,default=32)
    args=parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s',force=True)
    refit_archive(args.archive,args.catalog,args.output,work=args.work,workers=args.workers,bootstrap=args.bootstrap)


if __name__=='__main__':main()
