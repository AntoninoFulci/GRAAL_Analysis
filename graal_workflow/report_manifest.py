"""Completion boundary for portable reports; never certifies scientific conclusions."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess


MANIFEST = 'metadata/report_manifest.json'
REPORT_SUFFIXES = {'.pdf', '.png', '.jpg', '.jpeg', '.json', '.csv', '.txt', '.log', '.yaml', '.yml'}


def report_files(campaign: Path, *, historical: bool = False) -> list[Path]:
    """Enumerate reports only, rejecting aliases even when they stay in the root."""
    roots = [campaign] if historical else [campaign / 'plots', campaign / 'metadata']
    files = []
    for root in roots:
        if root.is_symlink():
            raise ValueError(f'symlink report directory: {root}')
        if not root.exists():
            continue
        for path in sorted(root.rglob('*')):
            if path.is_symlink():
                raise ValueError(f'symlink in reports: {path}')
            relative = path.relative_to(campaign)
            if any(part in {'artifacts', '_cache'} for part in relative.parts):
                continue
            if path.is_file() and path.suffix.lower() in REPORT_SUFFIXES and relative.as_posix() != MANIFEST:
                files.append(path)
    return sorted(files)


def file_record(path: Path, root: Path) -> dict:
    content = path.read_bytes()
    return {'path': path.relative_to(root).as_posix(), 'size': len(content),
            'sha256': hashlib.sha256(content).hexdigest()}


def revision(repo_root: Path) -> dict:
    def git(*args):
        try:
            result = subprocess.run(['git', '-C', str(repo_root), *args], capture_output=True, text=True, check=False)
            return result.stdout.strip() if result.returncode == 0 else None
        except OSError:
            return None
    status = git('status', '--porcelain')
    return {'source_revision': git('rev-parse', 'HEAD') or 'unknown',
            'source_dirty': None if status is None else bool(status)}


def complete_campaign(campaign: Path, *, repo_root: Path, mode: str,
                      now: datetime | None = None) -> dict:
    """Called by launchers only after all requested stages and publication succeed."""
    if mode not in {'production', 'test_data'}:
        raise ValueError(f'invalid campaign mode: {mode}')
    completed = now or datetime.now(timezone.utc)
    if completed.tzinfo is None:
        raise ValueError('completion time needs a timezone')
    payload = {'schema_version': 1, 'campaign': campaign.name, 'status': 'complete',
               'mode': mode, 'completed_at': completed.isoformat(), **revision(repo_root),
               'files': [file_record(path, campaign) for path in report_files(campaign)]}
    target = campaign / MANIFEST
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix('.tmp')
    try:
        temporary.write_text(json.dumps(payload, indent=2, allow_nan=False) + '\n', encoding='utf-8')
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
    return payload


def read_manifest(campaign: Path) -> dict:
    target = campaign / MANIFEST
    if target.is_symlink():
        raise ValueError('symlink manifest')
    payload = json.loads(target.read_text(encoding='utf-8'))
    if (not isinstance(payload, dict) or payload.get('schema_version') != 1
            or payload.get('status') != 'complete' or payload.get('mode') not in {'production', 'test_data'}):
        raise ValueError(f'invalid completion manifest: {target}')
    if (not isinstance(payload.get('source_revision'), str) or not payload['source_revision']
            or payload.get('source_dirty') not in (True, False, None)):
        raise ValueError('invalid source provenance')
    completed = datetime.fromisoformat(payload['completed_at'])
    if completed.tzinfo is None:
        raise ValueError('completion time needs a timezone')
    actual = [file_record(path, campaign) for path in report_files(campaign)]
    if payload.get('files') != actual:
        raise ValueError(f'reports changed since completion: {campaign}')
    return payload
