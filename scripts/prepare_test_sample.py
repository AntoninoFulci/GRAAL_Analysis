#!/usr/bin/env python3
"""Freeze a diagnostic UV/VIS cohort without changing source exposure or branch types.

The declared first complete runs (1321 UV, 1964 VIS) were audited before
sampling. Selection is based only on strip coverage, particle multiplicity,
and source identity, never fitted observables. ROOT inputs remain legacy h80.
"""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import shutil
import tempfile

import numpy as np


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def choose_entries(source_hash, strips, states, topology_entries, limit):
    """Reserve all real strip cells and topology events, fill by identity SHA256."""
    strips = np.asarray(strips).astype(int)
    states = np.asarray(states)
    reserved = set(map(int, topology_entries))
    for state in (0, 1, 2):
        indices = np.flatnonzero(states == state)
        cells = {}
        for entry in indices:
            cells.setdefault(int(strips[entry]), int(entry))
        if len(cells) < 5 or not {1, 128} <= cells.keys():
            raise ValueError(f'incomplete calibration coverage for state {state}')
        reserved.update(cells.values())
    if len(reserved) > limit:
        raise ValueError('coverage and topology reserve exceeds event limit')
    remaining = (i for i in range(len(states)) if i not in reserved)
    ranked = sorted(remaining, key=lambda i: (hashlib.sha256(f'{source_hash}:{i}'.encode()).digest(), i))
    return np.asarray(sorted(reserved.union(ranked[:limit-len(reserved)])), dtype=np.int64)


def read_cohort(source, run):
    import awkward as ak
    import uproot
    names = ['RunNumber', 'Polarization', 'Xstrip', 'gammas/gammas.fCoordinates.fX',
             'protons/protons.fCoordinates.fX', 'protons/protons.fCoordinates.fY',
             'protons/protons.fCoordinates.fZ', 'pions_theta', 'fcharged_theta']
    strips, states, topology = [], [], []
    offset = 0
    with uproot.open(source) as stream:
        entries = stream['h80'].num_entries
        for a in stream['h80'].iterate(names, step_size=50000, library='ak'):
            runs = ak.to_numpy(a['RunNumber'])
            other = np.flatnonzero(runs != run)
            stop = int(other[0]) if len(other) else len(runs)
            a = a[:stop]
            if len(a):
                p = [ak.fill_none(ak.firsts(a[k]), 0) for k in names[4:7]]
                forward = np.arctan2(np.sqrt(p[0]**2 + p[1]**2), p[2]) < np.deg2rad(25)
                selected = ak.to_numpy((ak.num(a[names[3]]) == 4) & (ak.num(a[names[4]]) == 1) &
                    (ak.num(a['pions_theta']) == 0) & ((forward & (ak.num(a['fcharged_theta']) == 1)) |
                    (~forward & (ak.num(a['fcharged_theta']) == 0))))
                topology.extend((offset + np.flatnonzero(selected)).tolist())
                strips.extend(ak.to_numpy(a['Xstrip']).tolist())
                states.extend(ak.to_numpy(a['Polarization']).tolist())
                offset += len(a)
            if len(other):
                break
    if not offset:
        raise ValueError(f'declared run {run} must be the first contiguous source run')
    return np.asarray(strips), np.asarray(states), np.asarray(topology, dtype=int), entries


def clone_sample(source, target, entries, metadata):
    import ROOT
    original = ROOT.TFile.Open(str(source), 'READ')
    output = None
    try:
        tree = original.Get('h80')
        tree.SetBranchStatus('*', 1)
        output = ROOT.TFile.Open(str(target), 'RECREATE')
        clone = tree.CloneTree(0)
        for entry in entries:
            if tree.GetEntry(int(entry)) <= 0:
                raise RuntimeError(f'cannot read source entry {entry}')
            clone.Fill()
        clone.Write()
        ROOT.TNamed('sample_provenance', json.dumps(metadata, sort_keys=True)).Write()
    finally:
        if output:
            output.Close()
        original.Close()


def prepare(uv, vis, output, *, limit=100000, dependencies=()):
    if not 1 <= limit <= 100000:
        raise ValueError('event limit must be between 1 and 100000')
    output = Path(output).absolute()
    if output.exists() or output.is_symlink():
        raise FileExistsError(f'refusing to overwrite sample: {output}')
    sources = {'uv': (Path(uv).resolve(), 1321), 'vis': (Path(vis).resolve(), 1964)}
    for source, _ in sources.values():
        if output == source or source.is_relative_to(output):
            raise ValueError('sample output overlaps input')
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix='.sample-', dir=output.parent))
    manifest = {'schema': 1, 'diagnostic_only': True, 'exposure_policy': 'original_source_exposure',
        'legacy_metadata': 'No h70 identity, raw-track certification or tagger-discard certification available.',
        'inclusion_rule': 'Declared first complete source run; first source entry in every real state/strip cell; all four-gamma one-proton zero-pion topology survivors with forward charged multiplicity; fill by ascending SHA256(source_sha256:zero_based_entry), tie break by entry; output sorted by source entry.',
        'selection_uses_observable_results': False, 'profiles': {},
        'dependencies': {str(p): sha256(Path(p)) for p in dependencies}}
    try:
        for profile, (source, run) in sources.items():
            digest = sha256(source)
            strips, states, topology, original_count = read_cohort(source, run)
            chosen = choose_entries(digest, strips, states, topology, limit)
            target = staging / f'pre_analisi_sample_{profile}.root'
            provenance = {'diagnostic_only': True, 'exposure_policy': 'original_source_exposure',
                          'source_sha256': digest, 'run': run, 'profile': profile}
            clone_sample(source, target, chosen, provenance)
            manifest['profiles'][profile] = {**provenance, 'source_path': str(source),
                'file': target.name, 'sha256': sha256(target), 'original_file_entries': original_count,
                'original_cohort_entries': len(states), 'sampled_entries': len(chosen),
                'source_entries': chosen.tolist(), 'topology_reserve_count': len(topology),
                'original_state_counts': dict(Counter(map(int, states))),
                'sampled_state_counts': dict(Counter(map(int, states[chosen]))),
                'strip_coverage': {str(s): sorted(set(map(int, strips[chosen[states[chosen] == s]]))) for s in (0, 1, 2)}}
        (staging / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
        staging.rename(output)
    except BaseException:
        shutil.rmtree(staging)
        raise
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--uv', type=Path, required=True)
    parser.add_argument('--vis', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=Path('data_test/sample'))
    parser.add_argument('--limit', type=int, default=100000)
    parser.add_argument('--dependency', type=Path, action='append', default=[])
    args = parser.parse_args()
    prepare(args.uv, args.vis, args.output, limit=args.limit, dependencies=args.dependency)


if __name__ == '__main__':
    main()
