"""Shared grammar for immutable S4 fit release directory names."""

from __future__ import annotations

import re


FIT_RELEASE_ID_GRAMMAR = r"[A-Za-z0-9][A-Za-z0-9._-]*"
FIT_RELEASE_ID_PATTERN = re.compile(rf"{FIT_RELEASE_ID_GRAMMAR}\Z")
_OWNED_STAGING_PATTERN = re.compile(
    rf"\.({FIT_RELEASE_ID_GRAMMAR})\.staging-[a-z0-9_]{{8}}\Z"
)


def validate_fit_release_id(value: object) -> str:
    """Return one portable ASCII release component or raise ``ValueError``.

    Leading dots are reserved for publisher-owned staging directories.  This
    deliberately rejects ``.fit-v1`` as well as whitespace and path syntax.
    """
    if (
        not isinstance(value, str)
        or FIT_RELEASE_ID_PATTERN.fullmatch(value) is None
    ):
        raise ValueError(
            "S4 fit release ID must match [A-Za-z0-9][A-Za-z0-9._-]*"
        )
    return value


def is_owned_fit_staging_name(value: str) -> bool:
    """Recognize only names emitted by ``tempfile.mkdtemp`` for valid IDs."""
    return _OWNED_STAGING_PATTERN.fullmatch(value) is not None
