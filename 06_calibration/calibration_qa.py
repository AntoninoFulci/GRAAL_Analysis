"""Content-bound provenance for calibrated, measured flux."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import tempfile


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def write_calibration_qa(path: Path, calibrated_path: Path, *, inputs: dict,
                         coverage: list[dict], diagnostics: dict) -> None:
    payload = dict(schema_version=1, calibrated_sha256=sha256_file(calibrated_path),
                   inputs=inputs, coverage=coverage, diagnostics=diagnostics)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f'.{path.name}.', dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(payload, stream, indent=2, sort_keys=True, allow_nan=False)
            stream.write('\n')
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def load_calibration_qa(path: Path, calibrated_path: Path, *, expected_inputs: dict) -> dict:
    with Path(path).open() as stream:
        payload = json.load(stream)
    if not isinstance(payload, dict) or payload.get('schema_version') != 1:
        raise ValueError('unsupported calibration QA schema')
    if (payload.get('calibrated_sha256') != sha256_file(calibrated_path)
            or any(payload.get('inputs', {}).get(key) != value
                   for key, value in expected_inputs.items())):
        raise ValueError('calibration QA identity mismatch')
    if not isinstance(payload.get('coverage'), list):
        raise ValueError('invalid calibration QA coverage')
    return payload
