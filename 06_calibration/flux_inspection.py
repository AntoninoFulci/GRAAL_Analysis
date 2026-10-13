"""Read-only ROOT inspection preserving all key cycles and object defects."""
from __future__ import annotations

from pathlib import Path
import re
import numpy as np

_NAME = re.compile(r'^run([0-9]+)_(POL1|POL2|BREM)$')


def inspect_histograms(path: Path, *, axis_kind: str) -> list[dict]:
    import ROOT
    if axis_kind not in ('strip', 'energy'):
        raise ValueError('axis_kind must be strip or energy')
    if not Path(path).is_file():
        raise FileNotFoundError(path)
    source = ROOT.TFile.Open(str(path), 'READ')
    if not source or source.IsZombie():
        raise ValueError(f'cannot read flux ROOT: {path}')
    rows = []
    try:
        for key in source.GetListOfKeys():
            match = _NAME.fullmatch(key.GetName())
            if not match:
                continue
            run, state = match.groups()
            row = dict(run_number=int(run), state=state, name=key.GetName(),
                       cycle=int(key.GetCycle()), class_name=key.GetClassName(),
                       problems=[], values=None, errors=None, edges=None, integral=None)
            if row['name'] != f'run{int(run)}_{state}':
                row['problems'].append('noncanonical_name')
            try:
                hist = key.ReadObj()
                if not hist or not hist.InheritsFrom('TH1') or hist.GetDimension() != 1:
                    row['problems'].append('not_1d_histogram')
                else:
                    size = hist.GetNbinsX()
                    row['bins'] = size
                    if size != 128:
                        row['problems'].append('wrong_bin_count')
                    values = np.array([hist.GetBinContent(i) for i in range(size + 2)])
                    errors = np.array([hist.GetBinError(i) for i in range(size + 2)])
                    edges = np.array([hist.GetXaxis().GetBinLowEdge(i) for i in range(1, size + 2)])
                    row.update(values=values[1:-1], errors=errors[1:-1], edges=edges,
                               underflow=float(values[0]), overflow=float(values[-1]),
                               integral=float(values[1:-1].sum()), entries=float(hist.GetEntries()))
                    if not np.all(np.isfinite(edges)) or not np.all(np.diff(edges) > 0):
                        row['problems'].append('invalid_axis')
                    elif axis_kind == 'strip' and (size != 128 or not np.allclose(edges, np.arange(129), rtol=0, atol=1e-6)):
                        row['problems'].append('invalid_strip_axis')
                    if not np.all(np.isfinite(values)):
                        row['problems'].append('nonfinite_content')
                    if np.any(values < 0):
                        row['problems'].append('negative_content')
                    if not np.all(np.isfinite(errors)) or np.any(errors < 0):
                        row['problems'].append('invalid_bin_error')
            except (ReferenceError, TypeError, ValueError, RuntimeError) as exc:
                row['problems'].append('unreadable_object')
                row['error'] = str(exc)
            rows.append(row)
    finally:
        source.Close()
    return rows
