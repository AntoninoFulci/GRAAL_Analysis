"""Shared ROOT helpers retain the existing mass axes and drawn object lifetime."""
import gc

import numpy as np
import ROOT

from plots import dalitz, mass_histograms


def test_public_mass_helpers_are_the_dalitz_helpers():
    assert dalitz.mass2d_hist is mass_histograms.mass2d_hist
    assert dalitz.draw_truth_cross is mass_histograms.draw_truth_cross


def test_mass_histogram_keeps_axes_entries_and_flow_bins():
    hist = mass_histograms.mass2d_hist('public_mass_test', 'sample',
        np.array([.548, .1, .9]), np.array([.135, .135, .3]))
    assert hist.ClassName() == 'TH2F'
    assert hist.GetTitle() == 'sample'
    for axis, title, low, high in [
        (hist.GetXaxis(), 'M(#eta)  [GeV]', .3, .8),
        (hist.GetYaxis(), 'M(#pi^{0})  [GeV]', .05, .25)]:
        assert (axis.GetTitle(), axis.GetNbins(), axis.GetXmin(), axis.GetXmax()) == (
            title, 90, low, high)
    assert hist.GetEntries() == 3
    assert hist.Integral() == 1
    assert hist.Integral(0, 91, 0, 91) == 3


def test_truth_cross_stays_alive_through_rendering(tmp_path):
    ROOT.gROOT.SetBatch(True)
    canvas = ROOT.TCanvas('public_truth_cross', 'cross', 400, 400)
    try:
        hist = mass_histograms.mass2d_hist('public_cross_mass', 'sample',
                                          np.array([.548]), np.array([.135]))
        hist.Draw('colz')
        keep_alive = mass_histograms.draw_truth_cross()
        gc.collect()
        canvas.Update()
        canvas.SaveAs(str(tmp_path / 'cross.pdf'))
        assert (tmp_path / 'cross.pdf').stat().st_size > 0
        assert len(keep_alive) == 2
        assert sum(obj.InheritsFrom('TLine') for obj in canvas.GetListOfPrimitives()) == 2
        vertical, horizontal = keep_alive
        assert (vertical.GetX1(), vertical.GetY1(), vertical.GetX2(), vertical.GetY2()) == (
            dalitz.kin.M_ETA, .05, dalitz.kin.M_ETA, .25)
        assert (horizontal.GetX1(), horizontal.GetY1(), horizontal.GetX2(), horizontal.GetY2()) == (
            .3, dalitz.kin.M_PI0, .8, dalitz.kin.M_PI0)
        assert all(line.GetLineColor() == ROOT.kRed + 1 and line.GetLineStyle() == 2
                   for line in keep_alive)
    finally:
        canvas.Close()
