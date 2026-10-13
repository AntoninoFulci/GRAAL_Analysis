"""Lossless raw-track diagnostics; these fields do not define a physics cut.

Array positions remain in the original h70 order. Index_trf is stored verbatim,
including zero and unknown codes. Never use it as a reconstructed-particle index.
"""
from array import array

SCALARS = {"Nass_3": ("i", "I"), "Nparf": ("i", "I"),
           "N_traf": ("i", "I"), "Nparf_strange": ("B", "b"),
           "RawSourceEntry": ("q", "L")}
VECTORS = {"Itipo_track": "int", "Index_trf": "unsigned char",
           "Iass_trf": "unsigned char"}
BRANCHES = (*SCALARS, *VECTORS, "RawSourceFile")


def has_raw_tracks(tree, where="tree"):
    """All absent means legacy; a partial group cannot be interpreted safely."""
    present = {n for n in BRANCHES if tree.GetBranch(n)}
    if present and len(present) != len(BRANCHES):
        raise ValueError(f"{where}: partial raw-track metadata; missing {sorted(set(BRANCHES) - present)}")
    if present:
        for name, (code, _) in SCALARS.items():
            branch = tree.GetBranch(name)
            leaf = branch.GetLeaf(name)
            expected = {"i": "Int_t", "B": "UChar_t", "q": "Long64_t"}[code]
            if (not leaf or branch.GetListOfLeaves().GetEntries() != 1
                    or leaf.GetTypeName() != expected or leaf.GetLeafCount()
                    or leaf.GetLenStatic() != 1):
                raise ValueError(f"{where}: incompatible raw-track scalar {name}; expected {expected}")
        for name, expected in {**{n: f"vector<{kind}>" for n, kind in VECTORS.items()},
                               "RawSourceFile": "string"}.items():
            actual = tree.GetBranch(name).GetClassName().replace("std::", "").replace(" ", "")
            if actual != expected.replace(" ", ""):
                raise ValueError(f"{where}: incompatible raw-track branch {name}; expected {expected}")
    return bool(present)


def _integer(value):
    # PyROOT exposes UChar_t leaves as a one-character string on some versions.
    return ord(value) if isinstance(value, (str, bytes)) else int(value)


def snapshot_raw_tracks(tree):
    """Detach data from ROOT's mutable entry buffers before batching events."""
    values = {n: _integer(getattr(tree, n)) for n in SCALARS}
    values.update({n: tuple(_integer(v) for v in getattr(tree, n)) for n in VECTORS})
    values["RawSourceFile"] = str(tree.RawSourceFile)
    for count, branch, capacity in (("Nass_3", "Itipo_track", 291),
                                     ("Nparf", "Index_trf", 90),
                                     ("N_traf", "Iass_trf", 90)):
        if not 0 <= values[count] <= capacity or len(values[branch]) != values[count]:
            raise ValueError(f"raw-track metadata: {branch} length/count mismatch or invalid {count}")
    if not 0 <= values["Nparf_strange"] <= 255:
        raise ValueError("raw-track metadata: Nparf_strange outside UChar_t range")
    for name in ("Index_trf", "Iass_trf"):
        if any(not 0 <= v <= 255 for v in values[name]):
            raise ValueError(f"raw-track metadata: {name} outside UChar_t range")
    if values["RawSourceEntry"] < 0 or not values["RawSourceFile"]:
        raise ValueError("raw-track metadata: missing raw source identity")
    return values


class RawTrackWriter:
    """ROOT output buffers owned by the IO adapter, not the reconstruction model."""

    def __init__(self, tree):
        import ROOT

        self.scalars = {n: array(code, [0]) for n, (code, _) in SCALARS.items()}
        self.vectors = {n: ROOT.std.vector(kind)() for n, kind in VECTORS.items()}
        self.source = ROOT.std.string()
        for n, value in self.scalars.items():
            tree.Branch(n, value, f"{n}/{SCALARS[n][1]}")
        for n, value in self.vectors.items():
            tree.Branch(n, value)
        tree.Branch("RawSourceFile", self.source)

    def assign(self, values):
        for n, buffer in self.scalars.items():
            buffer[0] = values[n]
        for n, buffer in self.vectors.items():
            buffer.clear()
            for value in values[n]:
                buffer.push_back(value)
        self.source.assign(values["RawSourceFile"])
