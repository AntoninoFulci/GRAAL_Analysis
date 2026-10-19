"""Frozen, run-atomic quality policy shared by studies and observable extraction.

The diagnostic is descriptive only. It never writes policy or changes sample
membership: the default decisions were fixed from inspected development data.
"""
from __future__ import annotations

from collections import defaultdict
import hashlib
import json
import math
from numbers import Real
from pathlib import Path
import statistics

DEFAULT_RUN_QUALITY_PATH = Path(__file__).resolve().parents[1] / 'config/run_quality_exclusions.json'
SCHEMA_VERSION = 2
LOWER_RATIO, UPPER_RATIO = .01, 100.


def _positive(value):
    return isinstance(value, Real) and not isinstance(value, bool) and math.isfinite(value) and value > 0


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'duplicate key {key}')
        result[key] = value
    return result


def load_run_quality(path=None) -> dict:
    """Validate the complete policy and attach identity of the exact input bytes."""
    path = DEFAULT_RUN_QUALITY_PATH if path is None else Path(path)
    try:
        raw = path.read_bytes()
    except FileNotFoundError as exc:
        raise FileNotFoundError(f'run quality policy not found: {path}') from exc
    try:
        policy = json.loads(raw, object_pairs_hook=_unique_object)
        if type(policy.get('schema_version')) is not int or policy['schema_version'] != SCHEMA_VERSION:
            raise ValueError('unsupported schema_version')
        if policy.get('scope') != 'whole_run' or policy.get('selection_basis') != 'inspected_development_data':
            raise ValueError('scope and development selection basis must be explicit')
        if policy.get('criterion') != dict(lower_ratio=LOWER_RATIO, upper_ratio=UPPER_RATIO,
                                          reference='period_state_median_positive_finite_flux_per_event'):
            raise ValueError('invalid criterion')
        sources = policy['evidence_sources']
        if not isinstance(sources, dict) or not sources or any(
                not isinstance(name, str) or not name or not isinstance(digest, str)
                or len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest)
                for name, digest in sources.items()):
            raise ValueError('invalid evidence_sources')
        exclusions = policy['excluded_runs']
        if not isinstance(exclusions, list):
            raise ValueError('excluded_runs must be a list')
        seen = set()
        for item in exclusions:
            run = item['run']
            if type(run) is not int or run <= 0 or run in seen:
                raise ValueError('invalid or duplicate excluded run')
            seen.add(run)
            if any(not isinstance(item.get(key), str) or not item[key].strip()
                   for key in ('period', 'reason')):
                raise ValueError('excluded run needs period and reason')
            basis = item['decision_basis']
            if basis not in ('flux_per_event_factor_100', 'user_requested_development_benchmark_errors'):
                raise ValueError('invalid decision_basis')
            evidence = item['evidence']
            if not isinstance(evidence, list) or not evidence:
                raise ValueError('excluded run needs measured evidence')
            states = set()
            for row in evidence:
                state = row['state']
                if state not in ('POL1', 'POL2', 'BREM') or state in states:
                    raise ValueError('invalid or duplicate evidence state')
                states.add(state)
                if basis == 'user_requested_development_benchmark_errors':
                    _validate_benchmark_evidence(row, sources)
                    continue
                numeric = ('flux_integral', 'event_count', 'flux_per_event',
                           'period_state_median', 'ratio_to_period_state_median')
                if any(not _positive(row[key]) for key in numeric) or type(row['event_count']) is not int:
                    raise ValueError('evidence must be finite positive measured quantities')
                ratio = row['ratio_to_period_state_median']
                if (not math.isclose(row['flux_per_event'], row['flux_integral'] / row['event_count'], rel_tol=1e-9)
                        or not math.isclose(ratio, row['flux_per_event'] / row['period_state_median'], rel_tol=1e-9)
                        or LOWER_RATIO <= ratio <= UPPER_RATIO):
                    raise ValueError('evidence does not satisfy stated criterion')
    except (ValueError, TypeError, KeyError, AttributeError) as exc:
        raise ValueError(f'invalid run quality policy {path}: {exc}') from exc
    return {**policy, 'path': str(path.resolve()), 'sha256': hashlib.sha256(raw).hexdigest()}



def _validate_benchmark_evidence(row, sources):
    """Validate provenance and arithmetic, without imposing an exclusion threshold."""
    if (row['state'] != 'BREM' or row['method'] != 'linear' or row['role'] != 'test'
            or row['source'] not in sources):
        raise ValueError('benchmark evidence needs the inspected BREM linear/test source')
    if (type(row['event_count']) is not int or not _positive(row['event_count'])
            or not _positive(row['true_integral']) or not _positive(row['predicted_integral'])):
        raise ValueError('benchmark evidence needs positive measured counts and integrals')
    for key in ('relative_integral_error', 'relative_l1', 'shape_l1'):
        value = row[key]
        if not isinstance(value, Real) or isinstance(value, bool) or not math.isfinite(value):
            raise ValueError('benchmark errors must be finite numbers')
    error = row['predicted_integral'] / row['true_integral'] - 1
    if (not math.isclose(row['relative_integral_error'], error, rel_tol=1e-9, abs_tol=1e-12)
            or row['relative_l1'] < 0 or row['relative_l1'] + 1e-12 < abs(error)
            or not 0 <= row['shape_l1'] <= 2):
        raise ValueError('benchmark error metrics are inconsistent')


def excluded_run_numbers(path=None) -> set[int]:
    return {item['run'] for item in load_run_quality(path)['excluded_runs']}


def diagnose_flux_per_event(records, *, reference_medians=None) -> list[dict]:
    """Describe extreme measured ratios; never apply exclusions automatically.

    Optional reference medians map (period, state) to a frozen positive value.
    Otherwise use positive finite measured rates in the supplied development
    data. Invalid or zero measurements are not ratio anomalies and are omitted.
    """
    measured, groups = [], defaultdict(list)
    for row in records:
        count, total = row['count'], float(sum(row['values']))
        if not _positive(count) or not _positive(total):
            continue
        rate = total / count
        key = (row['period'], row['state'])
        groups[key].append(rate)
        measured.append((row, total, rate, key))
    medians = ({key: statistics.median(values) for key, values in groups.items()}
               if reference_medians is None else reference_medians)
    findings = []
    for row, total, rate, key in measured:
        median = medians[key]
        if not _positive(median):
            raise ValueError(f'invalid reference median for {key}')
        ratio = rate / median
        if ratio < LOWER_RATIO or ratio > UPPER_RATIO:
            findings.append(dict(run=row['run'], period=key[0], state=key[1],
                                 flux_integral=total, event_count=int(row['count']),
                                 flux_per_event=rate, period_state_median=median,
                                 ratio_to_period_state_median=ratio))
    return findings
