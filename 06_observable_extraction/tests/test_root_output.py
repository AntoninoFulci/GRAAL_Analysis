import numpy as np
import ROOT

from observable_extraction.core.models import FitDiagnostics, SigmaPoint
from observable_extraction.io.root_output import (
    OutputPoint,
    RatioObject,
    RootOutputPayload,
    write_root_output,
)


def _point():
    return OutputPoint(
        sample="raw_bdt",
        estimator="ratio",
        point=SigmaPoint(
            pair="p_pi0",
            energy_bin=0,
            mass_bin=0,
            energy_low_gev=1.1,
            energy_high_gev=1.2,
            mass_low_gev=1.07,
            mass_high_gev=1.10,
            mass_mean_gev=1.085,
            sigma=0.3,
            stat_low=0.05,
            stat_high=0.06,
            diagnostics=FitDiagnostics(True, 8.0, 10, 0.63, False),
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


def test_root_output_contains_points_edges_covariance_and_ratio_objects(tmp_path):
    output = tmp_path / "beam_asymmetry.root"
    ratio = RatioObject(
        pair="p_pi0",
        energy_bin=0,
        mass_bin=0,
        phi=np.array([0.2, 0.7]),
        value=np.array([0.1, -0.1]),
        error=np.array([0.02, 0.03]),
        sigma=0.3,
    )
    payload = RootOutputPayload(
        points=(_point(),),
        energy_edges=np.array([1.1, 1.2, 1.3, 1.4, 1.5]),
        mass_edges={"p_pi0": np.linspace(1.07, 1.37, 11)},
        covariance_total=np.array([[0.01]]),
        systematic_covariances={"polarization_scale_3pct": np.array([[0.001]])},
        ratio_objects=(ratio,),
        provenance="synthetic test",
        statistical_covariance=np.array([[0.009]]),
        bootstrap_covariance=np.array([[0.008]]),
    )

    write_root_output(output, payload)

    source = ROOT.TFile.Open(str(output))
    try:
        assert source.Get("sigma_points").GetEntries() == 1
        assert source.Get("binning/energy_edges")
        assert source.Get("binning/p_pi0_mass_edges")
        assert source.Get("covariance/total")
        assert source.Get("covariance/statistical")
        assert source.Get("covariance/bootstrap_run")
        assert source.Get("covariance/correlation_total")
        assert source.Get("diagnostics/ratio_vs_likelihood")
        assert source.Get("covariance/systematic/polarization_scale_3pct")
        assert source.Get("ratio_objects/p_pi0/e0/m0/ratio")
        assert source.Get("ratio_objects/p_pi0/e0/m0/fit")
        assert source.Get("provenance")
    finally:
        source.Close()
