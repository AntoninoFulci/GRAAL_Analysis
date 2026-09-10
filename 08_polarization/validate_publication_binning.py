#!/usr/bin/env python3
"""Validate P1/P2 mappings from released elementary Sigma bins."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from contracts import PolarizationContractError
from release import validate_publication_mapping, validate_sigma_release


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--mapping-dir", type=Path, required=True)
    parser.add_argument("--papers", nargs="+", choices=("P1", "P2"), required=True)
    args = parser.parse_args(argv)
    try:
        release = validate_sigma_release(args.results, args.repository_root)
        for paper in args.papers:
            path = args.mapping_dir / f"{paper.lower()}_binning.json"
            validate_publication_mapping(path, paper, release)
    except PolarizationContractError as exc:
        print(f"Invalid publication binning: {exc}", file=sys.stderr)
        return 1
    print("Valid publication binning: " + ", ".join(args.papers))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
