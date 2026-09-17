"""Filesystem publication helpers shared by pipeline stages."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import shutil
import tempfile
from typing import Iterator


@contextmanager
def atomic_output_directory(destination: Path) -> Iterator[Path]:
    """Build a directory beside its destination, then publish it atomically."""
    destination = Path(destination)
    if destination.exists() and not destination.is_dir():
        raise NotADirectoryError(f"destination is not a directory: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(prefix=f".{destination.name}.", dir=destination.parent)
    )
    backup: Path | None = None
    try:
        yield staging
        if destination.exists():
            backup = Path(
                tempfile.mkdtemp(
                    prefix=f".{destination.name}.previous.",
                    dir=destination.parent,
                )
            )
            backup.rmdir()
            destination.replace(backup)
        try:
            staging.replace(destination)
        except BaseException:
            if backup is not None and backup.exists() and not destination.exists():
                backup.replace(destination)
            raise
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    if backup is not None:
        try:
            shutil.rmtree(backup)
        except OSError:
            pass
