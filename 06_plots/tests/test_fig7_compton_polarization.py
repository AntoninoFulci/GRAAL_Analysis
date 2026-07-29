import math

import pytest

from plots import fig7_compton_polarization as fig7


def test_default_output_path_is_pdf():
    # Changing the default artifact type or location breaks the reproducible
    # Figure 7 workflow used by the paper build.
    assert fig7.DEFAULT_OUTPUT.name == "fig7_compton_polarization.pdf"
    assert fig7.DEFAULT_OUTPUT.parent.name == "06_plots"


def test_default_root_output_is_root_file():
    # The ROOT artifact is the machine-readable companion to the PDF figure.
    assert fig7.DEFAULT_ROOT_OUTPUT.name == "fig7_compton_polarization.root"
    assert fig7.DEFAULT_ROOT_OUTPUT.parent.name == "06_plots"


def test_draw_fig7_persists_named_root_objects(tmp_path):
    # Omitting a graph, edge marker, threshold, or canvas makes the ROOT
    # artifact unusable for downstream inspection even if the PDF is drawn.
    import ROOT

    pdf_path = tmp_path / "fig7.pdf"
    root_path = tmp_path / "fig7.root"
    fig7.draw_fig7(pdf_path, root_path)
    assert pdf_path.is_file()

    root_file = ROOT.TFile.Open(str(root_path))
    try:
        assert root_file and not root_file.IsZombie()
        for object_name in (
            "fig7",
            "polarization_514nm",
            "polarization_351nm",
            "tagging_threshold",
            "edge_514nm",
            "edge_351nm",
        ):
            assert root_file.Get(object_name), f"missing ROOT object: {object_name}"

        for object_name, edge_mev, polarization in (
            ("edge_514nm", 1098.0, 0.980),
            ("edge_351nm", 1482.4, 0.961),
        ):
            edge_line = root_file.Get(object_name)
            assert edge_line.GetX1() == pytest.approx(edge_mev, abs=0.1)
            assert edge_line.GetX2() == pytest.approx(edge_mev, abs=0.1)
            assert edge_line.GetY1() == pytest.approx(0.0)
            assert edge_line.GetY2() == pytest.approx(polarization, abs=0.002)
            assert edge_line.GetLineStyle() == 2

        threshold = root_file.Get("tagging_threshold")
        assert threshold.GetX1() == pytest.approx(550.0)
        assert threshold.GetX2() == pytest.approx(550.0)
        assert threshold.GetY2() == pytest.approx(1.05)
    finally:
        if root_file:
            root_file.Close()


def test_compton_edges_match_fig7():
    # A broken laser-energy conversion or Compton denominator moves both edges.
    assert fig7.compton_edge_mev(
        fig7.ELECTRON_ENERGY_MEV, fig7.GREEN_WAVELENGTH_NM
    ) == pytest.approx(1100, abs=10)
    assert fig7.compton_edge_mev(
        fig7.ELECTRON_ENERGY_MEV, fig7.UV_WAVELENGTH_NM
    ) == pytest.approx(1480, abs=10)


def test_fig7_operating_constants_are_exact():
    # These inputs define the published Figure 7 curves; rounded substitutes
    # visibly change the physical Compton edge.
    assert fig7.ELECTRON_ENERGY_MEV == 6027.6
    assert fig7.GREEN_WAVELENGTH_NM == 514.0
    assert fig7.UV_WAVELENGTH_NM == 351.0
    assert fig7.TAGGING_THRESHOLD_MEV == 550.0


def test_edge_polarizations_match_fig7():
    # The transfer expression must reproduce the figure's rounded edge values.
    for wavelength, expected in (
        (fig7.GREEN_WAVELENGTH_NM, 0.980),
        (fig7.UV_WAVELENGTH_NM, 0.962),
    ):
        edge = fig7.compton_edge_mev(fig7.ELECTRON_ENERGY_MEV, wavelength)
        assert fig7.linear_polarization_transfer(
            edge, fig7.ELECTRON_ENERGY_MEV, wavelength
        ) == pytest.approx(expected, abs=0.002)


def test_polarization_rejects_energies_outside_the_compton_range():
    # A negative energy and the next representable value above the UV edge are
    # both unphysical; the physical bound must have no tolerance.
    uv_edge = fig7.compton_edge_mev(
        fig7.ELECTRON_ENERGY_MEV, fig7.UV_WAVELENGTH_NM
    )
    for photon_energy_mev in (-1.0, math.nextafter(uv_edge, math.inf)):
        with pytest.raises(ValueError, match="outside Compton range"):
            fig7.linear_polarization_transfer(
                photon_energy_mev,
                fig7.ELECTRON_ENERGY_MEV,
                fig7.UV_WAVELENGTH_NM,
            )
