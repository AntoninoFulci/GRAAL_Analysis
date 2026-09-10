#!/usr/bin/env python3
"""Validate S6 Sigma table, covariance matrices, QA, and provenance."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from contracts import PolarizationContractError
from release import validate_sigma_release


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--check-covariance", action="store_true")
    parser.add_argument("--check-qa", action="store_true")
    args = parser.parse_args(argv)
    if not args.check_covariance or not args.check_qa:
        print(
            "Invalid Sigma release: --check-covariance and --check-qa are required",
            file=sys.stderr,
        )
        return 2
    try:
        release = validate_sigma_release(args.results, args.repository_root)
    except PolarizationContractError as exc:
        print(f"Invalid Sigma release: {exc}", file=sys.stderr)
        return 1
    print(f"Valid Sigma release: {len(release.bin_keys)} bins")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
