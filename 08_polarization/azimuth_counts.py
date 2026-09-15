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
from acceptance_handoff import (
    ResponseCovarianceScope,
    ResponsePeriodCoverage,
    validate_acceptance_handoff,
)
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
from phi_response import PhiResponse, ResponseKey
from reco_inventory import RecoInventory, load_gate0_run_numbers, load_reco_inventory
from root_events import EventSample, read_reco_root
from state_mapping import (
    StateInterval,
    load_state_mapping,
    validate_intervals,
)
from graal_common.strip_energy_flux import normalize_xstrip


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
CANONICAL_LOOKUP_PATH = "results/observable_runs/strip_energy_lookup.csv"
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
_LOOKUP_REQUIRED_FIELDS = (
    "run_number", "source_period", "target", "beam_type", "group",
    "xstrip", "event_count", "energy_median_gev", "energy_mad_gev",
    "energy_min_gev", "energy_max_gev", "provenance",
)


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
class StripEnergyLookupRow:
    run_number: int
    source_period: str
    target: str
    beam_type: str
    beam_group: str
    xstrip: int
    event_count: int
    energy_median_gev: float
    energy_mad_gev: float
    energy_min_gev: float
    energy_max_gev: float
    provenance: str


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
    gate0_manifest_file: AuthenticatedFile
    gate0_bundle_files: tuple[AuthenticatedFile, ...]
    flux_file: AuthenticatedFile
    strip_energy_lookup_file: AuthenticatedFile
    gate0_run_numbers: frozenset[int]
    n2_inventory: RecoInventory
    n2_inventory_file: AuthenticatedFile
    n2_processed_run_ledger_file: AuthenticatedFile
    n2_files: tuple[AuthenticatedFile, ...]
    response: PhiResponse
    response_covariance_scope: ResponseCovarianceScope
    response_period_coverage: tuple[ResponsePeriodCoverage, ...]
    acceptance_files: tuple[AuthenticatedFile, ...]
    n3_schema_file: AuthenticatedFile
    state_map: tuple[StateInterval, ...]
    state_mapping_file: AuthenticatedFile
    compton: Mapping[str, PolarizationCurve]
    compton_files: tuple[PeriodComptonAuthority, ...]
    flux_rows: tuple[FluxAuthorityRow, ...]
    strip_energy_lookup_rows: tuple[StripEnergyLookupRow, ...]
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

    @property
    def n2_file_sha256s(self) -> frozenset[str]:
        """Return the exact reconstruction-file digest set authenticated by N2."""
        return frozenset(item.sha256 for item in self.n2_files)


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


def _parse_strip_energy_lookup(
    path: Path,
    *,
    target: str,
    gate0_run_numbers: frozenset[int],
) -> tuple[StripEnergyLookupRow, ...]:
    try:
        stream = Path(path).open(newline="", encoding="utf-8")
    except OSError as exc:
        raise PolarizationContractError(
            f"cannot read strip-energy lookup CSV: {path}"
        ) from exc
    rows = []
    keys = set()
    with stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != _LOOKUP_REQUIRED_FIELDS:
            raise PolarizationContractError(
                "strip-energy lookup CSV must contain exact canonical columns"
            )
        for row_number, raw in enumerate(reader, start=2):
            try:
                run_number = int(raw["run_number"])
                xstrip = int(raw["xstrip"])
                event_count = int(raw["event_count"])
                median = float(raw["energy_median_gev"])
                mad = float(raw["energy_mad_gev"])
                low = float(raw["energy_min_gev"])
                high = float(raw["energy_max_gev"])
            except (TypeError, ValueError) as exc:
                raise PolarizationContractError(
                    f"strip-energy lookup row {row_number} has invalid numeric fields"
                ) from exc
            try:
                canonical_strip = normalize_xstrip(float(xstrip))
            except ValueError as exc:
                raise PolarizationContractError(
                    f"strip-energy lookup row {row_number} has invalid Xstrip"
                ) from exc
            source_period = _canonical_text(
                raw["source_period"], f"strip-energy lookup row {row_number} source_period"
            )
            row_target = _canonical_text(
                raw["target"], f"strip-energy lookup row {row_number} target"
            )
            beam_type = _canonical_text(
                raw["beam_type"], f"strip-energy lookup row {row_number} beam_type"
            )
            beam_group = _canonical_text(
                raw["group"], f"strip-energy lookup row {row_number} group"
            )
            provenance = _canonical_text(
                raw["provenance"], f"strip-energy lookup row {row_number} provenance"
            )
            if (
                run_number <= 0
                or canonical_strip != xstrip
                or event_count <= 0
                or not all(math.isfinite(value) for value in (median, mad, low, high))
                or mad < 0.0
                or not low <= median <= high
            ):
                raise PolarizationContractError(
                    f"strip-energy lookup row {row_number} is nonphysical"
                )
            if run_number not in gate0_run_numbers or row_target != target:
                continue
            key = (run_number, xstrip)
            if key in keys:
                raise PolarizationContractError(
                    "strip-energy lookup rows must map RunNumber/Xstrip uniquely"
                )
            keys.add(key)
            rows.append(
                StripEnergyLookupRow(
                    run_number, source_period, row_target, beam_type, beam_group,
                    xstrip, event_count, median, mad, low, high, provenance,
                )
            )
    if not rows:
        raise PolarizationContractError(
            "strip-energy lookup has no rows for selected target/Gate 0 runs"
        )
    return tuple(sorted(rows, key=lambda row: (row.run_number, row.xstrip)))


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
    gate0_manifest_file = _authenticated_file(
        root,
        gate0.get("manifest_path"),
        "Gate 0 curated manifest",
        expected_sha256=gate0.get("manifest_sha256"),
    )
    bundle_files = _gate0_bundle_files(root, gate0)
    bundle_by_path = {item.relative_path: item for item in bundle_files}
    flux_file = bundle_by_path[CANONICAL_FLUX_PATH]
    lookup_file = bundle_by_path[CANONICAL_LOOKUP_PATH]
    runs_file = bundle_by_path[CANONICAL_RUNS_PATH]
    gate0_runs = load_gate0_run_numbers(runs_file.path, target=config.figure4_target)

    inventory_file = _authenticated_file(
        root, n2_inventory_path, "N2 reconstruction inventory"
    )
    raw_inventory = load_json(inventory_file.path)
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
    raw_n2_files = raw_inventory.get("files")
    if not isinstance(raw_n2_files, list):
        raise PolarizationContractError(
            "N2 reconstruction inventory file records are unavailable"
        )
    n2_files = tuple(
        sorted(
            (
                _authenticated_file(
                    root,
                    record.get("path"),
                    "N2 reconstruction file",
                    expected_sha256=record.get("sha256"),
                )
                for record in raw_n2_files
            ),
            key=lambda item: item.relative_path,
        )
    )
    if tuple(item.path for item in n2_files) != tuple(sorted(inventory.paths)):
        raise PolarizationContractError(
            "authenticated N2 files disagree with reconstruction inventory"
        )
    ledger_record = raw_inventory.get("processed_run_ledger")
    if not isinstance(ledger_record, Mapping):
        raise PolarizationContractError(
            "N2 reconstruction inventory processed-run ledger is unavailable"
        )
    ledger_file = _authenticated_file(
        root,
        ledger_record.get("path"),
        "N2 processed-run ledger",
        expected_sha256=ledger_record.get("sha256"),
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
    n3_schema_file = _relative_authenticated_file(
        root,
        acceptance.schema_path,
        "N3 phi-response schema",
        expected_sha256=acceptance.schema_sha256,
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

    parsed_flux_rows = _parse_flux_rows(
        flux_file.path,
        target=config.figure4_target,
        gate0_run_numbers=gate0_runs,
    )
    response_flux_universe = {
        (key.target, key.beam_group, key.Egamma_low, key.Egamma_high)
        for key in acceptance.response.keys
    }
    flux_rows = tuple(
        row
        for row in parsed_flux_rows
        if (
            row.target,
            row.beam_group,
            row.energy_low_gev,
            row.energy_high_gev,
        )
        in response_flux_universe
    )
    if not flux_rows:
        raise PolarizationContractError(
            "count flux CSV has no rows in authenticated response universe"
        )
    lookup_rows = _parse_strip_energy_lookup(
        lookup_file.path,
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
    coverage_by_group = {
        record.beam_group: record for record in acceptance.response_period_coverage
    }
    response_groups = {key.beam_group for key in acceptance.response.keys}
    if set(coverage_by_group) != response_groups:
        raise PolarizationContractError(
            "N3 response period coverage disagrees with response beam groups"
        )
    for beam_group, coverage in coverage_by_group.items():
        response_keys = tuple(
            key for key in acceptance.response.keys if key.beam_group == beam_group
        )
        actual_periods = set()
        for row in flux_rows:
            if row.beam_group != beam_group or not any(
                row.target == key.target
                and row.energy_low_gev == key.Egamma_low
                and row.energy_high_gev == key.Egamma_high
                for key in response_keys
            ):
                continue
            for interval in state_map:
                if (
                    interval.source_period == row.source_period
                    and interval.run_start <= row.run_number <= interval.run_end
                    and getattr(row, interval.flux_component) > 0.0
                ):
                    actual_periods.add(row.source_period)
        declared = set(coverage.covered_source_periods)
        if declared != actual_periods:
            raise PolarizationContractError(
                "N3 declared periods disagree with periods actually used by response/flux"
            )
        for source_period in declared:
            if (
                source_period not in mapped_periods
                or source_period not in compton_periods
            ):
                raise PolarizationContractError(
                    "N3 declared period lacks state or Compton authority"
                )

    retained_files = (
        config_file,
        gate0_file,
        gate0_manifest_file,
        *bundle_files,
        inventory_file,
        ledger_file,
        *n2_files,
        state_file,
        *[item.file for item in compton_files],
        *acceptance_files,
        n3_schema_file,
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
        gate0_manifest_file=gate0_manifest_file,
        gate0_bundle_files=bundle_files,
        flux_file=flux_file,
        strip_energy_lookup_file=lookup_file,
        gate0_run_numbers=gate0_runs,
        n2_inventory=inventory,
        n2_inventory_file=inventory_file,
        n2_processed_run_ledger_file=ledger_file,
        n2_files=n2_files,
        response=acceptance.response,
        response_covariance_scope=acceptance.response_covariance_scope,
        response_period_coverage=acceptance.response_period_coverage,
        acceptance_files=acceptance_files,
        n3_schema_file=n3_schema_file,
        state_map=state_map,
        state_mapping_file=state_file,
        compton=immutable_curves,
        compton_files=tuple(compton_files),
        flux_rows=flux_rows,
        strip_energy_lookup_rows=lookup_rows,
        _loader_token=_COUNT_AUTHORITY_TOKEN,
    )


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


@dataclass(frozen=True)
class ExpectedRecoGrid:
    """One response-defined count grid retained even when every count is zero."""

    analysis_version: str
    fit_release_id: str
    bin_set_id: str
    response_key: ResponseKey
    source_period: str
    orientation: str
    reco_mass_edges: tuple[float, ...]
    reco_phi_edges: tuple[float, ...]


@dataclass(frozen=True)
class _DerivedCountCell:
    expected: ExpectedRecoGrid
    exposure: float
    beam_polarization: float
    beam_polarization_variance: float
    compton_source_sha256: str


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


def _expected_group(expected: ExpectedRecoGrid) -> tuple:
    key = expected.response_key
    return (
        1,
        expected.analysis_version,
        expected.fit_release_id,
        expected.bin_set_id,
        key.channel,
        key.target,
        key.beam_group,
        expected.source_period,
        key.Egamma_low,
        key.Egamma_high,
        key.cos_theta_low,
        key.cos_theta_high,
        key.observable,
        key.selection_id,
        expected.orientation,
    )


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


def _physical_expected_group(expected: ExpectedRecoGrid) -> tuple:
    return _expected_group(expected)[:-1]


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
    expected_universe: tuple[ExpectedRecoGrid, ...]
    expected_replica_ids: tuple[int, ...]

    def __post_init__(self) -> None:
        if (
            type(self.expected_universe) is not tuple
            or not self.expected_universe
            or any(
                not isinstance(expected, ExpectedRecoGrid)
                for expected in self.expected_universe
            )
        ):
            raise PolarizationContractError(
                "azimuth count table requires a frozen expected universe"
            )
        expected_order = tuple(
            _expected_group(expected) for expected in self.expected_universe
        )
        if (
            expected_order != tuple(sorted(expected_order))
            or len(set(expected_order)) != len(expected_order)
        ):
            raise PolarizationContractError(
                "azimuth count expected universe must be unique and canonical"
            )
        for expected in self.expected_universe:
            _validate_expected_grid(expected)
        expected_orientations: dict[tuple, set[str]] = {}
        for expected in self.expected_universe:
            expected_orientations.setdefault(
                _physical_expected_group(expected), set()
            ).add(expected.orientation)
        if any(
            orientations != set(ORIENTATIONS)
            for orientations in expected_orientations.values()
        ):
            raise PolarizationContractError(
                "azimuth count expected universe requires both orientations"
            )
        if (
            type(self.expected_replica_ids) is not tuple
            or not self.expected_replica_ids
            or any(type(replica) is not int for replica in self.expected_replica_ids)
            or self.expected_replica_ids
            != tuple(range(self.expected_replica_ids[-1] + 1))
        ):
            raise PolarizationContractError(
                "azimuth count expected replica IDs must be contiguous from zero"
            )
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
        if not self.has_every_reco_cell():
            raise PolarizationContractError(
                "azimuth count rows must contain the complete reconstructed grid"
            )

    @property
    def replica_ids(self) -> tuple[int, ...]:
        """Return the complete ordered nominal-plus-bootstrap replica IDs."""
        return self.expected_replica_ids

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
        """Report whether every response-defined group has its exact full grid."""
        replicas = self.expected_replica_ids
        if {row.replica_id for row in self.rows} != set(replicas):
            return False
        grouped: dict[tuple, dict[int, list[AzimuthCountRow]]] = {}
        for row in self.rows:
            grouped.setdefault(_count_group(row), {}).setdefault(
                row.replica_id, []
            ).append(row)
        expected_by_group = {
            _expected_group(expected): expected for expected in self.expected_universe
        }
        if set(grouped) != set(expected_by_group):
            return False
        for group, expected_grid in expected_by_group.items():
            by_replica = grouped[group]
            if set(by_replica) != set(replicas):
                return False
            expected = {
                (
                    mass_bin,
                    phi_bin,
                    expected_grid.reco_mass_edges[mass_bin],
                    expected_grid.reco_mass_edges[mass_bin + 1],
                    expected_grid.reco_phi_edges[phi_bin],
                    expected_grid.reco_phi_edges[phi_bin + 1],
                )
                for mass_bin in range(len(expected_grid.reco_mass_edges) - 1)
                for phi_bin in range(len(expected_grid.reco_phi_edges) - 1)
            }
            for rows in by_replica.values():
                actual = {
                    (
                        row.reco_mass_bin,
                        row.reco_phi_bin,
                        row.reco_mass_low_gev,
                        row.reco_mass_high_gev,
                        row.reco_phi_low,
                        row.reco_phi_high,
                    )
                    for row in rows
                }
                if len(rows) != len(expected) or actual != expected:
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


def _validate_expected_axis(
    raw: tuple[float, ...],
    label: str,
    *,
    required_low: float | None = None,
    required_high: float | None = None,
) -> None:
    if (
        type(raw) is not tuple
        or len(raw) < 2
        or any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(float(value))
            for value in raw
        )
        or any(right <= left for left, right in zip(raw, raw[1:]))
    ):
        raise PolarizationContractError(
            f"azimuth count expected {label} must be a frozen finite partition"
        )
    if required_low is not None and not math.isclose(
        raw[0], required_low, rel_tol=0.0, abs_tol=1e-14
    ):
        raise PolarizationContractError(
            f"azimuth count expected {label} has the wrong lower boundary"
        )
    if required_high is not None and not math.isclose(
        raw[-1], required_high, rel_tol=0.0, abs_tol=1e-14
    ):
        raise PolarizationContractError(
            f"azimuth count expected {label} has the wrong upper boundary"
        )


def _validate_expected_grid(expected: ExpectedRecoGrid) -> None:
    _canonical_text(expected.analysis_version, "expected analysis_version")
    _canonical_text(expected.fit_release_id, "expected fit_release_id")
    _canonical_text(expected.bin_set_id, "expected bin_set_id")
    _canonical_text(expected.source_period, "expected source_period")
    if not isinstance(expected.response_key, ResponseKey):
        raise PolarizationContractError(
            "azimuth count expected universe requires response keys"
        )
    key = expected.response_key
    for name in ("channel", "target", "beam_group", "observable", "selection_id"):
        _canonical_text(getattr(key, name), f"expected response {name}")
    if key.observable not in PAIR_NAMES:
        raise PolarizationContractError(
            "azimuth count expected response observable is invalid"
        )
    if expected.orientation not in ORIENTATIONS:
        raise PolarizationContractError(
            "azimuth count expected orientation is invalid"
        )
    for value, label in (
        (key.Egamma_low, "energy lower edge"),
        (key.Egamma_high, "energy upper edge"),
        (key.cos_theta_low, "cosine lower edge"),
        (key.cos_theta_high, "cosine upper edge"),
    ):
        _finite(value, f"expected response {label}")
    if key.Egamma_low >= key.Egamma_high:
        raise PolarizationContractError(
            "azimuth count expected response energy bin is reversed"
        )
    if not -1.0 <= key.cos_theta_low < key.cos_theta_high <= 1.0:
        raise PolarizationContractError(
            "azimuth count expected response cosine bin is invalid"
        )
    _validate_expected_axis(expected.reco_mass_edges, "mass axis")
    _validate_expected_axis(
        expected.reco_phi_edges,
        "azimuth axis",
        required_low=0.0,
        required_high=math.pi,
    )


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


def _validate_sample(
    sample: EventSample,
    tree: str,
    *,
    n2_file_sha256s: frozenset[str],
    observed_run_numbers: frozenset[int],
) -> int:
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
    for name, vectors in (
        ("beam", sample.beam),
        ("proton", sample.proton),
        ("eta", sample.eta),
        ("pi0", sample.pi0),
    ):
        array = np.asarray(vectors)
        if array.shape != (event_count, 4):
            raise PolarizationContractError(f"N2 {name} vectors must have shape (events, 4)")
    numeric = (
        sample.beam_energy, sample.beam, sample.xstrip,
        sample.proton, sample.eta, sample.pi0,
    )
    if any(not np.all(np.isfinite(np.asarray(array, dtype=float))) for array in numeric):
        raise PolarizationContractError("N2 event sample contains non-finite values")
    if not np.allclose(
        np.asarray(sample.beam)[:, 3],
        np.asarray(sample.beam_energy),
        rtol=0.0,
        atol=1e-12,
    ):
        raise PolarizationContractError(
            "N2 beam four-vector energy disagrees with beam_energy"
        )
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
        file_digest = _digest(str(digest), "N2 file SHA-256")
        if file_digest not in n2_file_sha256s:
            raise PolarizationContractError(
                "N2 event file SHA-256 is absent from authenticated N2 inventory"
            )
        identities.append((file_digest, tree, int(entry)))
    if len(set(identities)) != event_count:
        raise PolarizationContractError("N2 stable event identity must be unique")
    if not set(int(run) for run in runs).issubset(observed_run_numbers):
        raise PolarizationContractError(
            "N2 event runs disagree with authenticated reconstruction inventory"
        )
    return event_count


def _retained_count_authority_files(
    authority: CountAuthority,
) -> tuple[AuthenticatedFile, ...]:
    return (
        authority.config_file,
        authority.gate0_handoff_file,
        authority.gate0_manifest_file,
        *authority.gate0_bundle_files,
        authority.n2_inventory_file,
        authority.n2_processed_run_ledger_file,
        *authority.n2_files,
        authority.state_mapping_file,
        *[item.file for item in authority.compton_files],
        *authority.acceptance_files,
        authority.n3_schema_file,
    )


def _require_count_authority(authority: CountAuthority) -> None:
    if type(authority) is not CountAuthority:
        raise PolarizationContractError(
            "azimuth counts require CountAuthority from load_count_authority"
        )


def _authority_acceptance_qa_file(authority: CountAuthority) -> AuthenticatedFile:
    qa_files = tuple(
        item
        for item in authority.acceptance_files
        if item.relative_path.endswith("/acceptance_qa.json")
    )
    if len(qa_files) != 1:
        raise PolarizationContractError(
            "CountAuthority lacks one canonical N3 acceptance QA file"
        )
    return qa_files[0]


def _reload_count_authority(authority: CountAuthority) -> CountAuthority:
    """Reload one authority from its canonical identifiers, never its values."""
    _require_count_authority(authority)
    qa_file = _authority_acceptance_qa_file(authority)
    return load_count_authority(
        repository_root=authority.repository_root,
        config_path=authority.config_file.relative_path,
        gate0_handoff_path=authority.gate0_handoff_file.relative_path,
        n2_inventory_path=authority.n2_inventory_file.relative_path,
        acceptance_handoff_path=qa_file.relative_path,
        fit_release_id=authority.fit_release_id,
        bin_set_id=authority.bin_set_id,
    )


def _authority_fingerprint(authority: CountAuthority) -> tuple[object, ...]:
    """Return the full transitive byte identity used across a ROOT read."""
    _require_count_authority(authority)
    return (
        authority.repository_root,
        authority.fit_release_id,
        authority.bin_set_id,
        tuple(
            (item.relative_path, item.sha256)
            for item in _retained_count_authority_files(authority)
        ),
    )


def _validate_count_authority(authority: CountAuthority) -> None:
    _require_count_authority(authority)
    config = authority.config
    scope = authority.response_covariance_scope
    if (
        type(scope) is not ResponseCovarianceScope
        or scope.qa_sha256 != config.acceptance_qa_sha256
        or scope.shared_mc_across_blocks is not False
        or scope.cross_block_covariance is not False
    ):
        raise PolarizationContractError(
            "count authority has invalid N3 response covariance scope"
        )
    coverage = authority.response_period_coverage
    if (
        not coverage
        or any(
            type(record) is not ResponsePeriodCoverage
            or record.qa_sha256 != config.acceptance_qa_sha256
            or record.coverage_valid is not True
            for record in coverage
        )
        or {record.beam_group for record in coverage}
        != {key.beam_group for key in authority.response.keys}
    ):
        raise PolarizationContractError(
            "count authority has invalid N3 response period coverage"
        )
    if config.status != "approved" or config.blocked_reasons:
        raise PolarizationContractError(
            "azimuth counts require approved canonical config"
        )
    if tuple(item.path for item in authority.n2_files) != tuple(
        sorted(authority.n2_inventory.paths)
    ):
        raise PolarizationContractError(
            "authenticated N2 files disagree with reconstruction inventory"
        )
    retained = _retained_count_authority_files(authority)
    if any(sha256_file(item.path) != item.sha256 for item in retained):
        raise PolarizationContractError(
            "count authority bytes changed after authentication"
        )
    response_files = tuple(
        item
        for item in authority.acceptance_files
        if item.relative_path.endswith("/acceptance_phi_response_v1.csv")
    )
    if (
        len(response_files) != 1
        or response_files[0].sha256 != authority.response.source_sha256
    ):
        raise PolarizationContractError(
            "count response disagrees with authenticated N3 bytes"
        )
    response_keys = set(authority.response.keys)
    if (
        response_keys
        != {key for key, _orientation in authority.response.matrices}
        or response_keys != set(authority.response.mass_edges)
        or response_keys != set(authority.response.phi_edges)
    ):
        raise PolarizationContractError(
            "count response axes do not cover its physical key universe"
        )


def _flux_exposure_totals(authority: CountAuthority) -> dict[tuple, float]:
    totals: dict[tuple, float] = {}
    for row in authority.flux_rows:
        matching = tuple(
            interval
            for interval in authority.state_map
            if interval.source_period == row.source_period
            and interval.run_start <= row.run_number <= interval.run_end
        )
        if not matching:
            raise PolarizationContractError(
                "valid count flux row lacks state-map coverage"
            )
        orientation_components: dict[str, set[str]] = {}
        component_orientations: dict[str, set[str]] = {}
        for interval in matching:
            orientation_components.setdefault(interval.orientation, set()).add(
                interval.flux_component
            )
            component_orientations.setdefault(interval.flux_component, set()).add(
                interval.orientation
            )
        if any(len(values) != 1 for values in orientation_components.values()) or any(
            len(values) != 1 for values in component_orientations.values()
        ):
            raise PolarizationContractError(
                "state mapping ambiguously assigns count flux components"
            )
        for orientation, components in orientation_components.items():
            component = next(iter(components))
            flux = getattr(row, component)
            group = (
                row.target,
                row.beam_group,
                row.energy_low_gev,
                row.energy_high_gev,
                row.source_period,
                orientation,
            )
            totals[group] = totals.get(group, 0.0) + flux
    return totals


def _derive_count_cells(authority: CountAuthority) -> tuple[_DerivedCountCell, ...]:
    totals = _flux_exposure_totals(authority)
    compton_files = {item.source_period: item.file for item in authority.compton_files}
    cells = []
    for key in authority.response.keys:
        if key.cos_theta_low != -1.0 or key.cos_theta_high != 1.0:
            raise PolarizationContractError(
                "azimuth_counts_v1 requires response cos_theta=[-1,1]"
            )
        mass_edges = authority.response.mass_edges[key]
        phi_edges = authority.response.phi_edges[key]
        expected_size = (len(mass_edges) - 1) * (len(phi_edges) - 1)
        for orientation in ORIENTATIONS:
            matrix = authority.response.matrix(key, orientation)
            if matrix.shape != (expected_size, expected_size):
                raise PolarizationContractError(
                    "response matrix shape disagrees with authenticated axes"
                )
        applicable = {
            group[4:]
            for group, exposure in totals.items()
            if group[:4]
            == (key.target, key.beam_group, key.Egamma_low, key.Egamma_high)
            and exposure > 0.0
        }
        periods = sorted({source_period for source_period, _ in applicable})
        if not periods:
            raise PolarizationContractError(
                "response physical key has no authenticated valid flux exposure"
            )
        for source_period in periods:
            orientations = {
                orientation
                for period, orientation in applicable
                if period == source_period
            }
            if orientations != set(ORIENTATIONS):
                raise PolarizationContractError(
                    "each response physical key/source_period requires both orientations"
                )
            curve = authority.compton.get(source_period)
            compton_file = compton_files.get(source_period)
            if not isinstance(curve, PolarizationCurve) or compton_file is None:
                raise PolarizationContractError(
                    f"approved Compton authority missing for {source_period}"
                )
            polarization, variance = curve.bin_average(
                1000.0 * key.Egamma_low, 1000.0 * key.Egamma_high
            )
            if not 0.0 < polarization <= 1.0 or variance < 0.0:
                raise PolarizationContractError(
                    "derived count beam polarization is not physical"
                )
            for orientation in ORIENTATIONS:
                exposure = totals[
                    (
                        key.target,
                        key.beam_group,
                        key.Egamma_low,
                        key.Egamma_high,
                        source_period,
                        orientation,
                    )
                ]
                cells.append(
                    _DerivedCountCell(
                        ExpectedRecoGrid(
                            analysis_version=authority.config.analysis_version,
                            fit_release_id=authority.fit_release_id,
                            bin_set_id=authority.bin_set_id,
                            response_key=key,
                            source_period=source_period,
                            orientation=orientation,
                            reco_mass_edges=mass_edges,
                            reco_phi_edges=phi_edges,
                        ),
                        exposure,
                        polarization,
                        variance,
                        compton_file.sha256,
                    )
                )
    return tuple(sorted(cells, key=lambda cell: _expected_group(cell.expected)))


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


def _count_layout(
    authority: CountAuthority,
) -> tuple[AnalysisConfig, tuple[_DerivedCountCell, ...], tuple[int, ...]]:
    """Derive the entire publishable grid from one authenticated authority."""
    _validate_count_authority(authority)
    config = authority.config
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
        raise PolarizationContractError(
            "azimuth counts require approved bootstrap configuration"
        )
    cells = _derive_count_cells(authority)
    sigma_vector_dimension = sum(
        len(authority.response.mass_edges[key]) - 1
        for key in authority.response.keys
    )
    if bootstrap.replicas <= sigma_vector_dimension:
        raise PolarizationContractError(
            "bootstrap replicas must exceed the published Sigma-vector dimension"
        )
    return config, cells, tuple(range(bootstrap.replicas + 1))


def _count_row(
    authority: CountAuthority,
    cell: _DerivedCountCell,
    *,
    replica_id: int,
    mass_bin: int,
    phi_bin: int,
    observed_count: int,
) -> AzimuthCountRow:
    """Build one authority-derived row; only the projected count is variable."""
    expected = cell.expected
    key = expected.response_key
    return AzimuthCountRow(
        schema_version=1,
        analysis_version=authority.config.analysis_version,
        fit_release_id=authority.fit_release_id,
        bin_set_id=authority.bin_set_id,
        channel=key.channel,
        target=key.target,
        beam_group=key.beam_group,
        source_period=expected.source_period,
        Egamma_low=key.Egamma_low,
        Egamma_high=key.Egamma_high,
        cos_theta_low=key.cos_theta_low,
        cos_theta_high=key.cos_theta_high,
        observable=key.observable,
        selection_id=key.selection_id,
        orientation=expected.orientation,
        replica_id=replica_id,
        reco_mass_bin=mass_bin,
        reco_mass_low_gev=expected.reco_mass_edges[mass_bin],
        reco_mass_high_gev=expected.reco_mass_edges[mass_bin + 1],
        reco_phi_bin=phi_bin,
        reco_phi_low=expected.reco_phi_edges[phi_bin],
        reco_phi_high=expected.reco_phi_edges[phi_bin + 1],
        observed_count=observed_count,
        exposure=cell.exposure,
        beam_polarization=cell.beam_polarization,
        beam_polarization_variance=cell.beam_polarization_variance,
        gate0_handoff_sha256=authority.gate0_handoff_sha256,
        n2_reconstruction_sha256=authority.n2_reconstruction_sha256,
        state_mapping_sha256=authority.state_mapping_sha256,
        compton_source_sha256=cell.compton_source_sha256,
        config_sha256=authority.config_sha256,
        input_sha256=authority.flux_file.sha256,
    )


def _project_azimuth_counts(
    sample: EventSample,
    *,
    authority: CountAuthority,
) -> AzimuthCountTable:
    """Project a reader-produced N2 sample; this is not a release API."""
    config, authority_cells, replica_ids = _count_layout(authority)
    bootstrap = config.bootstrap
    event_count = _validate_sample(
        sample,
        config.figure4_tree,
        n2_file_sha256s=authority.n2_file_sha256s,
        observed_run_numbers=authority.n2_inventory.observed_event_run_numbers,
    )
    intervals = validate_intervals(authority.state_map)
    observables = event_pair_observables(
        sample.beam,
        sample.proton,
        sample.eta,
        sample.pi0,
        angle=config.angle,
    )
    invalid_plane = np.flatnonzero(~observables[PAIR_NAMES[0]].valid_phi)
    if invalid_plane.size:
        raise PolarizationContractError(
            f"degenerate reaction plane for selected N2 event {int(invalid_plane[0])}"
        )
    counts: dict[tuple[int, int, int, int], int] = {}
    for exposure_index in range(len(authority_cells)):
        expected = authority_cells[exposure_index].expected
        for replica_id in replica_ids:
            for mass_bin in range(len(expected.reco_mass_edges) - 1):
                for phi_bin in range(len(expected.reco_phi_edges) - 1):
                    counts[exposure_index, replica_id, mass_bin, phi_bin] = 0

    cells_by_exposure_group: dict[tuple, list[int]] = {}
    for index, cell in enumerate(authority_cells):
        key = cell.expected.response_key
        group = (
            cell.expected.source_period,
            cell.expected.orientation,
            key.beam_group,
            key.Egamma_low,
            key.Egamma_high,
        )
        cells_by_exposure_group.setdefault(group, []).append(index)
    for indices in cells_by_exposure_group.values():
        projected_observables = [
            authority_cells[index].expected.response_key.observable
            for index in indices
        ]
        if len(set(projected_observables)) != len(projected_observables):
            raise PolarizationContractError(
                "N2 event projection has ambiguous response physical keys"
            )

    energy_edges = config.figure4_energy_edges_gev
    lookup_by_event = {
        (row.run_number, row.xstrip): row
        for row in authority.strip_energy_lookup_rows
    }
    for event_index in range(event_count):
        run_number = int(sample.run_number[event_index])
        state_code = int(sample.state_code[event_index])
        interval = _event_interval(run_number, state_code, intervals)
        energy = float(sample.beam_energy[event_index])
        try:
            xstrip = normalize_xstrip(float(sample.xstrip[event_index]))
        except (TypeError, ValueError) as exc:
            raise PolarizationContractError(
                f"selected N2 event {event_index} has invalid Xstrip"
            ) from exc
        lookup = lookup_by_event.get((run_number, xstrip))
        if lookup is None:
            raise PolarizationContractError(
                f"selected N2 event {event_index} lacks unique strip-energy lookup"
            )
        if (
            lookup.source_period != interval.source_period
            or lookup.target != config.figure4_target
        ):
            raise PolarizationContractError(
                f"selected N2 event {event_index} strip-energy lookup disagrees with state/target"
            )
        tolerance = config.angle.tolerance
        if not (
            lookup.energy_min_gev - tolerance
            <= energy
            <= lookup.energy_max_gev + tolerance
        ):
            raise PolarizationContractError(
                f"selected N2 event {event_index} beam energy is outside strip-energy interval"
            )
        energy_index = _energy_bin(energy, energy_edges)
        if energy_index is None:
            raise PolarizationContractError(
                f"selected N2 event {event_index} lacks response energy bin"
            )
        low, high = energy_edges[energy_index], energy_edges[energy_index + 1]
        matching_flux = tuple(
            row
            for row in authority.flux_rows
            if row.run_number == run_number
            and row.source_period == interval.source_period
            and row.target == config.figure4_target
            and row.beam_type == lookup.beam_type
            and row.beam_group == lookup.beam_group
            and row.energy_low_gev == low
            and row.energy_high_gev == high
            and (
                interval.source_period,
                interval.orientation,
                row.beam_group,
                low,
                high,
            )
            in cells_by_exposure_group
        )
        if len(matching_flux) != 1:
            raise PolarizationContractError(
                f"selected N2 event {event_index} lacks unique flux/response mapping"
            )
        flux_row = matching_flux[0]
        if getattr(flux_row, interval.flux_component) <= 0.0:
            raise PolarizationContractError(
                f"selected N2 event {event_index} has non-positive flux component"
            )
        beam_group = flux_row.beam_group
        matching_cells = cells_by_exposure_group[
            (interval.source_period, interval.orientation, beam_group, low, high)
        ]
        projected_cells = []
        for exposure_index in matching_cells:
            expected = authority_cells[exposure_index].expected
            projected = observables[expected.response_key.observable]
            mass_bin = _histogram_bin(
                float(projected.mass[event_index]),
                np.asarray(expected.reco_mass_edges),
            )
            phi_bin = _histogram_bin(
                float(projected.phi[event_index]),
                np.asarray(expected.reco_phi_edges),
            )
            identity = (
                f"run={run_number},file_sha256={sample.file_sha256[event_index]},"
                f"tree_entry={int(sample.tree_entry[event_index])}"
            )
            observable = expected.response_key.observable
            if mass_bin is None:
                raise PolarizationContractError(
                    f"selected N2 event {identity} observable={observable} "
                    "lacks exactly one reco mass cell"
                )
            if phi_bin is None:
                raise PolarizationContractError(
                    f"selected N2 event {identity} observable={observable} "
                    "lacks exactly one reco phi cell"
                )
            projected_cells.append((exposure_index, mass_bin, phi_bin))
        weights = tuple(
            event_bootstrap_weight(
                str(sample.file_sha256[event_index]),
                config.figure4_tree,
                int(sample.tree_entry[event_index]),
                replica_id,
                algorithm=bootstrap.algorithm_version,
                seed=bootstrap.seed,
            )
            for replica_id in replica_ids
        )
        for exposure_index, mass_bin, phi_bin in projected_cells:
            for replica_id, weight in enumerate(weights):
                counts[exposure_index, replica_id, mass_bin, phi_bin] += weight

    rows = []
    for exposure_index, cell in enumerate(authority_cells):
        expected = cell.expected
        for replica_id in replica_ids:
            for mass_bin in range(len(expected.reco_mass_edges) - 1):
                for phi_bin in range(len(expected.reco_phi_edges) - 1):
                    rows.append(
                        _count_row(
                            authority,
                            cell,
                            replica_id=replica_id,
                            mass_bin=mass_bin,
                            phi_bin=phi_bin,
                            observed_count=counts[
                                exposure_index,
                                replica_id,
                                mass_bin,
                                phi_bin,
                            ],
                        )
                    )
    rows.sort(key=_row_order)
    table = AzimuthCountTable(
        tuple(rows),
        tuple(cell.expected for cell in authority_cells),
        replica_ids,
    )
    if not table.has_every_reco_cell():
        raise PolarizationContractError("azimuth count table is missing reconstructed cells")
    return table


def build_azimuth_counts(*, authority: CountAuthority) -> AzimuthCountTable:
    """Build release counts from freshly authenticated N2 ROOT bytes only."""
    before = _reload_count_authority(authority)
    before_fingerprint = _authority_fingerprint(before)
    sample = read_reco_root(
        before.n2_inventory.paths,
        tree_name=before.config.figure4_tree,
        vectors=before.config.figure4_vectors,
    )
    after = _reload_count_authority(before)
    if _authority_fingerprint(after) != before_fingerprint:
        raise PolarizationContractError(
            "count authority changed while authenticated N2 ROOT data were read"
        )
    return _project_azimuth_counts(sample, authority=after)


def _validate_table_for_publication(
    table: AzimuthCountTable,
    authority: CountAuthority,
) -> None:
    """Compare an in-memory table with freshly derived authority descriptors."""
    if not isinstance(table, AzimuthCountTable):
        raise PolarizationContractError("cannot serialize a non-count table")
    _config, cells, replica_ids = _count_layout(authority)
    expected_universe = tuple(cell.expected for cell in cells)
    if table.expected_universe != expected_universe:
        raise PolarizationContractError(
            "azimuth count expected universe disagrees with fresh authority"
        )
    if table.expected_replica_ids != replica_ids:
        raise PolarizationContractError(
            "azimuth count replica IDs disagree with fresh authority"
        )
    templates = {}
    for cell in cells:
        expected = cell.expected
        for replica_id in replica_ids:
            for mass_bin in range(len(expected.reco_mass_edges) - 1):
                for phi_bin in range(len(expected.reco_phi_edges) - 1):
                    template = _count_row(
                        authority,
                        cell,
                        replica_id=replica_id,
                        mass_bin=mass_bin,
                        phi_bin=phi_bin,
                        observed_count=0,
                    )
                    templates[_row_order(template)] = template
    if tuple(_row_order(row) for row in table.rows) != tuple(sorted(templates)):
        raise PolarizationContractError(
            "azimuth count rows disagree with fresh authority grid"
        )
    for row in table.rows:
        template = templates[_row_order(row)]
        if any(
            getattr(row, field.name) != getattr(template, field.name)
            for field in fields(AzimuthCountRow)
            if field.name != "observed_count"
        ):
            raise PolarizationContractError(
                "azimuth count row metadata disagrees with fresh authority"
            )


def write_azimuth_counts(
    table: AzimuthCountTable,
    path: Path,
    *,
    authority: CountAuthority,
) -> str:
    """Write the exact canonical CSV schema and return its lowercase SHA-256."""
    fresh_authority = _reload_count_authority(authority)
    _validate_table_for_publication(table, fresh_authority)
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
