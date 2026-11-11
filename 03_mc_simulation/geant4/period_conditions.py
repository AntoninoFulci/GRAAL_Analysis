#!/usr/bin/env python3
"""Prepare period-specific diagnostic geometry and observed-interaction XY profiles.

Published inputs and the frozen snapshot are read-only. Mechanical adjustments,
nominal cell XY and liquid-hydrogen density are explicit diagnostic assumptions.
"""
import argparse
import copy
import csv
import hashlib
import json
import math
from pathlib import Path
import re

import numpy as np

MODULE = Path(__file__).resolve().parent
DEFAULT_CONDITIONS = MODULE.parents[1] / "config/support/target_conditions_current"


def digest(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def read_publication(directory):
    """Verify publication and the referenced archive once for a preparation batch."""
    directory = Path(directory).resolve()
    publication_path = directory / "publication.json"
    publication = json.loads(publication_path.read_text())
    if publication.get("schema") != 1:
        raise ValueError("Unsupported target publication schema")
    hashes = {}
    for name, expected in publication["output_checksums"].items():
        if Path(name).name != name or digest(directory / name) != expected:
            raise ValueError(f"Publication checksum mismatch: {name}")
        hashes[name] = expected
    if "geant4_candidates.json" not in hashes:
        raise ValueError("Missing candidates checksum")
    payload = json.loads((directory / "geant4_candidates.json").read_text())
    if payload.get("schema") != 2 or not isinstance(payload.get("periods"), dict):
        raise ValueError("Unsupported period candidates schema")
    if "target_periods.csv" not in hashes:
        raise ValueError("Missing target periods checksum")
    with (directory / "target_periods.csv").open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    catalog = {row["period"]: row for row in rows}
    if len(catalog) != len(rows) or set(catalog) != set(payload["periods"]):
        raise ValueError("Period catalog and candidates disagree")
    archive = (directory / publication["source_products"] / "run_plots.npz").resolve()
    stamp = archive.stat()
    expected = publication["source_checksums"]["run_plots.npz"]
    if digest(archive) != expected:
        raise ValueError("Archive checksum mismatch: run_plots.npz")
    hashes["run_plots.npz"] = expected
    hashes["publication.json"] = digest(publication_path)
    return dict(directory=directory, periods=payload["periods"], catalog=catalog, archive=archive,
                archive_stamp=stamp, hashes=hashes)


def load_period(directory, period, *, publication=None):
    publication = publication or read_publication(directory)
    if not re.fullmatch(r"[A-Za-z0-9_]+", period) or period not in publication["periods"]:
        raise ValueError(f"Unknown period: {period}")
    row = copy.deepcopy(publication["periods"][period])
    target, proxy = row["target"], row["photon_beam_proxy"]
    catalog = publication["catalog"][period]
    if catalog["target_labels"] != target.get("material_label") or catalog["beam_labels"] not in ("UV", "VIS"):
        raise ValueError(f"Unresolved target or beam label: {period}")
    if (row.get("coverage_status") != "complete"
            or row.get("geometry_status") != "compatible_lengths"
            or row.get("weighting") != "equal_weight_per_valid_run"
            or not row.get("included_runs") or row.get("missing_runs")
            or target.get("material_label") not in ("P", "D")):
        raise ValueError(f"Unavailable or incompatible period conditions: {period}")
    for key in ("length_mm", "center_z_mm", "diameter_mm"):
        value = target.get(key)
        if type(value) not in (int, float) or not math.isfinite(value):
            raise ValueError(f"Invalid period target {key}: {period}")
    if target["length_mm"] <= 0 or target["diameter_mm"] != 50 or target.get("center_xy_mm") is not None:
        raise ValueError("Only the declared historical 50 mm, nominal-XY cell is supported")
    if (target.get("diameter_source") != "historical_reference_assumption_not_run_measurement"
            or proxy.get("available") is not True or proxy.get("frame") != "native_h70_detector"
            or proxy.get("units") != "mm"
            or proxy.get("kind") != "equal_run_mean_observed_interaction_xy_not_unfolded_incident_beam"):
        raise ValueError(f"Unsupported period beam proxy: {period}")
    archive = (publication["directory"] / proxy["profile_file"]).resolve()
    if archive != publication["archive"]:
        raise ValueError("Beam profile does not reference the verified archive")
    prefix = proxy["archive_prefix"]
    if proxy["probability_key"] != prefix + "xy_probability":
        raise ValueError("Beam profile key does not match archive prefix")
    with np.load(archive, allow_pickle=False) as source:
        x = source[prefix + "x_edges_mm"]
        y = source[prefix + "y_edges_mm"]
        probability = source[proxy["probability_key"]]
    after = archive.stat()
    before = publication["archive_stamp"]
    if (before.st_size, before.st_mtime_ns, before.st_ino) != (after.st_size, after.st_mtime_ns, after.st_ino):
        raise ValueError("Beam archive changed during verification")
    if (x.ndim != 1 or y.ndim != 1 or len(x) < 2 or len(y) < 2
            or not np.isfinite(x).all() or not np.isfinite(y).all()
            or not (np.diff(x) > 0).all() or not (np.diff(y) > 0).all()
            or probability.shape != (len(x)-1, len(y)-1)
            or not np.isfinite(probability).all() or (probability < 0).any()
            or not np.isclose(probability.sum(), 1., rtol=0, atol=1.e-10)):
        raise ValueError(f"Invalid normalized XY histogram: {period}")
    # A positive-area intersection is necessary for conditional cylinder sampling.
    dx = np.maximum(np.maximum(x[:-1], -x[1:]), 0)
    dy = np.maximum(np.maximum(y[:-1], -y[1:]), 0)
    if not np.any((probability > 0) & (dx[:, None]**2 + dy[None, :]**2 < 25**2)):
        raise ValueError("Beam profile has no support inside the nominal target")
    row.update(period=period, source_directory=str(publication["directory"]),
               source_hashes=publication["hashes"], x_edges_mm=x.tolist(),
               y_edges_mm=y.tolist(), xy_probability=probability.tolist())
    from graal_common.physics.beam_profiles import get_beam_profile
    beam = get_beam_profile(catalog["beam_labels"].lower())
    row.update(beam_type=catalog["beam_labels"], beam_window_GeV=list(beam.energy_range_gev),
               beam_window_policy="shared_analysis_profile; incident_spectrum_and_polarization_not_inferred_from_XY")
    return row


def validate_period_truth(conditions, truth):
    if conditions["target"]["material_label"] != "P" or truth["generation_target"] != "free_proton":
        raise ValueError("Free-proton truth cannot represent a deuterium period; nuclear generator required")
    low, high = truth["beam_window_GeV"]
    expected_low, expected_high = conditions["beam_window_GeV"]
    if low < expected_low-1.e-10 or high > expected_high+1.e-10:
        raise ValueError("Truth beam window lies outside the period analysis beam profile")


def period_snapshot(source, conditions):
    """Derive a snapshot; keep all detector records outside the cell assembly exact."""
    lines = source.read_text().splitlines()
    records = [line.split() for line in lines]

    def find(*prefix):
        matches = [i for i, row in enumerate(records) if row[:len(prefix)] == list(prefix)]
        if len(matches) != 1:
            raise ValueError(f"Expected one snapshot record: {prefix}")
        return matches[0]

    def number(index, column, value):
        records[index][column] = format(value, ".17g")

    target = conditions["target"]
    length, center = target["length_mm"]/10, target["center_z_mm"]/10
    low, high = center-length/2, center+length/2
    cell, cap = find("V", "CIBM"), find("V", "FEN3")
    inner, outer = find("V", "ENVI"), find("V", "ENVM")
    inner_pos, outer_pos = find("P", "ENVI"), find("P", "ENVM")
    cap_half = float(records[cap][7])
    inner_low = float(records[inner_pos][6])-float(records[inner][7])
    outer_low = float(records[outer_pos][6])-float(records[outer][7])
    inner_high = low-2*cap_half
    if not inner_low < inner_high < high or not outer_low < high or abs(low) >= 15 or abs(high) >= 15:
        raise ValueError("Period cell does not fit the historical target assembly")
    changes = {cell, find("P", "CIBM"), find("P", "FEN3", "1"), find("P", "FEN3", "2"),
               inner, outer, inner_pos, outer_pos}
    number(cell, 7, length/2)
    number(find("P", "CIBM"), 6, center)
    number(find("P", "FEN3", "1"), 6, high+cap_half)
    number(find("P", "FEN3", "2"), 6, low-cap_half)
    for volume, placement, start, stop in ((inner, inner_pos, inner_low, inner_high),
                                            (outer, outer_pos, outer_low, high)):
        number(volume, 7, (stop-start)/2)
        number(placement, 6, (stop+start)/2)
    if target["material_label"] == "P":
        material = find("M", "1")
        records[material] = ["M", "1", "HYDROGEN$", "1.01", "1", "0.0708"]
        changes.add(material)
    return "\n".join(" ".join(records[i]) if i in changes else line
                     for i, line in enumerate(lines)) + "\n"


def write_inputs(conditions, output, snapshot, *, seed):
    if type(seed) is not int or not 0 < seed <= 2**31-1:
        raise ValueError("Period seed must be an integer in [1, 2147483647]")
    output, snapshot = Path(output), Path(snapshot)
    report = copy.deepcopy(conditions)
    report.update(schema=1, status="diagnostic_period_conditions", seed=seed,
                  frozen_snapshot_sha256=digest(snapshot),
                  vertex_policy="observed_xy_conditioned_on_nominal_cell_radius; independent_uniform_z",
                  assembly_policy="move_FEN3_caps; keep_ENVI_ENVM_upstream_ends_and_radial_dimensions",
                  target_center_xy_policy="frozen_nominal_origin_not_measured_beam_center",
                  material_policy="liquid_H1_0.0708_g_cm3_assumption" if report["target"]["material_label"] == "P"
                                  else "frozen_liquid_D2_0.162_g_cm3",
                  frame_policy="native_h70_detector_equals_nominal_legacy_detector; alignment_unvalidated")
    report["target"]["center_xy_mm"] = [0., 0.]
    geometry = period_snapshot(snapshot, conditions)
    x, y, probability = report["x_edges_mm"], report["y_edges_mm"], report["xy_probability"]
    target = report["target"]
    header = ["GRAAL_PERIOD_V1", report["period"], target["material_label"],
              *(format(target[key], ".17g") for key in ("length_mm", "center_z_mm", "diameter_mm")), str(seed)]
    bins = [" ".join(header)]
    for i, row in enumerate(probability):
        for j, weight in enumerate(row):
            if weight:
                bins.append(" ".join(format(v, ".17g") for v in (x[i], x[i+1], y[j], y[j+1], weight)))
    for name, content in (("geometry.g3", geometry), ("conditions.dat", "\n".join(bins)+"\n")):
        with (output / name).open("x") as stream:
            stream.write(content)
    report["artifact_hashes"] = {name: digest(output/name) for name in ("geometry.g3", "conditions.dat")}
    with (output / "period.json").open("x") as stream:
        stream.write(json.dumps(report, indent=2, allow_nan=False)+"\n")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--conditions", type=Path, default=DEFAULT_CONDITIONS)
    parser.add_argument("--period", action="append", help="Repeat to select periods; default: all available")
    parser.add_argument("--output", type=Path, required=True, help="New directory; never overwritten")
    parser.add_argument("--seed", type=int, required=True, help="Base seed; one distinct seed per sorted period")
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("Output exists; refusing overwrite")
    publication = read_publication(args.conditions)
    selected = sorted(args.period or publication["periods"])
    if len(selected) != len(set(selected)) or not 0 < args.seed <= 2**31-len(selected):
        raise ValueError("Duplicate periods or invalid seed range")
    ready, unavailable = {}, {}
    for period in selected:
        row = publication["periods"].get(period, {})
        if not args.period and row.get("geometry_status") != "compatible_lengths":
            unavailable[period] = row.get("geometry_status", "missing")
            continue
        ready[period] = load_period(args.conditions, period, publication=publication)
    args.output.mkdir(parents=True)
    manifest = dict(schema=1, status="prepared_not_simulated", periods={}, unavailable=unavailable)
    for index, (period, conditions) in enumerate(ready.items()):
        out = args.output / period
        out.mkdir()
        report = write_inputs(conditions, out, MODULE / "reference/geometry.g3", seed=args.seed+index)
        manifest["periods"][period] = dict(seed=report["seed"], target=report["target"],
                                          period_sha256=digest(out / "period.json"),
                                          free_proton_replay_supported=report["target"]["material_label"] == "P")
    (args.output / "campaign.json").write_text(json.dumps(manifest, indent=2)+"\n")
    print(f"Prepared {len(ready)} periods; unavailable: {', '.join(unavailable) or 'none'}")


if __name__ == "__main__":
    main()
