from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


FIELDNAMES = (
    "run_number",
    "source_period",
    "target",
    "beam_type",
    "group",
    "classification_source",
    "source_file",
)
RUN_FILE_RE = re.compile(r"^run([1-9][0-9]*)\.root$")
DEUTERIUM_PERIOD_RE = re.compile(r"(?:^|_)d[0-9]*$", re.IGNORECASE)


class ManifestError(ValueError):
    pass


@dataclass(frozen=True)
class RunRecord:
    run_number: int
    source_period: str
    target: str
    beam_type: str
    group: str
    classification_source: str
    source_file: str


def classify_period(period: str) -> tuple[str, str, str, str]:
    name = period.lower()
    if DEUTERIUM_PERIOD_RE.search(name):
        return "D", "UNKNOWN", "UNASSIGNED", "unresolved"
    if "fuv" in name or "uv" in name:
        return "P", "UV", "P_UV", "automatic"
    if "vis" in name:
        return "P", "VIS", "P_VIS", "automatic"
    return "UNKNOWN", "UNKNOWN", "UNASSIGNED", "unresolved"


def scan_runs(input_dir: Path) -> list[RunRecord]:
    root = Path(input_dir)
    if not root.is_dir():
        raise ManifestError(f"input directory not found: {root}")

    candidates = sorted(root.rglob("run*.root"))
    malformed = [path for path in candidates if RUN_FILE_RE.fullmatch(path.name) is None]
    if malformed:
        raise ManifestError(f"malformed run filename: {malformed[0].relative_to(root)}")

    records: list[RunRecord] = []
    seen: dict[int, Path] = {}
    for path in candidates:
        match = RUN_FILE_RE.fullmatch(path.name)
        assert match is not None
        run_number = int(match.group(1))
        if run_number in seen:
            raise ManifestError(
                f"duplicate run {run_number}: "
                f"{seen[run_number].relative_to(root)} and {path.relative_to(root)}"
            )
        seen[run_number] = path
        period = path.parent.name
        target, beam_type, group, source = classify_period(period)
        records.append(
            RunRecord(
                run_number,
                period,
                target,
                beam_type,
                group,
                source,
                path.relative_to(root).as_posix(),
            )
        )

    if not records:
        raise ManifestError(f"no run files found under {root}")
    return sorted(records, key=lambda record: record.run_number)


def write_manifest(records: Sequence[RunRecord], output: Path) -> None:
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDNAMES, lineterminator="\n")
        writer.writeheader()
        for record in records:
            writer.writerow(
                {
                    "run_number": record.run_number,
                    "source_period": record.source_period,
                    "target": record.target,
                    "beam_type": record.beam_type,
                    "group": record.group,
                    "classification_source": record.classification_source,
                    "source_file": record.source_file,
                }
            )
