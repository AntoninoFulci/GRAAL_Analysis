#!/usr/bin/env python3
"""Dalitz plot M(eta p) vs M(pi0 p), plus the meson invariant masses.

Figure families:
  dalitz_*    M(eta p) vs M(pi0 p), colz — the resonance view
  massa_*     M(eta) and M(pi0) on their own
  masse_2d_*  those same two masses against each other, colz — where the gate
              shows up as the blob tightening onto the truth crossing
  dalitz_s_*  signed pair invariant squares in GeV², filled directly
  residuo_*   event-wise departure from the nominal on-shell Dalitz identity
  *_unit_area copies normalized including under/overflow; fraction per bin


Compares the two reconstructions — plain chi2 against the BDT-gated one — which
is the whole reason both exist. Everything kinematic comes from
plots.core.kinematics; plots.core.reconstruction_data reads ROOT, while this module fills
histograms and draws.

Requires certified pairing/missing-mass reconstruction provenance. ROOT stores that provenance,
input hashes, sample populations, units and a histogram dictionary as TNamed JSON.

Two proton variants are produced, and they are NOT equivalent:

  misurato  — uses the measured `proton` branch.
              This variant carries recoil-track information.
  implicito — uses `missing`. Note the algebraic identity
                  eta + missing = beam + target - pi0,
              so this variant depends on neither the measured proton nor the
              measured eta. It is a missing-mass plot: clean by construction,
              but it is not new information.

Run:
    python -m plots.dalitz --chi2 results/reco/reco_eta_pi0_chi2.root \\
                           --bdt  results/reco/reco_eta_pi0_bdt.root
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack
import json
import sys
from collections.abc import Mapping
from pathlib import Path

import numpy as np
import ROOT

from plots.core import kinematics as kin
from plots.core import reconstruction_data
from plots.core import dalitz_metadata

CHI2_TREE = "reco_eta_pi0_chi2"
BDT_TREE = "reco_eta_pi0_bdt"

# Dalitz axis range. Physics bounds it from below (M(eta p) >= m_eta + m_p =
# 1.486) and W stays under 2 GeV at GRAAL beam energies. The window is
# deliberately wider so anything unphysical stays visible instead of piling into
# the edge bin.
_DALITZ_MIN, _DALITZ_MAX, _DALITZ_BINS = 1.0, 2.8, 90

# Windows for the meson masses. The 1D distributions and the 2D correlation share
# them on purpose: the 2D figure is those two plots crossed, so it can only be
# read against them if the axes match.
_ETA_MASS_MIN, _ETA_MASS_MAX = 0.3, 0.8
_PI0_MASS_MIN, _PI0_MASS_MAX = 0.05, 0.25
_MASS2D_BINS = 90


# Compatibility for callers that imported the former private helpers. New code
# uses the explicit adapter API and ReconstructionArrays structure below.
_as_array = reconstruction_data.as_array
_open_tree = reconstruction_data.open_tree
_collect = reconstruction_data.collect_legacy


def _dalitz_hist(name: str, title: str, x: np.ndarray, y: np.ndarray) -> ROOT.TH2F:
    h = ROOT.TH2F(
        name,
        f"{title};M(#eta p)  [GeV];M(#pi^{{0}} p)  [GeV]",
        _DALITZ_BINS, _DALITZ_MIN, _DALITZ_MAX,
        _DALITZ_BINS, _DALITZ_MIN, _DALITZ_MAX,
    )
    for xi, yi in zip(x, y):
        h.Fill(xi, yi)
    return h


def _dalitz_squared_hist(name, title, x, y):
    """Fill signed s directly; this is yield per bin, not a transformed density."""
    h = ROOT.TH2D(name, f"{title};s_{{p#eta}}  [GeV^{{2}}];s_{{p#pi^{{0}}}}  [GeV^{{2}}]",
                  _DALITZ_BINS, _DALITZ_MIN**2, _DALITZ_MAX**2,
                  _DALITZ_BINS, _DALITZ_MIN**2, _DALITZ_MAX**2)
    for xi, yi in zip(x, y):
        h.Fill(xi, yi)
    return h


def _histogram_summary(h):
    """Count corner flow cells once, and retain axes for ROOT-only readers."""
    total = (h.Integral(0, h.GetNbinsX()+1, 0, h.GetNbinsY()+1)
             if h.GetDimension() == 2 else h.Integral(0, h.GetNbinsX()+1))
    axes = [h.GetXaxis()] + ([h.GetYaxis()] if h.GetDimension() == 2 else [])
    return {'entries': h.GetEntries(), 'all_bins': total, 'visible_bins': h.Integral(),
            'flow_bins': total - h.Integral(),
            'axes': [{'title': a.GetTitle(), 'bins': a.GetNbins(),
                      'edges': [a.GetBinLowEdge(i) for i in range(1, a.GetNbins()+2)]}
                     for a in axes]}


def _unit_area(h):
    clone = h.Clone(h.GetName() + '_unit_area')
    clone.SetDirectory(0)
    clone.Sumw2()
    total = _histogram_summary(h)['all_bins']
    if total:
        clone.Scale(1. / total)
    label = ('area unitaria (under/overflow inclusi)' if total
             else 'campione vuoto (normalizzazione n/d)')
    clone.SetTitle(h.GetTitle() + ' - ' + label)
    axis = clone.GetZaxis() if clone.GetDimension() == 2 else clone.GetYaxis()
    axis.SetTitle('frazione / bin')
    return clone


def _draw_diagnostics(hists, out_dir):
    for prefix in ('dalitz_s', 'residuo'):
        names = [f'{prefix}_{tag}_{mode}' for mode in ('misurato', 'implicito')
                 for tag in ('chi2', 'bdt')]
        for suffix in ('', '_unit_area') if prefix == 'dalitz_s' else ('',):
            stem = prefix + '_confronto' + suffix
            c = ROOT.TCanvas('c_' + stem, stem, 1500, 1000)
            c.Divide(2, 2)
            # Same color scale makes the two normalized samples comparable.
            maximum = max(hists[name + suffix].GetMaximum() for name in names)
            for i, name in enumerate(names, 1):
                c.cd(i)
                ROOT.gPad.SetRightMargin(0.17)
                h = hists[name + suffix]
                h.GetZaxis().SetTitleOffset(1.0)
                h.SetMinimum(0.)
                h.SetMaximum(maximum * (1.1 if prefix == 'residuo' else 1.0) if maximum > 0 else 1.)
                h.Draw('colz' if prefix == 'dalitz_s' else 'hist')
            _save(c, out_dir, stem)
    for meson in ('eta', 'pi0'):
        stem = f'massa_{meson}_confronto_unit_area'
        c = ROOT.TCanvas('c_' + stem, stem, 900, 700)
        hc, hb = (hists[f'massa_{meson}_{tag}_unit_area'] for tag in ('chi2', 'bdt'))
        hc.SetMaximum(max(hc.GetMaximum(), hb.GetMaximum(), 0.01) * 1.15)
        hc.Draw('hist')
        hb.Draw('hist same')
        leg = ROOT.TLegend(0.60, 0.72, 0.90, 0.87)
        leg.AddEntry(hc, 'solo chi2', 'l')
        leg.AddEntry(hb, 'gate BDT', 'l')
        leg.Draw()
        _save(c, out_dir, stem)


def _mass_hist(name: str, title: str, x: np.ndarray, lo: float, hi: float) -> ROOT.TH1F:
    h = ROOT.TH1F(name, title, 100, lo, hi)
    for xi in x:
        h.Fill(xi)
    return h


def _mass2d_hist(name: str, title: str, eta: np.ndarray, pi0: np.ndarray) -> ROOT.TH2F:
    """The same two masses the 1D plots show, plotted against each other.

    Deliberately on the 1D windows: this figure is those two plots crossed, and
    reading one against the other only works if the axes agree with them.
    """
    h = ROOT.TH2F(
        name,
        f"{title};M(#eta)  [GeV];M(#pi^{{0}})  [GeV]",
        _MASS2D_BINS, _ETA_MASS_MIN, _ETA_MASS_MAX,
        _MASS2D_BINS, _PI0_MASS_MIN, _PI0_MASS_MAX,
    )
    for xi, yi in zip(eta, pi0):
        h.Fill(xi, yi)
    return h


def _draw_truth_cross() -> list:
    """Mark (M_ETA, M_PI0) on the current pad: where the signal must sit.

    Returns the lines so the caller can hold a reference — PyROOT collects a
    TLine nothing points at, and it disappears from the canvas silently.
    """
    v = ROOT.TLine(kin.M_ETA, _PI0_MASS_MIN, kin.M_ETA, _PI0_MASS_MAX)
    h = ROOT.TLine(_ETA_MASS_MIN, kin.M_PI0, _ETA_MASS_MAX, kin.M_PI0)
    for line in (v, h):
        line.SetLineColor(ROOT.kRed + 1)
        line.SetLineStyle(2)
        line.Draw()
    return [v, h]


def _save(canvas, out_dir: Path, stem: str) -> None:
    """Every figure goes out as PNG (to look at) and PDF (vector, for talks)."""
    # canvas.SaveAs(str(out_dir / f"{stem}.png"))
    canvas.SaveAs(str(out_dir / f"{stem}.pdf"))


def _draw_raw_mass_comparison(
    meson: str,
    truth: float,
    chi2: reconstruction_data.ReconstructionArrays | Mapping[str, np.ndarray],
    bdt: reconstruction_data.ReconstructionArrays | Mapping[str, np.ndarray],
    out_dir: Path,
    hists: dict,
) -> None:
    """Compare chi2 and BDT+chi2 meson masses after pairing and missing-mass selection."""
    label = "#eta" if meson == "eta" else "#pi^{0}"
    lo, hi = (
        (_ETA_MASS_MIN, _ETA_MASS_MAX)
        if meson == "eta"
        else (_PI0_MASS_MIN, _PI0_MASS_MAX)
    )
    chi2_name = f"massa_{meson}_chi2_raw_confronto"
    bdt_name = f"massa_{meson}_bdt_raw_confronto"
    raw_mass_field = f"{meson}_mass_raw"
    chi2_raw = (
        chi2[raw_mass_field]
        if isinstance(chi2, Mapping)
        else getattr(chi2, raw_mass_field)
    )
    bdt_raw = (
        bdt[raw_mass_field]
        if isinstance(bdt, Mapping)
        else getattr(bdt, raw_mass_field)
    )
    hc = _mass_hist(
        chi2_name, "solo chi2", chi2_raw, lo, hi
    )
    hb = _mass_hist(
        bdt_name, "gate BDT + chi2", bdt_raw, lo, hi
    )
    hb.GetXaxis().SetTitle(f"M({label})  [GeV]")
    hb.GetYaxis().SetTitle("eventi")
    hists[chi2_name] = hc
    hists[bdt_name] = hb

    c = ROOT.TCanvas(
        f"c_massa_{meson}_raw_confronto", f"{meson} raw", 900, 700
    )
    c.SetLeftMargin(0.12)
    hc.SetTitle(
        f"massa invariante {label} dopo la selezione;"
        f"M({label})  [GeV];eventi"
    )
    hc.GetYaxis().CenterTitle()
    hc.GetYaxis().SetTitleOffset(1.45)
    hc.SetLineColor(ROOT.kGray + 2)
    hc.SetFillColorAlpha(ROOT.kGray, 0.4)
    hb.SetLineColor(ROOT.kAzure + 1)
    hb.SetLineWidth(2)
    hc.SetMaximum(max(hc.GetMaximum(), hb.GetMaximum(), 1.) * 1.15)
    hc.Draw("hist")
    hb.Draw("hist same")

    leg = ROOT.TLegend(0.58, 0.68, 0.90, 0.88)
    leg.AddEntry(hc, "solo chi2", "f")
    leg.AddEntry(hb, "gate BDT + chi2", "l")
    line = ROOT.TLine(truth, 0, truth, max(hc.GetMaximum(), hb.GetMaximum()) * 1.05)
    line.SetLineColor(ROOT.kRed + 1)
    line.SetLineStyle(2)
    line.Draw()
    leg.AddEntry(line, "valore vero", "l")
    leg.Draw()
    _save(c, out_dir, f"massa_{meson}_raw_confronto")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--chi2", type=Path, required=True,
                   help="output di reconstruct_eta_pi0_chi2")
    p.add_argument("--bdt", type=Path, required=True,
                   help="output di reconstruct_eta_pi0_bdt")
    p.add_argument("--out-dir", type=Path, default=Path("results/plots"))
    p.add_argument("--profile", choices=("uv", "vis"), help="sample label; no additional energy cut")
    p.add_argument("--run-manifest", type=Path, default=dalitz_metadata.DEFAULT_MANIFEST)
    args = p.parse_args(argv)

    ROOT.gROOT.SetBatch(True)
    ROOT.gStyle.SetOptStat(0)
    ROOT.gStyle.SetPalette(ROOT.kBird)

    args.out_dir.mkdir(parents=True, exist_ok=True)

    print("Lettura degli alberi ricostruiti:")
    with ExitStack() as inputs:
        fc, tc = reconstruction_data.open_tree(args.chi2, CHI2_TREE, allow_empty=True)
        inputs.callback(fc.Close)
        fb, tb = reconstruction_data.open_tree(args.bdt, BDT_TREE, allow_empty=True)
        inputs.callback(fb.Close)
        provenance = {tag: dalitz_metadata.read_provenance(source, tree)
                      for tag, source, tree in (("chi2", fc, tc), ("bdt", fb, tb))}
        comparison = dalitz_metadata.compare_selections(
            provenance['chi2'], provenance['bdt'])
        chi2 = reconstruction_data.collect(tc)
        bdt = reconstruction_data.collect(tb)

    samples = {'chi2': chi2, 'bdt': bdt}
    for tag, data in samples.items():
        arrays = [data.eta_mass, data.pi0_mass, data.eta_mass_raw, data.pi0_mass_raw,
                  data.beam_energy, data.w, *data.identity_residual.values(),
                  *(a for pairs in data.pair_mass_squared.values() for a in pairs.values())]
        if any(not np.all(np.isfinite(a)) for a in arrays):
            raise ValueError(f'non-finite Dalitz input in {tag}; no events silently removed')
    metadata = dalitz_metadata.build_metadata(
        args, samples, provenance, comparison, ['python', '-m', 'plots.dalitz',
                                               *(argv if argv is not None else sys.argv[1:])])

    hists = {}
    for tag, data, lab in (("chi2", chi2, "solo chi2"), ("bdt", bdt, "gate BDT")):
        for var, vlab in (("meas", "misurato"), ("miss", "implicito")):
            name = f"dalitz_{tag}_{vlab}"
            hists[name] = _dalitz_hist(
                name, f"{lab}  -  protone {vlab}",
                getattr(data, f"mep_{var}"), getattr(data, f"mpp_{var}"),
            )
            name_s = f'dalitz_s_{tag}_{vlab}'
            squares = data.pair_mass_squared[var]
            hists[name_s] = _dalitz_squared_hist(
                name_s, f'{lab} - protone {vlab}', squares['p_eta'], squares['p_pi0'])
            name_r = f'residuo_{tag}_{vlab}'
            hists[name_r] = _mass_hist(
                name_r, f'{lab} - protone {vlab};#Sigma s - W^{{2}} - #Sigma m_{{nom}}^{{2}} [GeV^{{2}}];eventi',
                data.identity_residual[var], -2., 2.)

    hists["massa_eta_chi2"] = _mass_hist(
        "massa_eta_chi2", "solo chi2", chi2.eta_mass, _ETA_MASS_MIN, _ETA_MASS_MAX)
    hists["massa_eta_bdt"] = _mass_hist(
        "massa_eta_bdt", "gate BDT", bdt.eta_mass, _ETA_MASS_MIN, _ETA_MASS_MAX)
    hists["massa_pi0_chi2"] = _mass_hist(
        "massa_pi0_chi2", "solo chi2", chi2.pi0_mass, _PI0_MASS_MIN, _PI0_MASS_MAX)
    hists["massa_pi0_bdt"] = _mass_hist(
        "massa_pi0_bdt", "gate BDT", bdt.pi0_mass, _PI0_MASS_MIN, _PI0_MASS_MAX)

    # The two meson masses against each other: on this figure the gate shows up
    # as the blob tightening onto the truth crossing, not as a shifted median.
    for tag, data, lab in (("chi2", chi2, "solo chi2"), ("bdt", bdt, "gate BDT")):
        name = f"masse_2d_{tag}"
        hists[name] = _mass2d_hist(name, lab, data.eta_mass, data.pi0_mass)

    # --- one canvas per Dalitz ---
    for name in [k for k in hists if k.startswith("dalitz_")]:
        c = ROOT.TCanvas(f"c_{name}", name, 800, 700)
        c.SetRightMargin(0.13)
        hists[name].GetZaxis().SetTitle('eventi / bin')
        hists[name].Draw("colz")
        _save(c, args.out_dir, name)

    # --- the two meson masses against each other, one canvas each ---
    # The crossing lines mark where the signal must sit. Kept alive in a list
    # because PyROOT garbage-collects a TLine that nothing references, and it
    # then vanishes from the canvas without any error.
    keep_alive = []
    for name in ["masse_2d_chi2", "masse_2d_bdt"]:
        c = ROOT.TCanvas(f"c_{name}", name, 800, 700)
        c.SetRightMargin(0.13)
        hists[name].Draw("colz")
        keep_alive.extend(_draw_truth_cross())
        _save(c, args.out_dir, name)

    # --- the two side by side ---
    c = ROOT.TCanvas("c_masse_2d", "masse 2D", 1500, 650)
    c.Divide(2, 1)
    for i, name in enumerate(["masse_2d_chi2", "masse_2d_bdt"], start=1):
        c.cd(i)
        ROOT.gPad.SetRightMargin(0.13)
        hists[name].Draw("colz")
        keep_alive.extend(_draw_truth_cross())
    _save(c, args.out_dir, "masse_2d_confronto")

    # --- the four-panel summary ---
    c = ROOT.TCanvas("c_confronto", "Dalitz", 1500, 1000)
    c.Divide(2, 2)
    for i, name in enumerate(
        ["dalitz_chi2_misurato", "dalitz_bdt_misurato",
         "dalitz_chi2_implicito", "dalitz_bdt_implicito"], start=1
    ):
        c.cd(i)
        ROOT.gPad.SetRightMargin(0.13)
        hists[name].Draw("colz")
    _save(c, args.out_dir, "dalitz_confronto")

    # --- mass distributions, the two samples overlaid ---
    for meson, truth in (("eta", kin.M_ETA), ("pi0", kin.M_PI0)):
        c = ROOT.TCanvas(f"c_massa_{meson}", meson, 900, 700)
        hc = hists[f"massa_{meson}_chi2"]
        hb = hists[f"massa_{meson}_bdt"]
        label = "#eta" if meson == "eta" else "#pi^{0}"
        hc.SetTitle(f"massa invariante {label};M({label})  [GeV];eventi")
        hc.SetLineColor(ROOT.kGray + 2)
        hc.SetFillColorAlpha(ROOT.kGray, 0.4)
        hb.SetLineColor(ROOT.kAzure + 1)
        hb.SetLineWidth(2)
        hb.GetXaxis().SetTitle(f"M({label})  [GeV]")
        hb.GetYaxis().SetTitle("eventi")
        hc.SetMaximum(max(hc.GetMaximum(), hb.GetMaximum(), 1.) * 1.15)
        hc.Draw("hist")
        hb.Draw("hist same")

        leg = ROOT.TLegend(0.58, 0.62, 0.90, 0.88)
        leg.AddEntry(hc, "solo chi2", "f")
        leg.AddEntry(hb, "gate BDT", "l")

        line = ROOT.TLine(truth, 0, truth, hc.GetMaximum() * 1.05)
        line.SetLineColor(ROOT.kRed + 1)
        line.SetLineStyle(2)
        line.Draw()
        leg.AddEntry(line, "valore vero", "l")
        leg.Draw()
        _save(c, args.out_dir, f"massa_{meson}")

    # Raw mass comparison with normalized overlays.
    for meson, truth in (("eta", kin.M_ETA), ("pi0", kin.M_PI0)):
        _draw_raw_mass_comparison(
            meson, truth, chi2, bdt, args.out_dir, hists
        )

    for name, h in list(hists.items()):
        if name.startswith('massa_'):
            label = '#eta' if name.startswith('massa_eta_') else '#pi^{0}'
            h.GetXaxis().SetTitle(f'M({label})  [GeV]')
            h.GetYaxis().SetTitle('eventi')
        elif h.GetDimension() == 2:
            h.GetZaxis().SetTitle('eventi / bin')
        hists[name + '_unit_area'] = _unit_area(h)
    _draw_diagnostics(hists, args.out_dir)

    # --- ROOT-only readers receive full provenance and a histogram dictionary ---
    fout = ROOT.TFile(str(args.out_dir / "istogrammi.root"), "RECREATE")
    if not fout or fout.IsZombie():
        raise OSError(f'cannot create ROOT output in {args.out_dir}')
    for h in hists.values():
        h.Write()
    dictionary = {}
    for name, histogram in hists.items():
        summary = _histogram_summary(histogram)
        normalized = name.endswith('_unit_area')
        summary['normalization'] = 'unit_area_including_flows' if normalized else 'yield'
        summary['normalization_defined'] = bool(summary['all_bins']) if normalized else True
        dictionary[name] = summary
    ROOT.TNamed('dalitz_metadata', json.dumps(metadata, sort_keys=True, allow_nan=False)).Write()
    ROOT.TNamed('histogram_dictionary', json.dumps(dictionary, sort_keys=True, allow_nan=False)).Write()
    fout.Close()

    print("\n====================================")
    print(f"Scritti in {args.out_dir}/")
    print(f"  eventi         chi2 {len(chi2.eta_mass):7d}   BDT {len(bdt.eta_mass):7d}")
    def percentage(values):
        return f'{100 * np.mean(values):.1f}%' if len(values) else 'n/d (vuoto)'

    print(f"  M(eta p) > W_event - m_pi0 (diagnostica ricostruzione):"
          f"  chi2 {percentage(chi2.over_limit)}   BDT {percentage(bdt.over_limit)}")
    print("  (contati, non tagliati)")

    # Should be 0 on anything the current reconstruction produced.
    stale = max((float(np.mean(data.eta_over_beam)) if len(data.eta_over_beam) else 0.)
                for data in samples.values())
    if stale > 0:
        print("")
        print(f"  ATTENZIONE: {100 * stale:.1f}% degli eventi ha un'eta piu' energetica")
        print("  del fotone di fascio, che e' cinematicamente impossibile. La reco")
        print("  taglia questi eventi: questi alberi sono stati prodotti prima del")
        print("  taglio. Rifai la fase 7.")
    print("====================================")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
