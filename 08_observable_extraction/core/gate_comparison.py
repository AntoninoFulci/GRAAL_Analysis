"""Contracts and common-grid diagnostics for the no-fit gate comparison."""

from collections import Counter
from dataclasses import asdict, fields

import numpy as np

from observable_extraction.core.binning import PAIR_NAMES, pair_mass_edges
from observable_extraction.core.systematics import difference_covariance


def compare_contracts(pairing, bdt):
    """Require identical recorded reconstruction, apart from the optional gate."""
    for record in (pairing, bdt):
        if record.get("do_fit") is not False:
            raise ValueError("comparison requires proven no-fit reconstruction")
        for key in ("inputs", "source_files", "counts_by_run_state"):
            if not record.get(key):
                raise ValueError(f"missing reconstruction provenance: {key}")
    for key in ("inputs", "source_files"):
        identity = lambda record: sorted((item["size"], item["sha256"]) for item in record[key])
        if identity(pairing) != identity(bdt):
            raise ValueError(f"different reconstruction {key}")
    for key in ("channel", "input_tree"):
        if not pairing.get(key) or pairing[key] != bdt.get(key):
            raise ValueError(f"different reconstruction {key}")
    selections = [dict(record["selection"]) for record in (pairing, bdt)]
    threshold_a, threshold_b = (selection.pop("bdt_threshold") for selection in selections)
    if threshold_a is not None or selections[0] != selections[1]:
        raise ValueError("selection differs beyond the BDT gate")
    approved = dict(chi2_cut=10., chi2_resolution_relative=.08,
                    missing_mass_window_gev=.06, fit_cl=None,
                    photons="first_four_of_at_least_four", protons="exactly_one")
    if any(selections[0].get(key) != value for key, value in approved.items()):
        raise ValueError("selection does not match the approved no-fit baseline")
    def universe(record):
        rows = record["counts_by_run_state"]
        keys = [(row["run"], row["polarization"]) for row in rows]
        if len(set(keys)) != len(keys):
            raise ValueError("duplicate run/state in reconstruction cutflow")
        return {key: row["input"] for key, row in zip(keys, rows)}
    if universe(pairing) != universe(bdt):
        raise ValueError("different inclusive run/state universe")
    return dict(selections[0], bdt_threshold=threshold_b)


def subset_audit(pairing, bdt):
    """Exact multiset check, NOT a replacement for persistent source-entry IDs.

    Stable under filtering/reordering; duplicate content remains explicitly
    ambiguous. Run bootstrap never consumes a positional event correspondence.
    """
    def fingerprints(events):
        columns = [np.asarray(getattr(events, field.name), dtype="<f8").reshape(len(events), -1)
                   for field in fields(events) if field.name != "bdt_score"] if len(events) else []
        if not columns:
            return Counter()
        values = np.concatenate(columns, axis=1)
        if not np.isfinite(values).all():
            raise ValueError("nonfinite event content cannot certify subset")
        values[values == 0] = 0.  # Canonicalize signed zero.
        return Counter(row.tobytes() for row in values)
    parent, child = fingerprints(pairing), fingerprints(bdt)
    unmatched = sum((child - parent).values())
    if unmatched:
        raise ValueError(f"BDT is not a kinematic multiset subset: {unmatched} unmatched events")
    return dict(matched=len(bdt), removed=len(pairing) - len(bdt),
                ambiguous_fingerprints=sum(parent[key] > 1 for key in child),
                identity="exact_kinematic_multiset_only", source_entry_identity="unavailable")


def grid_key(estimator, pair, energy_bin, mass_bin):
    return f"{estimator}:{pair}:E{energy_bin}:M{mass_bin}"


def point_map(points):
    result = {}
    for item in points:
        point = item.point
        key = grid_key(item.estimator, point.pair, point.energy_bin, point.mass_bin)
        if key in result:
            raise ValueError(f"duplicate comparison point: {key}")
        result[key] = item
    return result


def align_points(pairing, bdt, energy_edges, *, sample_names=("pairing", "bdt")):
    """Enumerate the full requested grid, including failed and absent fits."""
    first, second = sample_names
    lookups = [point_map(points) for points in (pairing, bdt)]
    rows = []
    for estimator in ("ratio", "likelihood"):
        for pair in PAIR_NAMES:
            masses = pair_mass_edges(pair)
            for energy_bin in range(len(energy_edges) - 1):
                for mass_bin in range(len(masses) - 1):
                    key = grid_key(estimator, pair, energy_bin, mass_bin)
                    items = [lookup.get(key) for lookup in lookups]
                    available = [item is not None and item.point.diagnostics.converged for item in items]
                    status = {(True, True): "both_estimable", (True, False): f"{first}_only",
                              (False, True): f"{second}_only", (False, False): "neither_estimable"}[tuple(available)]
                    rows.append(dict(key=key, estimator=estimator, pair=pair,
                                     energy_bin=energy_bin, mass_bin=mass_bin,
                                     energy_low=float(energy_edges[energy_bin]),
                                     energy_high=float(energy_edges[energy_bin + 1]),
                                     mass_low=float(masses[mass_bin]), mass_high=float(masses[mass_bin + 1]),
                                     **{first: asdict(items[0]) if items[0] else None,
                                        second: asdict(items[1]) if items[1] else None}, status=status,
                                     delta=items[1].point.sigma - items[0].point.sigma if all(available) else None))
    return rows


def paired_difference_summary(replicas, keys):
    """Cov(BDT-pairing) for bins estimable in EVERY draw; never delete draws.

    Columns are [all pairing keys, all BDT keys]. Unstable bins remain in the
    central grid and in the replica array, but receive no covariance or error.
    """
    values = np.asarray(replicas, dtype=float)
    n = len(keys)
    if values.ndim != 2 or values.shape[1] != 2 * n or len(values) < 2:
        raise ValueError("paired replica shape must be (at least 2, twice the key count)")
    valid = np.isfinite(values[:, :n]) & np.isfinite(values[:, n:])
    indices = np.flatnonzero(valid.all(axis=0))
    result = dict(available_keys=[keys[i] for i in indices],
                  unavailable_keys=[keys[i] for i in range(n) if i not in indices],
                  failed_replicas_by_key={key: int((~valid[:, i]).sum()) for i, key in enumerate(keys)},
                  replicas=len(values), covariance_kind="paired_stratified_run_diagnostic",
                  joint_covariance=None, cross_covariance=None, difference_covariance=None,
                  difference_covariance_mc_se=None, rank=None)
    if len(indices):
        selected = values[:, np.r_[indices, n + indices]]
        joint = np.atleast_2d(np.cov(selected, rowvar=False, ddof=1))
        size = len(indices)
        cross = joint[:size, size:]
        delta_cov = difference_covariance(joint[size:, size:], joint[:size, :size], cross.T)
        differences = selected[:, size:] - selected[:, :size]
        centered = differences - differences.mean(axis=0)
        outer = np.einsum("bi,bj->bij", centered, centered) * len(values) / (len(values) - 1)
        mc_se = outer.std(axis=0, ddof=1) / np.sqrt(len(values))
        result.update(joint_covariance=joint.tolist(), cross_covariance=cross.tolist(),
                      difference_covariance=delta_cov.tolist(), difference_covariance_mc_se=mc_se.tolist(),
                      rank=int(np.linalg.matrix_rank(delta_cov)))
    return result
