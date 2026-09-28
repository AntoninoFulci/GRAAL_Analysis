from __future__ import annotations

import argparse
from collections.abc import Sequence


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="GRAAL pipeline orchestrator")
    parser.add_argument("--config", help="Path to pipeline TOML configuration")
    parser.add_argument("--profile", default="production", help="Configuration profile")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    build_parser().parse_args(argv)
    return 0
