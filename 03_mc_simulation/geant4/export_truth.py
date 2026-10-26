#!/usr/bin/env python3
"""Export unsmeared exclusive generator events for diagnostic Geant4 transport."""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import sys

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


def export_truth(source, output, channel=None, max_events=10):
    import ROOT  # Only this conversion step requires PyROOT.

    source, output = Path(source).resolve(), Path(output).resolve()
    if output.exists():
        raise FileExistsError(f"Output exists; refusing overwrite: {output}")
    if max_events <= 0:
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
        output.mkdir(parents=True)
        count = min(max_events, total)
        with (output / "primaries.dat").open("w") as primaries, (output / "truth.csv").open("w", newline="") as mapping:
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
                primaries.write(f"{1 + len(photons)}\n")
                for pdg, momentum, mass in [(2212, proton, M_PROTON), *((22, p, 0) for p in photons)]:
                    values = " ".join(format(v, ".17g") for v in (*momentum[:3], mass))
                    primaries.write(f"1 {pdg} 0 0 {values}\n")
                writer.writerow((entry, entry, format(beam[3], ".17g"), 1))
        if sha256(source) != source_hash:
            raise ValueError("Source changed during export")
        report = {
            "schema_version": 1, "status": "diagnostic_truth_export", "channel": channel.name,
            "source": str(source), "source_sha256": source_hash, "source_uuid": str(handle.GetUUID().AsString()),
            "generator": generator, "generator_schema_version": 1, "sampling": sampling,
            "generator_root_version": metadata("root_version", True), "seed": seed,
            "beam_window_GeV": [low, high], "source_events": total, "events": count,
            "primary_sha256": sha256(output / "primaries.dat"), "mapping_sha256": sha256(output / "truth.csv"),
            "units": "GeV", "vertex_mm": [0, 0, 0], "time_ns": 0,
            "generation_target": "free_proton", "geometry_target": "deuterium_diagnostic_only",
            "weight_policy": "unit_unweighted_no_flux_or_cross_section_normalization",
            "polarization": "not_modeled",
        }
        (output / "manifest.json").write_text(json.dumps(report, indent=2) + "\n")
        return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path, help="New output directory")
    parser.add_argument("--channel")
    parser.add_argument("--max-events", type=int, default=10)
    args = parser.parse_args()
    report = export_truth(args.source, args.output, args.channel, args.max_events)
    print(f"Exported {report['events']} diagnostic events: {args.output}")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, ImportError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)
