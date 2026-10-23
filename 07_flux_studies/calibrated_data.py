"""Measured calibrated spectra and inclusive h80 normalization for an offline pilot."""
from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
import numpy as np

from calibration.run_manifest import validate_manifest
from calibration.run_quality import load_run_quality

STATES = {0: 'BREM', 1: 'POL1', 2: 'POL2'}
ENERGY_EDGES = np.linspace(.5, 2., 129)


def rebin_counts(values, old_edges, new_edges):
    """Integrate piecewise-constant bin densities; never silently lose counts."""
    values, old_edges, new_edges = map(lambda x: np.asarray(x, dtype=float),
                                       (values, old_edges, new_edges))
    if (values.ndim != 1 or old_edges.shape != (len(values) + 1,)
            or new_edges.ndim != 1 or len(new_edges) < 2
            or any(not np.all(np.isfinite(x)) for x in (values, old_edges, new_edges))
            or np.any(values < 0) or np.any(np.diff(old_edges) <= 0)
            or np.any(np.diff(new_edges) <= 0)):
        raise ValueError('invalid histogram for conservative rebinning')
    if new_edges[0] > old_edges[0] or new_edges[-1] < old_edges[-1]:
        raise ValueError('energy range does not contain original histogram')
    cdf = np.interp(new_edges, old_edges, np.r_[0., np.cumsum(values)])
    return np.diff(cdf)


def count_h80(paths):
    import uproot
    from calibration.calibration_qa import sha256_file
    counts, sources, uuids = Counter(), [], set()
    for path in map(Path, paths):
        local = Counter()
        before = sha256_file(path)
        with uproot.open(path) as source:
            uuid = str(source.file.uuid)
            if uuid in uuids:
                raise ValueError(f'duplicate h80 UUID: {path}')
            uuids.add(uuid)
            tree = source['h80']
            for arrays in tree.iterate(['RunNumber', 'Polarization'], library='np', step_size=2_000_000):
                runs, states = arrays['RunNumber'], arrays['Polarization']
                if (not np.all(np.isfinite(runs)) or not np.all(runs == runs.astype(np.int64))
                        or np.any(runs <= 0) or not np.all(np.isin(states, list(STATES)))):
                    raise ValueError(f'invalid run/state in h80: {path}')
                encoded = runs.astype(np.int64) * 4 + states.astype(np.int64)
                keys, numbers = np.unique(encoded, return_counts=True)
                for key, number in zip(keys, numbers, strict=True):
                    local[(int(key // 4), STATES[int(key % 4)])] += int(number)
            sources.append(dict(path=str(path.resolve()), uuid=uuid, entries=int(tree.num_entries),
                                sample='all supplied h80 entries; no additional channel selection', sha256=before))
        if sha256_file(path) != before:
            raise ValueError(f'h80 content changed during inclusive scan: {path}')
        if counts.keys() & local.keys():
            raise ValueError(f'duplicate run/state coverage across h80 files: {path}')
        counts.update(local)
    return dict(counts), sources


def load_calibrated_dataset(manifest, calibrated_flux, counts, *, edges=ENERGY_EDGES,
                            representation='common_energy', run_quality_path=None):
    """Load complete run triplets, retaining calibration as separate metadata.

    Native values are ROOT bin contents in strip order, with no resampling.
    The per-record calibration axis is for observable mapping/diagnostics only;
    it must not be used to construct features for a hidden target spectrum.
    """
    import uproot
    if representation not in ('common_energy', 'native_strip'):
        raise ValueError(f'unknown flux representation: {representation}')
    quality = load_run_quality(run_quality_path)
    quality_exclusions = {item["run"]: item for item in quality["excluded_runs"]}
    split_runs = defaultdict(list)
    manifest_rows = validate_manifest(Path(manifest))
    periods = defaultdict(list)
    for row in manifest_rows:
        periods[row.source_period].append(row.run_number)
    positions = {run: index * 15. for runs in periods.values()
                 for index, run in enumerate(sorted(runs))}
    rows, exclusions, diagnostic_records = [], [], []
    observed_runs = {run for run, state in counts}
    with uproot.open(calibrated_flux) as source:
        keys = defaultdict(list)
        for key in source.keys(recursive=False):
            keys[key.rsplit(';', 1)[0]].append(key)
        for row in manifest_rows:
            if row.run_number not in observed_runs or row.target != 'P':
                continue
            run_rows, problems = [], []
            for state in STATES.values():
                name = f'run{row.run_number}_{state}'
                count = counts.get((row.run_number, state), 0)
                if count <= 0:
                    problems.append(f'{state}:missing_or_zero_count')
                    continue
                if len(keys[name]) != 1:
                    problems.append(f'{state}:missing_or_duplicate_calibrated')
                    continue
                hist = source[keys[name][0]]
                try:
                    values, original_edges = hist.to_numpy(flow=False)
                    flow = hist.values(flow=True)
                    if len(values) != 128 or not np.all(np.isfinite(flow)) or np.any(flow < 0):
                        raise ValueError('invalid calibrated bins')
                    if flow[0] != 0 or flow[-1] != 0:
                        raise ValueError('nonzero flow bins')
                    if (np.shape(original_edges) != (129,)
                            or not np.all(np.isfinite(original_edges))
                            or np.any(np.diff(original_edges) <= 0)):
                        raise ValueError('invalid calibration axis')
                    represented = (np.asarray(values, dtype=float).copy()
                                   if representation == 'native_strip'
                                   else rebin_counts(values, original_edges, edges))
                except (ValueError, TypeError, AttributeError) as exc:
                    problems.append(f'{state}:{exc}')
                    continue
                run_rows.append(dict(run=row.run_number, state=state, period=row.source_period,
                                     group=(row.source_period, row.target, row.beam_type, state),
                                     position=positions[row.run_number], count=count,
                                     values=represented,
                                     calibration_edges=np.asarray(original_edges).copy(),
                                     axis_source=dict(path=str(Path(calibrated_flux).resolve()),
                                                      histogram=name,
                                                      kind='stored_calibrated_root_axis')))
            diagnostic_records.extend(run_rows)
            if problems:
                exclusions.append(dict(run=row.run_number, period=row.source_period, reasons=problems))
            else:
                split_runs[row.source_period].append(row.run_number)
                if row.run_number in quality_exclusions:
                    finding = quality_exclusions[row.run_number]
                    exclusions.append(dict(run=row.run_number, period=row.source_period,
                                           category="run_quality", reasons=[finding["reason"]],
                                           evidence=finding["evidence"]))
                else:
                    rows.extend(run_rows)
    known = {r.run_number for r in manifest_rows}
    return dict(records=rows, diagnostic_records=diagnostic_records,
                exclusions=exclusions, run_quality=quality,
                split_runs_by_period={period: sorted(runs) for period, runs in split_runs.items()},
                extra_h80_runs=sorted(observed_runs - known), representation=representation,
                strip_indices=np.arange(1, 129),
                energy_edges=(None if representation == 'native_strip' else np.asarray(edges)))
