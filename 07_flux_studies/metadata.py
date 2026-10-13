"""Acquisition evidence; absent conditions never imply compatibility."""
from __future__ import annotations

from datetime import datetime
import json
import math
from pathlib import Path
from typing import Sequence

from calibration.run_manifest import RunRecord

STATES = ('POL1', 'POL2', 'BREM')
RunKey = tuple[int, str]
GROUP_FIELDS = ('source_period', 'target', 'beam_type', 'configuration_id', 'laser_id')


def _utc(value):
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError('acquisition timestamp must be a UTC string')
    date = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if date.tzinfo is None or date.utcoffset().total_seconds() != 0:
        raise ValueError('acquisition timestamps must specify UTC')
    return date.timestamp()


def load_metadata(path: Path | None, manifest: Sequence[RunRecord]) -> dict[RunKey, dict]:
    if path is None:
        return {}
    payload = json.loads(Path(path).read_text())
    if not isinstance(payload, dict) or payload.get('schema_version') != 1 or not isinstance(payload.get('records'), list):
        raise ValueError('invalid acquisition metadata schema')
    known = {row.run_number: row for row in manifest}
    result = {}
    for raw in payload['records']:
        if not isinstance(raw, dict):
            raise ValueError('metadata record must be an object')
        run, state = raw.get('run_number'), raw.get('state')
        if type(run) is not int or run not in known or state not in STATES:
            raise ValueError('unknown metadata run/state')
        key = (run, state)
        if key in result:
            raise ValueError(f'duplicate metadata: {key}')
        if not isinstance(raw.get('source'), str) or not raw['source'].strip():
            raise ValueError('metadata source is required')
        record = dict(raw)
        for field in ('source_period', 'target', 'beam_type'):
            value = getattr(known[run], field)
            if raw.get(field, value) != value:
                raise ValueError(f'metadata conflicts with manifest: {field}')
            record[field] = value
        for field in ('configuration_id', 'laser_id', 'experiment_group'):
            value = raw.get(field)
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise ValueError(f'invalid {field}')
            record[field] = value
        record['start'] = _utc(raw.get('start_utc'))
        record['end'] = _utc(raw.get('end_utc'))
        if record['start'] is not None and record['end'] is not None and record['end'] < record['start']:
            raise ValueError('reversed acquisition interval')
        exposure = raw.get('exposure')
        if exposure is not None:
            if not isinstance(exposure, dict):
                raise ValueError('exposure must be an object')
            exposure = dict(exposure)
            for name in ('value', 'error'):
                value = exposure.get(name)
                if name == 'error' and value is None:
                    continue
                if type(value) not in (int, float) or not math.isfinite(value) or value < 0 or (name == 'value' and value == 0):
                    raise ValueError(f'invalid exposure {name}')
            for name in ('unit', 'definition'):
                if not isinstance(exposure.get(name), str) or not exposure[name].strip():
                    raise ValueError(f'exposure {name} required')
            exposure.setdefault('error', None)
            exposure.setdefault('uncertainty_group', None)
            group = exposure['uncertainty_group']
            if group is not None and (not isinstance(group, str) or not group.strip()):
                raise ValueError('invalid exposure uncertainty group')
        record['exposure'] = exposure
        result[key] = record
    groups = {}
    for row in result.values():
        exposure = row['exposure']
        if exposure and exposure['uncertainty_group']:
            group = exposure['uncertainty_group']
            meaning = (exposure['unit'], exposure['definition'])
            if group in groups and groups[group] != meaning:
                raise ValueError('inconsistent shared exposure uncertainty meaning')
            groups[group] = meaning
    return result


def compatible(a: dict, b: dict) -> bool:
    return all(a.get(name) is not None and a.get(name) == b.get(name)
               for name in (*GROUP_FIELDS, 'state'))


def acquisition_midpoint(record: dict) -> float:
    if record.get('start') is None or record.get('end') is None:
        raise ValueError('acquisition interval unavailable')
    return (record['start'] + record['end']) / 2


def eligible(record: dict) -> bool:
    return (all(record.get(field) is not None for field in GROUP_FIELDS)
            and record.get('start') is not None and record.get('end') is not None)


def temporal_run_blocks(metadata, runs):
    """Chronological run clusters; overlapping acquisitions stay indivisible.

    Caller supplies metadata from one compatible configuration.
    """
    allowed = set(runs)
    intervals = {}
    for (run, state), row in metadata.items():
        if run not in allowed or not eligible(row):
            continue
        start, end = intervals.get(run, (row['start'], row['end']))
        intervals[run] = min(start, row['start']), max(end, row['end'])
    blocks, end = [], float('-inf')
    for run in sorted(intervals, key=lambda r: (intervals[r][0], r)):
        start, stop = intervals[run]
        if blocks and start <= end:
            blocks[-1].append(run)
            end = max(end, stop)
        else:
            blocks.append([run])
            end = stop
    return blocks
