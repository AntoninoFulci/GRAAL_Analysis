#!/usr/bin/env python3
"""Inspect bounded raw-track samples without assigning a physics interpretation."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

import awkward as ak
import uproot

FIELDS = ("Nass_3", "Itipo_track", "Nparf", "Nparf_strange", "N_traf",
          "Index_trf", "Iass_trf")


def audit(path: Path, entries: int = 10000, *, sha256: bool = False) -> dict:
    if entries < 1:
        raise ValueError("entries must be positive")
    path = Path(path).resolve()
    stat = path.stat()
    result = {"path": str(path), "size_bytes": stat.st_size,
              "mtime_ns": stat.st_mtime_ns, "trees": {}}
    if sha256:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        result["sha256"] = digest.hexdigest()
    with uproot.open(path) as f:
        result["root_uuid"] = str(f.file.uuid)
        for name in ("h70", "h80", "h85", "reco"):
            if name not in f:
                continue
            tree = f[name]
            present = [n for n in FIELDS if n in tree]
            info = {"entries": tree.num_entries, "schema": {},
                    "missing": sorted(set(FIELDS) - set(present))}
            result["trees"][name] = info
            for n in present:
                branch = tree[n]
                leaves = []
                for leaf in branch.member("fLeaves"):
                    count = leaf.member("fLeafCount")
                    leaves.append({"name": leaf.member("fName"),
                                   "count_leaf": count.member("fName") if count else None,
                                   "static_length": leaf.member("fLen")})
                info["schema"][n] = {"typename": branch.typename, "leaves": leaves}
            if not present:
                continue
            stop = min(entries, tree.num_entries)
            data = tree.arrays(present, entry_stop=stop, library="ak")
            info["sample"] = {"entry_start": 0, "entry_stop": stop, "values": {}}
            for n in present:
                counts = Counter(ak.to_list(ak.flatten(data[n], axis=None)))
                info["sample"]["values"][n] = {str(k): v for k, v in sorted(counts.items())}
            if set(FIELDS) <= set(present):
                info["sample"].update(
                    nonzero_strange_events=int(ak.sum(data.Nparf_strange != 0)),
                    zero_forward_indices=int(ak.sum(data.Index_trf == 0)),
                    out_of_bounds_nonzero_indices=int(ak.sum((data.Index_trf != 0) & (data.Index_trf > data.N_traf))),
                    count_length_mismatches={
                        branch: int(ak.sum(ak.num(data[branch]) != data[count]))
                        for count, branch in (("Nass_3", "Itipo_track"), ("Nparf", "Index_trf"), ("N_traf", "Iass_trf"))
                    },
                    capacity_violations={
                        count: int(ak.sum((data[count] < 0) | (data[count] > limit)))
                        for count, limit in (("Nass_3", 291), ("Nparf", 90), ("N_traf", 90))
                    },
                )
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--entries", type=int, default=10000)
    parser.add_argument("--sha256", action="store_true", help="hash whole inputs (expensive for campaign files)")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    payload = {"schema": 1, "command": sys.argv, "cut": "disabled_pending_definition",
               "versions": {"python": sys.version, "uproot": uproot.__version__, "awkward": ak.__version__},
               "files": [audit(p, args.entries, sha256=args.sha256) for p in args.inputs]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as stream:
        json.dump(payload, stream, indent=2)
        stream.write("\n")
    print(args.output)


if __name__ == "__main__":
    main()
