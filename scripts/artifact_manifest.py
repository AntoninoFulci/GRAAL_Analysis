"""Manifest and payload checks for launcher-owned production artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile
from typing import Callable, Iterable


MAX_AGE = timedelta(days=10)
PREANALYSIS_BRANCHES = ("gammas", "fcharged_theta", "RunNumber", "Polarization", "Xstrip")


@dataclass(frozen=True)
class CacheItem:
    name: str
    manifest: Path
    outputs: tuple[Path, ...]
    signature: dict


def inventory(paths: Iterable[Path]) -> list[dict]:
    """Identify files by canonical path, byte size, and nanosecond mtime."""
    files: list[Path] = []
    for path in paths:
        path = Path(path)
        if path.is_dir():
            files.extend(child for child in path.rglob("*") if child.is_file())
        elif path.is_file():
            files.append(path)
        else:
            raise FileNotFoundError(path)
    if not files:
        raise ValueError("artifact inventory is empty")
    return [
        {"path": str(path.resolve()), "size": path.stat().st_size, "mtime_ns": path.stat().st_mtime_ns}
        for path in sorted(files, key=lambda item: str(item.resolve()))
    ]


def source_fingerprint(paths: Iterable[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted((Path(path) for path in paths), key=str):
        digest.update(str(path.resolve()).encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _json_value(value):
    return json.loads(json.dumps(value, sort_keys=True))


def cache_status(
    item: CacheItem,
    validate: Callable[[], None],
    now: datetime | None = None,
) -> tuple[bool, str]:
    now = now or datetime.now(timezone.utc)
    try:
        stored = json.loads(item.manifest.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return False, f"missing or malformed manifest: {exc}"
    if not isinstance(stored, dict):
        return False, "malformed manifest: expected JSON object"
    if stored.get("version") != 1 or stored.get("name") != item.name:
        return False, "manifest schema or item mismatch"
    if stored.get("signature") != _json_value(item.signature):
        return False, "input, options, or source changed"
    try:
        completed = datetime.fromisoformat(stored["completed_at"])
        if completed.tzinfo is None or not timedelta() <= now - completed <= MAX_AGE:
            return False, "expired or invalid completion time"
        if stored.get("output_identity") != inventory(item.outputs):
            return False, "output identity changed"
        validate()
    except Exception as exc:
        return False, f"output invalid: {exc}"
    return True, "valid"


def record_cache(
    item: CacheItem,
    validate: Callable[[], None],
    now: datetime | None = None,
) -> None:
    validate()
    identity = inventory(item.outputs)
    payload = {
        "version": 1,
        "name": item.name,
        "signature": _json_value(item.signature),
        "completed_at": (now or datetime.now(timezone.utc)).isoformat(),
        "output_identity": identity,
    }
    item.manifest.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{item.manifest.name}.", dir=item.manifest.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        Path(temporary).replace(item.manifest)
    finally:
        Path(temporary).unlink(missing_ok=True)


def validate_root(path: Path, tree: str, branches: Iterable[str], *, nonempty: bool = True) -> None:
    import uproot

    with uproot.open(path) as source:
        value = source[tree]
        if not hasattr(value, "num_entries"):
            raise ValueError(f"{path}:{tree} is not a tree")
        if nonempty and value.num_entries == 0:
            raise ValueError(f"{path}:{tree} has no entries")
        missing = set(branches) - set(value.keys())
        if missing:
            raise ValueError(f"{path}:{tree} missing branches {sorted(missing)}")


def validate_preanalysis(paths: Iterable[Path]) -> None:
    files = tuple(paths)
    if not files:
        raise ValueError("no pre-analysis files")
    for path in files:
        validate_root(path, "h80", PREANALYSIS_BRANCHES)


def validate_selected(directory: Path, inputs: Iterable[Path]) -> None:
    expected = {path.name.replace("pre_", "", 1) for path in inputs}
    actual = {path.name for path in directory.glob("*.root")}
    if not expected or actual != expected:
        raise ValueError(f"selected set mismatch: expected {sorted(expected)}, got {sorted(actual)}")
    for name in expected:
        validate_root(directory / name, "h85", PREANALYSIS_BRANCHES, nonempty=False)


def validate_mc(path: Path, channel_name: str) -> None:
    from graal_common.physics.channels import get_channel
    import numpy as np
    import uproot

    channel = get_channel(channel_name)
    if channel.photon_branches is None:
        with uproot.open(path) as source:
            counts = np.asarray(source["mc"]["n_true_gamma"].array(library="np"))
        if counts.size == 0 or not np.issubdtype(counts.dtype, np.integer) or np.any(counts < 1) or np.any(counts > 32):
            raise ValueError(f"{path}: invalid n_true_gamma")
        photons = ("n_true_gamma", *(f"g{index}" for index in range(int(counts.max()))))
    else:
        photons = channel.photon_branches
    required = ("beam", "proton", *photons)
    if channel_name == "eta_pi0":
        required += ("target",)
    validate_root(path, "mc", required)


def validate_bdt(directory: Path, profile: str) -> None:
    from bdt_training.dataset.stage1_dataset import load_stage1_dataset
    from graal_common.stage1.artifacts import Stage1ArtifactPaths, Stage1Provenance

    beam = directory / "beam_spectrum.npz"
    validate_beam_spectrum(beam, profile)
    dataset = load_stage1_dataset(directory / "features_stage1.npz")
    if dataset.metadata.beam_profile != profile:
        raise ValueError("feature profile mismatch")
    artifacts = Stage1ArtifactPaths.from_directory(directory / "artifacts/stage1")
    provenance = Stage1Provenance.from_json(artifacts.provenance.read_text())
    if provenance.beam_profile != profile:
        raise ValueError("model profile mismatch")
    validate_bdt_model(artifacts.model, dataset.X.shape[1])
    threshold = float(artifacts.threshold.read_text())
    if not math.isfinite(threshold) or not 0 <= threshold <= 1:
        raise ValueError("invalid model threshold")
    validate_training_reports(artifacts.model.parent, threshold, dataset.metadata.signal_channel, dataset.metadata.hypothesis)


def validate_bdt_model(path: Path, feature_count: int) -> None:
    import xgboost as xgb

    try:
        model = xgb.Booster(model_file=str(path))
    except Exception as exc:
        raise ValueError(f"invalid BDT model {path}: {exc}") from exc
    if model.num_features() != feature_count:
        raise ValueError("model feature count mismatch")


def validate_beam_spectrum(path: Path, profile: str) -> None:
    import numpy as np
    from graal_common.physics.beam_profiles import get_beam_profile

    with np.load(path, allow_pickle=False) as stored:
        edges = np.asarray(stored["edges"], dtype=float)
        density = np.asarray(stored["density"], dtype=float)
    expected = get_beam_profile(profile).energy_range_gev
    if (edges.ndim != 1 or density.shape != (len(edges) - 1,) or
            len(edges) < 2 or not np.isfinite(edges).all() or
            not np.all(np.diff(edges) > 0) or not np.isfinite(density).all() or
            np.any(density < 0) or not np.allclose((edges[0], edges[-1]), expected, atol=1e-12, rtol=0)):
        raise ValueError(f"invalid {profile} beam spectrum")
    integral = float(np.sum(density * np.diff(edges)))
    if not math.isclose(integral, 1.0, rel_tol=1e-6, abs_tol=1e-6):
        raise ValueError(f"beam spectrum normalization invalid: {integral}")


def validate_training_reports(directory: Path, threshold: float, signal: str, hypothesis: str) -> None:
    from PIL import Image

    directory = Path(directory)
    metrics = {}
    for line in (directory / "stage1_metrics.txt").read_text().splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            metrics[key.strip()] = value.strip()
    if metrics.get("Signal") != signal or metrics.get("Hypothesis") != hypothesis:
        raise ValueError("training metrics channel or hypothesis mismatch")
    for key in ("AUC", "Threshold", "Precision", "Recall", "F1"):
        value = float(metrics[key])
        if not math.isfinite(value) or not 0 <= value <= 1:
            raise ValueError(f"invalid training metric {key}")
    if not math.isclose(float(metrics["Threshold"]), threshold, abs_tol=1e-4):
        raise ValueError("training metric threshold mismatch")
    for key in ("N_train", "N_val"):
        if int(metrics[key]) <= 0:
            raise ValueError(f"invalid training metric {key}")
    for stem in ("stage1_roc", "stage1_feature_importance", "stage1_score_dist"):
        path = directory / f"{stem}.png"
        try:
            with Image.open(path) as figure:
                figure.verify()
        except Exception as exc:
            raise ValueError(f"invalid training plot {path}: {exc}") from exc
