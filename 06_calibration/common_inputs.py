"""Validated shared input references, rooted in an explicit checkout or cache.

Schema 1 stores one authority per input, with exact byte identities. Run catalog
classification and frozen exclusions remain independent; neither implies a
universal list of good runs. Bundle references never adopt experimental policy.
"""
from __future__ import annotations

import json
from pathlib import Path

from calibration.calibration_qa import sha256_file
from calibration.run_manifest import validate_manifest
from calibration.run_quality import load_run_quality, _unique_object


def resolve_reference(reference: dict, *, checkout: Path, cache: Path) -> Path:
    if not isinstance(reference, dict) or reference.get('root') not in ('checkout', 'cache'):
        raise ValueError('common input reference needs checkout/cache root')
    relative = reference.get('path')
    if (not isinstance(relative, str) or not relative or Path(relative).is_absolute()
            or '..' in Path(relative).parts):
        raise ValueError('common input path must be relative without traversal')
    root = Path(checkout if reference['root'] == 'checkout' else cache).resolve()
    resolved = (root / relative).resolve()
    # Only explicitly declared data inputs may follow links onto a farm/server.
    # Cache references keep their containment contract, including through links.
    external_input = reference['root'] == 'checkout' and Path(relative).parts[:1] == ('data',)
    if not resolved.is_relative_to(root) and not external_input:
        raise ValueError('common input reference escapes its declared root')
    return resolved


def verified_reference(reference: dict, *, checkout: Path, cache: Path) -> Path:
    path = resolve_reference(reference, checkout=checkout, cache=cache)
    digest = reference.get('sha256')
    if (not isinstance(digest, str) or len(digest) != 64
            or any(c not in '0123456789abcdef' for c in digest)
            or sha256_file(path) != digest):
        raise ValueError(f'common input identity mismatch: {path}')
    return path


def load_common_inputs(checkout: Path, *, path: Path | None = None,
                       cache: Path | None = None, verify: bool = True) -> dict:
    """Resolve paths from explicit roots; verification hashes the actual inputs.

    ``verify=False`` is only for pure planning. Preflight always verifies bytes
    and existing catalog/policy validators before executing scientific work.
    Count bundles are opt-in named references, never inferred from cache age.
    """
    checkout = Path(checkout).resolve()
    cache = Path(cache).resolve() if cache is not None else checkout / 'results/_cache'
    path = Path(path) if path is not None else checkout / 'config/common_inputs.json'
    payload = json.loads(path.read_text(), object_pairs_hook=_unique_object)
    if (not isinstance(payload, dict) or type(payload.get('schema_version')) is not int
            or payload['schema_version'] != 1):
        raise ValueError('unsupported common input schema')
    if set(payload) != {'schema_version', 'inputs', 'bundles'}:
        raise ValueError('invalid common input fields')
    if set(payload['inputs']) != {'run_catalog', 'run_quality', 'raw_flux'}:
        raise ValueError('common inputs require catalog, quality and raw flux')
    resolver = verified_reference if verify else resolve_reference
    resolved = {name: resolver(ref, checkout=checkout, cache=cache)
                for name, ref in payload['inputs'].items()}
    bundles = payload['bundles']
    if (not isinstance(bundles, dict) or set(bundles) != {'calibration', 'inclusive_counts'}
            or not isinstance(bundles['inclusive_counts'], dict)):
        raise ValueError('invalid common bundle declarations')
    calibration = bundles['calibration']
    if calibration != {'root': 'cache', 'path': '06_calibration', 'schema_version': 1}:
        raise ValueError('unsupported measured calibration cache declaration')
    for ref in bundles['inclusive_counts'].values():
        resolve_reference(ref, checkout=checkout, cache=cache)
        if type(ref.get('diagnostic_only')) is not bool or not isinstance(ref.get('sha256'), str):
            raise ValueError('count bundle needs identity and diagnostic scope')
    if verify:
        records = validate_manifest(resolved['run_catalog'])
        if any(row.classification_source != 'manual' for row in records):
            raise ValueError('common run catalog must retain manual classifications')
        load_run_quality(resolved['run_quality'])
    return dict(path=path.resolve(), sha256=sha256_file(path), inputs=resolved,
                bundles=bundles, checkout=checkout, cache=cache)


def common_counts_path(common: dict, name: str, *, production: bool = False) -> Path:
    try:
        reference = common['bundles']['inclusive_counts'][name]
    except KeyError:
        raise ValueError(f'unknown inclusive count bundle: {name}') from None
    if production and reference['diagnostic_only']:
        raise ValueError('diagnostic count bundle is forbidden in production')
    path = verified_reference(reference, checkout=common['checkout'], cache=common['cache'])
    payload = json.loads(path.read_text(), object_pairs_hook=_unique_object)
    if (payload.get('schema_version') != 1
            or payload.get('diagnostic_only') is not reference['diagnostic_only']):
        raise ValueError('inclusive count bundle scope/schema mismatch')
    return path
