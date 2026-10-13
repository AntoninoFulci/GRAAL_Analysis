"""Filesystem publication helpers shared by pipeline stages."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import shutil
import tempfile
from typing import Iterator


@contextmanager
def atomic_output_directory(destination: Path, *, overwrite: bool = True) -> Iterator[Path]:
    """Build beside the destination and publish atomically.

    With overwrite=False, reserve the destination exclusively before building.
    Competing writers using this mode cannot replace each other's results.
    """
    destination = Path(destination)
    if destination.exists() and not destination.is_dir():
        raise NotADirectoryError(f"destination is not a directory: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not overwrite:
        destination.mkdir()  # Atomic reservation; fails even for an existing empty directory.
    staging = Path(
        tempfile.mkdtemp(prefix=f".{destination.name}.", dir=destination.parent)
    )
    backup: Path | None = None
    try:
        yield staging
        if overwrite and destination.exists():
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
        if not overwrite:
            try:
                destination.rmdir()  # Never remove files deposited by another writer.
            except OSError:
                pass
        raise
    if backup is not None:
        try:
            shutil.rmtree(backup)
        except OSError:
            pass
