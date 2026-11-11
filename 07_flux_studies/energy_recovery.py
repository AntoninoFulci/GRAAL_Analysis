"""Explicit common-energy products and independently calibrated strip mapping.

Bin contents are integrated fluxes. Partial transfer results are diagnostics;
uncovered destination intervals are never admitted as extrapolated exposures.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import numpy as np


def _edges(values):
    values = np.asarray(values, dtype=float)
    if (values.ndim != 1 or len(values) < 2 or not np.all(np.isfinite(values))
            or np.any(np.diff(values) <= 0)):
        raise ValueError('invalid energy edges')
    return values


def conservative_transfer(values, source_edges, destination_edges, *, underflow=0., overflow=0.):
    """Integrate bin overlap and account explicitly for tails and ROOT flow."""
    source_edges, destination_edges = _edges(source_edges), _edges(destination_edges)
    values = np.asarray(values, dtype=float)
    flow = np.asarray([underflow, overflow], dtype=float)
    if (values.shape != (len(source_edges) - 1,) or not np.all(np.isfinite(values))
            or np.any(values < 0) or not np.all(np.isfinite(flow)) or np.any(flow < 0)):
        raise ValueError('invalid integrated flux values')
    cumulative = np.r_[0., np.cumsum(values)]
    cdf = np.interp(destination_edges, source_edges, cumulative)
    rebinned = np.diff(cdf)
    overlap = np.maximum(0., np.minimum(destination_edges[1:], source_edges[-1])
                         - np.maximum(destination_edges[:-1], source_edges[0]))
    coverage = overlap / np.diff(destination_edges)
    low, high = float(cdf[0]), float(cumulative[-1] - cdf[-1])
    total = float(cumulative[-1] + np.sum(flow))
    audit = dict(source_integral=float(cumulative[-1]), destination_integral=float(np.sum(rebinned)),
                 lower_tail=low, upper_tail=high, underflow=float(underflow), overflow=float(overflow),
                 source_total_including_flow=total,
                 accounted_total=float(np.sum(rebinned) + low + high + np.sum(flow)),
                 destination_covered=bool(destination_edges[0] >= source_edges[0]
                                          and destination_edges[-1] <= source_edges[-1]),
                 coverage_fraction=coverage.tolist(), approximation='constant density within source bin')
    return dict(values=rebinned, audit=audit)


@dataclass(frozen=True)
class IndependentStripAxis:
    run: int
    state: str
    edges: np.ndarray
    provenance: dict

    def __post_init__(self):
        edges = _edges(self.edges).copy()
        if len(edges) != 129 or self.state not in ('BREM', 'POL1', 'POL2') or self.run <= 0:
            raise ValueError('independent axis requires real run/state and 128 strips')
        if self.provenance.get('kind') != 'inclusive_h80_calibration':
            raise ValueError('independent axis requires inclusive h80 calibration provenance')
        edges.setflags(write=False)
        object.__setattr__(self, 'edges', edges)


def map_energy_to_strips(values, energy_edges, axis: IndependentStripAxis):
    """Map a declared energy estimate onto authentic strip intervals."""
    transfer = conservative_transfer(values, energy_edges, axis.edges)
    if not transfer['audit']['destination_covered']:
        raise ValueError('uncovered independent strip axis; extrapolation forbidden')
    return dict(run=axis.run, state=axis.state, strip_indices=np.arange(1, 129),
                values=transfer['values'], calibration_edges=axis.edges.copy(),
                axis_source=dict(axis.provenance), audit=transfer['audit'])


def load_independent_axes(product_path, provenance_path, *, manifest, h80_paths):
    """Read existing stage-06 pol4 fits, authenticated against declared h80.

    The stage-06 producer fits inclusive h80 calibration cells independently
    of flux contents. Only its calibration fits and coverage QA are consumed;
    no measured flux histogram or donor axis is consulted. Insufficient groups
    are absent from the result and remain unavailable for strip mapping.
    """
    import uproot
    from calibration.calibration_qa import load_calibration_qa, sha256_file
    from calibration.calibrated_flux_root import minimum_pol4_derivative
    from calibration.run_manifest import validate_manifest
    from calibration.strip_energy_root import _import_root, _open_root_file

    product_path, provenance_path, manifest = map(Path, (product_path, provenance_path, manifest))
    manifest_hash = sha256_file(manifest)
    qa_hash = sha256_file(provenance_path)
    qa = load_calibration_qa(provenance_path, product_path,
                             expected_inputs={'manifest': manifest_hash})
    expected = qa.get('inputs', {}).get('h80')
    if not isinstance(expected, list) or not expected:
        raise ValueError('independent axis requires authenticated inclusive h80 identity')
    try:
        expected_identity = sorted((int(row[1]), row[3]) for row in expected)
    except (IndexError, TypeError, ValueError) as exc:
        raise ValueError('invalid h80 identity in calibration QA') from exc
    inputs, uuids = [], set()
    for path in map(Path, h80_paths):
        digest = sha256_file(path)
        with uproot.open(path) as source:
            uuid = str(source.file.uuid)
            if uuid in uuids:
                raise ValueError('duplicate h80 ROOT identity')
            uuids.add(uuid)
            tree = source['h80']
            inputs.append(dict(path=str(path.resolve()), sha256=digest, size=path.stat().st_size,
                               uuid=uuid, tree='h80', entries=int(tree.num_entries)))
        if sha256_file(path) != digest:
            raise ValueError('h80 identity changed during axis authentication')
    if sorted((row['size'], row['sha256']) for row in inputs) != expected_identity:
        raise ValueError('h80 input identity differs from calibration provenance')
    known = {row.run_number for row in validate_manifest(manifest) if row.target == 'P'}
    _import_root()
    source = _open_root_file(product_path)
    axes = {}
    try:
        directory = source.GetDirectory('calibration')
        if not directory:
            raise ValueError('missing independent calibration directory')
        names = [key.GetName() for key in directory.GetListOfKeys()]
        seen = set()
        for coverage in qa['coverage']:
            run, state = int(coverage['run_number']), coverage['state']
            key = run, state
            if key in seen:
                raise ValueError('duplicate independent calibration coverage')
            seen.add(key)
            if run not in known or not coverage.get('accepted'):
                continue
            span = coverage.get('strip_coverage') or {}
            if (span.get('observed_strip_count', 0) < 5 or span.get('first_strip') != 1
                    or span.get('last_strip') != 128):
                raise ValueError('accepted calibration lacks full independent strip coverage')
            name = f'run{run}_{state}_fit'
            if names.count(name) != 1:
                raise ValueError(f'missing or duplicate independent fit: {name}')
            fit = directory.Get(name)
            if not fit.InheritsFrom('TF1') or fit.GetNpar() != 5:
                raise ValueError(f'invalid independent pol4 fit: {name}')
            minimum = minimum_pol4_derivative(fit, .5, 128.5)
            if not np.isfinite(minimum) or minimum <= 0:
                raise ValueError(f'nonmonotonic independent fit: {name}')
            edges = np.array([fit.Eval(.5 + i) for i in range(129)])
            axes[key] = IndependentStripAxis(run, state, edges,
                dict(kind='inclusive_h80_calibration', path=str(product_path.resolve()),
                     sha256=qa['calibrated_sha256'], uuid=str(source.GetUUID().AsString()),
                     object=f'calibration/{name}', qa_path=str(provenance_path.resolve()),
                     qa_sha256=qa_hash, manifest_sha256=manifest_hash, h80=inputs,
                     coverage=coverage, fit_model='pol4'))
    finally:
        source.Close()
    if (sha256_file(product_path) != qa['calibrated_sha256']
            or sha256_file(provenance_path) != qa_hash or sha256_file(manifest) != manifest_hash):
        raise ValueError('independent calibration identity changed while reading')
    return axes
