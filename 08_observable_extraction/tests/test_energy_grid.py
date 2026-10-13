from dataclasses import replace
import json

import numpy as np
import pytest

from observable_extraction import beam_asymmetry, combine_profiles
from observable_extraction.core.models import FluxExposure
from observable_extraction.io.root_input import read_output_contract, read_output_points
from observable_extraction.io.root_output import RootOutputPayload, write_root_output
from observable_extraction.tests.test_beam_asymmetry_cli import _synthetic_events
from observable_extraction.tests.test_figure4 import _points


def test_split_vis_cli_round_trip_and_combiner_validation(tmp_path, monkeypatch):
    events = _synthetic_events(beam_energy_gev=1.04)
    monkeypatch.setattr(beam_asymmetry, "read_reconstructed", lambda *a, **k: events)
    monkeypatch.setattr(beam_asymmetry, "load_exposures", lambda *a, **k: {
        (811, 17): FluxExposure(811, 17, 1.04, 1.2, .9, .2, .6, .55)})
    output = tmp_path / "output"
    beam_asymmetry.main(["--profile", "vis", "--energy-edges", ".9313", "1.01565", "1.1",
                         "--raw", str(tmp_path / "raw.root"), "--raw-bdt", str(tmp_path / "bdt.root"),
                         "--output-dir", str(output), "--estimator", "ratio"])
    root = output / "beam_asymmetry.root"
    contract = read_output_contract(root)
    assert contract.explicit_energy_grid
    assert contract.energy_edges_gev == (.9313, 1.01565, 1.1)
    points = read_output_points(root)
    assert points and all(p.point.energy_bin == 1 for p in points)
    combine_profiles._validate_profile_root("vis", root, points)


def test_root_rejects_discordant_grid_declaration(tmp_path):
    point = _points()[0]
    root = tmp_path / "bad.root"
    write_root_output(root, RootOutputPayload(
        points=(point,), energy_edges=np.array([1.1, 1.2]), mass_edges={},
        covariance_total=np.eye(1), systematic_covariances={}, ratio_objects=(),
        provenance='profile=uv\nenergy_edges_gev=[1.1, 1.3]'))
    with pytest.raises(RuntimeError, match="energy grid provenance"):
        read_output_contract(root)


def test_split_rows_do_not_receive_nominal_published_reference():
    from observable_extraction.plotting.figure4 import (
        PublishedPoint, profile_energy_rows, build_profile_figure4_comparison)
    import matplotlib.pyplot as plt
    figure, axes = build_profile_figure4_comparison(
        {}, [PublishedPoint("p_pi0", 0, 1.2, .4, .1, .1)],
        profile_energy_rows("uv", (1.1, 1.15, 1.2)))
    assert not any(ax.containers for ax in axes.flat)
    plt.close(figure)


def test_bin_inventory_assigns_shared_and_last_edges_once():
    from observable_extraction.core.energy_audit import energy_bin_inventory
    events = _synthetic_events().take(np.arange(len(_synthetic_events())) < 3)
    events = replace(events, beam_energy_gev=np.array([1.1, 1.2, 1.3]),
                     polarization=np.array([1, 2, 1]), xstrip=np.array([1, 2, 3]))
    exposures = {(811, i): FluxExposure(811, i, energy, 1., 2., .1, .6, .5)
                 for i, energy in enumerate((1.1, 1.2, 1.3), 1)}
    rows = energy_bin_inventory({"raw": events}, exposures, (1.1, 1.2, 1.3), ())
    assert [r["samples"]["raw"]["selected"] for r in rows] == [1, 2]
    assert [r["exposure"]["strata"] for r in rows] == [1, 2]
    assert all(r["status"] == "not_estimable" for r in rows)


def test_nominal_extraction_rejects_explicitly_truncated_reconstruction(tmp_path):
    import ROOT
    root = tmp_path / "narrow.root"
    with ROOT.TFile(str(root), "RECREATE") as output:
        ROOT.TNamed("reconstruction_provenance", json.dumps({
            "beam_profile": "uv", "selection": {"energy_range_gev": [1.1, 1.2]}})).Write()
    args = beam_asymmetry.build_parser().parse_args([
        "--raw", str(root), "--nominal-sample", "raw", "--raw-bdt", str(tmp_path / "absent.root")])
    with pytest.raises(ValueError, match="cover"):
        beam_asymmetry._validate_energy_inputs(args)


def test_expanded_extraction_checks_signal_mc_template_domain(tmp_path):
    import ROOT
    def write(name, bounds):
        root = tmp_path / name
        with ROOT.TFile(str(root), "RECREATE"):
            ROOT.TNamed("reconstruction_provenance", json.dumps({
                "beam_profile": "uv", "selection": {"energy_range_gev": bounds},
                "bdt_domain": {"beam_profile": "uv", "energy_range_gev": bounds}})).Write()
        return root
    low = write("low.root", [.9313, 1.1])
    mc = write("mc.root", [1.1, 1.5])
    args = beam_asymmetry.build_parser().parse_args([
        "--raw", str(low), "--nominal-sample", "raw", "--raw-bdt", str(tmp_path / "absent.root"),
        "--energy-edges", ".9313", "1.1", "--sideband", str(low), "--signal-mc", str(mc)])
    with pytest.raises(ValueError, match="cover"):
        beam_asymmetry._validate_energy_inputs(args)
