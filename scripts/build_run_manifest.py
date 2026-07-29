#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from graal_common.run_manifest import (
    ManifestError,
    scan_runs,
    validate_manifest,
    write_manifest,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate or validate the GRAAL run manifest."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--input-dir", type=Path)
    mode.add_argument("--validate", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.input_dir is not None and args.output is None:
        parser.error("--output is required with --input-dir")
    if args.validate is not None and args.output is not None:
        parser.error("--output cannot be used with --validate")
    return args


def main() -> int:
    args = parse_args()
    try:
        if args.validate is not None:
            records = validate_manifest(args.validate)
            counts = Counter(record.group for record in records)
            groups = ", ".join(
                f"{group}={counts[group]}" for group in sorted(counts)
            )
            print(f"Valid manifest: {len(records)} runs ({groups})")
            return 0

        records = scan_runs(args.input_dir)
        write_manifest(records, args.output)
        unresolved = sum(
            record.classification_source == "unresolved" for record in records
        )
        print(
            f"Generated {len(records)} runs -> {args.output} "
            f"({unresolved} unresolved)"
        )
        return 0
    except (ManifestError, OSError) as exc:
        print(f"ERROR: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
