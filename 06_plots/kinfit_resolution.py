#!/usr/bin/env python3
"""Kinematic-fit resolution study: M(eta p) and M(pi0 p), before vs after.

Three families of figure, all about what the 6C kinematic fit buys on the two
Dalitz observables M(eta p) and M(pi0 p):

  risoluzione_*_p   residual (reco - true) on signal MC. Its width IS the
                    resolution (the physics spread cancels in the subtraction),
                    so this is the honest before/after: raw vs fitted sigma.
  massa_*_p_mc      the plain mass spectrum on signal MC with the generator
                    truth overlaid — shows the fit pulling the smeared spectrum
                    back onto the truth (the threshold sharpens, the tail below
                    the kinematic edge disappears).
  massa_*_p         the plain mass spectrum on the reconstructed data. Here the
                    width mixes resolution with the real physics spread, so the
                    narrowing is modest and honest: the fit does not (and must
                    not) collapse genuine structure.

The mesons themselves are NOT a useful before/after: the fit constrains
m(eta) and m(pi0) to the pole exactly, so the fitted meson mass is a delta by
construction (no information). The recoil observables M(eta p)/M(pi0 p) are
where the constraint propagates and the resolution is recovered.

The fit is run live on the MC (smeared inputs, truth kept for comparison), the
same call reco_core makes. Data curves read the fitted branches already written
to the reco file (eta_fit, pi0_fit, proton_fit — the fit adjusts the proton too,
so both the meson and the proton use their fitted 4-vector).

No ROOT: uproot reads the TLorentzVector branches, plots.kinematics does the
arithmetic, matplotlib draws.

Run:
    python -m plots.kinfit_resolution \\
        --signal 03_mc_simulation/data/eta_pi0_mc.root \\
        --bdt    results/reco/reco_eta_pi0_bdt.root \\
        --out-dir results/plots
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import uproot

from graal_common.channels import ETA_PI0_HYP
from graal_common.pairing import Pairing
from graal_common.vectors import lorentz_array
from plots.kinematics import invariant_mass, invariant_masses
from reconstruction.kinematic_fit import FitCovariance, fit_event

# The eta is the heavy pair (0, 1), the pi0 the light pair (2, 3): the same
# order reco_core stacks the photons in before it calls the fit.
PAIRING = Pairing(heavy=(0, 1), light=(2, 3))


def core_sigma(x: np.ndarray, lo: float = -0.3, hi: float = 0.3) -> float:
    """Standard deviation inside a central window — the resolution core.

    The tails (mis-reconstructed events outside +-0.3 GeV) are dropped so a few
    outliers do not inflate the width; std about the sample mean, so a genuine
    mean bias would still leave the width honest.
    """
    c = x[(x > lo) & (x < hi)]
    return float(c.std()) if len(c) else float("nan")


def fit_signal_mc(signal: Path, n: int):
    """Run the fit on n signal-MC events; return the mass arrays it needs.

    Returns a dict of arrays: for each observable, the raw/fit residuals against
    truth and the raw/fit/true absolute masses. Non-converged events are dropped
    from the fitted arrays (and only those).
    """
    with uproot.open(signal) as f:
        t = f["mc"]
        names = ["eta_gamma1", "eta_gamma2", "pi0_gamma1", "pi0_gamma2",
                 "proton", "beam"]
        sm = {nm: lorentz_array(t, nm) for nm in names}
        tr = {nm: lorentz_array(t, nm + "_true") for nm in names}

    n = min(n, len(sm["proton"]))
    cov = FitCovariance()
    out = {k: [] for k in ("etap_res_raw", "etap_res_fit", "pip_res_raw",
                           "pip_res_fit", "etap_raw", "etap_fit", "etap_true",
                           "pip_raw", "pip_fit", "pip_true")}

    for i in range(n):
        photons = np.stack([sm["eta_gamma1"][i], sm["eta_gamma2"][i],
                            sm["pi0_gamma1"][i], sm["pi0_gamma2"][i]])
        p_raw = sm["proton"][i]
        eta_t = tr["eta_gamma1"][i] + tr["eta_gamma2"][i]
        pi_t = tr["pi0_gamma1"][i] + tr["pi0_gamma2"][i]
        p_t = tr["proton"][i]
        m_etap_t = invariant_mass(eta_t, p_t)
        m_pip_t = invariant_mass(pi_t, p_t)
        m_etap_raw = invariant_mass(photons[0] + photons[1], p_raw)
        m_pip_raw = invariant_mass(photons[2] + photons[3], p_raw)
        out["etap_true"].append(m_etap_t)
        out["pip_true"].append(m_pip_t)
        out["etap_raw"].append(m_etap_raw)
        out["pip_raw"].append(m_pip_raw)
        out["etap_res_raw"].append(m_etap_raw - m_etap_t)
        out["pip_res_raw"].append(m_pip_raw - m_pip_t)

        res = fit_event(photons, p_raw, sm["beam"][i], PAIRING, ETA_PI0_HYP, cov)
        if not res.converged:
            continue
        fph = res.fitted_photons
        p_f = res.fitted_proton
        m_etap_f = invariant_mass(fph[0] + fph[1], p_f)
        m_pip_f = invariant_mass(fph[2] + fph[3], p_f)
        out["etap_fit"].append(m_etap_f)
        out["pip_fit"].append(m_pip_f)
        out["etap_res_fit"].append(m_etap_f - m_etap_t)
        out["pip_res_fit"].append(m_pip_f - m_pip_t)

    d = {k: np.asarray(v) for k, v in out.items()}
    d["n"] = n
    d["converged"] = len(d["etap_fit"])
    return d


def data_masses(bdt: Path):
    """Raw and fitted M(eta p)/M(pi0 p) from the reconstructed data file."""
    with uproot.open(bdt) as f:
        tree_name = next(k for k, cls in f.classnames().items() if cls == "TTree")
        t = f[tree_name]
        eta = lorentz_array(t, "eta"); pi0 = lorentz_array(t, "pi0")
        proton = lorentz_array(t, "proton")
        eta_fit = lorentz_array(t, "eta_fit"); pi0_fit = lorentz_array(t, "pi0_fit")
        proton_fit = lorentz_array(t, "proton_fit")

    return {
        "etap_raw": invariant_masses(eta, proton),
        "etap_fit": invariant_masses(eta_fit, proton_fit),
        "pip_raw": invariant_masses(pi0, proton),
        "pip_fit": invariant_masses(pi0_fit, proton_fit),
    }


def _residual_fig(res_raw, res_fit, label, fname, out_dir, plt):
    fig, ax = plt.subplots(figsize=(7, 5))
    rng = (-0.4, 0.4)
    ax.hist(res_raw, bins=80, range=rng, alpha=0.5, color="tab:red",
            label=f"prima (raw), $\\sigma$={core_sigma(res_raw):.3f} GeV")
    ax.hist(res_fit, bins=80, range=rng, alpha=0.5, color="tab:blue",
            label=f"dopo (fit), $\\sigma$={core_sigma(res_fit):.3f} GeV")
    ax.axvline(0, color="k", lw=0.8, ls="--")
    ax.set_xlabel(f"{label}$_{{reco}} - {label}_{{true}}$  [GeV]")
    ax.set_ylabel("eventi")
    ax.set_title(f"Risoluzione {label}: prima vs dopo il fit (MC segnale)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(str(out_dir / fname))
    plt.close(fig)


def _mc_dist_fig(raw, fit, true, label, rng, fname, out_dir, plt):
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.hist(true, bins=100, range=rng, histtype="step", lw=2.2, color="k",
            label="verita (true)")
    ax.hist(raw, bins=100, range=rng, histtype="step", lw=1.6, color="tab:red",
            label="prima (raw)")
    ax.hist(fit, bins=100, range=rng, histtype="step", lw=1.6, color="tab:blue",
            label="dopo (fit)")
    ax.set_xlabel(f"{label}  [GeV]")
    ax.set_ylabel("eventi")
    ax.set_title(f"{label} su MC segnale: raw / fit / verita")
    ax.legend()
    fig.tight_layout()
    fig.savefig(str(out_dir / fname))
    plt.close(fig)


def _data_dist_fig(raw, fit, label, rng, fname, out_dir, plt):
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.hist(raw, bins=100, range=rng, histtype="step", lw=1.8, color="tab:red",
            label=f"prima (raw), $\\sigma$={raw.std():.3f} GeV")
    ax.hist(fit, bins=100, range=rng, histtype="step", lw=1.8, color="tab:blue",
            label=f"dopo (fit), $\\sigma$={fit.std():.3f} GeV")
    ax.set_xlabel(f"{label}  [GeV]")
    ax.set_ylabel("eventi")
    ax.set_title(f"{label}: prima vs dopo il fit (dati, gate BDT)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(str(out_dir / fname))
    plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--signal", type=Path,
                    default=Path("03_mc_simulation/data/eta_pi0_mc.root"))
    ap.add_argument("--bdt", type=Path,
                    default=Path("results/reco/reco_eta_pi0_bdt.root"))
    ap.add_argument("--out-dir", type=Path, default=Path("results/plots"))
    ap.add_argument("--n", type=int, default=20000, help="signal events to fit")
    args = ap.parse_args()

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    if not args.signal.exists():
        raise SystemExit(
            f"signal MC {args.signal} not found: the residual and MC-spectrum "
            f"figures need it to run the fit against truth. Point --signal at "
            f"the generated file, or generate it first."
        )

    args.out_dir.mkdir(parents=True, exist_ok=True)

    mc = fit_signal_mc(args.signal, args.n)
    print(f"MC: {mc['converged']}/{mc['n']} converged")
    print(f"  M(eta p) resolution [GeV]: raw {core_sigma(mc['etap_res_raw']):.4f}"
          f" -> fit {core_sigma(mc['etap_res_fit']):.4f}")
    print(f"  M(pi0 p) resolution [GeV]: raw {core_sigma(mc['pip_res_raw']):.4f}"
          f" -> fit {core_sigma(mc['pip_res_fit']):.4f}")

    _residual_fig(mc["etap_res_raw"], mc["etap_res_fit"], r"$M(\eta\,p)$",
                  "risoluzione_eta_p.pdf", args.out_dir, plt)
    _residual_fig(mc["pip_res_raw"], mc["pip_res_fit"], r"$M(\pi^0 p)$",
                  "risoluzione_pi0_p.pdf", args.out_dir, plt)
    _mc_dist_fig(mc["etap_raw"], mc["etap_fit"], mc["etap_true"], r"$M(\eta\,p)$",
                 (1.45, 2.05), "massa_eta_p_mc.pdf", args.out_dir, plt)
    _mc_dist_fig(mc["pip_raw"], mc["pip_fit"], mc["pip_true"], r"$M(\pi^0 p)$",
                 (1.05, 1.75), "massa_pi0_p_mc.pdf", args.out_dir, plt)

    if args.bdt.exists():
        dat = data_masses(args.bdt)
        print(f"  data M(eta p) std: raw {dat['etap_raw'].std():.4f}"
              f" -> fit {dat['etap_fit'].std():.4f}")
        _data_dist_fig(dat["etap_raw"], dat["etap_fit"], r"$M(\eta\,p)$",
                       (1.4, 2.4), "massa_eta_p.pdf", args.out_dir, plt)
        _data_dist_fig(dat["pip_raw"], dat["pip_fit"], r"$M(\pi^0 p)$",
                       (1.0, 2.2), "massa_pi0_p.pdf", args.out_dir, plt)
    else:
        print(f"  {args.bdt} absent, skipped the data figures")

    print(f"wrote figures to {args.out_dir}")


if __name__ == "__main__":
    main()
