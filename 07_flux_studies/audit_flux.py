"""Inventory measured flux independently of production's fail-fast loader."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from pathlib import Path
import sys
import numpy as np

from calibration.calibration_qa import sha256_file, load_calibration_qa
from calibration.flux_inspection import inspect_histograms
from calibration.run_manifest import validate_manifest
from flux_studies.metadata import STATES, load_metadata
from flux_studies.reporting import publish_output, write_audit


def audit_flux(*, manifest: Path, raw_flux: Path, calibrated_flux: Path | None = None,
               calibration_qa: Path | None = None, run_metadata: Path | None = None,
               target: str = 'P', beam_type: str | None = None, periods: tuple[str, ...] = ()) -> dict:
    records = validate_manifest(manifest)
    metadata = load_metadata(run_metadata, records)
    selected = [row for row in records if row.target == target
                and (beam_type is None or row.beam_type == beam_type)
                and (not periods or row.source_period in periods)]
    if not selected:
        raise ValueError('manifest has no selected runs')
    inputs = {name: dict(path=str(Path(path).resolve()), sha256=sha256_file(path))
              for name, path in dict(manifest=manifest, raw_flux=raw_flux,
                                     calibrated_flux=calibrated_flux, calibration_qa=calibration_qa,
                                     run_metadata=run_metadata).items() if path is not None}
    indexed = {}
    for label, path, axis in [('raw', raw_flux, 'strip'), ('calibrated', calibrated_flux, 'energy')]:
        indexed[label] = defaultdict(list)
        if path is not None:
            for entry in inspect_histograms(path, axis_kind=axis):
                indexed[label][(entry['run_number'], entry['state'])].append(entry)
    coverage, qa_status = {}, 'not_supplied'
    if calibration_qa is not None:
        if calibrated_flux is None:
            raise ValueError('calibration QA requires calibrated flux')
        try:
            qa = load_calibration_qa(calibration_qa, calibrated_flux,
                                    expected_inputs={k: inputs[k]['sha256'] for k in ('manifest', 'raw_flux')})
        except ValueError as exc:
            if 'identity' not in str(exc):
                raise
            qa_status = 'identity_mismatch'
        else:
            qa_status = 'verified'
            coverage = {(r['run_number'], r['state']): r for r in qa['coverage']}
    rows, strips, histograms = [], [], {}
    for record in selected:
        for state in STATES:
            key = (record.run_number, state)
            row = dict(run_number=record.run_number, state=state, source_period=record.source_period,
                       target=record.target, beam_type=record.beam_type, problems=[],
                       coverage=coverage.get(key, {}).get('reason', 'unknown'),
                       raw_usable=False, shape_usable=False, extraction_valid_strips=0)
            objects = {}
            for label in ('raw', 'calibrated'):
                entries = indexed[label].get(key, [])
                row[f'{label}_keys'] = [dict(name=e['name'], cycle=e['cycle'], class_name=e['class_name']) for e in entries]
                row[f'{label}_integral'] = None
                if not entries:
                    if label == 'raw' or calibrated_flux is not None:
                        row['problems'].append(f'missing_{label}')
                    continue
                if len(entries) != 1:
                    row['problems'].append(f'duplicate_{label}')
                for entry in entries:
                    row['problems'].extend(entry['problems'] if label == 'raw' else [f'calibrated_{p}' for p in entry['problems']])
                if len(entries) != 1:
                    continue
                obj = objects[label] = entries[0]
                row[f'{label}_integral'] = obj['integral']
                row[f'{label}_underflow'] = obj.get('underflow')
                row[f'{label}_overflow'] = obj.get('overflow')
                values = obj['values']
                if label == 'raw' and not obj['problems']:
                    row['raw_usable'] = True
                    row['shape_usable'] = bool(obj['integral'] > 0)
                    if row['shape_usable']:
                        histograms[key] = values.copy()
                if values is None:
                    continue
                for index, value in enumerate(values):
                    positive = bool(np.isfinite(value) and (value >= 0 if state == 'BREM' else value > 0))
                    valid = positive and not any(p in obj['problems'] for p in ('not_1d_histogram', 'wrong_bin_count', 'invalid_axis', 'invalid_strip_axis', 'noncanonical_name'))
                    if label == 'calibrated' and valid:
                        row['extraction_valid_strips'] += 1
                    strips.append(dict(run_number=record.run_number, state=state, source=label,
                                       strip=index+1, value=float(value), error=float(obj['errors'][index]),
                                       low=float(obj['edges'][index]), high=float(obj['edges'][index+1]),
                                       value_valid=positive, structurally_valid=valid))
            raw, calibrated = objects.get('raw'), objects.get('calibrated')
            if raw and calibrated and raw['values'] is not None and calibrated['values'] is not None and len(raw['values']) == len(calibrated['values']):
                rv, cv = raw['values'], calibrated['values']
                row['content_changed_strips'] = int(np.count_nonzero(rv != cv))
                row['negative_clamp_consistent'] = bool(np.array_equal(np.maximum(rv, 0), cv))
            if row['coverage'] in ('not_covered', 'insufficient_coverage'):
                row['problems'].append(row['coverage'])
            row['problems'] = sorted(set(row['problems']))
            rows.append(row)
    # Extraction is run-atomic, and each strip needs all three measured states.
    by_run = defaultdict(list)
    valid_by_key = defaultdict(set)
    for strip in strips:
        if strip["source"] == "calibrated" and strip["structurally_valid"]:
            valid_by_key[(strip["run_number"], strip["state"])].add(strip["strip"])
    for row in rows:
        by_run[row['run_number']].append(row)
    for run_rows in by_run.values():
        complete = all(len(row['calibrated_keys']) == 1 for row in run_rows)
        valid_sets = [valid_by_key[(row['run_number'], row['state'])] for row in run_rows]
        count = len(set.intersection(*valid_sets)) if complete else 0
        for row in run_rows:
            row['run_triplet_complete'] = complete
            row['run_valid_strips'] = count
    return dict(schema_version=1, inputs=inputs,
                summary=dict(selected_runs=len(selected), rows=len(rows), qa_status=qa_status,
                             problems=dict(Counter(p for row in rows for p in row['problems'])),
                             complete_raw_runs=sum(all(len(row['raw_keys']) == 1 for row in rr) for rr in by_run.values())),
                rows=rows, strips=strips, histograms=histograms,
                metadata={key: row for key, row in metadata.items() if key[0] in {r.run_number for r in selected}})


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('manifest', 'raw-flux', 'output-dir'):
        parser.add_argument('--'+name, type=Path, required=True)
    for name in ('calibrated-flux', 'calibration-qa', 'run-metadata'):
        parser.add_argument('--'+name, type=Path)
    parser.add_argument('--target', choices=('P', 'D'), default='P')
    parser.add_argument('--beam-type', choices=('UV', 'VIS'))
    parser.add_argument('--period', dest='periods', action='append', default=[])
    return parser


def audit_kwargs(args):
    return {name: getattr(args, name) for name in ('manifest', 'raw_flux', 'calibrated_flux', 'calibration_qa', 'run_metadata', 'target', 'beam_type', 'periods')}


def input_paths(args):
    return [getattr(args, name) for name in ('manifest', 'raw_flux', 'calibrated_flux', 'calibration_qa', 'run_metadata') if getattr(args, name) is not None]


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        with publish_output(args.output_dir, input_paths(args)) as staged:
            result = audit_flux(**audit_kwargs(args))
            write_audit(staged, result)
        print(f"Flux audit: {result['summary']}\nOutput: {args.output_dir}")
        return 0
    except (ValueError, OSError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
