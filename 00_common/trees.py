"""Resolve preselection tree names for ROOT and uproot readers."""
from __future__ import annotations

# Keep the current name first, with the legacy name as fallback.
KNOWN_INPUT_TREES: tuple[str, ...] = ("h85", "h80")

AUTO = "auto"


def resolve(available: list[str], requested: str = AUTO, where: str = "the file") -> str:
    """Resolve the requested tree from the available names."""
    if requested != AUTO:
        if requested not in available:
            raise RuntimeError(
                f"tree '{requested}' not found in {where}; found: {available}"
            )
        return requested

    for candidate in KNOWN_INPUT_TREES:
        if candidate in available:
            return candidate

    raise RuntimeError(
        f"no preselection tree in {where}: expected one of "
        f"{list(KNOWN_INPUT_TREES)}, found: {available}. If this is a pre-analysis "
        f"file rather than a selected one, run event_selector.select_events first."
    )
