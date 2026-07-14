#!/usr/bin/env python3
"""Report which Monte Carlo channels exist on disk and how old they are.

Regenerating six channels takes hours, so the pipeline reuses whatever is
already there. This module is what it asks. It is Python rather than shell
because `stat` takes different flags on macOS and Linux.

CLI:
    python -m mc_simulation.mc_status --data-dir 04_mc_simulation/data

Exit 0 = every channel is present (the pipeline may skip generation).
Exit 1 = at least one is missing (the pipeline must generate).
Exit 2 = internal error (e.g. this module failed to import its dependencies,
         or crashed for any other reason). The caller MUST NOT treat this the
         same as exit 1: doing so once made a bare `python` interpreter that
         could not import the package look like "MC missing" and triggered a
         multi-hour regeneration of six channels that were sitting on disk
         the whole time.
Staleness never changes the exit code: it warns, it does not block.
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

CHANNELS = ["eta_pi0", "pi0pi0", "3pi0", "eta_2pi0", "omega_pi0", "etaprime"]

STALE_DAYS = 10

DEFAULT_DATA_DIR = Path(__file__).parent / "data"


@dataclass
class ChannelStatus:
    name: str
    path: Path
    exists: bool
    mtime: datetime | None
    age_days: float | None


def status(data_dir: Path, now: datetime | None = None) -> list[ChannelStatus]:
    """One ChannelStatus per channel, in CHANNELS order."""
    data_dir = Path(data_dir)
    now = now or datetime.now()

    out = []
    for name in CHANNELS:
        path = data_dir / f"{name}_mc.root"
        if path.exists():
            mtime = datetime.fromtimestamp(path.stat().st_mtime)
            age = (now - mtime).total_seconds() / 86400.0
            out.append(ChannelStatus(name, path, True, mtime, age))
        else:
            out.append(ChannelStatus(name, path, False, None, None))
    return out


def all_present(statuses: list[ChannelStatus]) -> bool:
    return all(s.exists for s in statuses)


def stale(
    statuses: list[ChannelStatus], stale_days: float = STALE_DAYS
) -> list[ChannelStatus]:
    return [s for s in statuses if s.exists and s.age_days > stale_days]


def report(statuses: list[ChannelStatus]) -> None:
    """Print the table, then the outcome, then any staleness warning."""
    for s in statuses:
        if not s.exists:
            print(f"  {s.path.name:<20} ASSENTE")
        else:
            flag = "STALE" if s.age_days > STALE_DAYS else "OK"
            stamp = s.mtime.strftime("%Y-%m-%d %H:%M")
            print(f"  {s.path.name:<20} {stamp}  {s.age_days:5.1f}g   {flag}")

    n_present = sum(s.exists for s in statuses)
    total = len(statuses)

    if n_present == total:
        print(f"  -> {n_present}/{total} presenti: generazione SALTATA "
              "(--force-mc per rigenerare)")
    else:
        missing = [s.name for s in statuses if not s.exists]
        print(f"  -> {n_present}/{total} presenti, mancano: {', '.join(missing)}")

    for s in stale(statuses):
        print(f"  !! WARNING: {s.path.name} ha {s.age_days:.0f} giorni "
              f"(soglia {STALE_DAYS}g) — proseguo comunque")


def main(argv: list[str] | None = None) -> int:
    try:
        p = argparse.ArgumentParser(description="Check the Monte Carlo files on disk")
        p.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
        args = p.parse_args(argv)

        statuses = status(args.data_dir)
        report(statuses)

        return 0 if all_present(statuses) else 1
    except SystemExit:
        # argparse's own --help/bad-argument exits: pass through unchanged.
        raise
    except Exception as exc:  # noqa: BLE001 - this is the top-level error boundary
        print(f"ERROR: mc_status failed internally: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
