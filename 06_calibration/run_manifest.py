from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
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
ALLOWED_TARGETS = {"P", "D", "UNKNOWN"}
ALLOWED_BEAM_TYPES = {"UV", "VIS", "UNKNOWN"}
ALLOWED_GROUPS = {"P_UV", "P_VIS", "D_UV", "D_VIS", "UNASSIGNED"}
ALLOWED_SOURCES = {"automatic", "manual", "unresolved"}


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
    has_uv = "uv" in name
    has_vis = "vis" in name
    if DEUTERIUM_PERIOD_RE.search(name):
        return "D", "UNKNOWN", "UNASSIGNED", "unresolved"
    if has_uv and has_vis:
        return "UNKNOWN", "UNKNOWN", "UNASSIGNED", "unresolved"
    if has_uv:
        return "P", "UV", "P_UV", "automatic"
    if has_vis:
        return "P", "VIS", "P_VIS", "automatic"
    return "UNKNOWN", "UNKNOWN", "UNASSIGNED", "unresolved"


def scan_runs(input_dir: Path) -> list[RunRecord]:
    root = Path(input_dir)
    if not root.is_dir():
        raise ManifestError(f"input directory not found: {root}")

    candidates = sorted(path for path in root.rglob("run*.root") if path.is_file())
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


def read_manifest(path: Path) -> list[RunRecord]:
    manifest = Path(path)
    if not manifest.is_file():
        raise ManifestError(f"manifest not found: {manifest}")
    try:
        with manifest.open(encoding="utf-8", newline="") as stream:
            reader = csv.DictReader(stream, strict=True)
            if reader.fieldnames != list(FIELDNAMES):
                raise ManifestError(
                    f"invalid columns: expected {','.join(FIELDNAMES)}, "
                    f"got {','.join(reader.fieldnames or [])}"
                )
            records = []
            for row_number, row in enumerate(reader, start=2):
                if None in row:
                    raise ManifestError(f"row {row_number}: invalid row width")
                try:
                    run_number = int(row["run_number"])
                except (TypeError, ValueError):
                    raise ManifestError(
                        f"row {row_number}: run_number must be a positive integer"
                    ) from None
                records.append(
                    RunRecord(
                        run_number,
                        row["source_period"],
                        row["target"],
                        row["beam_type"],
                        row["group"],
                        row["classification_source"],
                        row["source_file"],
                    )
                )
    except UnicodeDecodeError:
        raise ManifestError(f"cannot decode manifest: {manifest}") from None
    except csv.Error:
        raise ManifestError(f"invalid CSV: {manifest}") from None
    return records


def validate_manifest(path: Path) -> list[RunRecord]:
    records = read_manifest(path)
    if not records:
        raise ManifestError("manifest has no data rows")

    expected_run = -1
    seen: set[int] = set()
    for row_number, record in enumerate(records, start=2):
        prefix = f"row {row_number}: "
        if record.run_number <= 0:
            raise ManifestError(prefix + "run_number must be a positive integer")
        if record.run_number in seen:
            raise ManifestError(prefix + f"duplicate run {record.run_number}")
        if record.run_number <= expected_run:
            raise ManifestError(prefix + "rows must be ordered by run_number")
        seen.add(record.run_number)
        expected_run = record.run_number
        if not record.source_period:
            raise ManifestError(prefix + "source_period is empty")
        if not record.source_file:
            raise ManifestError(prefix + "source_file is empty")
        if record.target not in ALLOWED_TARGETS:
            raise ManifestError(prefix + f"invalid target {record.target!r}")
        if record.beam_type not in ALLOWED_BEAM_TYPES:
            raise ManifestError(prefix + f"invalid beam_type {record.beam_type!r}")
        if record.group not in ALLOWED_GROUPS:
            raise ManifestError(prefix + f"invalid group {record.group!r}")
        if record.classification_source not in ALLOWED_SOURCES:
            raise ManifestError(
                prefix + f"invalid classification_source "
                f"{record.classification_source!r}"
            )
        if (
            record.target == "UNKNOWN"
            or record.beam_type == "UNKNOWN"
            or record.group == "UNASSIGNED"
            or record.classification_source == "unresolved"
        ):
            raise ManifestError(prefix + "classification is unresolved")
        expected_group = f"{record.target}_{record.beam_type}"
        if record.group != expected_group:
            raise ManifestError(
                prefix + f"group {record.group!r} conflicts with "
                f"target/beam {expected_group!r}"
            )
        source = PurePosixPath(record.source_file)
        windows_source = PureWindowsPath(record.source_file)
        if source.is_absolute() or windows_source.is_absolute():
            raise ManifestError(prefix + "source_file must be relative")
        if (
            "\\" in record.source_file
            or windows_source.drive
            or ".." in source.parts
        ):
            raise ManifestError(prefix + "source_file must be a portable relative path")
        if source.name != f"run{record.run_number}.root":
            raise ManifestError(
                prefix + "source_file basename does not match run_number"
            )
    return records
