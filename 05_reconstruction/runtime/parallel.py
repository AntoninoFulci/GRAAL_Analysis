"""Process-local ROOT reconstruction shards and deterministic atomic publication."""
from __future__ import annotations

from dataclasses import replace
import json
import os
from pathlib import Path
import tempfile

import ROOT

from graal_common.parallel import ordered_map
from reconstruction.runtime.provenance import KEY, acquisition_counts
from reconstruction.runtime.reco_core import _build_chain, _run_serial, _snapshot_inputs


def _entry_shards(files, workers):
    """Keep file order and split large files into nonoverlapping entry ranges."""
    total = sum(entries for _, entries in files)
    target = max(1, (total + workers - 1) // workers)
    for filename, entries in files:
        if entries == 0:
            yield filename, 0, 0
        else:
            for start in range(0, entries, target):
                yield filename, start, min(start + target, entries)


def _run_shard(task):
    cfg, channel, gate, snapshot, filename, start, stop = task
    # A reused process may have seen ROOT before; never nest implicit MT here.
    ROOT.DisableImplicitMT()
    if gate is not None:
        model = getattr(gate, "model", None)
        if hasattr(model, "set_params"):
            model.set_params(n_jobs=1)
        if hasattr(model, "get_booster"):
            model.get_booster().set_param({"nthread": 1})
    try:
        count = _run_serial(cfg, channel, gate, input_files=(filename,),
                            entry_range=(start, stop), snapshot=snapshot,
                            include_acquisition_counts=False)
    finally:
        # On an event/gate exception the serial writer may still own a file.
        # Close it before the parent removes the temporary directory.
        opened = ROOT.gROOT.GetListOfFiles().FindObject(str(cfg.output_file))
        if opened:
            opened.Close()
    return {"input": filename, "entry_start": start, "entry_stop": stop,
            "entries_written": int(count), "process_id": os.getpid()}


def _merge_shards(paths, destination, output_tree, execution, input_run_states):
    """Merge trees in task order, replacing per-shard cutflow with summed counts."""
    # A preceding RDataFrame stage may have enabled ROOT's global TBB pool.
    # Merge tree basket writes serially; only the shard processes run in parallel.
    if ROOT.IsImplicitMTEnabled():
        ROOT.DisableImplicitMT()
    counts = acquisition_counts(input_run_states)
    metadata = None
    compression = None
    for path in paths:
        source = ROOT.TFile.Open(str(path), "READ")
        if not source or source.IsZombie():
            raise OSError(f"cannot open reconstruction shard: {path}")
        try:
            current = json.loads(source.Get(KEY).GetTitle())
            if metadata is None:
                metadata = current
                compression = source.GetCompressionSettings()
            for record in current["counts_by_run_state"]:
                counts[(record["run"], record["polarization"])].update(
                    {key: value for key, value in record.items()
                     if key not in ("run", "polarization")})
        finally:
            source.Close()
    merger = ROOT.TFileMerger(False, False)
    # Preserve the input setting so ROOT can copy compressed baskets directly.
    output_args = (str(destination), "RECREATE")
    if compression is not None:
        output_args += (compression,)
    if not merger.OutputFile(*output_args):
        raise OSError(f"cannot create merged reconstruction: {destination}")
    try:
        for path in paths:
            if not merger.AddFile(str(path)):
                raise OSError(f"cannot add reconstruction shard: {path}")
        if not merger.Merge():
            raise OSError("ROOT reconstruction shard merge failed")
    finally:
        # Let the owner clear its pointer, including after a failed merge.
        # Closing the borrowed TFile leaves ROOT cleanup able to abort later.
        merger.CloseOutputFile()
    metadata["counts_by_run_state"] = [dict(run=run, polarization=pol, **counter)
        for (run, pol), counter in sorted(counts.items())]
    metadata["execution"] = execution
    output = ROOT.TFile.Open(str(destination), "UPDATE")
    if not output or output.IsZombie():
        raise OSError(f"cannot reopen merged reconstruction: {destination}")
    try:
        tree = output.Get(output_tree)
        if not tree:
            raise OSError(f"merged reconstruction has no tree {output_tree!r}")
        count = int(tree.GetEntries())
        expected = sum(shard["entries_written"] for shard in execution["shards"])
        if count != expected:
            raise OSError(f"merged reconstruction count {count} differs from shards {expected}")
        ROOT.TNamed(KEY, json.dumps(metadata, sort_keys=True)).Write("", ROOT.TObject.kOverwrite)
    finally:
        output.Close()
    return count


def run_parallel_reconstruction(cfg, channel, gate=None):
    # Inspect every file before starting workers, including metadata consistency.
    snapshot = _snapshot_inputs(cfg)
    chain = _build_chain(Path(cfg.input_dir), cfg.input_tree)
    files = chain.input_file_entries
    input_run_states = chain.input_run_states
    tree_name = chain.GetName()
    chain.Reset()
    del chain
    ranges = tuple(_entry_shards(files, cfg.workers))
    destination = Path(cfg.output_file)
    if any(destination.resolve() == Path(filename) for filename, _ in files):
        raise ValueError("reconstruction output must not overwrite an input ROOT file")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f".{destination.name}.shards-",
                                      dir=destination.parent) as temporary:
        staging = Path(temporary)
        outputs = [staging/f"shard-{index:06d}.root" for index in range(len(ranges))]
        tasks = [(replace(cfg, input_tree=tree_name, output_file=output, workers=1),
                  channel, gate, snapshot, filename, start, stop)
                 for output, (filename, start, stop) in zip(outputs, ranges)]
        workers_used = min(cfg.workers, len(tasks))
        shards = ordered_map(_run_shard, tasks, workers=workers_used)
        execution = {"workers_requested": cfg.workers,
                     "workers_used": workers_used,
                     "shards": shards}
        merged = staging/"merged.root"
        count = _merge_shards(outputs, merged, cfg.output_tree, execution, input_run_states)
        os.replace(merged, destination)
    print(f"Created file: {destination}; events written: {count}; processes: {execution['workers_used']}")
    return count
