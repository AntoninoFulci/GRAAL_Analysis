"""Build replayable nominal and shared-event-bootstrap counts from N2 events."""

from __future__ import annotations

import csv
from dataclasses import InitVar, dataclass, fields
from decimal import Decimal, localcontext
from hashlib import sha256
import math
from pathlib import Path
from types import MappingProxyType
from typing import Mapping, Sequence

import numpy as np

from analysis_config import (
    AnalysisConfig,
    BOOTSTRAP_ALGORITHM_VERSION,
    load_analysis_config,
)
from acceptance_handoff import validate_acceptance_handoff
from compton import PolarizationCurve, load_period_curves
from contracts import (
    OBSERVABLE_BUNDLE_PATHS,
    PolarizationContractError,
    SHA256_PATTERN,
    canonical_relative_file,
    load_json,
    sha256_file,
    validate_gate0_handoff,
)
from figure4_analysis import PAIR_NAMES, event_pair_observables
from phi_response import PhiResponse
from reco_inventory import RecoInventory, load_gate0_run_numbers, load_reco_inventory
from root_events import EventSample
from state_mapping import (
    StateInterval,
    load_state_mapping,
    validate_intervals,
)


AZIMUTH_COUNT_FIELDS = tuple(
    """
schema_version analysis_version fit_release_id bin_set_id channel target beam_group
source_period Egamma_low Egamma_high cos_theta_low cos_theta_high observable
selection_id orientation replica_id reco_mass_bin reco_mass_low_gev
reco_mass_high_gev reco_phi_bin reco_phi_low reco_phi_high observed_count exposure
beam_polarization beam_polarization_variance gate0_handoff_sha256
n2_reconstruction_sha256 state_mapping_sha256 compton_source_sha256 config_sha256
input_sha256
""".split()
)
ORIENTATIONS = ("parallel", "perpendicular")
CANONICAL_CONFIG_PATH = "config/physics/polarization_v1.json"
CANONICAL_GATE0_PATH = "results/observable_runs/HANDOFF.json"
CANONICAL_RUNS_PATH = "results/observable_runs/run_manifest_observables.csv"
CANONICAL_FLUX_PATH = "results/observable_runs/flux_by_run_energy.csv"
_FLUX_REQUIRED_FIELDS = frozenset(
    {
        "binning",
        "run_number",
        "source_period",
        "target",
        "beam_type",
        "group",
        "energy_low_gev",
        "energy_high_gev",
        "pol1_net",
        "pol2_net",
        "status",
    }
)
_COUNT_AUTHORITY_TOKEN = object()


@dataclass(frozen=True)
class AuthenticatedFile:
    """One canonical repository file whose digest was checked from its bytes."""

    relative_path: str
    path: Path
    sha256: str


@dataclass(frozen=True)
class FluxAuthorityRow:
    """One valid observable-run flux row retained for count exposure building."""

    run_number: int
    source_period: str
    target: str
    beam_type: str
    beam_group: str
    energy_low_gev: float
    energy_high_gev: float
    pol1_net: float
    pol2_net: float


@dataclass(frozen=True)
class PeriodComptonAuthority:
    """The authenticated external source backing one parsed Compton curve."""

    source_period: str
    file: AuthenticatedFile


@dataclass(frozen=True)
class CountAuthority:
    """Byte-authenticated immutable inputs required to construct S4 counts.

    Instances are created only by :func:`load_count_authority`; the private
    token prevents callers from assembling apparently valid provenance from
    hashes and in-memory values.
    """

    repository_root: Path
    fit_release_id: str
    bin_set_id: str
    config: AnalysisConfig
    config_file: AuthenticatedFile
    gate0_handoff_file: AuthenticatedFile
    gate0_bundle_files: tuple[AuthenticatedFile, ...]
    flux_file: AuthenticatedFile
    gate0_run_numbers: frozenset[int]
    n2_inventory: RecoInventory
    n2_inventory_file: AuthenticatedFile
    n2_files: tuple[AuthenticatedFile, ...]
    response: PhiResponse
    acceptance_files: tuple[AuthenticatedFile, ...]
    state_map: tuple[StateInterval, ...]
    state_mapping_file: AuthenticatedFile
    compton: Mapping[str, PolarizationCurve]
    compton_files: tuple[PeriodComptonAuthority, ...]
    flux_rows: tuple[FluxAuthorityRow, ...]
    _loader_token: InitVar[object] = None

    def __post_init__(self, _loader_token: object) -> None:
        if _loader_token is not _COUNT_AUTHORITY_TOKEN:
            raise PolarizationContractError(
                "CountAuthority instances must come from load_count_authority"
            )

    @property
    def config_sha256(self) -> str:
        return self.config_file.sha256

    @property
    def gate0_handoff_sha256(self) -> str:
        return self.gate0_handoff_file.sha256

    @property
    def n2_reconstruction_sha256(self) -> str:
        return self.n2_inventory_file.sha256

    @property
    def state_mapping_sha256(self) -> str:
        return self.state_mapping_file.sha256


def _canonical_input_path(raw_path: str | Path, label: str) -> str:
    if isinstance(raw_path, Path):
        raw_path = raw_path.as_posix()
    if not isinstance(raw_path, str):
        raise PolarizationContractError(
            f"{label} path must be canonical repository-relative POSIX"
        )
    return raw_path


def _authenticated_file(
    repository_root: Path,
    raw_path: str | Path,
    label: str,
    *,
    expected_sha256: object | None = None,
) -> AuthenticatedFile:
    relative, path = canonical_relative_file(
        repository_root, _canonical_input_path(raw_path, label), label
    )
    actual = sha256_file(path)
    if expected_sha256 is not None:
        expected = _digest(expected_sha256, f"{label} SHA-256")
        if actual != expected:
            raise PolarizationContractError(
                f"{label} SHA-256 mismatch: expected {expected}, got {actual}"
            )
    return AuthenticatedFile(relative, path, actual)


def _gate0_bundle_files(
    repository_root: Path, handoff: Mapping[str, object]
) -> tuple[AuthenticatedFile, ...]:
    records = handoff.get("files")
    if not isinstance(records, list):
        raise PolarizationContractError("HANDOFF bundle records are unavailable")
    authenticated = []
    for record in records:
        if not isinstance(record, Mapping):
            raise PolarizationContractError("HANDOFF bundle record must be an object")
        authenticated.append(
            _authenticated_file(
                repository_root,
                record.get("path"),
                "Gate 0 bundle file",
                expected_sha256=record.get("sha256"),
            )
        )
    if {item.relative_path for item in authenticated} != set(
        OBSERVABLE_BUNDLE_PATHS
    ):
        raise PolarizationContractError(
            "HANDOFF bundle records disagree with canonical observable bundle"
        )
    return tuple(sorted(authenticated, key=lambda item: item.relative_path))


def _parse_flux_rows(
    path: Path,
    *,
    target: str,
    gate0_run_numbers: frozenset[int],
) -> tuple[FluxAuthorityRow, ...]:
    try:
        stream = Path(path).open(newline="", encoding="utf-8")
    except OSError as exc:
        raise PolarizationContractError(f"cannot read count flux CSV: {path}") from exc
    rows = []
    keys = set()
    with stream:
        reader = csv.DictReader(stream)
        missing = _FLUX_REQUIRED_FIELDS - set(reader.fieldnames or ())
        if missing:
            raise PolarizationContractError(
                "count flux CSV missing columns: " + ", ".join(sorted(missing))
            )
        for row_number, raw in enumerate(reader, start=2):
            if raw["binning"] != "ajaka_sigma" or raw["target"] != target:
                continue
            try:
                run_number = int(raw["run_number"])
            except (TypeError, ValueError) as exc:
                raise PolarizationContractError(
                    f"count flux row {row_number} has invalid run_number"
                ) from exc
            if run_number not in gate0_run_numbers:
                continue
            if raw["status"] != "valid":
                raise PolarizationContractError(
                    f"count flux row {row_number} is not valid"
                )
            source_period = _canonical_text(
                raw["source_period"], f"count flux row {row_number} source_period"
            )
            beam_type = _canonical_text(
                raw["beam_type"], f"count flux row {row_number} beam_type"
            )
            beam_group = _canonical_text(
                raw["group"], f"count flux row {row_number} group"
            )
            try:
                low = float(raw["energy_low_gev"])
                high = float(raw["energy_high_gev"])
                pol1_net = float(raw["pol1_net"])
                pol2_net = float(raw["pol2_net"])
            except (TypeError, ValueError) as exc:
                raise PolarizationContractError(
                    f"count flux row {row_number} has invalid numeric fields"
                ) from exc
            if (
                not all(math.isfinite(value) for value in (low, high, pol1_net, pol2_net))
                or high <= low
                or pol1_net < 0.0
                or pol2_net < 0.0
            ):
                raise PolarizationContractError(
                    f"count flux row {row_number} has invalid energy or net flux"
                )
            key = (run_number, source_period, target, beam_group, low, high)
            if key in keys:
                raise PolarizationContractError("count flux rows must be unique")
            keys.add(key)
            rows.append(
                FluxAuthorityRow(
                    run_number,
                    source_period,
                    target,
                    beam_type,
                    beam_group,
                    low,
                    high,
                    pol1_net,
                    pol2_net,
                )
            )
    if not rows:
        raise PolarizationContractError(
            "count flux CSV has no valid ajaka_sigma rows for Gate 0 runs"
        )
    return tuple(
        sorted(
            rows,
            key=lambda row: (
                row.run_number,
                row.source_period,
                row.beam_group,
                row.energy_low_gev,
                row.energy_high_gev,
            ),
        )
    )


def _source_file(
    repository_root: Path,
    source: object,
    label: str,
) -> AuthenticatedFile:
    if not isinstance(source, Mapping):
        raise PolarizationContractError(f"{label} source must be an object")
    return _authenticated_file(
        repository_root,
        source.get("path"),
        label,
        expected_sha256=source.get("sha256"),
    )


def _relative_authenticated_file(
    repository_root: Path,
    path: Path,
    label: str,
    *,
    expected_sha256: str,
) -> AuthenticatedFile:
    try:
        relative = Path(path).relative_to(repository_root).as_posix()
    except ValueError as exc:
        raise PolarizationContractError(f"{label} is outside repository") from exc
    return _authenticated_file(
        repository_root, relative, label, expected_sha256=expected_sha256
    )


def load_count_authority(
    *,
    repository_root: Path,
    config_path: str | Path,
    gate0_handoff_path: str | Path,
    n2_inventory_path: str | Path,
    acceptance_handoff_path: str | Path,
    fit_release_id: str,
    bin_set_id: str,
) -> CountAuthority:
    """Load the exact byte-authenticated authority bundle for S4 counts."""
    try:
        root = Path(repository_root).resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise PolarizationContractError(
            f"count repository root does not exist: {repository_root}"
        ) from exc
    if not root.is_dir():
        raise PolarizationContractError("count repository root must be a directory")
    release_id = _canonical_text(fit_release_id, "fit_release_id")
    bins_id = _canonical_text(bin_set_id, "bin_set_id")

    config_relative = _canonical_input_path(config_path, "analysis config")
    if config_relative != CANONICAL_CONFIG_PATH:
        raise PolarizationContractError(
            f"analysis config path must be {CANONICAL_CONFIG_PATH}"
        )
    config_file = _authenticated_file(root, config_relative, "analysis config")
    config = load_analysis_config(config_file.path, root, require_approved=True)
    raw_config = load_json(config_file.path)
    if sha256_file(config_file.path) != config_file.sha256:
        raise PolarizationContractError("analysis config changed during validation")

    gate0_relative = _canonical_input_path(gate0_handoff_path, "Gate 0 HANDOFF")
    if gate0_relative != CANONICAL_GATE0_PATH:
        raise PolarizationContractError(
            f"Gate 0 HANDOFF path must be {CANONICAL_GATE0_PATH}"
        )
    if raw_config.get("gate0_handoff") != gate0_relative:
        raise PolarizationContractError(
            "Gate 0 HANDOFF path disagrees with canonical config"
        )
    gate0_file = _authenticated_file(root, gate0_relative, "Gate 0 HANDOFF")
    gate0 = validate_gate0_handoff(gate0_file.path, root)
    if sha256_file(gate0_file.path) != gate0_file.sha256:
        raise PolarizationContractError("Gate 0 HANDOFF changed during validation")
    bundle_files = _gate0_bundle_files(root, gate0)
    bundle_by_path = {item.relative_path: item for item in bundle_files}
    flux_file = bundle_by_path[CANONICAL_FLUX_PATH]
    runs_file = bundle_by_path[CANONICAL_RUNS_PATH]
    gate0_runs = load_gate0_run_numbers(runs_file.path, target=config.figure4_target)

    inventory_file = _authenticated_file(
        root, n2_inventory_path, "N2 reconstruction inventory"
    )
    inventory = load_reco_inventory(
        inventory_file.path,
        root,
        expected_handoff_sha256=gate0_file.sha256,
        expected_tree=config.figure4_tree,
        expected_vectors=config.figure4_vectors,
        expected_run_numbers=gate0_runs,
    )
    if sha256_file(inventory_file.path) != inventory_file.sha256:
        raise PolarizationContractError(
            "N2 reconstruction inventory changed during validation"
        )
    n2_files = tuple(
        sorted(
            (
                _relative_authenticated_file(
                    root,
                    path,
                    "N2 reconstruction file",
                    expected_sha256=sha256_file(path),
                )
                for path in inventory.paths
            ),
            key=lambda item: item.relative_path,
        )
    )

    acceptance_relative = _canonical_input_path(
        acceptance_handoff_path, "N3 acceptance handoff QA"
    )
    expected_acceptance_qa = (
        f"{config.acceptance_handoff_directory}/acceptance_qa.json"
    )
    if acceptance_relative != expected_acceptance_qa:
        raise PolarizationContractError(
            "N3 acceptance handoff path disagrees with canonical config"
        )
    acceptance_qa_file = _authenticated_file(
        root, acceptance_relative, "N3 acceptance handoff QA"
    )
    acceptance = validate_acceptance_handoff(
        acceptance_qa_file.path.parent,
        root,
        config=config,
        expected_gate0_sha256=gate0_file.sha256,
    )
    if acceptance.n2_reconstruction_sha256 != inventory_file.sha256:
        raise PolarizationContractError(
            "N3 acceptance handoff is bound to a different N2 reconstruction"
        )
    acceptance_files = tuple(
        _relative_authenticated_file(
            root, path, label, expected_sha256=digest
        )
        for path, label, digest in (
            (
                acceptance.acceptance_csv,
                "N3 acceptance CSV",
                acceptance.acceptance_sha256,
            ),
            (
                acceptance.phi_response_csv,
                "N3 phi-response CSV",
                acceptance.phi_response_sha256,
            ),
            (acceptance.qa_json, "N3 acceptance QA", acceptance.qa_sha256),
        )
    )
    if acceptance_qa_file != acceptance_files[-1]:
        raise PolarizationContractError(
            "N3 acceptance QA path or digest changed during validation"
        )

    state_map = load_state_mapping(config_file.path, root)
    state_section = raw_config.get("state_mapping")
    if not isinstance(state_section, Mapping):
        raise PolarizationContractError("canonical config lacks state mapping")
    state_file = _source_file(
        root, state_section.get("source"), "state mapping authority"
    )

    curves = load_period_curves(config_file.path, root)
    compton_section = raw_config.get("compton_polarization")
    periods = (
        compton_section.get("periods")
        if isinstance(compton_section, Mapping)
        else None
    )
    if not isinstance(periods, list):
        raise PolarizationContractError("canonical config lacks Compton periods")
    compton_files = []
    for period in periods:
        if not isinstance(period, Mapping):
            raise PolarizationContractError("Compton period must be an object")
        source_period = _canonical_text(
            period.get("source_period"), "Compton source_period"
        )
        if source_period not in curves:
            raise PolarizationContractError(
                f"parsed Compton curve missing for source_period {source_period}"
            )
        compton_files.append(
            PeriodComptonAuthority(
                source_period,
                _source_file(
                    root,
                    period.get("source"),
                    f"Compton authority for {source_period}",
                ),
            )
        )
    if len({item.source_period for item in compton_files}) != len(compton_files):
        raise PolarizationContractError("Compton source_period must be unique")
    for curve in curves.values():
        curve.energies_mev.setflags(write=False)
        curve.values.setflags(write=False)
        curve.covariance.setflags(write=False)
    immutable_curves = MappingProxyType(dict(curves))

    flux_rows = _parse_flux_rows(
        flux_file.path,
        target=config.figure4_target,
        gate0_run_numbers=gate0_runs,
    )
    mapped_periods = {interval.source_period for interval in state_map}
    compton_periods = set(immutable_curves)
    for row in flux_rows:
        if row.source_period not in mapped_periods:
            raise PolarizationContractError(
                f"count flux source_period {row.source_period} lacks state mapping"
            )
        if row.source_period not in compton_periods:
            raise PolarizationContractError(
                f"count flux source_period {row.source_period} lacks Compton authority"
            )

    retained_files = (
        config_file,
        gate0_file,
        *bundle_files,
        inventory_file,
        *n2_files,
        state_file,
        *[item.file for item in compton_files],
        *acceptance_files,
    )
    if any(sha256_file(item.path) != item.sha256 for item in retained_files):
        raise PolarizationContractError(
            "count authority file changed during validation"
        )
    return CountAuthority(
        repository_root=root,
        fit_release_id=release_id,
        bin_set_id=bins_id,
        config=config,
        config_file=config_file,
        gate0_handoff_file=gate0_file,
        gate0_bundle_files=bundle_files,
        flux_file=flux_file,
        gate0_run_numbers=gate0_runs,
        n2_inventory=inventory,
        n2_inventory_file=inventory_file,
        n2_files=n2_files,
        response=acceptance.response,
        acceptance_files=acceptance_files,
        state_map=state_map,
        state_mapping_file=state_file,
        compton=immutable_curves,
        compton_files=tuple(compton_files),
        flux_rows=flux_rows,
        _loader_token=_COUNT_AUTHORITY_TOKEN,
    )


@dataclass(frozen=True)
class CountExposure:
    """One validated flux/Compton authority cell used by the N2 projector.

    ``input_sha256`` identifies the exact observable-run flux input. The
    unsaved ``source_stage`` and ``n2_inventory_path`` fields make the N2
    origin explicit at construction time; only their anchored inventory
    digest is repeated in the count CSV schema.
    """

    fit_release_id: str
    bin_set_id: str
    channel: str
    target: str
    beam_group: str
    source_period: str
    Egamma_low: float
    Egamma_high: float
    cos_theta_low: float
    cos_theta_high: float
    selection_id: str
    orientation: str
    exposure: float
    beam_polarization: float
    beam_polarization_variance: float
    source_stage: str
    n2_inventory_path: str
    gate0_handoff_sha256: str
    n2_reconstruction_sha256: str
    state_mapping_sha256: str
    compton_source_sha256: str
    config_sha256: str
    input_sha256: str


@dataclass(frozen=True)
class AzimuthCountRow:
    schema_version: int
    analysis_version: str
    fit_release_id: str
    bin_set_id: str
    channel: str
    target: str
    beam_group: str
    source_period: str
    Egamma_low: float
    Egamma_high: float
    cos_theta_low: float
    cos_theta_high: float
    observable: str
    selection_id: str
    orientation: str
    replica_id: int
    reco_mass_bin: int
    reco_mass_low_gev: float
    reco_mass_high_gev: float
    reco_phi_bin: int
    reco_phi_low: float
    reco_phi_high: float
    observed_count: int
    exposure: float
    beam_polarization: float
    beam_polarization_variance: float
    gate0_handoff_sha256: str
    n2_reconstruction_sha256: str
    state_mapping_sha256: str
    compton_source_sha256: str
    config_sha256: str
    input_sha256: str


def _row_order(row: AzimuthCountRow) -> tuple:
    return (
        row.schema_version,
        row.analysis_version,
        row.fit_release_id,
        row.bin_set_id,
        row.channel,
        row.target,
        row.beam_group,
        row.source_period,
        row.Egamma_low,
        row.Egamma_high,
        row.cos_theta_low,
        row.cos_theta_high,
        row.observable,
        row.selection_id,
        row.orientation,
        row.replica_id,
        row.reco_mass_bin,
        row.reco_phi_bin,
    )


def _count_group(row: AzimuthCountRow) -> tuple:
    return _row_order(row)[:15]


def _physical_count_group(row: AzimuthCountRow) -> tuple:
    return (
        row.schema_version,
        row.analysis_version,
        row.fit_release_id,
        row.bin_set_id,
        row.channel,
        row.target,
        row.beam_group,
        row.source_period,
        row.Egamma_low,
        row.Egamma_high,
        row.cos_theta_low,
        row.cos_theta_high,
        row.selection_id,
    )


def _has_contiguous_partition(
    rows: Sequence[AzimuthCountRow],
    *,
    index_name: str,
    low_name: str,
    high_name: str,
    required_low: float | None = None,
    required_high: float | None = None,
) -> bool:
    """Check that one axis has stable, contiguous bin edges."""
    by_index: dict[int, set[tuple[float, float]]] = {}
    for row in rows:
        index = getattr(row, index_name)
        by_index.setdefault(index, set()).add(
            (getattr(row, low_name), getattr(row, high_name))
        )
    if tuple(sorted(by_index)) != tuple(range(len(by_index))):
        return False
    edges = []
    for index in range(len(by_index)):
        values = by_index[index]
        if len(values) != 1:
            return False
        edges.append(next(iter(values)))
    if required_low is not None and not math.isclose(
        edges[0][0], required_low, rel_tol=0.0, abs_tol=1e-14
    ):
        return False
    if required_high is not None and not math.isclose(
        edges[-1][1], required_high, rel_tol=0.0, abs_tol=1e-14
    ):
        return False
    return all(
        math.isclose(left[1], right[0], rel_tol=0.0, abs_tol=1e-14)
        for left, right in zip(edges, edges[1:])
    )


@dataclass(frozen=True)
class AzimuthCountTable:
    rows: tuple[AzimuthCountRow, ...]

    def __post_init__(self) -> None:
        if not self.rows:
            raise PolarizationContractError("azimuth count table must contain rows")
        ordering = tuple(_row_order(row) for row in self.rows)
        if ordering != tuple(sorted(ordering)) or len(set(ordering)) != len(ordering):
            raise PolarizationContractError(
                "azimuth count rows must be unique and in canonical order"
            )
        for row in self.rows:
            _validate_count_row(row)
        for name in (
            "analysis_version",
            "fit_release_id",
            "gate0_handoff_sha256",
            "n2_reconstruction_sha256",
            "state_mapping_sha256",
            "config_sha256",
            "input_sha256",
        ):
            if len({getattr(row, name) for row in self.rows}) != 1:
                raise PolarizationContractError(
                    "azimuth count rows mix incompatible publication provenance"
                )
        period_compton: dict[str, set[str]] = {}
        for row in self.rows:
            period_compton.setdefault(row.source_period, set()).add(
                row.compton_source_sha256
            )
        if any(len(hashes) != 1 for hashes in period_compton.values()):
            raise PolarizationContractError(
                "azimuth count rows mix Compton authorities within a source period"
            )

    @property
    def replica_ids(self) -> tuple[int, ...]:
        """Return the complete ordered nominal-plus-bootstrap replica IDs."""
        return tuple(sorted({row.replica_id for row in self.rows}))

    def sum_for(self, observable: str, replica_id: int) -> int:
        """Sum all reconstructed cells for one observable and replica."""
        if observable not in PAIR_NAMES:
            raise PolarizationContractError(f"unknown pair observable: {observable}")
        if replica_id not in self.replica_ids:
            raise PolarizationContractError(f"unknown bootstrap replica: {replica_id}")
        return sum(
            row.observed_count
            for row in self.rows
            if row.observable == observable and row.replica_id == replica_id
        )

    def has_every_reco_cell(self) -> bool:
        """Report whether every present physical group has a full replica grid."""
        replicas = self.replica_ids
        if not replicas or replicas != tuple(range(replicas[-1] + 1)):
            return False
        coverage: dict[tuple, set[tuple[str, str]]] = {}
        for row in self.rows:
            coverage.setdefault(_physical_count_group(row), set()).add(
                (row.observable, row.orientation)
            )
        expected_coverage = {
            (observable, orientation)
            for observable in PAIR_NAMES
            for orientation in ORIENTATIONS
        }
        if any(pairs != expected_coverage for pairs in coverage.values()):
            return False
        grouped: dict[tuple, dict[int, list[AzimuthCountRow]]] = {}
        for row in self.rows:
            grouped.setdefault(_count_group(row), {}).setdefault(
                row.replica_id, []
            ).append(row)
        for by_replica in grouped.values():
            if tuple(sorted(by_replica)) != replicas:
                return False
            reference = by_replica[0]
            mass_bins = sorted({row.reco_mass_bin for row in reference})
            phi_bins = sorted({row.reco_phi_bin for row in reference})
            if mass_bins != list(range(len(mass_bins))) or phi_bins != list(
                range(len(phi_bins))
            ):
                return False
            if not _has_contiguous_partition(
                reference,
                index_name="reco_mass_bin",
                low_name="reco_mass_low_gev",
                high_name="reco_mass_high_gev",
            ) or not _has_contiguous_partition(
                reference,
                index_name="reco_phi_bin",
                low_name="reco_phi_low",
                high_name="reco_phi_high",
                required_low=0.0,
                required_high=math.pi,
            ):
                return False
            expected = {
                (mass_bin, phi_bin)
                for mass_bin in mass_bins
                for phi_bin in phi_bins
            }
            reference_edges = {
                (
                    row.reco_mass_bin,
                    row.reco_phi_bin,
                    row.reco_mass_low_gev,
                    row.reco_mass_high_gev,
                    row.reco_phi_low,
                    row.reco_phi_high,
                )
                for row in reference
            }
            for rows in by_replica.values():
                cells = [(row.reco_mass_bin, row.reco_phi_bin) for row in rows]
                if len(cells) != len(expected) or set(cells) != expected:
                    return False
                if {
                    (
                        row.reco_mass_bin,
                        row.reco_phi_bin,
                        row.reco_mass_low_gev,
                        row.reco_mass_high_gev,
                        row.reco_phi_low,
                        row.reco_phi_high,
                    )
                    for row in rows
                } != reference_edges:
                    return False
        return True


def _canonical_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise PolarizationContractError(f"{label} must be non-empty and canonical")
    return value


def _digest(value: object, label: str) -> str:
    if not isinstance(value, str) or SHA256_PATTERN.fullmatch(value) is None:
        raise PolarizationContractError(f"{label} must be lowercase SHA-256")
    return value


def _finite(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PolarizationContractError(f"{label} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise PolarizationContractError(f"{label} must be finite")
    return result


def _validate_count_row(row: AzimuthCountRow) -> None:
    if not isinstance(row, AzimuthCountRow):
        raise PolarizationContractError("azimuth count table contains a non-row value")
    if type(row.schema_version) is not int or row.schema_version != 1:
        raise PolarizationContractError("azimuth count schema_version must be integer 1")
    for name in (
        "analysis_version", "fit_release_id", "bin_set_id", "channel", "target",
        "beam_group", "source_period", "selection_id",
    ):
        _canonical_text(getattr(row, name), f"azimuth count {name}")
    if row.analysis_version != "polarization-v1":
        raise PolarizationContractError("azimuth count analysis_version is unsupported")
    if row.observable not in PAIR_NAMES:
        raise PolarizationContractError("azimuth count observable is invalid")
    if row.orientation not in ORIENTATIONS:
        raise PolarizationContractError("azimuth count orientation is invalid")
    for name in ("replica_id", "reco_mass_bin", "reco_phi_bin", "observed_count"):
        value = getattr(row, name)
        if type(value) is not int or value < 0:
            raise PolarizationContractError(
                f"azimuth count {name} must be a nonnegative integer"
            )
    numeric = {
        name: _finite(getattr(row, name), f"azimuth count {name}")
        for name in (
            "Egamma_low", "Egamma_high", "cos_theta_low", "cos_theta_high",
            "reco_mass_low_gev", "reco_mass_high_gev", "reco_phi_low",
            "reco_phi_high", "exposure", "beam_polarization",
            "beam_polarization_variance",
        )
    }
    if numeric["Egamma_low"] >= numeric["Egamma_high"]:
        raise PolarizationContractError("azimuth count energy bin is reversed")
    if not -1.0 <= numeric["cos_theta_low"] < numeric["cos_theta_high"] <= 1.0:
        raise PolarizationContractError("azimuth count cosine bin is invalid")
    if numeric["reco_mass_low_gev"] >= numeric["reco_mass_high_gev"]:
        raise PolarizationContractError("azimuth count mass bin is reversed")
    if not 0.0 <= numeric["reco_phi_low"] < numeric["reco_phi_high"] <= math.pi:
        raise PolarizationContractError("azimuth count azimuth bin must lie in [0,pi]")
    if numeric["exposure"] <= 0.0:
        raise PolarizationContractError("azimuth count exposure must be positive")
    if not 0.0 < numeric["beam_polarization"] <= 1.0:
        raise PolarizationContractError("azimuth count beam polarization must lie in (0,1]")
    if numeric["beam_polarization_variance"] < 0.0:
        raise PolarizationContractError(
            "azimuth count beam polarization variance must be nonnegative"
        )
    for name in (
        "gate0_handoff_sha256", "n2_reconstruction_sha256",
        "state_mapping_sha256", "compton_source_sha256", "config_sha256",
        "input_sha256",
    ):
        _digest(getattr(row, name), f"azimuth count {name}")


def event_bootstrap_weight(
    file_sha256: str,
    tree: str,
    entry: int,
    replica_id: int,
    *,
    algorithm: str,
    seed: int,
) -> int:
    """Return the deterministic Poisson(1) multiplier for one stable N2 event.

    Version 1 hashes the six UTF-8 fields below with NUL separators. The
    big-endian 256-bit digest is mapped to the midpoint of its equal-width
    interval, ``(integer + 1/2) / 2**256``, and inverted with the Poisson(1)
    probability recurrence. Replica zero is the unresampled nominal event.
    """
    file_digest = _digest(file_sha256, "N2 file SHA-256")
    tree_name = _canonical_text(tree, "ROOT tree name")
    if "\0" in tree_name:
        raise PolarizationContractError("ROOT tree name must not contain NUL")
    if algorithm != BOOTSTRAP_ALGORITHM_VERSION:
        raise PolarizationContractError("unsupported bootstrap algorithm")
    for value, label in (
        (entry, "tree entry"),
        (replica_id, "replica_id"),
        (seed, "bootstrap seed"),
    ):
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise PolarizationContractError(f"{label} must be a nonnegative integer")
    if replica_id == 0:
        return 1
    payload = "\0".join(
        (
            algorithm,
            str(seed),
            str(replica_id),
            file_digest,
            tree_name,
            str(entry),
        )
    ).encode("utf-8")
    integer = int.from_bytes(sha256(payload).digest(), "big")
    with localcontext() as context:
        context.prec = 110
        uniform = (Decimal(integer) + Decimal("0.5")) / (Decimal(2) ** 256)
        probability = (-Decimal(1)).exp()
        cumulative = probability
        value = 0
        while uniform > cumulative:
            value += 1
            probability /= value
            cumulative += probability
    return value


def _validate_sample(sample: EventSample, tree: str) -> int:
    if not isinstance(sample, EventSample):
        raise PolarizationContractError("counts require an EventSample derived from N2")
    one_dimensional = (
        sample.beam_energy,
        sample.run_number,
        sample.state_code,
        sample.xstrip,
        sample.file_sha256,
        sample.tree_entry,
    )
    if any(np.asarray(array).ndim != 1 for array in one_dimensional):
        raise PolarizationContractError("N2 event metadata must be one-dimensional")
    event_count = len(sample.beam_energy)
    if event_count == 0 or any(len(array) != event_count for array in one_dimensional):
        raise PolarizationContractError("N2 event metadata must have equal nonzero length")
    for name, vectors in (("proton", sample.proton), ("eta", sample.eta), ("pi0", sample.pi0)):
        array = np.asarray(vectors)
        if array.shape != (event_count, 4):
            raise PolarizationContractError(f"N2 {name} vectors must have shape (events, 4)")
    numeric = (sample.beam_energy, sample.xstrip, sample.proton, sample.eta, sample.pi0)
    if any(not np.all(np.isfinite(np.asarray(array, dtype=float))) for array in numeric):
        raise PolarizationContractError("N2 event sample contains non-finite values")
    runs = np.asarray(sample.run_number)
    states = np.asarray(sample.state_code)
    if (
        not np.issubdtype(runs.dtype, np.integer)
        or not np.issubdtype(states.dtype, np.integer)
        or np.any(runs <= 0)
    ):
        raise PolarizationContractError(
            "N2 RunNumber and Polarization metadata must be integer-valued"
        )
    entries = np.asarray(sample.tree_entry)
    if not np.issubdtype(entries.dtype, np.integer) or np.any(entries < 0):
        raise PolarizationContractError("N2 tree entries must be nonnegative integers")
    identities = []
    for digest, entry in zip(sample.file_sha256, entries):
        identities.append((_digest(str(digest), "N2 file SHA-256"), tree, int(entry)))
    if len(set(identities)) != event_count:
        raise PolarizationContractError("N2 stable event identity must be unique")
    return event_count


def _exposure_group(exposure: CountExposure) -> tuple:
    return (
        exposure.fit_release_id,
        exposure.bin_set_id,
        exposure.channel,
        exposure.target,
        exposure.beam_group,
        exposure.source_period,
        exposure.Egamma_low,
        exposure.Egamma_high,
        exposure.cos_theta_low,
        exposure.cos_theta_high,
        exposure.selection_id,
        exposure.source_stage,
        exposure.n2_inventory_path,
        exposure.gate0_handoff_sha256,
        exposure.n2_reconstruction_sha256,
        exposure.state_mapping_sha256,
        exposure.compton_source_sha256,
        exposure.config_sha256,
        exposure.input_sha256,
    )


def _exposure_order(exposure: CountExposure) -> tuple:
    return _exposure_group(exposure)[:11] + (exposure.orientation,)


def _validate_exposures(
    raw: Sequence[CountExposure],
    *,
    config: AnalysisConfig,
    state_map: tuple[StateInterval, ...],
    compton: Mapping[str, PolarizationCurve],
) -> tuple[CountExposure, ...]:
    try:
        exposures = tuple(raw)
    except TypeError as exc:
        raise PolarizationContractError("count exposures must be a sequence") from exc
    if not exposures or any(
        not isinstance(item, CountExposure) for item in exposures
    ):
        raise PolarizationContractError("count exposures must contain CountExposure records")
    energy_bins = tuple(
        zip(config.figure4_energy_edges_gev, config.figure4_energy_edges_gev[1:])
    )
    keys = set()
    groups: dict[tuple, set[str]] = {}
    release_ids = set()
    common_provenance = set()
    for item in exposures:
        for name in (
            "fit_release_id", "bin_set_id", "channel", "target", "beam_group",
            "source_period", "selection_id",
        ):
            _canonical_text(getattr(item, name), name)
        if item.source_stage != "N2":
            raise PolarizationContractError(
                "count construction accepts N2 events only; N4 is forbidden"
            )
        for name in (
            "gate0_handoff_sha256", "n2_reconstruction_sha256",
            "state_mapping_sha256", "compton_source_sha256", "config_sha256",
            "input_sha256",
        ):
            _digest(getattr(item, name), name)
        if item.orientation not in ORIENTATIONS:
            raise PolarizationContractError("count exposure orientation is invalid")
        values = {
            name: _finite(getattr(item, name), name)
            for name in (
                "Egamma_low", "Egamma_high", "cos_theta_low", "cos_theta_high",
                "exposure", "beam_polarization", "beam_polarization_variance",
            )
        }
        if values["Egamma_low"] >= values["Egamma_high"] or (
            values["Egamma_low"], values["Egamma_high"]
        ) not in energy_bins:
            raise PolarizationContractError("count exposure energy bin disagrees with config")
        if not -1.0 <= values["cos_theta_low"] < values["cos_theta_high"] <= 1.0:
            raise PolarizationContractError("count exposure cosine bin is invalid")
        if values["exposure"] <= 0.0:
            raise PolarizationContractError("count exposure must be positive")
        if not 0.0 < values["beam_polarization"] <= 1.0:
            raise PolarizationContractError("count beam polarization must lie in (0,1]")
        if values["beam_polarization_variance"] < 0.0:
            raise PolarizationContractError("count beam polarization variance must be nonnegative")
        if item.target != config.figure4_target:
            raise PolarizationContractError("count exposure target disagrees with config")
        curve = compton.get(item.source_period)
        if not isinstance(curve, PolarizationCurve):
            raise PolarizationContractError(
                f"approved Compton curve missing for source_period {item.source_period}"
            )
        expected_polarization, expected_variance = curve.bin_average(
            1000.0 * item.Egamma_low, 1000.0 * item.Egamma_high
        )
        polarization_matches = np.isclose(
            item.beam_polarization,
            expected_polarization,
            rtol=1e-12,
            atol=1e-14,
        )
        variance_matches = np.isclose(
            item.beam_polarization_variance,
            expected_variance,
            rtol=1e-12,
            atol=1e-14,
        )
        if not polarization_matches or not variance_matches:
            raise PolarizationContractError(
                "count beam polarization/variance disagrees with Compton authority"
            )
        if not any(
            interval.source_period == item.source_period
            and interval.orientation == item.orientation
            for interval in state_map
        ):
            raise PolarizationContractError(
                "count exposure period/orientation lacks state-map coverage"
            )
        key = _exposure_order(item)
        if key in keys:
            raise PolarizationContractError("count exposures must be canonically unique")
        keys.add(key)
        groups.setdefault(_exposure_group(item), set()).add(item.orientation)
        release_ids.add(item.fit_release_id)
        common_provenance.add(
            (
                item.n2_inventory_path,
                item.gate0_handoff_sha256,
                item.n2_reconstruction_sha256,
                item.state_mapping_sha256,
                item.config_sha256,
                item.input_sha256,
            )
        )
    if len(release_ids) != 1:
        raise PolarizationContractError("count exposures require one fit_release_id")
    if len(common_provenance) != 1:
        raise PolarizationContractError(
            "count exposures must share Gate 0, N2, state-map, config, and flux provenance"
        )
    if any(orientations != set(ORIENTATIONS) for orientations in groups.values()):
        raise PolarizationContractError(
            "each physical key/source_period requires both orientations"
        )
    return tuple(sorted(exposures, key=_exposure_order))


def _validate_mass_edges(
    raw: Mapping[str, np.ndarray], bins: int
) -> dict[str, np.ndarray]:
    if not isinstance(raw, Mapping) or set(raw) != set(PAIR_NAMES):
        raise PolarizationContractError(
            "mass_edges must define exactly the three pair observables"
        )
    result = {}
    for observable in PAIR_NAMES:
        edges = np.asarray(raw[observable], dtype=float)
        if (
            edges.shape != (bins + 1,)
            or not np.all(np.isfinite(edges))
            or not np.all(np.diff(edges) > 0.0)
        ):
            raise PolarizationContractError(
                f"{observable} mass edges must define the approved finite partition"
            )
        result[observable] = edges
    return result


def _event_interval(
    run_number: int, state_code: int, intervals: tuple[StateInterval, ...]
) -> StateInterval:
    matches = tuple(
        interval
        for interval in intervals
        if interval.state_code == state_code
        and interval.run_start <= run_number <= interval.run_end
    )
    if len(matches) != 1:
        qualifier = "unmapped" if not matches else "ambiguous"
        raise PolarizationContractError(
            f"{qualifier} N2 state: run={run_number}, state_code={state_code}"
        )
    return matches[0]


def _energy_bin(energy: float, edges: tuple[float, ...]) -> int | None:
    if energy < edges[0] or energy > edges[-1]:
        return None
    index = int(np.searchsorted(edges, energy, side="right") - 1)
    return min(index, len(edges) - 2)


def _histogram_bin(value: float, edges: np.ndarray) -> int | None:
    if value < edges[0] or value > edges[-1]:
        return None
    index = int(np.searchsorted(edges, value, side="right") - 1)
    return min(index, len(edges) - 2)


def build_azimuth_counts(
    sample: EventSample,
    *,
    config: AnalysisConfig,
    state_map,
    exposures,
    compton,
    mass_edges: Mapping[str, np.ndarray],
) -> AzimuthCountTable:
    """Project metadata-bearing N2 events into complete replayable count grids."""
    if (
        not isinstance(config, AnalysisConfig)
        or config.status != "approved"
        or config.blocked_reasons
    ):
        raise PolarizationContractError("azimuth counts require approved canonical config")
    bootstrap = config.bootstrap
    if (
        bootstrap.algorithm_version != BOOTSTRAP_ALGORITHM_VERSION
        or isinstance(bootstrap.replicas, bool)
        or not isinstance(bootstrap.replicas, int)
        or bootstrap.replicas <= 0
        or isinstance(bootstrap.seed, bool)
        or not isinstance(bootstrap.seed, int)
        or bootstrap.seed < 0
    ):
        raise PolarizationContractError("azimuth counts require approved bootstrap configuration")
    event_count = _validate_sample(sample, config.figure4_tree)
    intervals = validate_intervals(state_map)
    if not isinstance(compton, Mapping):
        raise PolarizationContractError("Compton authority must map source periods to curves")
    authority_cells = _validate_exposures(
        exposures, config=config, state_map=intervals, compton=compton
    )
    sigma_keys = {
        (
            cell.fit_release_id,
            cell.bin_set_id,
            cell.channel,
            cell.target,
            cell.beam_group,
            cell.Egamma_low,
            cell.Egamma_high,
            cell.cos_theta_low,
            cell.cos_theta_high,
            cell.selection_id,
        )
        for cell in authority_cells
    }
    sigma_vector_dimension = (
        len(sigma_keys) * len(PAIR_NAMES) * config.figure4_mass_bins
    )
    if bootstrap.replicas <= sigma_vector_dimension:
        raise PolarizationContractError(
            "bootstrap replicas must exceed the published Sigma-vector dimension"
        )
    edges_by_observable = _validate_mass_edges(mass_edges, config.figure4_mass_bins)
    phi_edges = np.linspace(0.0, np.pi, config.figure4_phi_bins + 1)
    observables = event_pair_observables(sample.proton, sample.eta, sample.pi0)
    counts: dict[tuple[int, int, str, int, int], int] = {}
    for exposure_index in range(len(authority_cells)):
        for replica_id in range(bootstrap.replicas + 1):
            for observable in PAIR_NAMES:
                for mass_bin in range(config.figure4_mass_bins):
                    for phi_bin in range(config.figure4_phi_bins):
                        counts[exposure_index, replica_id, observable, mass_bin, phi_bin] = 0

    energy_edges = config.figure4_energy_edges_gev
    for event_index in range(event_count):
        run_number = int(sample.run_number[event_index])
        state_code = int(sample.state_code[event_index])
        interval = _event_interval(run_number, state_code, intervals)
        energy = float(sample.beam_energy[event_index])
        energy_index = _energy_bin(energy, energy_edges)
        if energy_index is None:
            continue
        low, high = energy_edges[energy_index], energy_edges[energy_index + 1]
        matching_exposures = [
            index
            for index, cell in enumerate(authority_cells)
            if cell.source_period == interval.source_period
            and cell.orientation == interval.orientation
            and cell.Egamma_low == low
            and cell.Egamma_high == high
        ]
        if len(matching_exposures) != 1:
            qualifier = "missing" if not matching_exposures else "ambiguous"
            raise PolarizationContractError(
                f"{qualifier} count exposure for mapped N2 event"
            )
        exposure_index = matching_exposures[0]
        weights = tuple(
            event_bootstrap_weight(
                str(sample.file_sha256[event_index]),
                config.figure4_tree,
                int(sample.tree_entry[event_index]),
                replica_id,
                algorithm=bootstrap.algorithm_version,
                seed=bootstrap.seed,
            )
            for replica_id in range(bootstrap.replicas + 1)
        )
        for observable, projected in observables.items():
            if not projected.valid_phi[event_index]:
                continue
            mass_bin = _histogram_bin(
                float(projected.mass[event_index]), edges_by_observable[observable]
            )
            phi_bin = _histogram_bin(float(projected.phi[event_index]), phi_edges)
            if mass_bin is None or phi_bin is None:
                continue
            for replica_id, weight in enumerate(weights):
                counts[exposure_index, replica_id, observable, mass_bin, phi_bin] += weight

    rows = []
    for exposure_index, authority in enumerate(authority_cells):
        for observable in sorted(PAIR_NAMES):
            observable_edges = edges_by_observable[observable]
            for replica_id in range(bootstrap.replicas + 1):
                for mass_bin in range(config.figure4_mass_bins):
                    for phi_bin in range(config.figure4_phi_bins):
                        rows.append(
                            AzimuthCountRow(
                                schema_version=1,
                                analysis_version=config.analysis_version,
                                fit_release_id=authority.fit_release_id,
                                bin_set_id=authority.bin_set_id,
                                channel=authority.channel,
                                target=authority.target,
                                beam_group=authority.beam_group,
                                source_period=authority.source_period,
                                Egamma_low=authority.Egamma_low,
                                Egamma_high=authority.Egamma_high,
                                cos_theta_low=authority.cos_theta_low,
                                cos_theta_high=authority.cos_theta_high,
                                observable=observable,
                                selection_id=authority.selection_id,
                                orientation=authority.orientation,
                                replica_id=replica_id,
                                reco_mass_bin=mass_bin,
                                reco_mass_low_gev=float(observable_edges[mass_bin]),
                                reco_mass_high_gev=float(observable_edges[mass_bin + 1]),
                                reco_phi_bin=phi_bin,
                                reco_phi_low=float(phi_edges[phi_bin]),
                                reco_phi_high=float(phi_edges[phi_bin + 1]),
                                observed_count=counts[
                                    exposure_index,
                                    replica_id,
                                    observable,
                                    mass_bin,
                                    phi_bin,
                                ],
                                exposure=authority.exposure,
                                beam_polarization=authority.beam_polarization,
                                beam_polarization_variance=authority.beam_polarization_variance,
                                gate0_handoff_sha256=authority.gate0_handoff_sha256,
                                n2_reconstruction_sha256=authority.n2_reconstruction_sha256,
                                state_mapping_sha256=authority.state_mapping_sha256,
                                compton_source_sha256=authority.compton_source_sha256,
                                config_sha256=authority.config_sha256,
                                input_sha256=authority.input_sha256,
                            )
                        )
    rows.sort(key=_row_order)
    table = AzimuthCountTable(tuple(rows))
    if not table.has_every_reco_cell():
        raise PolarizationContractError("azimuth count table is missing reconstructed cells")
    return table


def write_azimuth_counts(table: AzimuthCountTable, path: Path) -> str:
    """Write the exact canonical CSV schema and return its lowercase SHA-256."""
    if not isinstance(table, AzimuthCountTable) or not table.has_every_reco_cell():
        raise PolarizationContractError("cannot serialize an incomplete azimuth count table")
    path = Path(path)
    try:
        with path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(
                stream, fieldnames=AZIMUTH_COUNT_FIELDS, lineterminator="\n"
            )
            writer.writeheader()
            for row in table.rows:
                writer.writerow(
                    {field.name: getattr(row, field.name) for field in fields(row)}
                )
    except OSError as exc:
        raise PolarizationContractError(f"cannot write azimuth counts CSV: {path}") from exc
    return sha256_file(path)
