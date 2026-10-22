"""Extract cross sections from explicit detector/target calibration contracts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from observable_extraction.io.cross_section import prepare_analysis, write_result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output-dir", type=Path)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument(
        "--observations-only",
        action="store_true",
        help="report counts and observation signatures before target/response/background calibration",
    )
    modes.add_argument(
        "--audit-only",
        action="store_true",
        help="validate and report without publishing ROOT/PDF",
    )
    args = parser.parse_args(argv)
    if not (args.audit_only or args.observations_only) and args.output_dir is None:
        parser.error(
            "--output-dir is required unless --audit-only or --observations-only"
        )
    result = prepare_analysis(args.config, observations_only=args.observations_only)
    if args.audit_only or args.observations_only:
        print(json.dumps(result["audit"], indent=2, allow_nan=False))
    else:
        write_result(result, args.output_dir)
        print(
            f"Wrote conditional cross sections to {args.output_dir}; see provenance for missing uncertainties."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
