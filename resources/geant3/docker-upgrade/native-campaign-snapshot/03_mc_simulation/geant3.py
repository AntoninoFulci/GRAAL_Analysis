"""Digest-pinned historical GEANT3 execution and explicit response-table bridge.

The run command produces legacy hits only. It does not certify a signal
channel, trigger, reconstruction, target assignment or absolute efficiency.
The response command accepts a complete generated identity table and a
selected subset after the same reconstruction/BDT as data.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
import uuid
from pathlib import Path

import numpy as np
from mc_simulation.response import count_response, response_probabilities

IMAGE = "afulci/ubuntu77@sha256:cb810e84914ae1a440663c391b26058c3bb13fff1b41760da6bbc4d1c31a3ca6"
GRAAL = "/home/gmandaglio/graal"


def _identity(path):
    path = Path(path).resolve()
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(chunk)
    return {
        "path": str(path),
        "size": path.stat().st_size,
        "sha256": hasher.hexdigest(),
    }


def docker_command(card, output_dir, geometry, name, context="orbstack"):
    if geometry not in ("old", "new"):
        raise ValueError(
            "geometry must explicitly select old or new cylindrical chambers"
        )
    card = Path(card).resolve()
    output = Path(output_dir).resolve()
    if not card.is_file():
        raise FileNotFoundError(card)
    if any("," in str(p) for p in (card, output)):
        raise ValueError("Docker bind paths cannot contain commas")
    command = [
        "docker",
        "--context",
        context,
        "run",
        "--rm",
        "--name",
        name,
        "--platform",
        "linux/386",
        "--network",
        "none",
        "--read-only",
        "--cpus",
        "1",
        "--memory",
        "1g",
        "--pids-limit",
        "256",
        "--tmpfs",
        "/tmp:rw,size=256m",
        "--workdir",
        "/tmp",
        "--mount",
        f"type=bind,src={card},dst={GRAAL}/data/inp_laggen/laggen_xs.dat,readonly",
    ]
    for directory in ("out_evgen", "out_laggen"):
        command += [
            "--mount",
            f"type=bind,src={output / directory},dst={GRAAL}/data/{directory}",
        ]
    for key, value in {
        "CERN_ROOT": f"{GRAAL}/2004",
        "LAGGEN": f"{GRAAL}/software/prog/laggen/",
        "INP_LAGGEN": f"{GRAAL}/data/inp_laggen/",
        "OUT_LAGGEN": f"{GRAAL}/data/out_laggen/",
        "KILL_LAGGEN": "/tmp/stop_requested",
        "BEAM": f"{GRAAL}/data/simul_beam/",
        "TAG_DAT": f"{GRAAL}/data/simul_beam/",
    }.items():
        command += ["--env", f"{key}={value}"]
    executable = (
        f"{GRAAL}/software/prog/laggen/laggen_{'oc' if geometry == 'old' else 'nc'}"
    )
    return command + ["--entrypoint", executable, IMAGE, "sample", "xs"]


def run_geant3(card, output_dir, geometry, *, timeout=120, context="orbstack"):
    if not np.isfinite(timeout) or timeout <= 0:
        raise ValueError("timeout must be positive")
    output = Path(output_dir).resolve()
    name = f"graal-cross-section-{uuid.uuid4().hex[:12]}"
    # Validate command/card before creating any output.
    command = docker_command(card, output, geometry, name, context)
    output.mkdir(parents=True, exist_ok=False)
    for directory in ("out_evgen", "out_laggen"):
        (output / directory).mkdir()
    status = {
        "image": IMAGE,
        "platform": "linux/386",
        "geometry": geometry,
        "card": _identity(card),
        "command": command,
        "scope": "legacy generated hits only; not a detector efficiency",
        "status": "started",
    }
    exit_code = 1
    try:
        with (output / "simulation.log").open("w") as log:
            try:
                completed = subprocess.run(
                    command,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    timeout=timeout,
                    check=False,
                )
                exit_code = completed.returncode
                hit = output / "out_laggen/sample.hit"
                log.flush()
                transcript = (output / "simulation.log").read_text()
                truth = output / "out_evgen/outev.dat"
                normal_end = (
                    "Time of CPU Used =" in transcript
                    and truth.is_file()
                    and truth.read_text().split()[-1:] == ["-1"]
                )
                status["status"] = (
                    "completed"
                    if exit_code == 0 and normal_end and hit.is_file()
                    else "failed"
                )
            except subprocess.TimeoutExpired:
                status["status"] = "timeout"
                subprocess.run(
                    ["docker", "--context", context, "rm", "-f", name],
                    capture_output=True,
                    check=False,
                    timeout=20,
                )
    except OSError as error:
        status.update(status="failed", error=str(error))
    finally:
        status["exit_code"] = exit_code
        status["outputs"] = [_identity(p) for p in output.rglob("*") if p.is_file()]
        (output / "run.json").write_text(
            json.dumps(status, indent=2, allow_nan=False) + "\n"
        )
    if status["status"] != "completed":
        raise RuntimeError(
            f"GEANT3 {status['status']}; inspect {output}/simulation.log"
        )
    return status


def _event_table(path):
    with Path(path).open(newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != ["event_id", "cell"]:
            raise ValueError("MC table requires exactly event_id,cell columns")
        rows = []
        for row in reader:
            if set(row) != {"event_id", "cell"} or any(v is None for v in row.values()):
                raise ValueError("malformed MC event row")
            rows.append((int(row["event_id"]), int(row["cell"])))
    return np.asarray(rows, dtype=np.int64).reshape(-1, 2)


def prepare_response(generated_path, selected_path, metadata_path, output_path):
    metadata = json.loads(Path(metadata_path).read_text())
    if metadata.get("schema_version") != 1:
        raise ValueError("response metadata requires schema_version=1")
    grid = metadata["grid"]
    edges = [grid["energy_edges_gev"], grid["phi_edges_rad"]]
    if grid.get("mass_edges_gev") is not None:
        edges.append(grid["mass_edges_gev"])
    for edge in edges:
        if len(edge) < 2 or not np.all(np.isfinite(edge)) or np.any(np.diff(edge) <= 0):
            raise ValueError("invalid response grid")
    n_bins = int(np.prod([len(e) - 1 for e in edges]))
    provenance = metadata["provenance"]
    if (
        provenance.get("independent_of_training") is not True
        or provenance.get("generated_complete") is not True
    ):
        raise ValueError(
            "MC must be independent of training with complete generated denominator"
        )
    if not metadata.get("selection_signature"):
        raise ValueError("response selection signature missing")
    generated, selected = _event_table(generated_path), _event_table(selected_path)
    n, counts = count_response(
        generated[:, 0], generated[:, 1], selected[:, 0], selected[:, 1], n_bins
    )
    response_probabilities(n, counts)
    identities = [_identity(p) for p in (generated_path, selected_path, metadata_path)]
    result = dict(
        metadata,
        generated=n.tolist(),
        selected=counts.tolist(),
        sample_id=identities[0]["sha256"],
        input_identities=identities,
    )
    serialized = json.dumps(result, indent=2, allow_nan=False) + "\n"
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x") as stream:
        stream.write(serialized)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="run supplied card; legacy hits only")
    run.add_argument("--card", required=True, type=Path)
    run.add_argument("--output-dir", required=True, type=Path)
    run.add_argument("--geometry", required=True, choices=("old", "new"))
    run.add_argument("--timeout", type=float, default=120)
    run.add_argument("--context", default="orbstack")
    response = sub.add_parser(
        "response", help="count response from matched, binned event tables"
    )
    for name in ("generated", "selected", "metadata", "output"):
        response.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "run":
        result = run_geant3(
            args.card,
            args.output_dir,
            args.geometry,
            timeout=args.timeout,
            context=args.context,
        )
        print(result["status"])
    else:
        prepare_response(args.generated, args.selected, args.metadata, args.output)
        print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
