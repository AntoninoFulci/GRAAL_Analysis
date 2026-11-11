"""Reconstruct central charged-pair vertices directly from raw h70 files.

Run with ``python -m plots.target_vertex INPUT.root ... --output NEW_DIRECTORY``.
This diagnostic does not select a reaction channel or identify target material.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

import awkward as ak
import numpy as np
import uproot

from graal_common.io.filesystem import atomic_output_directory
from plots.core.vertex import MIN_SIN2, STATUS, central_pairs, closest_vertex


COORDS = tuple(f"{axis}_trace_{side}" for side in ("int", "ext") for axis in "XYZ")
FIELDS = ("Idrun", "Idevt", "Nass_3", "Iass_3", "Itipo_track", "Nb_traces_cyl", *COORDS)
OUTPUT_TYPES = {
    **dict.fromkeys(("run", "event", "source_file", "association1", "association2",
                     "cylinder1", "cylinder2", "type1", "type2", "n_charged", "status"), "int64"),
    "source_entry": "int64",
    **dict.fromkeys(("x_cm", "y_cm", "z_cm", "dca_cm", "sin2"), "float64"),
}


def _validate_chunk(data):
    """Reject corrupt counts/layouts before interpreting association indices."""
    for count, capacity, names in (
        ("Nass_3", 291, ("Iass_3", "Itipo_track")),
        ("Nb_traces_cyl", 5, COORDS),
    ):
        if bool(ak.any((data[count] < 0) | (data[count] > capacity))):
            raise ValueError(f"invalid {count}")
        for name in names:
            if bool(ak.any(ak.num(data[name], axis=1) != data[count])):
                raise ValueError(f"{name}: count/length mismatch")
    if bool(ak.any(ak.num(data.Iass_3, axis=2) != 3)):
        raise ValueError("Iass_3: expected triples")
    if (bool(ak.any(data.Iass_3 < 0))
            or bool(ak.any(data.Iass_3[:, :, 2] > data.Nb_traces_cyl[:, None]))):
        raise ValueError("invalid cylinder/association index")


def _render(root_path, out, runs, view_cm, display_dca_cm):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import LogNorm

    limits = [(-v, v) for v in view_cm]
    with uproot.open(root_path) as f:
        tree = f["vertices"]
        for run, counts in runs.items():
            data = tree.arrays(["x_cm", "y_cm", "z_cm", "dca_cm", "n_charged"],
                               cut=f"(run == {run}) & (status == 0)", library="np")
            xyz = np.column_stack([data[f"{a}_cm"] for a in "xyz"])
            inside = np.all(np.abs(xyz) <= view_cm, axis=1)
            quality = data["dca_cm"] <= display_dca_cm
            counts["display_inside_box"] = int(inside.sum())
            counts["display_outside_box"] = int((~inside).sum())
            counts["display_inside_box_dca"] = int((inside & quality).sum())
            counts["coordinate_quantiles_cm"] = {
                a: np.quantile(xyz[:, i], [.01, .05, .5, .95, .99]).tolist()
                if len(xyz) else [] for i, a in enumerate("xyz")}
            fig = plt.figure(figsize=(16, 10), layout="constrained")
            fig.get_layout_engine().set(hspace=.18)
            fig.suptitle(f"Run {run} | vertici da camere + barrel | {len(xyz):,} coppie valide\n"
                         f"Vista ±({view_cm[0]:g}, {view_cm[1]:g}, {view_cm[2]:g}) cm; "
                         f"fuori vista: {counts['display_outside_box']:,}; nessun taglio spaziale nei dati", fontsize=14)
            for pos, mask, label in ((1, inside, "Tutte le coppie"),
                                     (2, inside & quality, f"Solo visualizzazione: DCA ≤ {display_dca_cm:g} cm")):
                ax = fig.add_subplot(2, 3, pos, projection="3d")
                indices = np.flatnonzero(mask)
                # Deterministic random display sample; densities below use every pair.
                if len(indices) > 20000:
                    indices = np.random.default_rng(0).choice(indices, 20000, replace=False)
                points = xyz[indices]
                ax.scatter(*points.T, s=2, alpha=.25, color="#126a91", rasterized=True)
                ax.set(xlim=limits[0], ylim=limits[1], zlim=limits[2],
                       xlabel="x [cm]", ylabel="y [cm]", zlabel="z [cm]",
                       title=f"{label}\n{int(mask.sum()):,} in vista; {len(indices):,} mostrati")
                ax.set_box_aspect(view_cm)
                ax.view_init(elev=20, azim=-60)
            ax = fig.add_subplot(2, 3, 3)
            bins = np.linspace(*limits[2], 121)
            ax.hist(xyz[:, 2], bins=bins, histtype="step", label="Tutte le coppie")
            ax.hist(xyz[quality, 2], bins=bins, histtype="step", label=f"DCA ≤ {display_dca_cm:g} cm")
            ax.set(xlabel="z [cm]", ylabel="Coppie / bin", title="Profilo longitudinale (nessun taglio x,y)")
            ax.legend(fontsize=9)
            for pos, (i, j) in enumerate(((0, 1), (0, 2), (1, 2)), start=4):
                ax = fig.add_subplot(2, 3, pos)
                h, xe, ye = np.histogram2d(xyz[:, i], xyz[:, j], bins=120,
                                          range=[limits[i], limits[j]])
                if np.any(h):
                    mesh = ax.pcolormesh(xe, ye, np.ma.masked_equal(h.T, 0),
                                         norm=LogNorm(vmin=1, vmax=max(2, h.max())), cmap="viridis")
                    fig.colorbar(mesh, ax=ax, label="Coppie / bin")
                ax.set(xlim=limits[i], ylim=limits[j], xlabel=f"{'xyz'[i]} [cm]",
                       ylabel=f"{'xyz'[j]} [cm]", title="Tutte le coppie; densità logaritmica")
                ax.set_aspect("equal")
            fig.savefig(out / f"run_{run}.png", dpi=160)
            plt.close(fig)
            fig, ax = plt.subplots(figsize=(8, 4), layout="constrained")
            ax.hist(data["dca_cm"], bins=np.linspace(0, 10, 101), histtype="step", label="Tutte")
            ax.hist(data["dca_cm"][data["n_charged"] == 2], bins=np.linspace(0, 10, 101),
                    histtype="step", label="Esattamente due carichi")
            ax.set(xlabel="Distanza minima fra rette [cm]", ylabel="Coppie / bin",
                   title=f"Run {run} | DCA > 10 cm: {int((data['dca_cm'] > 10).sum())}")
            ax.legend()
            fig.savefig(out / f"run_{run}_dca.png", dpi=140)
            plt.close(fig)


def analyze(inputs, output, *, max_entries=None, step_size=50000,
            view_cm=(5., 5., 15.), display_dca_cm=1., plots=True, expected_run=None):
    """Write an exclusive diagnostic campaign, preserving every attempted pair."""
    inputs = [Path(p).resolve(strict=True) for p in inputs]
    if not inputs:
        raise ValueError("no input files")
    if len(set(inputs)) != len(inputs):
        raise ValueError("duplicate input files")
    if max_entries is not None and max_entries < 1:
        raise ValueError("max_entries must be positive")
    if step_size < 1:
        raise ValueError("step_size must be positive")
    if len(view_cm) != 3 or not np.isfinite(view_cm).all() or min(view_cm) <= 0:
        raise ValueError("view_cm must contain three positive finite half-widths")
    if not np.isfinite(display_dca_cm) or display_dca_cm <= 0:
        raise ValueError("display_dca_cm must be positive and finite")
    runs = defaultdict(Counter)
    summary = {
        "schema": 1, "diagnostic": "central_pair_target_vertex", "production_validation": False,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "algorithm": "vertex2.F IWHERE=1: midpoint of closest points on infinite lines",
        "selection": "distinct cylinder tracks associated to distinct positive barrel indices; no BGO/PID/tagger/BDT requirement; all pairs",
        "duplicate_cylinder_policy": "first eligible association row",
        "units": "cm, native h70 detector frame; no alignment shift",
        "min_sin2": MIN_SIN2, "status_codes": STATUS,
        "vertex_position_cut": None, "dca_cut_on_saved_data": None,
        "display": {"half_widths_cm": list(view_cm), "comparison_dca_max_cm": display_dca_cm,
                    "scatter_max_points": 20000, "scatter_seed": 0},
        "interpretation": "pair counts, not independent event counts; geometry alone does not identify target material; acceptance and background are uncorrected",
        "versions": {"python": sys.version, "numpy": np.__version__, "uproot": uproot.__version__, "awkward": ak.__version__},
        "source_hashes": {str(Path(__file__).name): hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                          "vertex.py": hashlib.sha256(Path(__file__).with_name("core").joinpath("vertex.py").read_bytes()).hexdigest()},
        "files": [], "runs": runs,
    }
    with atomic_output_directory(Path(output), overwrite=False) as out:
        with uproot.recreate(out / "vertices.root") as dest:
            output_tree = dest.mktree("vertices", OUTPUT_TYPES)
            for file_index, path in enumerate(inputs):
                stat = path.stat()
                with uproot.open(path) as source:
                    if "h70" not in source:
                        raise ValueError(f"{path}: missing h70 (raw geometry required)")
                    tree = source["h70"]
                    missing = set(FIELDS) - set(tree.keys())
                    if missing:
                        raise ValueError(f"{path}: missing branches {sorted(missing)}")
                    stop = tree.num_entries if max_entries is None else min(max_entries, tree.num_entries)
                    summary["files"].append({"index": file_index, "path": str(path), "size_bytes": stat.st_size,
                                             "mtime_ns": stat.st_mtime_ns, "root_uuid": str(source.file.uuid),
                                             "entries_total": tree.num_entries, "entries_read": stop,
                                             "entry_start": 0, "entry_stop": stop})
                    for data, report in tree.iterate(FIELDS, entry_stop=stop, step_size=step_size,
                                                      library="ak", report=True):
                        _validate_chunk(data)
                        run_ids, totals = np.unique(ak.to_numpy(data.Idrun), return_counts=True)
                        if expected_run is not None and np.any(run_ids != expected_run):
                            raise ValueError(f"run identity differs from catalog run {expected_run}")
                        for run, total in zip(run_ids, totals):
                            runs[str(int(run))]["events_read"] += int(total)
                            runs[str(int(run))]["events_with_chamber_tracks"] += int(ak.sum(
                                (data.Idrun == run) & (data.Nb_traces_cyl > 0)))
                        eligible = (data.Iass_3[:, :, 1] > 0) & (data.Iass_3[:, :, 2] > 0)
                        candidates = np.flatnonzero(ak.to_numpy(ak.sum(eligible, axis=1) >= 2))
                        batch = {name: [] for name in OUTPUT_TYPES}
                        for local, event in zip(candidates, ak.to_list(data[candidates])):
                            pairs, multiplicity = central_pairs(event["Iass_3"], event["Nb_traces_cyl"])
                            counts = runs[str(event["Idrun"])]
                            if not pairs:
                                continue
                            counts["events_with_pairs"] += 1
                            counts[f"events_with_{multiplicity}_charges"] += 1
                            any_valid = False
                            for i, j in pairs:
                                ci, cj = event["Iass_3"][i][2], event["Iass_3"][j][2]
                                points = [[event[f"{axis}_trace_{side}"][c - 1] for axis in "XYZ"]
                                          for c in (ci, cj) for side in ("int", "ext")]
                                vertex = closest_vertex(*points)
                                counts["attempted_pairs"] += 1
                                counts[f"pairs_{vertex.status}"] += 1
                                if vertex.status == "ok":
                                    counts["valid_pairs"] += 1
                                    any_valid = True
                                row = dict(run=event["Idrun"], event=event["Idevt"], source_file=file_index,
                                           source_entry=int(report.tree_entry_start + local),
                                           association1=i+1, association2=j+1, cylinder1=ci, cylinder2=cj,
                                           type1=event["Itipo_track"][i], type2=event["Itipo_track"][j],
                                           n_charged=multiplicity, status=STATUS[vertex.status],
                                           x_cm=vertex.xyz[0], y_cm=vertex.xyz[1], z_cm=vertex.xyz[2],
                                           dca_cm=vertex.dca, sin2=vertex.sin2)
                                for key, value in row.items():
                                    batch[key].append(value)
                            counts["events_with_valid_pairs"] += int(any_valid)
                        if batch["run"]:
                            output_tree.extend({k: np.asarray(v, dtype=OUTPUT_TYPES[k]) for k, v in batch.items()})
                    after = path.stat()
                    if (stat.st_size, stat.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                        raise ValueError(f"input changed during analysis: {path}")
        if plots:
            _render(out / "vertices.root", out, runs, view_cm, display_dca_cm)
        (out / "summary.json").write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n")
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+", type=Path, help="h70 ROOT files or directories of *.root")
    parser.add_argument("--output", required=True, type=Path, help="new directory; existing output is never replaced")
    parser.add_argument("--max-entries", type=int, help="maximum entries per file; default reads all")
    parser.add_argument("--step-size", type=int, default=50000, help="entries per input chunk")
    parser.add_argument("--no-plots", action="store_true")
    parser.add_argument("--view-cm", nargs=3, type=float, default=(5., 5., 15.), metavar=("X", "Y", "Z"))
    parser.add_argument("--display-dca-cm", type=float, default=1., help="comparison view only; no saved-data cut")
    args = parser.parse_args(argv)
    inputs = [f for p in args.inputs for f in (sorted(p.glob("*.root")) if p.is_dir() else [p])]
    summary = analyze(inputs, args.output, max_entries=args.max_entries, step_size=args.step_size,
                      view_cm=args.view_cm, display_dca_cm=args.display_dca_cm, plots=not args.no_plots)
    for run, counts in summary["runs"].items():
        print(f"Run {run}: {counts['events_read']} events, {counts['valid_pairs']} valid pairs")
    print(args.output.resolve())


if __name__ == "__main__":
    main()
