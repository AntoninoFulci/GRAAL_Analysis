from dataclasses import replace

import numpy as np
import pytest
import ROOT

from observable_extraction.core.models import FitDiagnostics, SigmaPoint
from observable_extraction.io.root_input import read_output_points
from observable_extraction.io.root_output import (
    OutputPoint,
    RootOutputPayload,
    write_root_output,
)


def _points():
    diagnostics = FitDiagnostics(True, 8.0, 10, 0.63, False)
    ratio = OutputPoint(
        sample="raw_bdt",
        estimator="ratio",
        point=SigmaPoint(
            "p_pi0", 0, 2, 1.1, 1.2, 1.08, 1.12, 1.099,
            0.3, 0.05, 0.06, diagnostics,
        ),
        sigma_uncorrected=0.28,
        systematic_total=0.04,
        background_fraction=0.12,
        count_vertical=120,
        count_horizontal=100,
        flux_vertical=1000.0,
        flux_horizontal=900.0,
        polarization_vertical=0.60,
        polarization_horizontal=0.58,
    )
    likelihood = replace(
        ratio,
        estimator="likelihood",
        point=replace(
            ratio.point,
            sigma=0.31,
            stat_low=0.04,
            stat_high=0.07,
            diagnostics=FitDiagnostics(True, 0.0, 0, 1.0, False),
        ),
    )
    return ratio, likelihood


def _write(path):
    points = _points()
    payload = RootOutputPayload(
        points=points,
        energy_edges=np.array([1.1, 1.2]),
        mass_edges={"p_pi0": np.array([1.08, 1.12])},
        covariance_total=np.eye(len(points)),
        systematic_covariances={},
        ratio_objects=(),
        provenance="synthetic",
    )
    write_root_output(path, payload)
    return payload


def test_root_output_points_round_trip(tmp_path):
    output = tmp_path / "beam_asymmetry.root"
    payload = _write(output)

    assert read_output_points(output) == payload.points


def test_reader_rejects_missing_sigma_tree_with_path(tmp_path):
    output = tmp_path / "empty.root"
    source = ROOT.TFile(str(output), "RECREATE")
    source.Close()

    with pytest.raises(RuntimeError, match=r"empty\.root.*sigma_points"):
        read_output_points(output)


@pytest.mark.parametrize("mapping", [None, "not a valid mapping"])
def test_reader_rejects_missing_or_malformed_id_mapping(tmp_path, mapping):
    output = tmp_path / "bad_mapping.root"
    _write(output)
    source = ROOT.TFile(str(output), "UPDATE")
    source.Delete("id_mapping;*")
    if mapping is not None:
        ROOT.TNamed("id_mapping", mapping).Write()
    source.Close()

    with pytest.raises(RuntimeError, match=r"bad_mapping\.root.*id_mapping"):
        read_output_points(output)
