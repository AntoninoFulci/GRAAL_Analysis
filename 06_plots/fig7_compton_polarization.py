"""Compton-backscattering quantities used to reproduce GRAAL Figure 7.

All energies are MeV.  The two laser lines and ESRF electron energy are the
GRAAL operating values; the tagging threshold marks the lower energy shown in
the figure.
"""
from __future__ import annotations

from array import array
from pathlib import Path

from graal_common.physics.compton import (
    ELECTRON_ENERGY_MEV,
    GREEN_WAVELENGTH_NM,
    UV_WAVELENGTH_NM,
    compton_edge_mev,
    compton_x,
    laser_energy_mev,
    linear_polarization_transfer,
)

TAGGING_THRESHOLD_MEV = 550.0

_ARTIFACT_DIR = Path(__file__).resolve().parent / "artifacts"
DEFAULT_OUTPUT = _ARTIFACT_DIR / "fig7_compton_polarization.pdf"
DEFAULT_ROOT_OUTPUT = _ARTIFACT_DIR / "fig7_compton_polarization.root"

__all__ = [
    "ELECTRON_ENERGY_MEV",
    "GREEN_WAVELENGTH_NM",
    "UV_WAVELENGTH_NM",
    "TAGGING_THRESHOLD_MEV",
    "DEFAULT_OUTPUT",
    "DEFAULT_ROOT_OUTPUT",
    "laser_energy_mev",
    "compton_x",
    "compton_edge_mev",
    "linear_polarization_transfer",
    "draw_fig7",
]


def draw_fig7(
    output_path: Path = DEFAULT_OUTPUT,
    root_output_path: Path = DEFAULT_ROOT_OUTPUT,
) -> None:
    """Draw the Figure 7 curves as a PDF and persist their ROOT objects."""
    import ROOT

    output_path = Path(output_path)
    root_output_path = Path(root_output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    root_output_path.parent.mkdir(parents=True, exist_ok=True)
    ROOT.gROOT.SetBatch(True)

    canvas = ROOT.TCanvas("fig7", "Fig. 7 Compton polarization", 800, 650)
    canvas.SetLeftMargin(0.13)
    canvas.SetBottomMargin(0.12)

    legend = ROOT.TLegend(0.57, 0.19, 0.86, 0.38)
    legend.SetBorderSize(0)
    legend.SetFillStyle(0)

    graphs = []
    edge_lines = []
    curves = (
        (GREEN_WAVELENGTH_NM, ROOT.kGreen + 2, "514 nm laser"),
        (UV_WAVELENGTH_NM, ROOT.kBlue + 1, "351 nm laser"),
    )
    for wavelength_nm, color, label in curves:
        edge_mev = compton_edge_mev(ELECTRON_ENERGY_MEV, wavelength_nm)
        points = 201
        energies = array("d", (edge_mev * index / (points - 1) for index in range(points)))
        polarizations = array(
            "d",
            (
                linear_polarization_transfer(energy, ELECTRON_ENERGY_MEV, wavelength_nm)
                for energy in energies
            ),
        )
        graph = ROOT.TGraph(points, energies, polarizations)
        graph.SetName(f"polarization_{wavelength_nm:.0f}nm")
        graph.SetLineColor(color)
        graph.SetLineWidth(3)
        graph.SetTitle("")
        draw_option = "AL" if not graphs else "L SAME"
        graph.Draw(draw_option)
        if not graphs:
            graph.GetXaxis().SetTitle("Backscattered photon energy (MeV)")
            graph.GetYaxis().SetTitle("Linear polarization transfer")
            graph.GetXaxis().SetLimits(0.0, 1550.0)
            graph.SetMinimum(0.0)
            graph.SetMaximum(1.05)
        legend.AddEntry(graph, label, "l")
        graphs.append(graph)

        edge_line = ROOT.TLine(
            edge_mev, 0.0, edge_mev, polarizations[-1]
        )
        edge_line.SetLineColor(color)
        edge_line.SetLineStyle(2)
        edge_line.SetLineWidth(2)
        edge_line.Draw()
        edge_lines.append((f"edge_{wavelength_nm:.0f}nm", edge_line))

        print(
            f"{wavelength_nm:.0f} nm: edge = {edge_mev:.1f} MeV, "
            f"polarization = {polarizations[-1]:.3f}"
        )

    threshold = ROOT.TLine(TAGGING_THRESHOLD_MEV, 0.0, TAGGING_THRESHOLD_MEV, 1.05)
    threshold.SetLineColor(ROOT.kRed + 1)
    threshold.SetLineStyle(2)
    threshold.SetLineWidth(2)
    threshold.Draw()
    legend.AddEntry(threshold, "550 MeV tagging threshold", "l")
    legend.Draw()
    canvas.SaveAs(str(output_path))

    root_file = ROOT.TFile(str(root_output_path), "RECREATE")
    try:
        for graph in graphs:
            graph.Write()
        for edge_name, edge_line in edge_lines:
            edge_line.Write(edge_name)
        threshold.Write("tagging_threshold")
        canvas.Write()
    finally:
        root_file.Close()


if __name__ == "__main__":
    draw_fig7()
