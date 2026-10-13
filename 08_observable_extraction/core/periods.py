"""Run partitions and accounting shared by pooled and period extraction."""

import re

import numpy as np


def partition_runs(records, input_runs, *, target, beam_type):
    by_run = {}
    for record in records:
        if record.run_number in by_run:
            raise ValueError(f"duplicate manifest run {record.run_number}")
        if (record.source_period == "pooled"
                or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", record.source_period)):
            raise ValueError(f"unsafe source period: {record.source_period!r}")
        by_run[record.run_number] = record
    unknown = set(input_runs) - by_run.keys()
    if unknown:
        raise ValueError(f"unknown input runs absent from manifest: {sorted(unknown)}")
    groups = {}
    for run in sorted(input_runs):
        record = by_run[run]
        if record.target != target or record.beam_type != beam_type:
            raise ValueError(f"run {run} conflicts with selected target/profile {target}/{beam_type}")
        groups.setdefault(record.source_period, []).append(run)
    return dict(sorted(groups.items()))


def selection_audit(events, exposures, energy_range):
    low, high = energy_range
    energy = (events.beam_energy_gev >= low) & (events.beam_energy_gev <= high)
    sigma = np.isin(events.polarization, (1, 2))
    brem = events.polarization == 0
    exposed = np.array([(int(run), int(strip)) in exposures
                        for run, strip in zip(events.run_number, events.xstrip)], dtype=bool)
    selected = energy & sigma & exposed
    control = energy & brem & exposed
    return dict(
        input=len(events), selected=int(selected.sum()), brem=int(control.sum()),
        vertical=int(np.count_nonzero(selected & (events.polarization == 1))),
        horizontal=int(np.count_nonzero(selected & (events.polarization == 2))),
        excluded=int(np.count_nonzero(~(selected | control))),
        outside_energy=int(np.count_nonzero(~energy)),
        other_state=int(np.count_nonzero(energy & ~(sigma | brem))),
        missing_exposure=int(np.count_nonzero(energy & (sigma | brem) & ~exposed)),
        input_states={str(int(state)): int(np.count_nonzero(events.polarization == state))
                      for state in np.unique(events.polarization)},
    )


def exposure_summary(exposures):
    values = tuple(exposures.values())
    fv = sum(item.flux_vertical for item in values)
    fh = sum(item.flux_horizontal for item in values)
    return dict(strata=len(values), vertical=fv, horizontal=fh,
                brem=sum(item.flux_brem for item in values),
                polarization_vertical=(sum(item.flux_vertical * item.polarization_vertical
                                            for item in values) / fv if fv else None),
                polarization_horizontal=(sum(item.flux_horizontal * item.polarization_horizontal
                                              for item in values) / fh if fh else None))
