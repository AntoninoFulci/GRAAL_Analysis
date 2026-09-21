import numpy as np

from observable_extraction.tests.test_figure4 import _points
from observable_extraction.plotting.diagnostics import (
    write_fit_diagnostics_pdf,
    write_false_asymmetry_controls_pdf,
    write_photon_multiplicity_pdf,
    write_point_comparison_pdf,
    write_systematic_summary_pdf,
)


def test_diagnostic_writers_create_pdf_artifacts(tmp_path):
    comparison = tmp_path / "comparison.pdf"
    fits = tmp_path / "fits.pdf"
    systematics = tmp_path / "systematics.pdf"
    controls = tmp_path / "controls.pdf"
    multiplicity = tmp_path / "multiplicity.pdf"

    write_point_comparison_pdf(comparison, _points(), group_by="estimator")
    write_fit_diagnostics_pdf(fits, _points())
    write_systematic_summary_pdf(
        systematics,
        {"polarization_scale_3pct": np.eye(len(_points())) * 0.01},
    )
    write_false_asymmetry_controls_pdf(
        controls,
        {"p_pi0": np.linspace(0.0, 2.0 * np.pi, 20, endpoint=False)},
    )
    write_photon_multiplicity_pdf(
        multiplicity,
        inclusive_count=100,
        exactly_four_count=80,
        shifts=np.array([0.01, -0.02]),
        best_quartet_resolved=False,
    )

    for path in (comparison, fits, systematics, controls, multiplicity):
        assert path.read_bytes().startswith(b"%PDF")
