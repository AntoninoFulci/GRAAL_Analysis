"""Masks and conservative residuals for the twelve-panel Figure 4 gate."""

import csv
import json
from pathlib import Path

import numpy as np
import pytest

from graal_theory import figure4_comparison
from graal_theory.figure4_comparison import compare_figure4, write_figure4_run
from graal_theory.figure4_integration import (
    Figure4BinMoment, Figure4CertifiedBin, Figure4PanelResult,
)
from graal_theory.figure4_reference import PublishedCurvePoint


def _bin(index, sigma, status="calculated"):
    mass = 1.52+.04*index
    moment = Figure4BinMoment("p_eta", (1.4, 1.5),
        (mass-.02, mass+.02), (1.4, 1.5), (mass-.02, mass+.02),
        np.array([1.45]), sigma, 1., .5, .5, mass, 0., status)
    return Figure4CertifiedBin(moment, status, (), .003, {})


def test_comparison_interpolates_only_adjacent_accepted_bins():
    bins = (_bin(0, .10), _bin(1, .20),
            _bin(2, 0., "masked_nonconverged"), _bin(3, .40))
    panel = Figure4PanelResult("p_eta", (1.4, 1.5),
        np.array([1.50, 1.54, 1.58, 1.62, 1.66]), bins,
        np.eye(4)*1e-6, 4, 8, tuple(range(2026, 2034)), "direct")
    published = (
        PublishedCurvePoint("p_eta", 3, 1.54, .15, .02),
        PublishedCurvePoint("p_eta", 3, 1.58, .25, .02),
        PublishedCurvePoint("p_eta", 3, 1.49, .10, .02),
    )
    result = compare_figure4({(3, "p_eta"): panel}, published)
    assert [row.status for row in result.residuals] == ["compatible", "masked", "masked"]
    assert result.status == "incomplete"


def test_comparison_uses_additive_reading_and_numerical_bounds():
    bins = (_bin(0, .10), _bin(1, .20))
    panel = Figure4PanelResult("p_eta", (1.4, 1.5),
        np.array([1.50, 1.54, 1.58]), bins, np.eye(2)*1e-6,
        4, 8, tuple(range(2026, 2034)), "direct")
    points = (
        PublishedCurvePoint("p_eta", 3, 1.54, .15+.023, .020),
        PublishedCurvePoint("p_eta", 3, 1.55, .210, .020),
    )
    result = compare_figure4({(3, "p_eta"): panel}, points)
    assert result.residuals[0].status == "compatible"
    assert result.residuals[1].status == "discrepant"


def test_writer_preserves_all_nominal_bins_and_fingerprints(tmp_path):
    panels = {}
    for energy in range(4):
        for pair in ("p_pi0", "p_eta", "eta_pi0"):
            low = {"p_pi0": 1., "p_eta": 1.4, "eta_pi0": .6}[pair]
            bins = []
            for index in range(10):
                a, b = low+.04*index, low+.04*(index+1)
                status = "masked_kinematic" if index == 9 else "calculated"
                moment = Figure4BinMoment(pair, (1.1+.1*energy, 1.2+.1*energy),
                    (a,b), None if index == 9 else (1.1+.1*energy,1.2+.1*energy),
                    None if index == 9 else (a,b), np.array([1.15+.1*energy]),
                    .1 if index < 9 else 0., 1. if index < 9 else 0.,
                    .5 if index < 9 else 0., .5 if index < 9 else 0.,
                    (a+b)/2 if index < 9 else 0., 0., status)
                bins.append(Figure4CertifiedBin(moment, status, (), .003, {}))
            panels[(energy,pair)] = Figure4PanelResult(pair,
                (1.1+.1*energy, 1.2+.1*energy), np.linspace(low,low+.4,11),
                tuple(bins), np.eye(10)*1e-6, 4, 8,
                tuple(range(2026,2034)), "direct")
    comparison = compare_figure4(panels, ())
    output = write_figure4_run(tmp_path/"run", panels, comparison,
        {"source_sha256":"a", "parameters_sha256":"b", "code_sha256":"c"})
    with (output/"predictions.csv").open() as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 120
    assert {row["status"] for row in rows} == {"calculated", "masked_kinematic"}
    assert rows[0]["source_sha256"] == "a"
    assert (output/"figure4_comparison.pdf").is_file()
    assert len(json.loads((output/"predictions.json").read_text())) == 120


@pytest.mark.parametrize("publication_fails", [False, True])
def test_replacement_preserves_previous_bundle_until_published(tmp_path, monkeypatch, publication_fails):
    panels = {}
    for energy in range(4):
        for pair, low in (("p_pi0", 1.), ("p_eta", 1.4), ("eta_pi0", .6)):
            interval = (1.1+.1*energy, 1.2+.1*energy)
            edges = np.linspace(low, low+.4, 11)
            bins = []
            for left, right in zip(edges[:-1], edges[1:]):
                moment = Figure4BinMoment(pair, interval, (left, right), interval,
                    (left, right), np.array([sum(interval)/2]), .1, 1., .5, .5,
                    (left+right)/2, 0., "calculated")
                bins.append(Figure4CertifiedBin(moment, "calculated", (), .003, {}))
            panels[(energy, pair)] = Figure4PanelResult(pair, interval, edges,
                tuple(bins), np.eye(10), 4, 8, tuple(range(8)), "direct")
    destination = tmp_path / "run"
    destination.mkdir()
    previous = destination / "previous-result.txt"
    previous.write_text("previous result")
    original_replace = figure4_comparison.os.replace

    def fail_publication(source, target):
        if (publication_fails and Path(target) == destination
                and not (Path(source)/previous.name).exists()):
            raise OSError("simulated publication failure")
        return original_replace(source, target)

    monkeypatch.setattr(figure4_comparison.os, "replace", fail_publication)
    if publication_fails:
        with pytest.raises(OSError, match="publication failure"):
            write_figure4_run(destination, panels, compare_figure4(panels, ()),
                {"source_sha256": "a", "parameters_sha256": "b", "code_sha256": "c"},
                replace_existing=True)
        assert previous.is_file(), "previous bundle was deleted before publication succeeded"
        assert previous.read_text() == "previous result"
    else:
        write_figure4_run(destination, panels, compare_figure4(panels, ()),
            {"source_sha256": "a", "parameters_sha256": "b", "code_sha256": "c"},
            replace_existing=True)
        assert not previous.exists()
        assert (destination/"predictions.json").is_file()
    assert list(tmp_path.iterdir()) == [destination]
