"""Reconstruction selection provenance shared by downstream readers."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


KEY = "reconstruction_provenance"


def file_identities(paths):
    """Hash input bytes, keeping canonical paths and sizes for reproducibility."""
    identities = []
    for path in sorted(map(Path, paths)):
        with path.open("rb") as stream:
            hasher = hashlib.sha256()
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                hasher.update(chunk)
            digest = hasher.hexdigest()
        identities.append({"path": str(path.resolve()), "size": path.stat().st_size,
                           "sha256": digest})
    return identities


def validate_no_fit(source, tree) -> dict:
    """Reject historical raw branches whose event selection may include 6C."""
    record = source.Get(KEY)
    if not record:
        raise ValueError("no-fit baseline requires reconstruction provenance; rebuild from selected h85/h80")
    try:
        metadata = json.loads(record.GetTitle())
    except (TypeError, ValueError) as error:
        raise ValueError("invalid reconstruction provenance") from error
    if not isinstance(metadata, dict) or metadata.get("do_fit") is not False:
        raise ValueError("no-fit baseline requires provenance do_fit=false")
    if any("fit" in branch.GetName() for branch in tree.GetListOfBranches()):
        raise ValueError("no-fit baseline cannot reuse historical fit-selected raw branches")
    return metadata
