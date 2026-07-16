#!/usr/bin/env python3
"""Dalitz plot M(eta p) vs M(pi0 p), and the invariant-mass distributions.

Compares the two reconstructions — plain chi2 against the BDT-gated one — which
is the whole reason both exist. Everything kinematic comes from
plots.kinematics; this module only reads ROOT, fills histograms and draws.

Two proton variants are produced, and they are NOT equivalent:

  misurato  — uses the measured `proton` branch: information independent of the
              photons, and the only variant that can disagree with the beam.
  implicito — uses `missing`. Note the algebraic identity
                  eta + missing = beam + target - pi0,
              so this variant depends on neither the measured proton nor the
              measured eta. It is a missing-mass plot: clean by construction,
              but it is not new information.

Run:
    python -m plots.dalitz --chi2 data/analyzed/reco_eta_pi0_chi2.root \\
                           --bdt  data/analyzed/reco_eta_pi0_bdt.root
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


def _collect(tree) -> dict[str, np.ndarray]:
    """One pass over the tree, pulling out everything the plots need."""
    mep_meas, mpp_meas, mep_miss, mpp_miss = [], [], [], []
    eta_m, pi0_m, over_limit = [], [], []

    for e in tree:
        eta = _as_array(e.eta)
        pi0 = _as_array(e.pi0)
        proton = _as_array(e.proton)
        missing = _as_array(e.missing)
        beam = _as_array(e.beam)
        target = _as_array(e.target)

        mep_meas.append(kin.invariant_mass(eta, proton))
        mpp_meas.append(kin.invariant_mass(pi0, proton))
        mep_miss.append(kin.invariant_mass(eta, missing))
        mpp_miss.append(kin.invariant_mass(pi0, missing))

        eta_m.append(e.eta_mass)
        pi0_m.append(e.pi0_mass)

        # Counted, never cut — so the summary can say how much of the sample
        # sits outside what the kinematics allow.
        limit = kin.dalitz_limit(kin.sqrt_s(beam, target), kin.M_PI0)
        over_limit.append(mep_meas[-1] > limit)

    return {
        "mep_meas": np.array(mep_meas),
        "mpp_meas": np.array(mpp_meas),
        "mep_miss": np.array(mep_miss),
        "mpp_miss": np.array(mpp_miss),
        "eta_mass": np.array(eta_m),
        "pi0_mass": np.array(pi0_m),
        "over_limit": np.array(over_limit),
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


def _save(canvas, out_dir: Path, stem: str) -> None:
    """Every figure goes out as PNG (to look at) and PDF (vector, for talks)."""
    canvas.SaveAs(str(out_dir / f"{stem}.png"))
    canvas.SaveAs(str(out_dir / f"{stem}.pdf"))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--chi2", type=Path, required=True,
                   help="output di reconstruct_eta_pi0_chi2")
    p.add_argument("--bdt", type=Path, required=True,
                   help="output di reconstruct_eta_pi0_bdt")
    p.add_argument("--out-dir", type=Path, default=Path("06_plots/plots"))
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

    hists["massa_eta_chi2"] = _mass_hist("massa_eta_chi2", "solo chi2", chi2["eta_mass"], 0.3, 0.8)
    hists["massa_eta_bdt"] = _mass_hist("massa_eta_bdt", "gate BDT", bdt["eta_mass"], 0.3, 0.8)
    hists["massa_pi0_chi2"] = _mass_hist("massa_pi0_chi2", "solo chi2", chi2["pi0_mass"], 0.05, 0.25)
    hists["massa_pi0_bdt"] = _mass_hist("massa_pi0_bdt", "gate BDT", bdt["pi0_mass"], 0.05, 0.25)

    # --- one canvas per Dalitz ---
    for name in [k for k in hists if k.startswith("dalitz_")]:
        c = ROOT.TCanvas(f"c_{name}", name, 800, 700)
        c.SetRightMargin(0.13)
        hists[name].Draw("colz")
        _save(c, args.out_dir, name)

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

        line = ROOT.TLine(truth, 0, truth, hc.GetMaximum() * 1.05)
        line.SetLineColor(ROOT.kRed + 1)
        line.SetLineStyle(2)
        line.Draw()

        leg = ROOT.TLegend(0.62, 0.72, 0.88, 0.88)
        leg.AddEntry(hc, "solo chi2", "f")
        leg.AddEntry(hb, "gate BDT", "l")
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
    print(f"  M(eta p) oltre il limite cinematico:"
          f"  chi2 {100 * chi2['over_limit'].mean():.1f}%   BDT {100 * bdt['over_limit'].mean():.1f}%")
    print("  (contati, non tagliati)")
    print("====================================")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
