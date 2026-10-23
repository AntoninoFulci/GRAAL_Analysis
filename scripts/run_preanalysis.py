#!/usr/bin/env python3
"""Build fresh h80 files from h70, with bounded isolated ROOT processes."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from collections import defaultdict
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from graal_common.io.filesystem import atomic_output_directory
from graal_common.parallel import available_cpus, thread_environment, validate_workers
from graal_workflow.artifact_manifest import inventory, source_fingerprint

REPO_ROOT = Path(__file__).resolve().parents[1]


def _convert(task):
    source, target, raw_root, cuts, scratch = task
    macro = scratch / 'convert.C'
    macro.parent.mkdir(parents=True)
    quote = lambda value: json.dumps(str(value), ensure_ascii=False)
    macro.write_text(
        f'#include {quote(REPO_ROOT / "01_pre_analysis/PreAnalysis.C")}\n'
        'void convert() { try {\n'
        f'BuildCutMap({quote(raw_root)}, {quote(cuts)});\n'
        f'PreAnalysis({quote(source)}, {quote(target)});\n'
        '} catch (const std::exception &error) { std::cerr << error.what() << std::endl; gSystem->Exit(1); } }\n'
    )
    log = scratch / 'root.log'
    with log.open('w') as stream:
        result = subprocess.run(['root', '-l', '-b', '-q', str(macro)],
                                env={**os.environ, **thread_environment(1)},
                                stdout=stream, stderr=subprocess.STDOUT, check=False)
    if result.returncode:
        raise RuntimeError(f'Pre-analysis failed for {source}:\n{log.read_text()[-6000:]}')
    import uproot
    try:
        with uproot.open(target) as file:
            written = int(file['h80'].num_entries)
            skipped = int(file['preanalysis_skipped_no_tagger'].member('fVal'))
        with uproot.open(source) as file:
            inputs = int(file['h70'].num_entries)
            arrays = file['h70'].arrays(['Idrun', 'Ipol', 'Ncstrip'], library='np')
            import numpy as np
            pairs = np.column_stack((arrays['Idrun'], arrays['Ipol']))
            states = []
            for run, polarization in np.unique(pairs, axis=0):
                mask = (arrays['Idrun'] == run) & (arrays['Ipol'] == polarization)
                states.append({'run': int(run), 'polarization': int(polarization),
                               'input': int(np.count_nonzero(mask)),
                               'skipped_no_tagger': int(np.count_nonzero(mask & (arrays['Ncstrip'] == 0)))})
        if written + skipped != inputs:
            raise ValueError(f'event accounting mismatch: {written}+{skipped}!={inputs}')
    except Exception as exc:
        raise RuntimeError(f'Invalid pre-analysis output for {source}: {exc}') from exc
    return {'source': str(source), 'shard': str(target), 'input': inputs,
            'written': written, 'skipped_no_tagger': skipped, 'input_run_states': states}


def _merge(output, records, provenance):
    import ROOT
    # Previous in-process selectors may leave ROOT's global pool enabled.
    # This writer owns a serial merge; inherited basket flushing is unsafe.
    ROOT.DisableImplicitMT()
    merger = ROOT.TFileMerger(False)
    output_args = (str(output), 'RECREATE')
    if records:
        first = ROOT.TFile.Open(records[0]['shard'], 'READ')
        if not first:
            raise RuntimeError(f'Cannot open {records[0]["shard"]}')
        try:
            if first.IsZombie():
                raise RuntimeError(f'Cannot open {records[0]["shard"]}')
            # ROOT treats default settings 1 and explicit ZLIB 101 as different,
            # causing a full tree rewrite unless the input setting is preserved.
            output_args += (first.GetCompressionSettings(),)
        finally:
            first.Close()
    if not merger.OutputFile(*output_args):
        raise RuntimeError(f'Cannot create {output}')
    try:
        for record in records:
            if not merger.AddFile(record['shard']):
                raise RuntimeError(f'Cannot add {record["shard"]}')
        if not merger.Merge():
            raise RuntimeError(f'Cannot merge {output}')
    finally:
        merger.CloseOutputFile()
    file = ROOT.TFile.Open(str(output), 'UPDATE')
    try:
        tree = file.Get('h80')
        expected = sum(row['written'] for row in records)
        if not tree or tree.GetEntries() != expected:
            raise RuntimeError('Merged h80 event count mismatch')
        skipped = sum(row['skipped_no_tagger'] for row in records)
        ROOT.TParameter('Long64_t')('preanalysis_skipped_no_tagger', skipped).Write('', ROOT.TObject.kOverwrite)
        ROOT.TNamed('preanalysis_provenance', json.dumps(provenance, sort_keys=True)).Write('', ROOT.TObject.kOverwrite)
    finally:
        file.Close()


def run(raw_dir: Path, output_dir: Path, *, cpus: int = 1, cuts_dir: Path | None = None):
    validate_workers(cpus)
    raw_dir, output_dir = Path(raw_dir).resolve(), Path(output_dir).absolute()
    cuts = Path(cuts_dir or REPO_ROOT / '01_pre_analysis/cuts').resolve()
    if output_dir.exists():
        raise FileExistsError(f'Use a new h80 output directory: {output_dir}')
    if not cuts.is_dir() or not raw_dir.is_dir():
        raise ValueError('Raw and cut directories must exist')
    groups = {folder.name: sorted(folder.glob('*.root')) for folder in sorted(raw_dir.iterdir()) if folder.is_dir()}
    groups = {name: paths for name, paths in groups.items() if paths}
    if not groups:
        raise ValueError('No h70 files under acquisition subdirectories')
    if shutil.which('root') is None:
        raise RuntimeError('ROOT executable not found')
    inputs = inventory(path for paths in groups.values() for path in paths)
    source_paths = [REPO_ROOT / '01_pre_analysis/PreAnalysis.C',
                         REPO_ROOT / '01_pre_analysis/PreAnalysis.h',
                         REPO_ROOT / '01_pre_analysis/RawTrackContract.h',
                         REPO_ROOT / '01_pre_analysis/CutManager.h', *sorted(cuts.glob('*.cpp'))]
    sources = inventory(source_paths)
    source_hash = source_fingerprint(Path(item['path']) for item in sources)
    with atomic_output_directory(output_dir, overwrite=False) as staging:
        with tempfile.TemporaryDirectory(prefix='graal-h70-') as temporary:
            scratch = Path(temporary)
            tasks, names = [], []
            for name, paths in groups.items():
                for source in paths:
                    index = len(tasks)
                    tasks.append((source, scratch / f'{index}.root', raw_dir, cuts, scratch / str(index)))
                    names.append(name)
            with ThreadPoolExecutor(max_workers=min(cpus, len(tasks))) as pool:
                rows = list(pool.map(_convert, tasks))
            provenance = {'schema': 1, 'tagger_policy': 'discard_zero', 'cpus': cpus,
                          'inputs': inputs, 'sources': sources, 'source_sha256': source_hash,
                          'counts': [{k: v for k, v in row.items() if k != 'shard'} for row in rows]}
            for name in groups:
                selected = [row for group, row in zip(names, rows) if group == name]
                by_state = defaultdict(lambda: {'input': 0, 'skipped_no_tagger': 0})
                for record in selected:
                    for state in record['input_run_states']:
                        counts = by_state[(state['run'], state['polarization'])]
                        for key in counts:
                            counts[key] += state[key]
                states = [{'run': run, 'polarization': pol, **counts}
                          for (run, pol), counts in sorted(by_state.items())]
                _merge(staging / f'pre_analisi_{name}.root', selected,
                       {**provenance, 'acquisition': name, 'input_run_states': states})
            if inputs != inventory(sorted(raw_dir.glob('*/*.root'))):
                raise RuntimeError('Raw inputs changed during pre-analysis')
            current_sources = [*source_paths[:4], *sorted(cuts.glob('*.cpp'))]
            if source_hash != source_fingerprint(current_sources):
                raise RuntimeError('Pre-analysis sources changed during execution')
            (staging / 'preanalysis_manifest.json').write_text(json.dumps(provenance, indent=2) + '\n')
    print(f'h80 complete: {output_dir}; written={sum(r["written"] for r in rows)} skipped_no_tagger={sum(r["skipped_no_tagger"] for r in rows)}')
    return provenance


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raw-dir', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--cuts-dir', type=Path)
    parser.add_argument('--cpus', type=int, default=available_cpus())
    args = parser.parse_args()
    run(args.raw_dir, args.output_dir, cpus=args.cpus, cuts_dir=args.cuts_dir)


if __name__ == '__main__':
    main()
