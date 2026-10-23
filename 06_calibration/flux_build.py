"""Internal coordinator for measured strip calibration and flux QA."""
from __future__ import annotations

import argparse
from collections import defaultdict
from math import isfinite
import os
from pathlib import Path
import sys
from typing import Sequence

from calibration.run_manifest import validate_manifest
from calibration.calibration_qa import sha256_file, write_calibration_qa
from calibration.calibrated_flux_root import _POLARIZATION_SUFFIX, _write_calibrated_flux_root_atomic
from calibration.strip_energy_root import (
    _FLUX_SUFFIXES, ProgressReporter, read_h80_lookup, read_calibration_cells,
    read_flux_histograms,
)
from calibration.strip_energy_flux import (
    AJAKA_CROSS_SECTION, AJAKA_SIGMA, FLUX_SCHEMA_VERSION, EnergyBinning,
    StripEnergyFluxError, clamp_negative_flux, complete_strip_energy_lookup,
    find_monotonic_inversions, integrate_run_flux, join_strip_exposures,
)


def parse_custom_binnings(values: Sequence[str]) -> tuple[EnergyBinning, ...]:
    result = []
    seen = {AJAKA_CROSS_SECTION.name, AJAKA_SIGMA.name}
    for value in values:
        name, separator, raw_edges = value.partition(":")
        if not separator or not name or not raw_edges:
            raise StripEnergyFluxError(
                "custom binning must use NAME:EDGE,EDGE,..."
            )
        if name in seen:
            raise StripEnergyFluxError(f"duplicate binning name: {name}")
        try:
            edges = tuple(float(edge) for edge in raw_edges.split(","))
        except ValueError:
            raise StripEnergyFluxError(
                f"custom binning {name}: edges must be numeric"
            ) from None
        result.append(EnergyBinning(name, edges))
        seen.add(name)
    return tuple(result)



def _input_paths(args: argparse.Namespace) -> dict[str, str]:
    return {
        "preanalysis_dir": str(args.preanalysis_dir),
        "manifest": str(args.manifest),
        "flux": str(args.flux),
        "output_dir": str(args.output_dir),
    }



def _validate_output_location(args: argparse.Namespace) -> None:
    sidecar = (args.output_dir / "flux_calibrated.qa.json").resolve()
    sources = [args.manifest, args.flux,
               *(p for p in args.preanalysis_dir.rglob('*.root') if p.is_file())]
    for source in sources:
        if sidecar == Path(source).resolve():
            raise StripEnergyFluxError(f"QA output path overlaps input path: {source}")
    output_path = args.output_dir / "flux_calibrated.root"
    lexical_output = Path(os.path.abspath(output_path))
    resolved_output = output_path.resolve(strict=False)
    for input_path in sources:
        lexical_input = Path(os.path.abspath(input_path))
        resolved_input = input_path.resolve(strict=False)
        if lexical_input == lexical_output or resolved_input == resolved_output:
            raise StripEnergyFluxError(
                f"output path overlaps input path: {input_path}"
            )
    lexical_preanalysis = Path(os.path.abspath(args.preanalysis_dir))
    resolved_preanalysis = args.preanalysis_dir.resolve(strict=False)
    if (
        lexical_output == lexical_preanalysis
        or lexical_preanalysis in lexical_output.parents
        or resolved_output == resolved_preanalysis
        or resolved_preanalysis in resolved_output.parents
    ):
        raise StripEnergyFluxError(
            f"output path overlaps pre-analysis input: {args.preanalysis_dir}"
        )



def _h80_input_identity(directory: Path) -> list[tuple[str, int, int, str]]:
    """Record the recursive file inventory consumed by both h80 scans."""
    return [
        (str(path.resolve()), path.stat().st_size, path.stat().st_mtime_ns, sha256_file(path))
        for path in sorted(directory.rglob("*.root"))
        if path.is_file()
    ]



def build_qa_payload(
    args: argparse.Namespace,
    manifest,
    lookup,
    run_flux,
    h80_qa,
    flux_qa,
    errors,
    warnings,
) -> dict[str, object]:
    manifest_runs = {record.run_number for record in manifest}
    h80_runs = {record.run_number for record in lookup}
    unique_errors = sorted(set(errors))
    return {
        "schema_version": FLUX_SCHEMA_VERSION,
        "inputs": _input_paths(args),
        "thresholds": {
            "min_events_per_strip": args.min_events_per_strip,
            "max_mad_gev": args.max_mad_gev,
            "monotonic_tolerance_gev": args.monotonic_tolerance_gev,
        },
        "binnings": flux_qa["analysis_binnings"],
        "manifest_run_count": len(manifest_runs),
        "h80_run_count": len(h80_runs),
        "flux_run_count": flux_qa["run_count"],
        "lookup_strip_count": len(lookup),
        "h80": h80_qa,
        "flux": {
            key: value
            for key, value in flux_qa.items()
            if key not in {
                "analysis_binnings",
                "empty_strips",
                "extra_h80_runs",
                "low_stat_warnings",
                "mad_warnings",
                "missing_h80_runs",
                "monotonic_inversions",
                "negative_flux_bins",
                "nonzero_unmapped_strips",
                "nonpositive_selected_exposures",
                "out_of_range",
            }
        },
        "missing_h80_runs": flux_qa["missing_h80_runs"],
        "extra_h80_runs": flux_qa["extra_h80_runs"],
        "extra_flux_runs": flux_qa["extra_runs"],
        "malformed_flux_triplets": flux_qa["malformed_triplets"],
        "empty_strips": flux_qa["empty_strips"],
        "nonzero_unmapped_strips": flux_qa["nonzero_unmapped_strips"],
        "monotonic_inversions": flux_qa["monotonic_inversions"],
        "mad_warnings": flux_qa["mad_warnings"],
        "low_stat_warnings": flux_qa["low_stat_warnings"],
        "negative_flux_bins": flux_qa["negative_flux_bins"],
        "nonpositive_selected_exposures": flux_qa[
            "nonpositive_selected_exposures"
        ],
        "underflow_overflow": flux_qa["underflow_overflow"],
        "out_of_range": flux_qa["out_of_range"],
        "run_flux_bin_count": len(run_flux),
        "warnings": list(dict.fromkeys(warnings)),
        "errors": unique_errors,
        "valid": not unique_errors,
    }



def run(args: argparse.Namespace) -> int:
    progress = ProgressReporter()
    output_path = args.output_dir / "flux_calibrated.root"
    progress_every_events = getattr(args, "progress_every_events", 1_000_000)
    threads = getattr(args, "threads", os.cpu_count() or 1)
    samples_per_run_strip = getattr(args, "samples_per_run_strip", 256)
    target = getattr(args, "target", None)
    progress.log("starting strip-energy/flux build")
    progress.log(
        f"inputs: preanalysis={args.preanalysis_dir}; manifest={args.manifest}; "
        f"flux={args.flux}; output={output_path}"
    )
    _validate_output_location(args)
    input_identity = {"manifest": sha256_file(args.manifest), "raw_flux": sha256_file(args.flux)}
    h80_identity = _h80_input_identity(args.preanalysis_dir)
    if args.min_events_per_strip < 1:
        raise StripEnergyFluxError("min-events-per-strip must be at least 1")
    if not isfinite(args.max_mad_gev) or args.max_mad_gev < 0:
        raise StripEnergyFluxError("max-mad-gev must be finite and nonnegative")
    if (
        not isfinite(args.monotonic_tolerance_gev)
        or args.monotonic_tolerance_gev < 0
    ):
        raise StripEnergyFluxError(
            "monotonic-tolerance-gev must be finite and nonnegative"
        )
    if progress_every_events < 0:
        raise StripEnergyFluxError("progress-every-events must be nonnegative")
    if threads < 1:
        raise StripEnergyFluxError("threads must be at least 1")
    if samples_per_run_strip < 1:
        raise StripEnergyFluxError("samples-per-run-strip must be at least 1")

    progress.log("validating run manifest")
    all_records = validate_manifest(args.manifest)
    records = [
        record
        for record in all_records
        if target is None or record.target == target
    ]
    if not records:
        raise StripEnergyFluxError(f"manifest has no {target} target runs")
    progress.log(
        f"manifest loaded: {len(all_records)} runs; "
        f"selected: {len(records)} runs"
    )
    all_manifest_runs = {record.run_number for record in all_records}
    manifest_by_run = {record.run_number: record for record in records}
    progress.log("building strip-energy lookup with ROOT RDataFrame")
    lookup, h80_qa = read_h80_lookup(
        args.preanalysis_dir,
        run_numbers=sorted(manifest_by_run),
        samples_per_run_strip=samples_per_run_strip,
        threads=threads,
        progress=progress,
        progress_every_events=progress_every_events,
    )
    h80_qa["extra_runs"] = [
        run for run in h80_qa["extra_runs"] if run not in all_manifest_runs
    ]
    progress.log(f"h80 scan complete: {h80_qa['entries']} events")
    progress.log("building per-polarization calibration cells")
    calibration_cells, calibration_energy_bins = read_calibration_cells(
        args.preanalysis_dir,
        run_numbers=sorted(manifest_by_run),
        threads=threads,
    )
    progress.log(
        f"calibration cells built: {len(calibration_cells)} "
        "run/polarization/strip rows"
    )
    observed_strip_count = len(lookup)
    observed_runs = sorted({row.run_number for row in lookup})
    lookup, filled_strips = complete_strip_energy_lookup(
        lookup,
        run_numbers=observed_runs,
    )
    h80_qa.update(
        {
            "observed_strip_count": observed_strip_count,
            "completed_strip_count": len(lookup),
            "filled_strips": list(filled_strips),
        }
    )
    progress.log(
        f"strip-energy lookup built: {len(lookup)} run/strip rows; "
        f"filled missing rows: {len(filled_strips)}"
    )

    lookup_by_run = defaultdict(list)
    for row in lookup:
        lookup_by_run[row.run_number].append(row)
    manifest_runs = set(manifest_by_run)
    sample_runs = set(lookup_by_run)

    progress.log("reading POL1/POL2/BREM flux histograms")
    strips, flux_qa = read_flux_histograms(
        args.flux,
        sorted(manifest_runs),
        progress=progress,
    )
    flux_qa["extra_runs"] = [
        run for run in flux_qa["extra_runs"] if run not in all_manifest_runs
    ]
    strips, negative_flux_bins = clamp_negative_flux(strips)
    progress.log(f"flux scan complete: {len(strips)} run/strip rows")
    flux_by_run = defaultdict(list)
    for row in strips:
        flux_by_run[row.run_number].append(row)
    flux_by_run_strip = {
        run_number: {row.xstrip: row for row in rows}
        for run_number, rows in flux_by_run.items()
    }

    errors = []
    warnings = []
    extra_h80 = list(h80_qa["extra_runs"])
    missing_h80 = sorted(manifest_runs - sample_runs)
    if extra_h80:
        for run_number in extra_h80:
            print(
                f"WARNING: unused h80 run {run_number}",
                file=sys.stderr,
            )
    if missing_h80:
        warnings.append(f"manifest runs absent from h80: {missing_h80}")
    if negative_flux_bins:
        count = len(negative_flux_bins)
        noun = "bin" if count == 1 else "bins"
        warnings.append(
            f"{count} negative flux histogram {noun} clamped to zero"
        )
    if flux_qa["extra_runs"]:
        for run_number in flux_qa["extra_runs"]:
            print(
                f"WARNING: unused complete flux run {run_number}",
                file=sys.stderr,
            )
    for problem in flux_qa["malformed_triplets"]:
        errors.append(
            f"malformed flux triplet for run {problem['run_number']}"
        )

    binnings = (
        AJAKA_CROSS_SECTION,
        AJAKA_SIGMA,
        *parse_custom_binnings(args.binning),
    )

    progress.log("running lookup and flux QA")
    empty_strips = []
    nonzero_unmapped = []
    for run_number in sorted(manifest_runs & sample_runs):
        mapped = {row.xstrip for row in lookup_by_run[run_number]}
        for xstrip in range(1, 129):
            if xstrip in mapped:
                continue
            empty_strips.append({"run_number": run_number, "xstrip": xstrip})
            strip = flux_by_run_strip.get(run_number, {}).get(xstrip)
            if strip is not None and any(
                value != 0.0
                for value in (
                    strip.flux_pol1,
                    strip.flux_pol2,
                    strip.flux_brem,
                )
            ):
                nonzero_unmapped.append(
                    {
                        "run_number": run_number,
                        "xstrip": xstrip,
                        "flux_pol1": strip.flux_pol1,
                        "flux_pol2": strip.flux_pol2,
                        "flux_brem": strip.flux_brem,
                    }
                )
                errors.append(
                    f"run {run_number} strip {xstrip}: "
                    "nonzero flux without lookup"
                )

    inversions = []
    for inversion in find_monotonic_inversions(lookup):
        delta = inversion.get("delta_gev")
        if delta is None or abs(delta) > args.monotonic_tolerance_gev:
            inversions.append(inversion)
            if delta is None:
                errors.append(
                    f"run {inversion['run_number']}: "
                    "monotonic direction is undetermined"
                )
            else:
                errors.append(
                    f"run {inversion['run_number']} strips "
                    f"{inversion['left_strip']}-{inversion['right_strip']}: "
                    f"monotonic inversion {delta} GeV"
                )

    mad_warnings = [
        {
            "run_number": row.run_number,
            "xstrip": row.xstrip,
            "energy_mad_gev": row.energy_mad_gev,
        }
        for row in lookup
        if row.energy_mad_gev > args.max_mad_gev
    ]
    low_stat_warnings = [
        {
            "run_number": row.run_number,
            "xstrip": row.xstrip,
            "event_count": row.event_count,
        }
        for row in lookup
        if row.event_count < args.min_events_per_strip
    ]

    out_of_range = {}
    for binning in binnings:
        below = []
        above = []
        excluded = [0.0, 0.0, 0.0]
        for run_number in sorted(manifest_runs & sample_runs):
            flux_by_strip = flux_by_run_strip[run_number]
            for row in lookup_by_run[run_number]:
                if row.energy_median_gev < binning.edges_gev[0]:
                    below.append((run_number, row.xstrip))
                elif row.energy_median_gev > binning.edges_gev[-1]:
                    above.append((run_number, row.xstrip))
                else:
                    continue
                strip = flux_by_strip[row.xstrip]
                for index, value in enumerate(
                    (strip.flux_pol1, strip.flux_pol2, strip.flux_brem)
                ):
                    excluded[index] += value
        out_of_range[binning.name] = {
            "below_lookup_count": len(below),
            "above_lookup_count": len(above),
            "below_lookup_strips": [
                {"run_number": run_number, "xstrip": xstrip}
                for run_number, xstrip in below
            ],
            "above_lookup_strips": [
                {"run_number": run_number, "xstrip": xstrip}
                for run_number, xstrip in above
            ],
            "raw_flux_excluded": {
                "flux_pol1": excluded[0],
                "flux_pol2": excluded[1],
                "flux_brem": excluded[2],
            },
        }

    run_flux = []
    for binning in binnings:
        progress.log(f"integrating flux binning: {binning.name}")
        for run_number in sorted(manifest_runs & sample_runs):
            try:
                integrated = integrate_run_flux(
                    manifest_by_run[run_number],
                    lookup_by_run[run_number],
                    flux_by_run[run_number],
                    binning,
                )
            except StripEnergyFluxError as exc:
                errors.append(str(exc))
                continue
            run_flux.extend(integrated)

    progress.log("joining event strata to run/strip exposures")
    try:
        strip_exposures = join_strip_exposures(
            [row for row in lookup if row.run_number in manifest_by_run],
            [row for row in strips if row.run_number in sample_runs],
            manifest_by_run,
        )
    except StripEnergyFluxError as exc:
        errors.append(str(exc))
        strip_exposures = ()
    nonpositive_selected_exposures = []
    for row in strip_exposures:
        if row.status != "valid":
            nonpositive_selected_exposures.append(
                {"run_number": row.run_number, "xstrip": row.xstrip}
            )
    if nonpositive_selected_exposures:
        count = len(nonpositive_selected_exposures)
        noun = "exposure" if count == 1 else "exposures"
        warnings.append(
            f"{count} run/strip {noun} with non-positive POL1/POL2 "
            "excluded from extraction"
        )

    flux_qa.update(
        {
            "analysis_binnings": {
                binning.name: list(binning.edges_gev) for binning in binnings
            },
            "missing_h80_runs": missing_h80,
            "extra_h80_runs": extra_h80,
            "empty_strips": empty_strips,
            "nonzero_unmapped_strips": nonzero_unmapped,
            "monotonic_inversions": inversions,
            "mad_warnings": mad_warnings,
            "low_stat_warnings": low_stat_warnings,
            "negative_flux_bins": negative_flux_bins,
            "nonpositive_selected_exposures": nonpositive_selected_exposures,
            "out_of_range": out_of_range,
        }
    )

    qa = build_qa_payload(
        args,
        records,
        lookup,
        run_flux,
        h80_qa,
        flux_qa,
        errors,
        warnings,
    )
    if qa["warnings"]:
        total_warnings = len(qa["warnings"])
        for index, warning in enumerate(qa["warnings"], start=1):
            progress.log(f"QA WARNING [{index}/{total_warnings}]: {warning}")
    if qa["errors"]:
        visible_errors = qa["errors"][:20]
        total_errors = len(qa["errors"])
        for index, error in enumerate(visible_errors, start=1):
            progress.log(f"QA ERROR [{index}/{total_errors}]: {error}")
        if total_errors > len(visible_errors):
            progress.log(
                f"QA ERROR: {total_errors - len(visible_errors)} additional "
                "errors omitted from log"
            )
    if not qa["valid"]:
        progress.log(f"completed with invalid QA: {len(qa['errors'])} errors")
        return 1

    def validate_input_identity() -> None:
        current = {"manifest": sha256_file(args.manifest), "raw_flux": sha256_file(args.flux)}
        if input_identity != current:
            raise StripEnergyFluxError("calibration input identity changed during scan")
        if h80_identity != _h80_input_identity(args.preanalysis_dir):
            raise StripEnergyFluxError("pre-analysis input identity changed during scan")

    progress.log(f"writing calibrated ROOT: {output_path}")
    calibrated_root_qa = _write_calibrated_flux_root_atomic(
        args.flux,
        output_path,
        calibration_cells,
        calibration_energy_bins,
        before_publish=validate_input_identity,
    )
    observed = {(int(row["run_number"]), _POLARIZATION_SUFFIX[row["polarization"]]): row
                for row in calibrated_root_qa["calibration_coverage"]}
    coverage = []
    for record in records:
        for state in _FLUX_SUFFIXES:
            cell = observed.get((record.run_number, state))
            coverage.append(dict(run_number=record.run_number, state=state,
                                 h80_present=cell is not None,
                                 accepted=bool(cell and cell["accepted"]),
                                 reason=("accepted" if cell and cell["accepted"] else
                                         "insufficient_coverage" if cell else "not_covered"),
                                 strip_coverage=cell))
    write_calibration_qa(output_path.with_suffix(".qa.json"), output_path,
                         inputs={**input_identity, "h80": h80_identity}, coverage=coverage,
                         diagnostics={"pre_write": qa, "writer": calibrated_root_qa})
    if calibrated_root_qa["skipped_without_calibration"]:
        warning = (
            "flux histograms skipped without run/polarization calibration: "
            f"{len(calibrated_root_qa['skipped_without_calibration'])}"
        )
        progress.log(f"QA WARNING [post-write]: {warning}")
    progress.log("completed successfully")
    print(f"Wrote calibrated flux ROOT to {output_path}")
    return 0
