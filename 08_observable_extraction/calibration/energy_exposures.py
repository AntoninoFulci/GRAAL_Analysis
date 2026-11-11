"""Build explicit experimental exposures from independently projected strips.

This boundary does not fit, qualify, or activate a recovery policy. The caller
must inventory states and supply only valid measured states and explicitly
accepted projections. Defective present states must never be omitted to make
them appear missing. Common-energy transfer belongs to the study upstream.
"""
from __future__ import annotations

import numpy as np

from observable_extraction.core.models import FluxExposure
from observable_extraction.core.periods import exposure_summary

_STATES = ("POL1", "POL2", "BREM")


def _native_state(record, key, *, projected):
    run, state = key
    if record.get("run", run) != run or record.get("state", state) != state:
        raise ValueError("run/state identity conflicts with projection key")
    values = np.asarray(record["values"], dtype=float)
    edges = np.asarray(record["calibration_edges"], dtype=float)
    if (values.shape != (128,) or not np.all(np.isfinite(values)) or np.any(values < 0)):
        raise ValueError("native strip values require 128 finite nonnegative contents")
    if (edges.shape != (129,) or not np.all(np.isfinite(edges))
            or np.any(edges <= 0) or np.any(np.diff(edges) <= 0)):
        raise ValueError("invalid independent strip axis")
    if projected:
        if not np.sum(values) > 0:
            raise ValueError("zero-integral projection is not an exposure")
        if record.get("axis_source", {}).get("kind") != "inclusive_h80_calibration":
            raise ValueError("projection requires independent inclusive h80 axis provenance")
        if "strip_indices" in record and not np.array_equal(record["strip_indices"], np.arange(1, 129)):
            raise ValueError("projection must retain authentic strip identities 1..128")
        transfer = record.get("audit", {})
        if transfer.get("destination_covered") is not True:
            raise ValueError("projection has no verified full destination coverage")
        if not np.isclose(transfer.get("destination_integral", np.nan), np.sum(values), rtol=1e-10, atol=0.):
            raise ValueError("projection integral conflicts with transfer audit")
    return values, (edges[:-1] + edges[1:]) * .5


def build_projected_exposures(measured_states, projected, *, polarization_model,
                             energy_range=(1.1, 1.5), replace_measured=False):
    """Return ``(run/strip exposures, per-run audit)`` for explicit inputs.

    Both mappings use ``(run, state)`` keys. Measured records contain native
    ``values`` and ``calibration_edges``. Projected records additionally carry
    independent ``axis_source`` and conservative-transfer ``audit``. Optional
    run/state and strip identities are checked when present. Existing measured
    states are protected unless ``replace_measured`` explicitly selects a
    masked closure. In that case no hidden values or axes are inspected.

    Per-state conversion failures stay in the audit; neither a hidden measured
    state nor a zero sentinel fills a failed projection. Invalid POL states
    prevent exposure construction; unavailable BREM stays explicitly separate.
    """
    low, high = energy_range
    if not np.isfinite((low, high)).all() or high <= low:
        raise ValueError("energy range must be finite and increasing")
    keys = set(measured_states) | set(projected)
    if any(not isinstance(run, (int, np.integer)) or run <= 0 or state not in _STATES
           for run, state in keys):
        raise ValueError("invalid run/state key")
    overlap = set(measured_states) & set(projected)
    for key in overlap:
        if measured_states[key].get("status", "measured_valid") not in ("valid", "measured_valid"):
            raise ValueError(f"cannot replace defective measured state: {key}")
    if overlap and not replace_measured:
        raise ValueError("existing measured states require explicit replace_measured=True for closure")

    exposures, audit = {}, {}
    for run in sorted({key[0] for key in keys}):
        native, states, problems = {}, {}, []
        for state in _STATES:
            key = run, state
            is_projected = key in projected
            record = projected.get(key) if is_projected else measured_states.get(key)
            if record is None:
                states[state] = dict(status="missing")
                continue
            try:
                if not is_projected and record.get("status", "measured_valid") not in ("valid", "measured_valid"):
                    raise ValueError("defective measured state")
                native[state] = _native_state(record, key, projected=is_projected)
                states[state] = dict(status="projected" if is_projected else "measured_valid")
                if is_projected:
                    states[state].update(axis_source=dict(record["axis_source"]), audit=dict(record["audit"]))
            except (ValueError, TypeError, KeyError) as exc:
                states[state] = dict(status="invalid_projection" if is_projected else "invalid_content",
                                     reason=str(exc))
                problems.append(f"{state}: {exc}")
        values = []
        skipped = dict(outside_energy=0, nonpositive_pol=0, polarization_domain=0)
        if all(state in native for state in ("POL1", "POL2")):
            fv, ev = native["POL1"]
            fh, eh = native["POL2"]
            for index in range(128):
                energy = float((ev[index] + eh[index]) * .5)
                if not low <= energy <= high:
                    skipped["outside_energy"] += 1
                    continue
                if fv[index] <= 0 or fh[index] <= 0:
                    skipped["nonpositive_pol"] += 1
                    continue
                if "BREM" in native:
                    flux_brem = float(native["BREM"][0][index])
                    brem_status = "estimated" if (run, "BREM") in projected else "measured_valid"
                else:
                    flux_brem = None
                    brem_status = "missing" if states["BREM"]["status"] == "missing" else "invalid_content"
                try:
                    item = FluxExposure(int(run), index + 1, energy, float(fv[index]), float(fh[index]),
                        flux_brem, float(polarization_model(float(ev[index]))),
                        float(polarization_model(float(eh[index]))), brem_status=brem_status)
                except ValueError:
                    skipped["polarization_domain"] += 1
                    continue
                exposures[(int(run), index + 1)] = item
                values.append(item)
        else:
            problems.extend(f"{state}: unavailable polarized exposure" for state in ("POL1", "POL2")
                            if state not in native)
        audit[str(run)] = dict(status="valid" if values else "no_valid_exposure", states=states,
            problems=problems, valid_strata=len(values), skipped=skipped,
            exposure=exposure_summary({(item.run_number, item.xstrip): item for item in values}))
    return exposures, audit
