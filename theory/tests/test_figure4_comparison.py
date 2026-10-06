"""Masks and conservative residuals for the twelve-panel Figure 4 gate."""

import csv
import json

import numpy as np

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
