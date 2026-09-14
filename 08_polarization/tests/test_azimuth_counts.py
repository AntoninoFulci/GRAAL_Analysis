from __future__ import annotations

import csv
from dataclasses import replace

import numpy as np
import pytest

from analysis_config import BootstrapConfig
from azimuth_counts import (
    AZIMUTH_COUNT_FIELDS,
    AzimuthCountTable,
    CountExposure,
    build_azimuth_counts,
    event_bootstrap_weight,
    write_azimuth_counts,
)
from compton import PolarizationCurve
from contracts import PolarizationContractError, sha256_file
from root_events import EventSample
from state_mapping import StateInterval


FILE_HASH = "0123456789abcdef" * 4
EXPECTED_COUNT_FIELDS = tuple(
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


@pytest.fixture
def event_sample():
    proton = np.tile([0.10, 0.20, 0.00, 1.00], (4, 1))
    eta = np.tile([0.20, 0.10, 0.00, 0.70], (4, 1))
    pi0 = np.tile([0.30, 0.10, 0.00, 0.50], (4, 1))
    return EventSample(
        beam_energy=np.full(4, 1.15),
        run_number=np.array([100, 100, 101, 101]),
        state_code=np.array([1, 1, 2, 2]),
        xstrip=np.array([40.0, 41.0, 42.0, 43.0]),
        proton=proton,
        eta=eta,
        pi0=pi0,
        file_sha256=np.array([FILE_HASH] * 4),
        tree_entry=np.arange(4),
    )


@pytest.fixture
def authorities(response_fixture):
    config = replace(
        response_fixture.config,
        figure4_energy_edges_gev=(1.1, 1.2),
        figure4_phi_bins=4,
        bootstrap=BootstrapConfig(
            8, "poisson1-sha256-v1", 1701, 0.05, 0.5, 2.0
        ),
    )
    state_map = (
        StateInterval(100, 100, 1, "parallel", "period-a", "pol1_net"),
        StateInterval(101, 101, 2, "perpendicular", "period-a", "pol2_net"),
    )
    compton = {
        "period-a": PolarizationCurve(
            [1100.0, 1200.0], [0.8, 0.8], [[0.01, 0.0], [0.0, 0.01]]
        )
    }
    common = dict(
        fit_release_id="fit-test",
        bin_set_id="figure4-v1",
        channel="eta_pi0",
        target="P",
        beam_group="group-a",
        source_period="period-a",
        Egamma_low=1.1,
        Egamma_high=1.2,
        cos_theta_low=-1.0,
        cos_theta_high=1.0,
        selection_id="selection-v1",
        exposure=1000.0,
        beam_polarization=0.8,
        beam_polarization_variance=0.005,
        source_stage="N2",
        n2_inventory_path="results/reconstruction/inventory.json",
        gate0_handoff_sha256="a" * 64,
        n2_reconstruction_sha256="b" * 64,
        state_mapping_sha256="c" * 64,
        compton_source_sha256="d" * 64,
        config_sha256="e" * 64,
        input_sha256="f" * 64,
    )
    exposures = (
        CountExposure(orientation="parallel", **common),
        CountExposure(orientation="perpendicular", **common),
    )
    return {
        "config": config,
        "state_map": state_map,
        "exposures": exposures,
        "compton": compton,
        "mass_edges": {
            "p_pi0": np.array([1.0, 1.5, 2.0]),
            "p_eta": np.array([1.0, 1.7, 2.4]),
            "eta_pi0": np.array([0.5, 1.2, 2.0]),
        },
    }


def test_poisson_multiplier_has_frozen_versioned_vectors():
    assert event_bootstrap_weight(
        FILE_HASH,
        "reco_eta_pi0_chi2",
        0,
        0,
        algorithm="poisson1-sha256-v1",
        seed=1701,
    ) == 1
    expected = {(0, 1): 0, (0, 2): 1, (2, 7): 2, (4, 32): 4}
    for (entry, replica_id), wanted in expected.items():
        assert event_bootstrap_weight(
            FILE_HASH,
            "reco_eta_pi0_chi2",
            entry,
            replica_id,
            algorithm="poisson1-sha256-v1",
            seed=1701,
        ) == wanted


@pytest.mark.parametrize(
    "change",
    [
        {"algorithm": "other"},
        {"file_sha256": "A" * 64},
        {"tree": ""},
        {"entry": -1},
        {"replica_id": -1},
        {"seed": -1},
    ],
)
def test_poisson_multiplier_rejects_noncanonical_identity_or_config(change):
    arguments = dict(
        file_sha256=FILE_HASH,
        tree="reco_eta_pi0_chi2",
        entry=0,
        replica_id=1,
        algorithm="poisson1-sha256-v1",
        seed=1701,
    )
    arguments.update(change)
    with pytest.raises(PolarizationContractError):
        event_bootstrap_weight(**arguments)


def test_bootstrap_multiplier_is_shared_across_observables(event_sample, authorities):
    table = build_azimuth_counts(event_sample, **authorities)
    totals = [
        table.sum_for(name, replica_id=7)
        for name in ("p_pi0", "p_eta", "eta_pi0")
    ]
    assert len(set(totals)) == 1
    assert [table.sum_for(name, replica_id=0) for name in authorities["mass_edges"]] == [4, 4, 4]


def test_shared_replicas_retain_nonzero_cross_observable_covariance(event_sample, authorities):
    table = build_azimuth_counts(event_sample, **authorities)
    replica_totals = np.array(
        [
            [table.sum_for(name, replica_id=replica_id) for name in authorities["mass_edges"]]
            for replica_id in table.replica_ids[1:]
        ]
    )
    covariance = np.cov(replica_totals, rowvar=False)
    assert covariance[0, 1] > 0.0
    assert covariance[0, 2] > 0.0


def test_counts_publish_complete_nominal_and_replica_grids(event_sample, authorities):
    table = build_azimuth_counts(event_sample, **authorities)
    assert table.replica_ids == tuple(
        range(authorities["config"].bootstrap.replicas + 1)
    )
    assert table.has_every_reco_cell()
    assert len(table.rows) == 2 * 9 * 3 * 2 * 4
    assert any(row.observed_count == 0 for row in table.rows)


def test_counts_require_more_replicas_than_the_published_sigma_dimension(
    event_sample, authorities
):
    undersized = replace(
        authorities["config"],
        bootstrap=BootstrapConfig(6, "poisson1-sha256-v1", 1701, 0.05, 0.5, 2.0),
    )

    with pytest.raises(PolarizationContractError, match="Sigma-vector dimension"):
        build_azimuth_counts(event_sample, **{**authorities, "config": undersized})


def test_complete_grid_check_detects_wholly_missing_orientation(event_sample, authorities):
    table = build_azimuth_counts(event_sample, **authorities)
    incomplete = AzimuthCountTable(
        tuple(row for row in table.rows if row.orientation != "parallel")
    )
    assert not incomplete.has_every_reco_cell()


def test_count_grid_rejects_noncontiguous_azimuth_partition(
    event_sample, authorities, tmp_path
):
    table = build_azimuth_counts(event_sample, **authorities)
    malformed = AzimuthCountTable(
        tuple(
            replace(row, reco_phi_high=0.7) if row.reco_phi_bin == 0 else row
            for row in table.rows
        )
    )

    assert not malformed.has_every_reco_cell()
    with pytest.raises(PolarizationContractError, match="incomplete"):
        write_azimuth_counts(malformed, tmp_path / "azimuth_counts_v1.csv")


def test_counts_serialize_exact_ordered_schema_and_hash(event_sample, authorities, tmp_path):
    table = build_azimuth_counts(event_sample, **authorities)
    output = tmp_path / "azimuth_counts_v1.csv"

    digest = write_azimuth_counts(table, output)

    assert digest == sha256_file(output)
    with output.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        rows = list(reader)
    assert AZIMUTH_COUNT_FIELDS == EXPECTED_COUNT_FIELDS
    assert tuple(reader.fieldnames or ()) == EXPECTED_COUNT_FIELDS
    assert len(rows) == len(table.rows)
    assert rows[0]["replica_id"] == "0"
    assert rows[0]["reco_mass_bin"] == "0"
    assert rows[0]["reco_phi_bin"] == "0"
    assert rows[0]["n2_reconstruction_sha256"] == "b" * 64
    assert rows[0]["input_sha256"] == "f" * 64


@pytest.mark.parametrize(
    "mutation,match",
    [
        ({"input_sha256": "bad"}, "SHA-256"),
        ({"reco_phi_high": 4.0}, "azimuth"),
        ({"beam_polarization": 1.1}, "polarization"),
    ],
)
def test_count_table_rejects_malformed_serialized_rows(
    event_sample, authorities, mutation, match
):
    table = build_azimuth_counts(event_sample, **authorities)
    rows = (replace(table.rows[0], **mutation), *table.rows[1:])
    with pytest.raises(PolarizationContractError, match=match):
        AzimuthCountTable(rows)


@pytest.mark.parametrize(
    "mutation,match",
    [
        ({"source_stage": "N4"}, "N2"),
        ({"n2_inventory_path": "results/reco/n4-yields.csv"}, "N2 inventory"),
        ({"n2_reconstruction_sha256": "not-a-hash"}, "SHA-256"),
        ({"beam_polarization": 0.7}, "Compton"),
        ({"beam_polarization_variance": 0.004}, "Compton"),
    ],
)
def test_counts_reject_non_n2_or_unbound_authority(
    event_sample, authorities, mutation, match
):
    exposures = tuple(replace(item, **mutation) for item in authorities["exposures"])
    with pytest.raises(PolarizationContractError, match=match):
        build_azimuth_counts(event_sample, **{**authorities, "exposures": exposures})


def test_counts_require_both_orientations_for_each_physical_period(event_sample, authorities):
    with pytest.raises(PolarizationContractError, match="both orientations"):
        build_azimuth_counts(
            event_sample,
            **{**authorities, "exposures": authorities["exposures"][:1]},
        )


def test_counts_reject_duplicate_stable_event_identity(event_sample, authorities):
    duplicate = replace(event_sample, tree_entry=np.array([0, 0, 2, 3]))
    with pytest.raises(PolarizationContractError, match="event identity"):
        build_azimuth_counts(duplicate, **authorities)
