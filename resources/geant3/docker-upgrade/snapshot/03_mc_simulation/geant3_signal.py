"""Reproducible phase-space channel38 detector pilot in the pinned GEANT3 image.

This restricted pilot uses proton period21/old chambers and provisional 12cm hydrogen.
It produces PREAN .pol; a response still requires conversion and data selections.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import uuid
from pathlib import Path

import numpy as np
from mc_simulation.geant3 import IMAGE, _identity

RESOURCES = Path(__file__).resolve().parents[1] / "resources/geant3"


def signal_card(events=100, energy=1.2, seed=231021, energy_range=None):
    if not isinstance(events, int) or not 1 <= events < 2**24:
        raise ValueError("events must be in [1,2**24)")
    threshold = ((0.93821 + 0.54745 + 0.13496) ** 2 - 0.93821**2) / (2 * 0.93821)
    if not np.isfinite(energy) or not threshold < energy <= 1.4875:
        raise ValueError("energy must exceed eta pi0 threshold and be <=1.4875 GeV")
    if not isinstance(seed, int) or not 0 < seed < 2**30 or seed % 2 == 0:
        raise ValueError("seed must be a positive odd integer below 2**30")
    if energy_range is not None:
        bounds = np.asarray(energy_range, dtype=float)
        if (
            bounds.shape != (2,)
            or not np.isfinite(bounds).all()
            or not 0.94 < bounds[0] < bounds[1] <= 1.4875
        ):
            raise ValueError("energy_range must satisfy 0.94 < low < high <= 1.4875")
        energy = float(bounds.mean())
    card = (RESOURCES / "signal_smoke.dat").read_text()
    card = re.sub(r"^TRIG .*", f"TRIG {events}", card, flags=re.MULTILINE)
    card = re.sub(r"^ENER .*", f"ENER {energy:.9g}", card, flags=re.MULTILINE)
    if energy_range is not None:
        card = card.replace("PROC 38", f"EWIN {bounds[0]:.9g} {bounds[1]:.9g}\nPROC 38")
    card = re.sub(r"^RNDM .*", f"RNDM {seed} {seed + 2}", card, flags=re.MULTILINE)
    return card.replace("RUNG 1 1", "RUNG 3629 1").replace(
        "TIME 2=600.", "TIME 2=7200."
    )


def read_truth(path, expected_events=None):
    lines = Path(path).read_text().splitlines()
    if not lines or lines[-1].strip() != "-1":
        raise ValueError("incomplete generated truth: missing normal terminator")
    data = np.loadtxt(lines[:-1], ndmin=2)
    if data.ndim != 2 or data.shape[1] != 20 or not np.isfinite(data).all():
        raise ValueError("malformed signal truth")
    if expected_events is not None and len(data) != expected_events:
        raise ValueError("generated event count differs from requested count")
    if not np.all(data[:, :4] == data[:, :4].astype(np.int64)):
        raise ValueError("nonintegral event identity")
    if not np.all(data[:, 0] == 3629) or not np.all(data[:, 2:4] == [38, 3]):
        raise ValueError("wrong run, channel or particle count")
    if not np.array_equal(data[:, 1], np.arange(1, len(data) + 1)):
        raise ValueError("generated event IDs must be complete, unique and sequential")
    p4 = data[:, 8:].reshape(-1, 3, 4)
    expected = np.zeros((len(data), 4))
    expected[:, 2] = data[:, 4]
    expected[:, 3] = data[:, 4] + 0.93821
    residual = p4.sum(axis=1) - expected
    masses2 = p4[:, :, 3] ** 2 - np.sum(p4[:, :, :3] ** 2, axis=2)
    if np.max(np.abs(residual)) > 1e-5:
        raise ValueError("generated four-momentum is not conserved")
    if not np.allclose(masses2, np.square([0.54745, 0.13496, 0.93821]), atol=2e-6):
        raise ValueError("wrong generated masses")
    if np.any(np.abs(data[:, 7]) > 6.00001):
        raise ValueError("vertex outside explicit 12cm target")
    return data


def read_decay_truth(path, truth):
    """Validate prompt gg daughters and recover rest-frame angular diagnostics."""
    lines = Path(path).read_text().splitlines()
    if not lines or lines[-1].strip() != "-1":
        raise ValueError("incomplete generated decays")
    data = np.loadtxt(lines[:-1], ndmin=2)
    if data.shape != (2 * len(truth), 11) or not np.isfinite(data).all():
        raise ValueError("malformed generated decays")
    expected = np.column_stack(
        (
            np.repeat(truth[:, 0], 2),
            np.repeat(truth[:, 1], 2),
            np.tile([1, 2], len(truth)),
        )
    )
    if not np.array_equal(data[:, :3], expected):
        raise ValueError("decay identities differ from complete mother truth")
    photons = data[:, 3:].reshape(-1, 2, 4)
    mothers = truth[:, 8:].reshape(-1, 3, 4)[:, :2].reshape(-1, 4)
    if np.max(np.abs(photons.sum(axis=1) - mothers)) > 1e-5:
        raise ValueError("decay four-momentum is not conserved")
    mass2 = photons[:, :, 3] ** 2 - (photons[:, :, :3] ** 2).sum(axis=2)
    if np.any(photons[:, :, 3] <= 0) or np.max(np.abs(mass2)) > 2e-6:
        raise ValueError("decay daughters are not positive-energy photons")
    # Inverse boost first daughter to each meson's rest frame.
    mass = np.sqrt(mothers[:, 3] ** 2 - (mothers[:, :3] ** 2).sum(axis=1))
    gamma = mothers[:, 3] / mass
    beta = mothers[:, :3] / mothers[:, 3, None]
    dot = (beta * photons[:, 0, :3]).sum(axis=1)
    coefficient = gamma**2 / (gamma + 1) * dot - gamma * photons[:, 0, 3]
    rest = photons[:, 0, :3] + coefficient[:, None] * beta
    cosine = rest[:, 2] / np.linalg.norm(rest, axis=1)
    phi = np.arctan2(rest[:, 1], rest[:, 0])
    return {
        "decays": len(data),
        "max_four_momentum_residual_gev": float(
            np.max(np.abs(photons.sum(axis=1) - mothers))
        ),
        "max_photon_mass_squared_gev2": float(np.max(np.abs(mass2))),
        "rest_frame_cosine_mean": float(cosine.mean()),
        "rest_frame_cosine_second_moment": float(np.mean(cosine**2)),
        "rest_frame_sin_phi_mean": float(np.sin(phi).mean()),
        "rest_frame_cos_phi_mean": float(np.cos(phi).mean()),
    }


def run_signal(
    build_dir,
    output_dir,
    *,
    events=100,
    energy=1.2,
    seed=231021,
    energy_range=None,
    timeout=1800,
    context="orbstack",
):
    card = signal_card(events, energy, seed, energy_range)
    if not np.isfinite(timeout) or timeout <= 0:
        raise ValueError("timeout must be positive")
    build = Path(build_dir).resolve()
    binaries = [build / name / name for name in ("laggen", "lagdig", "prean")]
    binaries.append(build / "laggen/transport_probe")
    identities = [_identity(p) for p in binaries]
    output = Path(output_dir).resolve()
    if any("," in str(p) for p in (build, output, RESOURCES)):
        raise ValueError("Docker bind paths cannot contain commas")
    output.mkdir(parents=True, exist_ok=False)
    snapshot = output / "resource_snapshot"
    shutil.copytree(RESOURCES, snapshot)
    (output / "laggen_signal.dat").write_text(card)
    name = "graal-signal-" + uuid.uuid4().hex[:12]
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
        "2",
        "--memory",
        "2g",
        "--pids-limit",
        "256",
        "--tmpfs",
        "/tmp:rw,size=256m",
        "--env",
        f"GRAAL_DIG_SEED={seed + 4}",
    ]
    for src, dest, ro in (
        (snapshot, "/resources", True),
        (build, "/build", True),
        (output, "/work", False),
    ):
        command += [
            "--mount",
            f"type=bind,src={src},dst={dest}" + (",readonly" if ro else ""),
        ]
    command += ["--entrypoint", "/bin/sh", IMAGE, "/resources/run_signal_chain.sh"]
    status = {
        "schema_version": 1,
        "status": "started",
        "image": IMAGE,
        "command": command,
        "binaries": identities,
        "resource_snapshot": [
            _identity(p) for p in sorted(snapshot.rglob("*")) if p.is_file()
        ],
        "events_requested": events,
        "energy_gev": energy if energy_range is None else None,
        "energy_range_gev": list(energy_range) if energy_range is not None else None,
        "seeds": {"geant": [seed, seed + 2], "genbod": seed, "digitizer": seed + 4},
        "model": "unweighted Lorentz-invariant three-body phase space",
        "channel": 38,
        "transport_validated": False,
        "target_length_cm": 12,
        "geometry": "old",
        "period": 21,
        "source_period": "2002_uv1",
        "representative_run": 3629,
        "configuration": _identity(snapshot / "proton_periods_provisional.json"),
        "decay_transport": "explicit isotropic prompt gg daughters as GEANT primaries",
        "branching_convention": "forced eta->gg and pi0->gg; BR excluded from efficiency",
        "limitations": [
            "legacy meson-decay path bypassed with prompt photon primaries; shower validation ongoing",
            "provisional period21 old-cylinder geometry and BGO-only trigger",
            "legacy generator masses retained",
            "conversion and current data selections required",
        ],
    }
    try:
        with (output / "chain.log").open("w") as log:
            proc = subprocess.run(
                command,
                stdout=log,
                stderr=subprocess.STDOUT,
                timeout=timeout,
                check=False,
            )
        status["exit_code"] = proc.returncode
        if proc.returncode != 0:
            probe = output / "transport_probe.log"
            if probe.exists() and "TRANSPORT PROBE PASS" not in probe.read_text():
                raise RuntimeError(
                    "GEANT3 transport invariant failed in execution environment; "
                    "see transport_probe.log"
                )
            raise RuntimeError("signal detector chain failed")
        truth = read_truth(output / "generated_signal.dat", events)
        if energy_range is None:
            if not np.allclose(truth[:, 4], energy, rtol=0, atol=2e-7):
                raise ValueError("generated energy differs from requested energy")
        elif np.any((truth[:, 4] < energy_range[0]) | (truth[:, 4] > energy_range[1])):
            raise ValueError("generated energy outside requested energy_range")
        status["decay_validation"] = read_decay_truth(
            output / "generated_decays.dat", truth
        )
        digitization = (output / "lagdig.log").read_text()
        if "data21.base" not in digitization or "calib_3700.cal" not in digitization:
            raise ValueError("digitizer proton period/base mismatch")

        def count(label):
            match = re.search(re.escape(label) + r"\s*=\s*(\d+)", digitization)
            if not match:
                raise ValueError(f"missing digitizer count: {label}")
            return int(match.group(1))

        counts = {
            "generated": len(truth),
            "tag_rejected": count("Events rejected by Tagging Condition"),
            "trigger_rejected": count("Events rejected by Trigger Condition"),
            "digitized": count("Events collected"),
        }
        hit_match = re.search(r"NUMBER OF EVENTS\s*:\s*(\d+)", digitization)
        if not hit_match:
            raise ValueError("missing hit-ntuple input count")
        counts["hit_written"] = int(hit_match.group(1))
        counts["lost_before_digitizer"] = events - counts["hit_written"]
        if (
            counts["lost_before_digitizer"] < 0
            or sum(counts[k] for k in ("tag_rejected", "trigger_rejected", "digitized"))
            != counts["hit_written"]
        ):
            raise ValueError("inconsistent complete-denominator loss accounting")
        prean = (output / "prean.log").read_text()
        if (
            "OLD_CYL" not in prean
            or "GRAAL_21" not in prean
            or "calib_3700.cal" not in prean
            or "Normal Termination" not in prean
        ):
            raise ValueError("PREAN geometry or completion mismatch")
        prean_count = re.search(r"Number of events in NTUPLE:\s*(\d+)", prean)
        if not prean_count or int(prean_count.group(1)) != counts["digitized"]:
            raise ValueError("PREAN input count differs from digitizer output")
        counts["prean_input"] = int(prean_count.group(1))
        pol = output / "out_prean/signal.pol"
        if not pol.is_file() or pol.stat().st_size < 100:
            raise ValueError("PREAN output absent")
        status.update(status="detector_chain_complete_unvalidated", counts=counts)
    except subprocess.TimeoutExpired:
        status["status"] = "timeout"
        subprocess.run(
            ["docker", "--context", context, "rm", "-f", name],
            capture_output=True,
            timeout=30,
            check=False,
        )
        raise
    except Exception as exc:
        status.update(status="failed", error=str(exc))
        raise
    finally:
        status["outputs"] = [
            _identity(p)
            for p in output.rglob("*")
            if p.is_file() and p.name != "run.json"
        ]
        (output / "run.json").write_text(json.dumps(status, indent=2) + "\n")
    return status


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--events", type=int, default=100)
    parser.add_argument("--energy", type=float, default=1.2)
    parser.add_argument("--seed", type=int, default=231021)
    parser.add_argument("--energy-range", type=float, nargs=2, metavar=("LOW", "HIGH"))
    parser.add_argument("--timeout", type=float, default=1800)
    args = parser.parse_args(argv)
    print(
        json.dumps(
            run_signal(
                args.build_dir,
                args.output_dir,
                events=args.events,
                energy=args.energy,
                seed=args.seed,
                energy_range=args.energy_range,
                timeout=args.timeout,
            )["counts"]
        )
    )


if __name__ == "__main__":
    main()
