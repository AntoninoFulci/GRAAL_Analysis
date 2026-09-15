"""CLI validation for S2 period-dependent Compton polarization."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from compton import load_period_curves
from contracts import PolarizationContractError


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--repository-root", type=Path, default=Path("."))
    args = parser.parse_args(argv)
    try:
        curves = load_period_curves(args.config, args.repository_root.resolve())
    except PolarizationContractError as exc:
        print(f"Invalid Compton polarization: {exc}", file=sys.stderr)
        return 1
    print(f"Valid Compton polarization: {len(curves)} periods")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
