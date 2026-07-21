#!/usr/bin/env python3
"""Dalitz plot M(eta p) vs M(pi0 p), plus the meson invariant masses.

Three families of figure:
  dalitz_*    M(eta p) vs M(pi0 p), colz — the resonance view
  massa_*     M(eta) and M(pi0) on their own
  masse_2d_*  those same two masses against each other, colz — where the gate
              shows up as the blob tightening onto the truth crossing


Compares the two reconstructions — plain chi2 against the BDT-gated one — which
is the whole reason both exist. Everything kinematic comes from
plots.kinematics; this module only reads ROOT, fills histograms and draws.

When a tree carries the kinematic-fit branches (`eta_fit`/`pi0_fit`/`fit_chi2`,
written by the reconstruction when the fit is on), the eta/pi0 masses and the
Dalitz axes built from them switch to the fitted 4-vectors, and the massa_*
figures gain a dashed "raw" overlay of the pre-fit mass in the same color —
before/after, same sample. A pre-fit reco file has none of those branches and
everything falls back to the raw eta/pi0 as before.

Two proton variants are produced, and they are NOT equivalent:

  misurato  — uses the measured `proton` branch: information independent of the
              photons, and the only variant that can disagree with the beam.
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
from pathlib import Path

import numpy as np
import ROOT

from plots import kinematics as kin

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


def _as_array(v) -> np.ndarray:
    """TLorentzVector -> (4,) [px, py, pz, E], the convention kinematics wants."""
    return np.array([v.Px(), v.Py(), v.Pz(), v.E()], dtype=np.float64)


def _open_tree(path: Path, tree_name: str):
    """Open a file, hand back (file, tree). Fails loud on anything missing."""
    if not path.exists():
        raise FileNotFoundError(f"file ricostruito non trovato: {path}")

    f = ROOT.TFile.Open(str(path))
    if not f or f.IsZombie():
        raise RuntimeError(f"impossibile aprire {path}")

    t = f.Get(tree_name)
    if not t:
        keys = [k.GetName() for k in f.GetListOfKeys()]
        raise RuntimeError(
            f"albero '{tree_name}' non trovato in {path}; trovati: {keys}"
        )

    n = t.GetEntries()
    if n == 0:
        # An empty histogram still draws, and looks like a result. It is not.
        raise RuntimeError(f"l'albero '{tree_name}' in {path} e' vuoto")

    print(f"  {path.name}: {n} eventi")
    return f, t


def _has_fit(tree) -> bool:
    """Whether this tree carries the kinematic-fit branches (Task 3).

    PyROOT's TTree has no uproot-style .keys(), so this walks
    GetListOfBranches() instead. A pre-fit reco file has none of the fit_*
    branches, and every caller below is expected to fall back to the raw
    eta/pi0 in that case.
    """
    return "fit_chi2" in {b.GetName() for b in tree.GetListOfBranches()}


def _collect(tree) -> dict[str, np.ndarray]:
    """One pass over the tree, pulling out everything the plots need."""
    has_fit = _has_fit(tree)

    mep_meas, mpp_meas, mep_miss, mpp_miss = [], [], [], []
    eta_m, pi0_m, eta_m_raw, pi0_m_raw = [], [], [], []
    over_limit, eta_over_beam = [], []

    for e in tree:
        eta_raw = _as_array(e.eta)
        pi0_raw = _as_array(e.pi0)
        # Use the fitted 4-vectors when the tree has them: better mass
        # resolution feeds both the meson-mass plots and the Dalitz axes built
        # from eta/pi0 below. The raw ones are kept alongside for the
        # fitted-vs-raw overlay, never discarded.
        eta = _as_array(e.eta_fit) if has_fit else eta_raw
        pi0 = _as_array(e.pi0_fit) if has_fit else pi0_raw
        proton = _as_array(e.proton)
        missing = _as_array(e.missing)
        beam = _as_array(e.beam)
        target = _as_array(e.target)

        mep_meas.append(kin.invariant_mass(eta, proton))
        mpp_meas.append(kin.invariant_mass(pi0, proton))
        mep_miss.append(kin.invariant_mass(eta, missing))
        mpp_miss.append(kin.invariant_mass(pi0, missing))

        eta_m.append(e.eta_fit.M() if has_fit else e.eta_mass)
        pi0_m.append(e.pi0_fit.M() if has_fit else e.pi0_mass)
        eta_m_raw.append(e.eta_mass)
        pi0_m_raw.append(e.pi0_mass)

        # Counted, never cut — so the summary can say how much of the sample
        # sits outside what the kinematics allow. Mostly resolution smearing at
        # the Dalitz boundary, which is why it is a number and not a cut.
        limit = kin.dalitz_limit(kin.sqrt_s(beam, target), kin.M_PI0)
        over_limit.append(mep_meas[-1] > limit)

        # An eta carrying more energy than the beam photon is impossible rather
        # than mismeasured, and the reconstruction drops those events outright
        # now (reco_core._reconstruct_and_fill). Still counted here, and
        # expected to read 0: anything else means this tree was produced before
        # that cut existed, and the summary should say so rather than let it
        # pass unnoticed. Checked on the raw eta/beam — this is validating the
        # upstream cut, not something the fit should be able to paper over.
        eta_over_beam.append(eta_raw[3] > beam[3])

    return {
        "mep_meas": np.array(mep_meas),
        "mpp_meas": np.array(mpp_meas),
        "mep_miss": np.array(mep_miss),
        "mpp_miss": np.array(mpp_miss),
        "eta_mass": np.array(eta_m),
        "pi0_mass": np.array(pi0_m),
        "eta_mass_raw": np.array(eta_m_raw),
        "pi0_mass_raw": np.array(pi0_m_raw),
        "over_limit": np.array(over_limit),
        "eta_over_beam": np.array(eta_over_beam),
        "has_fit": has_fit,
    }


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


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--chi2", type=Path, required=True,
                   help="output di reconstruct_eta_pi0_chi2")
    p.add_argument("--bdt", type=Path, required=True,
                   help="output di reconstruct_eta_pi0_bdt")
    p.add_argument("--out-dir", type=Path, default=Path("results/plots"))
    args = p.parse_args(argv)

    ROOT.gROOT.SetBatch(True)
    ROOT.gStyle.SetOptStat(0)
    ROOT.gStyle.SetPalette(ROOT.kBird)

    args.out_dir.mkdir(parents=True, exist_ok=True)

    print("Lettura degli alberi ricostruiti:")
    fc, tc = _open_tree(args.chi2, CHI2_TREE)
    fb, tb = _open_tree(args.bdt, BDT_TREE)

    chi2 = _collect(tc)
    bdt = _collect(tb)
    fc.Close()
    fb.Close()

    hists = {}
    for tag, data, lab in (("chi2", chi2, "solo chi2"), ("bdt", bdt, "gate BDT")):
        for var, vlab in (("meas", "misurato"), ("miss", "implicito")):
            name = f"dalitz_{tag}_{vlab}"
            hists[name] = _dalitz_hist(
                name, f"{lab}  -  protone {vlab}",
                data[f"mep_{var}"], data[f"mpp_{var}"],
            )

    hists["massa_eta_chi2"] = _mass_hist(
        "massa_eta_chi2", "solo chi2", chi2["eta_mass"], _ETA_MASS_MIN, _ETA_MASS_MAX)
    hists["massa_eta_bdt"] = _mass_hist(
        "massa_eta_bdt", "gate BDT", bdt["eta_mass"], _ETA_MASS_MIN, _ETA_MASS_MAX)
    hists["massa_pi0_chi2"] = _mass_hist(
        "massa_pi0_chi2", "solo chi2", chi2["pi0_mass"], _PI0_MASS_MIN, _PI0_MASS_MAX)
    hists["massa_pi0_bdt"] = _mass_hist(
        "massa_pi0_bdt", "gate BDT", bdt["pi0_mass"], _PI0_MASS_MIN, _PI0_MASS_MAX)

    # Fitted-vs-raw overlay: only meaningful when the tree actually carries the
    # kinematic-fit branches (Task 3). When has_fit is False for a sample,
    # eta_mass/pi0_mass above are already the raw masses, so there is nothing
    # to overlay for it.
    for tag, data in (("chi2", chi2), ("bdt", bdt)):
        if data["has_fit"]:
            hists[f"massa_eta_{tag}_raw"] = _mass_hist(
                f"massa_eta_{tag}_raw", "raw",
                data["eta_mass_raw"], _ETA_MASS_MIN, _ETA_MASS_MAX)
            hists[f"massa_pi0_{tag}_raw"] = _mass_hist(
                f"massa_pi0_{tag}_raw", "raw",
                data["pi0_mass_raw"], _PI0_MASS_MIN, _PI0_MASS_MAX)

    # The two meson masses against each other: on this figure the gate shows up
    # as the blob tightening onto the truth crossing, not as a shifted median.
    for tag, data, lab in (("chi2", chi2, "solo chi2"), ("bdt", bdt, "gate BDT")):
        name = f"masse_2d_{tag}"
        hists[name] = _mass2d_hist(name, lab, data["eta_mass"], data["pi0_mass"])

    # --- one canvas per Dalitz ---
    for name in [k for k in hists if k.startswith("dalitz_")]:
        c = ROOT.TCanvas(f"c_{name}", name, 800, 700)
        c.SetRightMargin(0.13)
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
        hc.Draw("hist")
        hb.Draw("hist same")

        leg = ROOT.TLegend(0.58, 0.62, 0.90, 0.88)
        leg.AddEntry(hc, "solo chi2" + (" (fit)" if chi2["has_fit"] else ""), "f")
        leg.AddEntry(hb, "gate BDT" + (" (fit)" if bdt["has_fit"] else ""), "l")

        # Before/after: the raw mass for the same sample, dashed in the same
        # color — what the kinematic fit did to the peak. Only drawn where a
        # fit actually ran (see the massa_*_*_raw hists built above).
        hc_raw = hists.get(f"massa_{meson}_chi2_raw")
        if hc_raw is not None:
            hc_raw.SetLineColor(ROOT.kGray + 2)
            hc_raw.SetLineStyle(2)
            hc_raw.SetLineWidth(2)
            hc_raw.Draw("hist same")
            leg.AddEntry(hc_raw, "solo chi2 (raw)", "l")
        hb_raw = hists.get(f"massa_{meson}_bdt_raw")
        if hb_raw is not None:
            hb_raw.SetLineColor(ROOT.kAzure + 1)
            hb_raw.SetLineStyle(2)
            hb_raw.Draw("hist same")
            leg.AddEntry(hb_raw, "gate BDT (raw)", "l")

        line = ROOT.TLine(truth, 0, truth, hc.GetMaximum() * 1.05)
        line.SetLineColor(ROOT.kRed + 1)
        line.SetLineStyle(2)
        line.Draw()
        leg.AddEntry(line, "valore vero", "l")
        leg.Draw()
        _save(c, args.out_dir, f"massa_{meson}")

    # --- the histograms themselves, so they can be restyled without re-looping ---
    fout = ROOT.TFile(str(args.out_dir / "istogrammi.root"), "RECREATE")
    for h in hists.values():
        h.Write()
    fout.Close()

    print("\n====================================")
    print(f"Scritti in {args.out_dir}/")
    print(f"  eventi         chi2 {len(chi2['eta_mass']):7d}   BDT {len(bdt['eta_mass']):7d}")
    print(f"  fit cinematico chi2 {'si' if chi2['has_fit'] else 'no':>7}   "
          f"BDT {'si' if bdt['has_fit'] else 'no':>7}")
    print(f"  M(eta p) oltre il limite cinematico (soprattutto risoluzione al bordo Dalitz):"
          f"  chi2 {100 * chi2['over_limit'].mean():.1f}%   BDT {100 * bdt['over_limit'].mean():.1f}%")
    print("  (contati, non tagliati)")

    # Should be 0 on anything the current reconstruction produced.
    stale = max(chi2["eta_over_beam"].mean(), bdt["eta_over_beam"].mean())
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
