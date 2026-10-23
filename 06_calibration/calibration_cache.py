"""Content-addressed measured calibration bundles; no wall-clock expiration.

The producer owns this cache. ROOT and its original QA are published as a pair;
relocated consumers retain honest original source labels in QA and record their
current resolved inputs in a separate receipt. Threads remain scientific inputs:
RDataFrame sample claims and floating point merge order are schedule dependent.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import importlib
import importlib.metadata
import json
from pathlib import Path
import shutil
import sys

from calibration.calibration_qa import load_calibration_qa, sha256_file
from graal_common.io.filesystem import atomic_output_directory

CACHE_SCHEMA = 1
ROOT_NAME = 'flux_calibrated.root'
QA_NAME = 'flux_calibrated.qa.json'
RECEIPT_NAME = 'calibration_reuse.json'


def _json(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def content_key(signature: dict) -> str:
    return hashlib.sha256(_json(signature).encode()).hexdigest()


def implementation_identity(driver: Path) -> list[dict]:
    """Hash the installed implementation, using package-relative labels only."""
    rows = []
    for name in ('calibration', 'graal_common'):
        package = importlib.import_module(name)
        root = Path(package.__file__).resolve().parent
        sources = sorted(p for p in root.rglob('*.py') if 'tests' not in p.relative_to(root).parts)
        if not sources:
            raise ValueError(f'empty installed source inventory: {name}')
        if name == 'calibration':
            header = root / 'native/strip_energy_rdf.hxx'
            if not header.is_file():
                raise ValueError('missing installed calibration native resource')
            sources = sorted([*sources, header])
        rows.extend(dict(source=f'{name}/{p.relative_to(root).as_posix()}', sha256=sha256_file(p)) for p in sources)
    rows.append(dict(source='executed_driver', sha256=sha256_file(driver)))
    return rows


def h80_identity(directory: Path) -> list[dict]:
    paths = sorted(p for p in Path(directory).rglob('*.root') if p.is_file())
    if not paths:
        raise ValueError('empty h80 cohort')
    return [dict(path=p.relative_to(directory).as_posix(), size=p.stat().st_size,
                 sha256=sha256_file(p)) for p in paths]


def _diagnostic_markers(directory: Path, *, production: bool) -> dict:
    import uproot
    markers = {}
    marker = Path(directory) / 'manifest.json'
    if marker.is_file():
        payload = json.loads(marker.read_text())
        markers['manifest.json'] = sha256_file(marker)
        if production and payload.get('diagnostic_only'):
            raise ValueError('diagnostic sample is forbidden in production calibration')
    for path in sorted(Path(directory).rglob('*.root')):
        with uproot.open(path) as source:
            if 'sample_provenance' in source:
                obj = source['sample_provenance']
                payload = json.loads(obj.member('fTitle') if obj.classname == 'TNamed' else str(obj))
                if production and payload.get('diagnostic_only'):
                    raise ValueError(f'diagnostic sample is forbidden in production calibration: {path}')
    return markers


def calibration_signature(args: argparse.Namespace, *, driver: Path) -> dict:
    import ROOT
    from calibration.strip_energy_flux import FLUX_SCHEMA_VERSION
    scope = args.cache_scope
    if scope not in ('production', 'diagnostic'):
        raise ValueError('cache scope must be production or diagnostic')
    # Keep all producer options, including future options, except locations and
    # reporting cadence. Thus new scientific flags invalidate by default.
    excluded = {'preanalysis_dir', 'manifest', 'flux', 'output_dir', 'cache_root',
                'cache_scope', 'progress_every_events'}
    options = {k: v for k, v in vars(args).items() if k not in excluded}
    return dict(schema_version=CACHE_SCHEMA, flux_schema_version=FLUX_SCHEMA_VERSION,
                scope=scope, manifest=sha256_file(args.manifest), raw_flux=sha256_file(args.flux),
                h80=h80_identity(args.preanalysis_dir),
                sample_markers=_diagnostic_markers(args.preanalysis_dir, production=scope == 'production'),
                options=options, implementation=implementation_identity(driver),
                runtime=dict(python=list(sys.version_info[:3]), root=str(ROOT.gROOT.GetVersion()),
                             numpy=importlib.metadata.version('numpy'), uproot=importlib.metadata.version('uproot')))


@contextmanager
def bundle_lock(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a+') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def _validate_bundle(directory: Path, signature: dict) -> dict:
    record = json.loads((directory / 'bundle.json').read_text())
    if record.get('signature') != signature or record.get('key') != content_key(signature):
        raise ValueError('calibration bundle signature mismatch')
    for name in (ROOT_NAME, QA_NAME):
        if record.get('outputs', {}).get(name) != sha256_file(directory / name):
            raise ValueError('calibration bundle output identity mismatch')
    qa = load_calibration_qa(directory / QA_NAME, directory / ROOT_NAME,
                             expected_inputs={k: signature[k] for k in ('manifest', 'raw_flux')})
    producer_root = Path(record['producer_inputs']['preanalysis_dir'])
    try:
        cohort = [dict(path=Path(row[0]).relative_to(producer_root).as_posix(), size=row[1], sha256=row[3])
                  for row in qa['inputs']['h80']]
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise ValueError('calibration QA cohort provenance invalid') from exc
    if cohort != signature['h80']:
        raise ValueError('calibration QA cohort mismatch')
    return record


def run_cached_calibration(args: argparse.Namespace, builder, *, driver: Path) -> int:
    """Resolve/rebuild one locked bundle and atomically copy its pair to a campaign."""
    cache_root, output = Path(args.cache_root).resolve(), Path(args.output_dir).resolve()
    if args.cache_scope == 'diagnostic' and 'results_test' not in cache_root.parts:
        raise ValueError('diagnostic calibration cache must be under results_test')
    inputs = [Path(args.preanalysis_dir).resolve(), Path(args.manifest).resolve(), Path(args.flux).resolve()]
    for destination in (cache_root, output):
        for source in inputs:
            if destination == source or destination in source.parents or (source.is_dir() and source in destination.parents):
                raise ValueError('calibration publication overlaps inputs')
    if cache_root == output or output in cache_root.parents or cache_root in output.parents:
        raise ValueError('campaign and calibration cache must not overlap')
    signature = calibration_signature(args, driver=driver)
    key = content_key(signature)
    destination = cache_root / key
    resolved_inputs = dict(preanalysis_dir=str(inputs[0]), manifest=str(inputs[1]), raw_flux=str(inputs[2]),
                           driver=str(Path(driver).resolve()))
    with bundle_lock(cache_root / f'.{key}.lock'):
        try:
            record = _validate_bundle(destination, signature)
            reused = True
        except (OSError, ValueError, KeyError, TypeError):
            reused = False
            with atomic_output_directory(destination) as staged:
                build_args = argparse.Namespace(**{**vars(args), 'output_dir': staged})
                result = builder(build_args)
                if result != 0:
                    raise RuntimeError(f"calibration builder failed with exit {result}")
                if calibration_signature(args, driver=driver) != signature:
                    raise ValueError('calibration input or implementation changed during scan')
                load_calibration_qa(staged / QA_NAME, staged / ROOT_NAME,
                                    expected_inputs={k: signature[k] for k in ('manifest', 'raw_flux')})
                record = dict(key=key, signature=signature, producer_inputs=resolved_inputs,
                              outputs={name: sha256_file(staged / name) for name in (ROOT_NAME, QA_NAME)})
                (staged / 'bundle.json').write_text(json.dumps(record, indent=2, sort_keys=True) + '\n')
                _validate_bundle(staged, signature)
        # Recheck on hits as well; a changed source cannot be hidden by waiting
        # for a competing producer. QA keeps original paths after relocation.
        if calibration_signature(args, driver=driver) != signature:
            raise ValueError('calibration input or implementation changed during reuse')
        receipt = dict(schema_version=1, key=key, reused=reused, scope=args.cache_scope, signature=signature,
                       bundle=str(destination), producer_inputs=record['producer_inputs'],
                       resolved_inputs=resolved_inputs, outputs=record['outputs'])
        with bundle_lock(output.parent / f'.{output.name}.calibration.lock'):
            with atomic_output_directory(output) as staged:
                if output.exists():
                    shutil.copytree(output, staged, dirs_exist_ok=True)
                for name in (ROOT_NAME, QA_NAME):
                    shutil.copyfile(destination / name, staged / name)
                    if sha256_file(staged / name) != record['outputs'][name]:
                        raise ValueError('calibration bundle changed while copying')
                (staged / RECEIPT_NAME).write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n')
                if calibration_signature(args, driver=driver) != signature:
                    raise ValueError('calibration input or implementation changed during publication')
    print(f"Calibration {'reused' if reused else 'built'}: {key} from {destination}", flush=True)
    return 0
