"""Resumable, uncertified p6 preview of Ajaka Figure 4 theoretical curves.

This calculates raw coherent-model moments with published parameters. It does
not run convergence, replica, grid/direct, or source-compatibility gates.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import csv
from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path
import tempfile

import numpy as np

from graal_theory.cli import _figure4_model
from graal_theory.figure4_integration import _safe_predict
from graal_theory.figure4_reference import PAIR_MASS_AXES, load_published_theory_curves
from graal_theory.phase_space import SobolConfig


REFERENCES = Path(__file__).resolve().parents[1]/"references"
PAIRS = ("p_pi0", "p_eta", "eta_pi0")
POWER = 6
ENERGY_ORDER = 4
Q_ORDER = 64
ANGLE_ORDER = 48
PURPOSE = "figure4_qualitative_preview_only"


def _digest(paths: list[Path]) -> str:
    hasher = hashlib.sha256()
    for path in paths:
        hasher.update(path.name.encode("utf-8"))
        hasher.update(path.read_bytes())
    return hasher.hexdigest()


def _settings() -> dict:
    package = Path(__file__).resolve().parents[1]/"src"/"graal_theory"
    parameters = [REFERENCES/name for name in (
        "sources.json", "central_parameters.json",
        "nstar1535_reduced_parameters.json", "nstar1535_final_subtractions.json",
        "nstar1535_vmd_masses.json", "eta_pi0_p_full_parameters.json",
    )]
    return {
        "purpose": PURPOSE,
        "sobol_power": POWER,
        "energy_order": ENERGY_ORDER,
        "q_order": Q_ORDER,
        "angle_order": ANGLE_ORDER,
        "mode": "grid",
        "convergence_checked": False,
        "parameters_sha256": _digest(parameters),
        "code_sha256": _digest([*sorted(package.rglob("*.py")), Path(__file__).resolve()]),
        "reference_sha256": _digest([REFERENCES/"ajaka2008_figure4_theory.csv",
                                     REFERENCES/"ajaka2008_figure4_theory.json"]),
    }


@lru_cache(maxsize=1)
def _model():
    return _figure4_model(REFERENCES, "grid", Q_ORDER, ANGLE_ORDER)


def compute_bin(energy: int, pair: str, index: int) -> dict:
    """Calculate one raw moment without treating finiteness as convergence."""
    edges = np.linspace(*PAIR_MASS_AXES[pair], 11)
    interval = (float(edges[index]), float(edges[index+1]))
    energy_range = (round(1.10+.10*energy, 2), round(1.20+.10*energy, 2))
    moment = _safe_predict(_model(), pair, energy_range, interval,
                           ENERGY_ORDER, SobolConfig(POWER))
    calculated = moment.status == "calculated"
    return {
        "energy_bin": energy,
        "pair": pair,
        "mass_bin": index,
        "energy_range_gev": list(energy_range),
        "mass_range_gev": list(interval),
        "weighted_mass_gev": moment.weighted_mass_gev if calculated else None,
        "sigma": moment.sigma if calculated else None,
        "numerator": moment.numerator,
        "denominator": moment.denominator,
        "vertical_normalization": moment.vertical_normalization,
        "horizontal_normalization": moment.horizontal_normalization,
        "source_used_extension_fraction": (
            moment.source_used_extension_fraction if calculated else None),
        "status": moment.status,
        "reason": moment.reason,
    }


def _save_json(path: Path, value: dict) -> None:
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent,
                                     prefix=f".{path.stem}-", suffix=".json",
                                     delete=False) as stream:
        temporary = Path(stream.name)
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")
    os.replace(temporary, path)


def _bin_path(directory: Path, task: tuple[int, str, int]) -> Path:
    return directory/"bins"/f"e{task[0]}-{task[1]}-b{task[2]}.json"


def _record_matches(record: dict, task: tuple[int, str, int], digest: str) -> bool:
    energy, pair, index = task
    edges = np.linspace(*PAIR_MASS_AXES[pair], 11)
    expected_energy = [round(1.10+.10*energy, 2), round(1.20+.10*energy, 2)]
    expected_mass = [float(edges[index]), float(edges[index+1])]
    status = record.get("status")
    if (record.get("purpose") != PURPOSE or record.get("settings_sha256") != digest
            or (record.get("energy_bin"), record.get("pair"), record.get("mass_bin")) != task
            or record.get("energy_range_gev") != expected_energy
            or record.get("mass_range_gev") != expected_mass
            or status not in ("calculated", "masked_kinematic",
                              "masked_nonconverged", "masked_unsupported_domain")):
        return False
    if status == "calculated":
        sigma = record.get("sigma")
        mass = record.get("weighted_mass_gev")
        denominator = record.get("denominator")
        return (all(isinstance(x, (int, float)) and np.isfinite(x)
                    for x in (sigma, mass, denominator))
                and denominator > 0 and expected_mass[0] <= mass <= expected_mass[1])
    return record.get("sigma") is None


def _render(output: Path, rows: list[dict], settings: dict) -> int:
    csv_path = output/"preview.csv"
    csv_temp = output/".preview.tmp.csv"
    columns = ("energy_bin", "pair", "mass_bin", "energy_range_gev",
               "mass_range_gev", "weighted_mass_gev", "sigma", "numerator",
               "denominator", "vertical_normalization", "horizontal_normalization",
               "source_used_extension_fraction", "status", "reason")
    with csv_temp.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: json.dumps(row[key]) if isinstance(row.get(key), list)
                             else row.get(key) for key in columns})
    os.replace(csv_temp, csv_path)

    published = load_published_theory_curves(
        REFERENCES/"ajaka2008_figure4_theory.csv",
        REFERENCES/"ajaka2008_figure4_theory.json")
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_agg import FigureCanvasAgg

    figure = Figure(figsize=(13, 13))
    FigureCanvasAgg(figure)
    axes = figure.subplots(4, 3, sharey=True)
    figure.suptitle("PRELIMINARY Figure 4 — p6; convergence not checked")
    for energy in range(4):
        for column, pair in enumerate(PAIRS):
            axis = axes[energy, column]
            bins = [row for row in rows if row["energy_bin"] == energy and row["pair"] == pair]
            axis.plot([row["weighted_mass_gev"] if row["status"] == "calculated" else np.nan
                       for row in bins],
                      [row["sigma"] if row["status"] == "calculated" else np.nan
                       for row in bins],
                      "o-", color="#005c99", markersize=3, label="model p6 (preliminary)")
            reference = [point for point in published
                         if point.energy_bin == energy and point.pair == pair]
            axis.plot([point.mass_gev for point in reference],
                      [point.sigma for point in reference], "--", color="#bf4b25",
                      linewidth=1.2, label="Ajaka theory")
            axis.set_xlim(PAIR_MASS_AXES[pair])
            axis.set_ylim(-1.05, 1.05)
            axis.set_title(f"Eγ {1.1+.1*energy:.1f}–{1.2+.1*energy:.1f} GeV · {pair}")
            axis.set_xlabel("Pair mass (GeV)")
            if column == 0:
                axis.set_ylabel("Σ")
            if energy == 0 and column == 0:
                axis.legend(fontsize=8)
    figure.tight_layout(rect=(0, 0, 1, .97))
    pdf_temp = output/".preview.tmp.pdf"
    figure.savefig(pdf_temp, format="pdf")
    os.replace(pdf_temp, output/"preview.pdf")

    counts = {status: sum(row["status"] == status for row in rows)
              for status in ("calculated", "masked_kinematic",
                             "masked_nonconverged", "masked_unsupported_domain")}
    summary = {
        "status": "preliminary_uncertified",
        "purpose": PURPOSE,
        "calculated_bins": counts["calculated"],
        "kinematic_masks": counts["masked_kinematic"],
        "other_masks": counts["masked_nonconverged"]+counts["masked_unsupported_domain"],
        "settings": settings,
        "note": "Raw published-parameter moments; no convergence or Ajaka compatibility claim.",
    }
    _save_json(output/"summary.json", summary)
    return 2 if summary["other_masks"] else 0


def run_preview(output_dir: Path, *, workers: int) -> int:
    """Resume exact matching checkpoints, then write labeled 4×3 preview."""
    if not 1 <= workers <= 14:
        raise ValueError("workers must be between 1 and 14")
    output = Path(output_dir)
    (output/"bins").mkdir(parents=True, exist_ok=True)
    settings = _settings()
    settings_path = output/"settings.json"
    if settings_path.exists():
        if json.loads(settings_path.read_text(encoding="utf-8")) != settings:
            raise ValueError(f"incompatible existing settings: {settings_path}")
    else:
        _save_json(settings_path, settings)
    digest = hashlib.sha256(json.dumps(settings, sort_keys=True).encode()).hexdigest()
    tasks = [(energy, pair, index) for energy in range(4)
             for pair in PAIRS for index in range(10)]
    pending = []
    for task in tasks:
        path = _bin_path(output, task)
        if path.exists():
            record = json.loads(path.read_text(encoding="utf-8"))
            if not _record_matches(record, task, digest):
                raise ValueError(f"incompatible existing bin: {path}")
        else:
            pending.append(task)
    print(f"Figure 4 preliminary p6: {len(pending)} pending of 120; workers={workers}", flush=True)
    if workers == 1:
        for task in pending:
            record = dict(compute_bin(*task), purpose=PURPOSE, settings_sha256=digest)
            if not _record_matches(record, task, digest):
                raise ValueError(f"invalid calculated bin: {task}")
            _save_json(_bin_path(output, task), record)
            print(f"Saved {task}: {record['status']}", flush=True)
    else:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(compute_bin, *task): task for task in pending}
            for future in as_completed(futures):
                task = futures[future]
                record = dict(future.result(), purpose=PURPOSE, settings_sha256=digest)
                if not _record_matches(record, task, digest):
                    raise ValueError(f"invalid calculated bin: {task}")
                _save_json(_bin_path(output, task), record)
                print(f"Saved {task}: {record['status']}", flush=True)
    rows = [json.loads(_bin_path(output, task).read_text(encoding="utf-8")) for task in tasks]
    code = _render(output, rows, settings)
    print(f"Preview saved: {output/'preview.pdf'}; {output/'preview.csv'}; "
          f"{output/'summary.json'}", flush=True)
    return code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args(argv)
    if not 1 <= args.workers <= 14:
        parser.error("--workers must be between 1 and 14")
    return run_preview(args.output_dir, workers=args.workers)


if __name__ == "__main__":
    raise SystemExit(main())
