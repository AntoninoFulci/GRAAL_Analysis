#!/usr/bin/env python3
"""Launch the installed workflow against this checkout's explicit resources."""
from pathlib import Path
import sys

from graal_workflow.cli import main


if __name__ == "__main__":
    raise SystemExit(main(["--repo-root", str(Path(__file__).resolve().parents[1]), *sys.argv[1:]]))
