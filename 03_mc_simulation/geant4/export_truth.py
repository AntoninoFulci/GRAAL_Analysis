#!/usr/bin/env python3
"""Export unsmeared exclusive generator events for diagnostic Geant4 transport."""
import argparse
from array import array
from contextlib import ExitStack
import csv
import hashlib
import json
import math
from pathlib import Path
import sys
import tempfile
import uuid

from graal_common.physics.channels import M_PROTON, channel_from_filename, get_channel


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def vector(value):
    return tuple(float(getattr(value, component)()) for component in ("Px", "Py", "Pz", "E"))


def validate_event(beam, proton, photons):
    """Require the generator's GeV, free-proton, on-shell final-state contract."""
    vectors = [beam, proton, *photons]
    if not photons or any(len(v) != 4 or not all(map(math.isfinite, v)) or v[3] <= 0
                          for v in vectors):
        raise ValueError("Invalid truth four-vector")
    expected = (*beam[:3], beam[3] + M_PROTON)
    actual = tuple(math.fsum(v[i] for v in [proton, *photons]) for i in range(4))
    if any(abs(a - b) > 1.e-8 for a, b in zip(actual, expected)):
        raise ValueError("Truth four-momentum conservation failed")
    for v, mass in [(beam, 0), (proton, M_PROTON), *((p, 0) for p in photons)]:
        if abs(v[3] ** 2 - math.fsum(p * p for p in v[:3]) - mass ** 2) > 1.e-8:
            raise ValueError("Truth particle is off shell")
    if abs(beam[0]) > 1.e-10 or abs(beam[1]) > 1.e-10 or beam[2] <= 0:
        raise ValueError("Expected a forward beam along +z")


def _export_truth(source, output, channel=None, max_events=10, export_format="root"):
    """Write into an unpublished staging directory; the public wrapper publishes it."""
    import ROOT  # Only this conversion step requires PyROOT.

    source, output = Path(source).resolve(), Path(output).resolve()
    if type(max_events) is not int or max_events <= 0:
        raise ValueError("max_events must be positive")
    channel = get_channel(channel) if channel else channel_from_filename(source)
    source_hash = sha256(source)
    with ROOT.TFile.Open(str(source), "READ") as handle:
        if not handle or handle.IsZombie():
            raise ValueError(f"Cannot read ROOT input: {source}")

        def metadata(name, text=False):
            value = handle.Get(name)
            if not value:
                raise ValueError(f"Missing generator metadata: {name}")
            return str(value.GetTitle()) if text else value.GetVal()

        generator = metadata("generator", True)
        if generator != f"generate_{channel.name}_dataset":
            raise ValueError(f"generator {generator} does not match channel {channel.name}")
        sampling = metadata("sampling", True)
        if metadata("generator_schema_version") != 1 or sampling != (
                "accept-reject-unweighted; TRandom3 shared with TGenPhaseSpace"):
            raise ValueError("Unsupported generator schema or sampling policy")
        truth_schema = handle.Get("truth_schema_version")
        if truth_schema and truth_schema.GetVal() != 1:
            raise ValueError("Unsupported truth schema")
        seed = int(metadata("seed"))
        low, high = float(metadata("beam_min_gev")), float(metadata("beam_max_gev"))
        tree = handle.Get("mc")
        if not tree or not tree.InheritsFrom("TTree"):
            raise ValueError("Missing mc tree")
        total = int(tree.GetEntries())
        if (total <= 0 or int(metadata("n_generated")) != total
                or int(metadata("n_requested")) != total or not 0 < seed <= 2**32 - 1
                or not (math.isfinite(low) and math.isfinite(high) and 0 < low < high)):
            raise ValueError("Invalid generator count, seed or beam window")

        def require_branch(name):
            if not tree.GetBranch(name):
                raise ValueError(f"Missing truth branch: {name}; regenerate a new diagnostic sample")

        for name in ("beam_true", "proton_true"):
            require_branch(name)
        if not channel.photon_branches:
            require_branch("n_true_gamma")
        count = min(max_events, total)
        with ExitStack() as stack:
            if export_format == "root":
                target = stack.enter_context(ROOT.TFile.Open(str(output / "truth.root"), "RECREATE"))
                if not target or target.IsZombie():
                    raise ValueError("Cannot create ROOT truth output")
                events = ROOT.TTree("events", "Unsmeared generator event ledger")
                particles = ROOT.TTree("primaries", "Unsmeared generator final states")
                eb = {name: array(code, [0]) for name, code in (
                    ("event", "i"), ("source_entry", "Q"), ("energy_GeV", "d"),
                    ("generation_weight", "d"), ("nprimaries", "i"))}
                pb = {name: array("i" if name in ("event", "primary_index", "pdg") else "d", [0])
                      for name in ("event", "primary_index", "pdg", "px_GeV", "py_GeV", "pz_GeV",
                                   "energy_GeV", "mass_GeV")}
                for tree_out, buffers in ((events, eb), (particles, pb)):
                    for name, buffer in buffers.items():
                        leaf = {"i": "I", "Q": "l", "d": "D"}[buffer.typecode]
                        tree_out.Branch(name, buffer, f"{name}/{leaf}")
            else:
                primaries = stack.enter_context((output / "primaries.dat").open("w"))
                mapping = stack.enter_context((output / "truth.csv").open("w", newline=""))
                writer = csv.writer(mapping)
                writer.writerow(("event", "source_entry", "beam_energy_GeV", "generation_weight"))
            for entry in range(count):
                if tree.GetEntry(entry) <= 0:
                    raise ValueError(f"Cannot read source entry {entry}")
                if channel.photon_branches:
                    names = channel.photon_branches
                else:
                    photons_count = int(tree.n_true_gamma)
                    if not 1 <= photons_count <= 8:
                        raise ValueError("Invalid n_true_gamma")
                    names = tuple(f"g{i}" for i in range(photons_count))
                for name in names:
                    require_branch(name + "_true")
                beam, proton = vector(tree.beam_true), vector(tree.proton_true)
                photons = [vector(getattr(tree, name + "_true")) for name in names]
                validate_event(beam, proton, photons)
                if not low <= beam[3] <= high:
                    raise ValueError("Truth beam energy outside generator metadata window")
                final = [(2212, proton, M_PROTON), *((22, p, 0) for p in photons)]
                if not 2 <= len(final) <= 9:
                    raise ValueError("Unsupported primary count")
                if export_format == "root":
                    for name, value in zip(eb, (entry, entry, beam[3], 1., len(final))):
                        eb[name][0] = value
                    events.Fill()
                    for index, (pdg, momentum, mass) in enumerate(final):
                        for name, value in zip(pb, (entry, index, pdg, *momentum, mass)):
                            pb[name][0] = value
                        particles.Fill()
                else:
                    primaries.write(f"{len(final)}\n")
                    for pdg, momentum, mass in final:
                        values = " ".join(format(v, ".17g") for v in (*momentum[:3], mass))
                        primaries.write(f"1 {pdg} 0 0 {values}\n")
                    writer.writerow((entry, entry, format(beam[3], ".17g"), 1))
            if export_format == "root":
                target.cd()
                events.Write()
                particles.Write()
        if sha256(source) != source_hash:
            raise ValueError("Source changed during export")
        report = {
            "schema_version": 2 if export_format == "root" else 1, "status": "diagnostic_truth_export", "channel": channel.name,
            "source": str(source), "source_sha256": source_hash, "source_uuid": str(handle.GetUUID().AsString()),
            "generator": generator, "generator_schema_version": 1, "sampling": sampling,
            "generator_root_version": metadata("root_version", True), "seed": seed,
            "beam_window_GeV": [low, high], "source_events": total, "events": count,
            "units": "GeV", "vertex_mm": [0, 0, 0], "time_ns": 0,
            "generation_target": "free_proton", "geometry_target": "period_conditions_required" if export_format == "root" else "deuterium_diagnostic_only",
            "weight_policy": "unit_unweighted_no_flux_or_cross_section_normalization",
            "polarization": "not_modeled",
        }
        if export_format == "root":
            report.update(truth_schema_version=1 if truth_schema else None,
                          exported_entries_policy="contiguous_source_prefix",
                          flux_normalization="not_applied", branching_ratio_normalization="not_applied",
                          cross_section_normalization="not_applied")
            with ROOT.TFile.Open(str(output / "truth.root"), "UPDATE") as target:
                target.cd()
                ROOT.TObjString(json.dumps(report, sort_keys=True, allow_nan=False)).Write("metadata")
            report["truth_root_sha256"] = sha256(output / "truth.root")
            report["source_root_sha256"] = source_hash
        else:
            report.update(primary_sha256=sha256(output / "primaries.dat"),
                          mapping_sha256=sha256(output / "truth.csv"))
            (output / "manifest.json").write_text(json.dumps(report, indent=2) + "\n")
        return report


def validate_root_truth(path):
    """Validate the complete scalar ROOT contract and its unchanged generator identity."""
    import numpy as np
    import uproot

    path = Path(path).resolve()
    before = sha256(path)
    with uproot.open(path) as root:
        if root.classnames(cycle=False) != {"events": "TTree", "primaries": "TTree", "metadata": "TObjString"}:
            raise ValueError("Invalid truth ROOT objects")
        report = json.loads(str(root["metadata"]))
        required = {"schema_version": 2, "status": "diagnostic_truth_export", "units": "GeV",
                    "vertex_mm": [0, 0, 0], "time_ns": 0, "generation_target": "free_proton",
                    "geometry_target": "period_conditions_required", "polarization": "not_modeled",
                    "weight_policy": "unit_unweighted_no_flux_or_cross_section_normalization",
                    "exported_entries_policy": "contiguous_source_prefix", "flux_normalization": "not_applied",
                    "branching_ratio_normalization": "not_applied", "cross_section_normalization": "not_applied"}
        if (not isinstance(report, dict) or any(report.get(k) != v for k, v in required.items())
                or type(report.get("schema_version")) is not int
                or type(report.get("time_ns")) not in (int, float)
                or not isinstance(report.get("vertex_mm"), list)
                or any(type(v) not in (int, float) for v in report["vertex_mm"])):
            raise ValueError("Unsupported ROOT truth metadata")
        count, total = report.get("events"), report.get("source_events")
        seed, window = report.get("seed"), report.get("beam_window_GeV")
        channel = report.get("channel")
        if (type(count) is not int or type(total) is not int or not 0 < count <= total
                or count > 2**31-1 or type(seed) is not int or not 0 < seed <= 2**32-1
                or not isinstance(window, list) or len(window) != 2
                or not all(type(v) in (int, float) and math.isfinite(v) for v in window)
                or not 0 < window[0] < window[1]
                or not isinstance(channel, str) or get_channel(channel).name != channel
                or report.get("generator") != f"generate_{channel}_dataset"
                or type(report.get("generator_schema_version")) is not int
                or report["generator_schema_version"] != 1
                or "truth_schema_version" not in report
                or (report["truth_schema_version"] is not None and
                    (type(report["truth_schema_version"]) is not int or report["truth_schema_version"] != 1))
                or report.get("sampling") != "accept-reject-unweighted; TRandom3 shared with TGenPhaseSpace"
                or not all(isinstance(report.get(k), str) and report[k] for k in
                           ("source", "source_sha256", "source_uuid", "generator_root_version"))):
            raise ValueError("Invalid ROOT truth provenance")
        try:
            uuid.UUID(report["source_uuid"])
            source_hash = report["source_sha256"]
            if len(source_hash) != 64 or any(c not in "0123456789abcdef" for c in source_hash):
                raise ValueError("Invalid SHA-256")
        except ValueError as error:
            raise ValueError("Invalid truth source identity") from error
        source = Path(report["source"])
        if not source.is_absolute() or sha256(source) != source_hash:
            raise ValueError("Truth source hash mismatch")
        with uproot.open(source) as original:
            if str(original.file.uuid) != report["source_uuid"] or original["mc"].num_entries != total:
                raise ValueError("Truth source UUID or count mismatch")
            source_fields = {"generator": ("fTitle", report["generator"]),
                             "sampling": ("fTitle", report["sampling"]),
                             "root_version": ("fTitle", report["generator_root_version"]),
                             "seed": ("fVal", seed), "n_generated": ("fVal", total),
                             "n_requested": ("fVal", total), "generator_schema_version": ("fVal", 1),
                             "beam_min_gev": ("fVal", window[0]), "beam_max_gev": ("fVal", window[1])}
            for key, (member, expected) in source_fields.items():
                if original[key].member(member) != expected:
                    raise ValueError(f"Truth source metadata mismatch: {key}")
            source_truth_schema = original["truth_schema_version"].member("fVal") if "truth_schema_version" in original else None
            if source_truth_schema != report["truth_schema_version"]:
                raise ValueError("Truth source schema mismatch")
            source_tree = original["mc"]
            photon_names = get_channel(channel).photon_branches or ()
            source_counts = None if photon_names else source_tree["n_true_gamma"].array(entry_stop=count, library="np")
            if source_counts is not None and not np.all((source_counts >= 1) & (source_counts <= 8)):
                raise ValueError("Invalid source photon counts")
            names = ("beam_true", "proton_true", *(name+"_true" for name in photon_names))
            if source_counts is not None:
                names += tuple(f"g{i}_true" for i in range(int(source_counts.max())))
            source_vectors = {}
            for name in names:
                values = source_tree[name].array(entry_stop=count, library="np")
                source_vectors[name] = [tuple(value.member("fP").member(k) for k in ("fX", "fY", "fZ"))
                                        + (value.member("fE"),) for value in values]
        contracts = {
            "events": {"event": "int32", "source_entry": "uint64", "energy_GeV": "float64",
                       "generation_weight": "float64", "nprimaries": "int32"},
            "primaries": {"event": "int32", "primary_index": "int32", "pdg": "int32",
                          **{key: "float64" for key in ("px_GeV", "py_GeV", "pz_GeV", "energy_GeV", "mass_GeV")}}}
        arrays = {}
        for name, contract in contracts.items():
            tree = root[name]
            if list(tree.keys()) != list(contract):
                raise ValueError(f"Invalid truth branches: {name}")
            arrays[name] = tree.arrays(library="np")
            for key, dtype in contract.items():
                values = arrays[name][key]
                if values.ndim != 1 or values.dtype != np.dtype(dtype) or not np.isfinite(values).all():
                    raise ValueError(f"Invalid scalar truth branch: {name}/{key}")
        events, particles = arrays["events"], arrays["primaries"]
        if (len(events["event"]) != count or not np.array_equal(events["event"], np.arange(count))
                or not np.array_equal(events["source_entry"], np.arange(count))
                or not np.all(events["generation_weight"] == 1.)
                or not np.all((events["energy_GeV"] >= window[0]) & (events["energy_GeV"] <= window[1]))
                or not np.all((events["nprimaries"] >= 2) & (events["nprimaries"] <= 9))
                or len(particles["event"]) != int(events["nprimaries"].sum())):
            raise ValueError("Invalid truth event order, counts, energy or weights")
        offset = 0
        for event, n in enumerate(events["nprimaries"]):
            n = int(n)
            segment = slice(offset, offset+n)
            if (not np.all(particles["event"][segment] == event)
                    or not np.array_equal(particles["primary_index"][segment], np.arange(n))
                    or not np.array_equal(particles["pdg"][segment], [2212] + [22]*(n-1))
                    or not np.array_equal(particles["mass_GeV"][segment], [M_PROTON] + [0.]*(n-1))):
                raise ValueError("Invalid truth primary order, PDG or mass")
            vectors = list(zip(*(particles[k][segment] for k in ("px_GeV", "py_GeV", "pz_GeV", "energy_GeV"))))
            energy = float(events["energy_GeV"][event])
            validate_event((0., 0., energy, energy), vectors[0], vectors[1:])
            names = photon_names if photon_names else tuple(f"g{i}" for i in range(int(source_counts[event])))
            expected = [source_vectors[name][event] for name in ("proton_true", *(name+"_true" for name in names))]
            beam = source_vectors["beam_true"][event]
            if vectors != expected or energy != beam[3]:
                raise ValueError("Truth primaries differ from the claimed unsmeared source entry")
            validate_event(beam, expected[0], expected[1:])
            offset += n
    if sha256(source) != source_hash or sha256(path) != before:
        raise ValueError("Truth or source changed during validation")
    return dict(report, truth_root_sha256=before, source_root_sha256=source_hash)


def export_truth(source, output, channel=None, max_events=10, *, export_format="root"):
    """Export ROOT schema 2 by default; publish only a complete, valid new directory."""
    output = Path(output).resolve()
    if export_format not in ("root", "hepevt"):
        raise ValueError("export_format must be root or hepevt")
    if output.exists():
        raise FileExistsError(f"Output exists; refusing overwrite: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f".{output.name}-", dir=output.parent) as temporary:
        staging = Path(temporary) / "export"
        staging.mkdir()
        report = _export_truth(source, staging, channel, max_events, export_format)
        if export_format == "root":
            validate_root_truth(staging / "truth.root")
        # mkdir exclusively reserves the destination; no existing directory is replaced.
        output.mkdir()
        try:
            for artifact in staging.iterdir():
                artifact.rename(output / artifact.name)
        except BaseException:
            for artifact in output.iterdir():
                artifact.unlink()
            output.rmdir()
            raise
        return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path, help="New output directory")
    parser.add_argument("--channel")
    parser.add_argument("--max-events", type=int, default=10)
    parser.add_argument("--format", choices=("root", "hepevt"), default="root", dest="export_format")
    args = parser.parse_args()
    report = export_truth(args.source, args.output, args.channel, args.max_events, export_format=args.export_format)
    print(f"Exported {report['events']} diagnostic events: {args.output}")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, ImportError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)
