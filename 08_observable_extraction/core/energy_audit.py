"""Per-energy accounting, including bins that cannot yield an asymmetry."""

import numpy as np

from observable_extraction.core.binning import bin_index
from observable_extraction.core.periods import selection_audit, exposure_summary


def energy_bin_inventory(samples, exposures, edges, points):
    rows = []
    for index, (low, high) in enumerate(zip(edges[:-1], edges[1:])):
        counts = {}
        for name, events in samples.items():
            energy = events.beam_energy_gev
            inside = (energy >= low) & ((energy <= high) if index == len(edges) - 2 else (energy < high))
            counts[name] = selection_audit(events.take(inside), exposures, (low, high))
        strata = {key: value for key, value in exposures.items()
                  if bin_index(value.energy_gev, edges) == index}
        fitted = [item for item in points if item.point.energy_bin == index]
        rows.append(dict(
            energy_bin=index, low_gev=float(low), high_gev=float(high),
            samples=counts, exposure=exposure_summary(strata),
            status="estimable" if fitted else "not_estimable",
            estimable_points=len(fitted),
            efficiency=None, efficiency_status="not_evaluated; requires validated MC support",
            fits=[dict(sample=item.sample, pair=item.point.pair, mass_bin=item.point.mass_bin,
                       estimator=item.estimator, sigma=item.point.sigma, stat_low=item.point.stat_low, stat_high=item.point.stat_high,
                       at_boundary=bool(np.isclose(abs(item.point.sigma), 1.0, atol=1e-6, rtol=0)),
                       fallback=item.point.diagnostics.used_fallback) for item in fitted],
        ))
    return rows
