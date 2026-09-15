"""CLI validation for S1 polarization-state mapping."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from contracts import PolarizationContractError, validate_gate0_handoff
from state_mapping import load_state_mapping


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--handoff", type=Path, required=True)
    parser.add_argument("--repository-root", type=Path, default=Path("."))
    args = parser.parse_args(argv)
    root = args.repository_root.resolve()
    try:
        validate_gate0_handoff(args.handoff, root)
        intervals = load_state_mapping(args.config, root)
    except PolarizationContractError as exc:
        print(f"Invalid polarization state mapping: {exc}", file=sys.stderr)
        return 1
    print(f"Valid polarization state mapping: {len(intervals)} intervals")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
