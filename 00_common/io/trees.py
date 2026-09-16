"""What the preselected detector files call their tree.

Two vintages of selected/ exist and differ only in this name: the selection
writes h85, and a selected/ produced before it started renaming the tree still
carries the h80 it inherited from the pre-analysis. Both are on disk in
practice, which is why nothing should hard-code either one.

Kept here rather than in the reconstruction because the reconstruction is not
the only reader: the beam-spectrum measurement opens the same files through
uproot, and cannot import a list that lives next to `import ROOT`. A second copy
of these two names is a second thing to forget to update.

Takes the names a caller already read (`probe.GetListOfKeys()` in ROOT,
`file.keys()` in uproot) and returns one. It opens nothing itself, which is what
keeps it usable from both.
"""
from __future__ import annotations

# Preselection tree names, best first. AUTO walks this list.
KNOWN_INPUT_TREES: tuple[str, ...] = ("h85", "h80")

AUTO = "auto"


def resolve(available: list[str], requested: str = AUTO, where: str = "the file") -> str:
    """Which tree to read, given the names a file actually contains.

    A named tree must be present. AUTO takes the first known preselection tree
    that is there, so callers do not have to know which vintage of the selection
    they are holding.
    """
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
