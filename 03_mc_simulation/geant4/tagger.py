"""Recovered legacy09 TAG + single-strip LSIMUL PREAN diagnostic.

Incident beam energy is an explicit response input, never a reconstructed
observable. GPS final-state primaries do not supply it. Sampling preserves the
archived histogram bin masses with PCG64 and uniform within-bin displacement;
it does not reproduce CERNLIB HRNDM1's random stream.
"""
import argparse
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import struct

import numpy as np
import uproot

from mc_simulation.geant4.cylinder_config import _f15_3, _list_real
from mc_simulation.geant4.digitize import sha256, _write_provenance
from mc_simulation.geant4.central import _json
from mc_simulation.geant4.root_output import read_transport_summary

MODULE = Path(__file__).resolve().parent
ARCHIVE = MODULE.parents[1] / "docs/reference/fortran/prog"
MODE = "legacy09_simulated_tagger_diagnostic"
# HRGET/HGIVE/HUNPAK extraction of preserved tag.hist; id,nx,xmin,xmax
# little-endian INTEGER/REAL followed by the original regular REAL bins.
HISTOGRAM_PAYLOAD_SHA256 = "acd41e1862942e22beab9110bedebbda24951146bd7a2c647300656f18f60473"
STATUS_CODES = {0: "accepted", 1: "outside_aperture", 2: "missing_incident_beam",
                3: "source_histogram_out_of_range", 4: "nonfinite_or_singular",
                5: "source_digit_out_of_range_stop", 6: "transport_aborted"}
EVENT_TYPES = dict(run="int32", event="int32", source_entry="uint64",
                   available="int32", nclusters="int32", status="int32")
CLUSTER_TYPES = dict(run="int32", event="int32", cluster_index="int32",
                     xstrip="float64", energy_GeV="float64", multiplicity="int32")


def _r(value):
    return np.float32(value)


def read_config(acquisition_run):
    if type(acquisition_run) is not int or not 0 < acquisition_run < 2**31:
        raise ValueError("Explicit positive int32 acquisition_run required")
    path = ARCHIVE / "data/base/data09.base"
    lines = path.read_text().splitlines()
    parameters = {}
    for key, record, label in (("offset_mm", 157, "XOFFMS"), ("pitch_um", 158, "PITCHMS"),
                               ("length_mm", 159, "LENMS"), ("ee_GeV", 163, "EE"),
                               ("a0_mm", 164, "A0")):
        if not re.match(r"\s*" + label + r"(?:\s|$)", lines[record-1].split("!", 1)[-1]):
            raise ValueError(f"Missing legacy09 {label} record {record}")
        parameters[key] = (_list_real if record >= 163 else _f15_3)(lines[record-1])
    parameters["pitch_mm"] = float(_r(_r(parameters.pop("pitch_um")) / _r(1000)))
    # TAG uses beam.inc constants; PREAN uses data09 values. Check both, explicitly.
    beam = (ARCHIVE / "lagdig/include/beam.inc").read_text()
    active = beam.split("#if !defined(GRAAL_EGOLD)", 1)[1].split("#endif", 1)[0]
    for name, key in (("EE", "ee_GeV"), ("A0", "a0_mm")):
        match = re.search(r"PARAMETER\(" + name + r"=([0-9.]+)\)", active)
        if not match or float(_r(float(match[1]))) != parameters[key]:
            raise ValueError("Active beam.inc and legacy09 PREAN constants differ")
    paths = [path] + [ARCHIVE / item for item in (
        "lagdig/src/tag.F", "lagdig/src/initag.F", "lagdig/src/constan.F",
        "lagdig/include/beam.inc", "lagdig/pilot.h", "prean/src/anastrip_tag.F",
        "prean/src/eg_tag_sim.F", "prean/src/swap_strip.F", "prean/src/constan.F")]
    return dict(schema=1, profile="legacy09", acquisition_run=acquisition_run,
                mode=MODE, **parameters, sources={str(p): sha256(p) for p in paths},
                precision="Fortran REAL IEEE binary32 expression operations",
                swap_odd_even=3173 <= acquisition_run < 4512,
                physics_validation=False)


@dataclass(frozen=True)
class Response:
    status: int
    histogram_id: int = -1
    digit: int = -1
    xstrip: float = math.nan
    energy_GeV: float = math.nan
    position_mm: float = math.nan

    @property
    def available(self):
        return self.status in (0, 1)


def histogram_id(beam_energy_GeV):
    """TAG INT truncates towards zero, including its 150--250 MeV sliver."""
    if not math.isfinite(beam_energy_GeV) or abs(beam_energy_GeV) > np.finfo(np.float32).max:
        return None
    with np.errstate(over="ignore", invalid="ignore"):
        value = _r(_r(_r(beam_energy_GeV) * _r(1000)) - _r(250)) / _r(100)
    # Original INT has no defined representable result beyond signed INTEGER.
    return int(value) + 101 if np.isfinite(value) and -2**31 <= value < 2**31-101 else None


def respond(beam_energy_GeV, displacement_mm, config):
    """Original TAG map with injected HRNDM1 displacement and PREAN inverse.

    Source STOP at digit 129 becomes an unavailable status, not a silently
    clamped valid strip. Aperture losses are known empty detector responses.
    """
    ident = histogram_id(beam_energy_GeV)
    if ident is None:
        return Response(4)
    if not 101 <= ident <= 117:
        return Response(3, ident)
    if not math.isfinite(displacement_mm) or abs(displacement_mm) > np.finfo(np.float32).max:
        return Response(4, ident)
    energy, ee, a0 = map(_r, (beam_energy_GeV, config["ee_GeV"], config["a0_mm"]))
    if energy == ee:
        return Response(4, ident)
    offset, length, pitch = map(_r, (config["offset_mm"], config["length_mm"], config["pitch_mm"]))
    position = _r(_r(_r(a0 * energy) / _r(ee - energy)) + _r(displacement_mm))
    if not np.isfinite(position):
        return Response(4, ident)
    if position < offset or position > _r(offset + length):
        return Response(1, ident, position_mm=float(position))
    digit = int(_r(_r(position - offset) / pitch)) + 1
    if not 1 <= digit <= 128:
        return Response(5, ident, digit, position_mm=float(position))
    strip = digit + (1 if digit % 2 else -1) if config["swap_odd_even"] else digit
    measured_position = _r(offset + _r(_r(_r(strip) - _r(.5)) * pitch))
    measured_energy = _r(_r(ee * measured_position) / _r(a0 + measured_position))
    return Response(0, ident, digit, float(strip), float(measured_energy), float(position))


def _metadata(root):
    value = _json(root["metadata"])
    if not isinstance(value, dict):
        raise ValueError("ROOT metadata must be an object")
    return value


def histogram_payload_sha256(histograms):
    digest = hashlib.sha256()
    for ident, (values, edges) in sorted(histograms.items()):
        digest.update(struct.pack("<iiff", ident, len(values), edges[0], edges[-1]))
        digest.update(np.asarray(values, dtype="<f4").tobytes())
    return digest.hexdigest()


def read_histograms(path):
    with uproot.open(path) as root:
        meta = _metadata(root)
        source = ARCHIVE / "data/simul_beam/tag.hist"
        if (meta.get("mode") != "exact_hbook_tagger_response" or
                meta.get("source_sha256") != sha256(source) or
                meta.get("source_histogram_ids") != list(range(101, 118)) or
                meta.get("displacement_unit") != "mm"):
            raise ValueError("Histogram source identity/schema mismatch")
        histograms = {}
        for ident in range(101, 118):
            weights, edges = root[f"response_{ident}"].to_numpy()
            if (weights.ndim != 1 or len(edges) != len(weights)+1 or
                    not np.isfinite(weights).all() or not np.isfinite(edges).all() or
                    np.any(weights < 0) or weights.sum() <= 0 or np.any(np.diff(edges) <= 0)):
                raise ValueError("Invalid response histogram")
            if (not np.array_equal(edges, np.linspace(edges[0], edges[-1], len(edges))) or
                    not np.array_equal(edges[[0, -1]], edges[[0, -1]].astype(np.float32).astype(np.float64)) or
                    not np.array_equal(weights, weights.astype(np.float32).astype(np.float64))):
                raise ValueError("Histogram does not preserve original uniform REAL bins")
            histograms[ident] = weights, edges
        if histogram_payload_sha256(histograms) != HISTOGRAM_PAYLOAD_SHA256:
            raise ValueError("Histogram axes/bin contents differ from exact original extraction")
    return histograms, meta


def sample_displacement(histogram, rng):
    weights, edges = histogram
    cumulative = np.cumsum(weights, dtype=np.float64)
    index = min(int(np.searchsorted(cumulative, rng.random() * cumulative[-1], side="right")), len(weights)-1)
    return float(_r(edges[index] + rng.random() * (edges[index+1] - edges[index])))


def _table(root, name, types):
    tree = root[name]
    if tree.classname != "TTree":
        raise ValueError(f"{name} must be a native TTree")
    result = {}
    for key, dtype in types.items():
        branch = tree[key]
        leaves = branch.member("fLeaves")
        if len(leaves) != 1 or leaves[0].member("fLen") != 1 or leaves[0].member("fLeafCount") is not None:
            raise ValueError(f"{name}.{key} must be one native scalar leaf")
        value = branch.array(library="np")
        if value.ndim != 1 or value.dtype != np.dtype(dtype):
            raise ValueError(f"Invalid {name}.{key} scalar type; expected {dtype}")
        if len(value) != tree.num_entries or branch.num_entries != tree.num_entries:
            raise ValueError(f"{name}.{key} tree/branch cardinality mismatch")
        result[key] = value
    if len({len(value) for value in result.values()}) != 1:
        raise ValueError(f"Unequal {name} branch lengths")
    return result


def _beam_input(path, events, transport_path, transport_hash):
    with uproot.open(path) as root:
        meta = _metadata(root)
        if (meta.get("transport_sha256") != transport_hash or
                meta.get("transport_path") != str(transport_path) or
                meta.get("role") != "incident_beam_response_input"):
            raise ValueError("Beam ledger must identify the exact transport and incident beam role")
        sources = meta.get("source_sha256")
        if not isinstance(sources, dict) or not sources:
            raise ValueError("Beam ledger requires source_path -> SHA256 provenance")
        for source_path, digest in sources.items():
            if not Path(source_path).is_absolute() or sha256(source_path) != digest:
                raise ValueError("Beam ledger source SHA256 mismatch")
        beam = _table(root, "beam_events", dict(run="int32", event="int32",
                                              source_entry="uint64", energy_GeV="float64"))
        if (not np.array_equal(beam["run"], events["run"]) or
                not np.array_equal(beam["event"], events["event"]) or
                not np.array_equal(beam["source_entry"], np.arange(len(events["run"]), dtype=np.uint64))):
            raise ValueError("Beam ledger must preserve every transport event in source order")
    return beam["energy_GeV"], meta


def _write_table(root, name, types, rows):
    root.mktree(name, types)
    if rows:
        root[name].extend({key: np.array([row[key] for row in rows], dtype=dtype)
                           for key, dtype in types.items()})


def reconstruct(input_root, beam_ledger_root, histogram_root, output, *, acquisition_run, seed):
    """Retain all transport events; None beam means explicitly unavailable.

    Beam ROOT: beam_events(run,event:int32,source_entry:uint64,energy_GeV:float64),
    metadata(role=incident_beam_response_input, transport_path/sha256,
    source_sha256={absolute source path: digest}). No inferred beam mapping.
    """
    if type(seed) is not int or not 0 <= seed < 2**64:
        raise ValueError("seed must be an integer in [0,2**64)")
    code = {str(p): sha256(p) for p in (Path(__file__), MODULE / "cylinder_config.py", MODULE / "digitize.py", MODULE / "central.py", MODULE / "root_output.py")}
    config = read_config(acquisition_run)
    input_root, histogram_root = [Path(p).resolve(strict=True) for p in (input_root, histogram_root)]
    hashes = {str(p): sha256(p) for p in (input_root, histogram_root)}
    transport_hash = hashes[str(input_root)]
    histograms, histogram_metadata = read_histograms(histogram_root)
    with uproot.open(input_root) as root:
        events = _table(root, "events", dict(run="int32", event="int32", aborted="int32"))
        transport_summary = read_transport_summary(root)
    count = len(events["run"])
    if (not isinstance(transport_summary, dict) or
            transport_summary.get("status") != "diagnostic_transport_only" or
            transport_summary.get("output_format") != "ROOT_TTree" or
            any(type(transport_summary.get(k)) is not int for k in ("events", "attempted_events", "aborted")) or
            transport_summary["attempted_events"] != count or
            transport_summary["aborted"] != int(np.sum(events["aborted"])) or
            transport_summary["events"] + transport_summary["aborted"] != count):
        raise ValueError("Transport summary/event conservation mismatch")
    keys = list(zip(events["run"].tolist(), events["event"].tolist()))
    if keys != sorted(set(keys)) or any(r < 0 or e < 0 for r, e in keys):
        raise ValueError("Transport event keys must be unique, ordered and nonnegative")
    previous_run, expected_event = None, 0
    for run, event in keys:
        if run != previous_run:
            expected_event = 0
        if event != expected_event:
            raise ValueError("Transport source events must be complete within each run")
        previous_run, expected_event = run, event + 1
    if not np.isin(events["aborted"], (0, 1)).all():
        raise ValueError("Invalid transport aborted flag")
    beam, beam_metadata = None, None
    if beam_ledger_root is not None:
        beam_ledger_root = Path(beam_ledger_root).resolve(strict=True)
        hashes[str(beam_ledger_root)] = sha256(beam_ledger_root)
        beam, beam_metadata = _beam_input(beam_ledger_root, events, input_root, transport_hash)
        hashes.update(beam_metadata["source_sha256"])
    rng = np.random.Generator(np.random.PCG64(seed))
    rows, clusters, diagnostic = [], [], []
    for entry, (run, event) in enumerate(keys):
        energy, displacement = (math.nan if beam is None else float(beam[entry])), math.nan
        if events["aborted"][entry]:
            response = Response(6)
        elif beam is None:
            response = Response(2)
        else:
            ident = histogram_id(energy)
            if ident in histograms:
                displacement = sample_displacement(histograms[ident], rng)
                response = respond(energy, displacement, config)
            else:
                response = Response(4 if ident is None else 3, -1 if ident is None else ident)
        rows.append(dict(run=run, event=event, source_entry=entry, available=int(response.available),
                         nclusters=int(response.status == 0), status=response.status))
        diagnostic.append(dict(run=run, event=event, source_entry=entry, beam_energy_GeV=energy,
                               displacement_mm=displacement, histogram_id=response.histogram_id,
                               digit=response.digit, position_mm=response.position_mm))
        if response.status == 0:
            clusters.append(dict(run=run, event=event, cluster_index=0, xstrip=response.xstrip,
                                 energy_GeV=response.energy_GeV, multiplicity=1))
    metadata = dict(schema=1, mode=MODE, transport_path=str(input_root), transport_sha256=transport_hash,
                    acquisition_run=acquisition_run, configuration=config, status_codes=STATUS_CODES,
                    histogram_path=str(histogram_root), histogram_sha256=hashes[str(histogram_root)],
                    histogram_metadata=histogram_metadata, beam_metadata=beam_metadata,
                    seed=seed, rng="numpy.PCG64; bin-mass CDF then uniform within bin; independent of HRNDM1",
                    numpy_version=np.__version__, physics_validation=False)
    summary = dict(status="legacy09_simulated_tagger_diagnostic_complete", events=len(rows),
                   available_events=sum(row["available"] for row in rows), clusters=len(clusters),
                   physics_validation=False)
    output = Path(output).resolve()
    output.mkdir(parents=False, exist_ok=False)
    pending = output / "tagger.pending"
    pending.mkdir()
    try:
        result = pending / "tagger.root"
        with uproot.create(result, compression=uproot.ZSTD(5)) as root:
            root["metadata"], root["summary"] = json.dumps(metadata, sort_keys=True), json.dumps(summary, sort_keys=True)
            _write_table(root, "tagger_events", EVENT_TYPES, rows)
            _write_table(root, "tagger_clusters", CLUSTER_TYPES, clusters)
            _write_table(root, "tagger_response_inputs", dict(run="int32", event="int32", source_entry="uint64",
                         beam_energy_GeV="float64", displacement_mm="float64", histogram_id="int32",
                         digit="int32", position_mm="float64"), diagnostic)
        provenance = dict(**metadata, input_sha256=hashes, code_sha256=code, result_sha256=sha256(result), summary=summary)
        _write_provenance(pending / "provenance.root", provenance)
        for path, digest in {**hashes, **code, **config["sources"]}.items():
            if sha256(path) != digest:
                raise RuntimeError(f"Tagger input/source changed during reconstruction: {path}")
        pending.rename(output / "tagger")
    except Exception:
        shutil.rmtree(pending)
        output.rmdir()
        raise
    return output / "tagger/tagger.root"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_root")
    parser.add_argument("histogram_root")
    parser.add_argument("output")
    parser.add_argument("--beam-ledger-root")
    parser.add_argument("--acquisition-run", required=True, type=int)
    parser.add_argument("--seed", required=True, type=int)
    args = parser.parse_args()
    reconstruct(args.input_root, args.beam_ledger_root, args.histogram_root, args.output,
                acquisition_run=args.acquisition_run, seed=args.seed)
