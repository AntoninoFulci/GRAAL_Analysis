"""Validate the kinematic fit on signal MC, where the truth is known.

Pulls (fitted - true)/sigma are the calibration: their width is 1 only when the
covariance matches the real spread. A width far from 1 says the sigma in
FitCovariance is off by that factor -- rescale and rerun. Also checks the fit
chi2 follows chi2(6) and that the fitted masses are narrower than the raw ones.

    python -m reconstruction.validate_kinematic_fit \\
        --signal 03_mc_simulation/data/eta_pi0_mc.root --out-dir results/plots
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import uproot

from graal_common.channels import ETA_PI0_HYP, M_ETA
from graal_common.pairing import Pairing
from graal_common.vectors import lorentz_array as _vec
from reconstruction.kinematic_fit import FitCovariance, fit_event

PAIRING = Pairing(heavy=(0, 1), light=(2, 3))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--signal", type=Path,
                    default=Path("03_mc_simulation/data/eta_pi0_mc.root"))
    ap.add_argument("--out-dir", type=Path, default=Path("results/plots"))
    ap.add_argument("--n", type=int, default=20000, help="events to fit")
    args = ap.parse_args()

    with uproot.open(args.signal) as f:
        t = f["mc"]
        names = ["eta_gamma1", "eta_gamma2", "pi0_gamma1", "pi0_gamma2",
                 "proton", "beam"]
        smeared = {n: _vec(t, n) for n in names}
        true = {n: _vec(t, n + "_true") for n in names}

    n = min(args.n, len(smeared["proton"]))
    cov = FitCovariance()
    chi2s, conv, raw_eta, fit_eta, pull_Eg = [], [], [], [], []

    for i in range(n):
        photons = np.stack([smeared["eta_gamma1"][i], smeared["eta_gamma2"][i],
                            smeared["pi0_gamma1"][i], smeared["pi0_gamma2"][i]])
        res = fit_event(photons, smeared["proton"][i], smeared["beam"][i],
                        PAIRING, ETA_PI0_HYP, cov)
        chi2s.append(res.chi2); conv.append(res.converged)
        gh_raw = photons[0] + photons[1]
        raw_eta.append(np.sqrt(max(gh_raw[3] ** 2 - (gh_raw[:3] ** 2).sum(), 0)))
        if res.converged:
            gh = res.fitted_photons[0] + res.fitted_photons[1]
            fit_eta.append(np.sqrt(max(gh[3] ** 2 - (gh[:3] ** 2).sum(), 0)))
            sigma_fit = np.sqrt(max(res.fitted_cov[0], 0.0))
            if sigma_fit > 0:
                pull_Eg.append((res.fitted_photons[0][3] - true["eta_gamma1"][i][3]) / sigma_fit)

    chi2s = np.array(chi2s); conv = np.array(conv)
    pull_Eg = np.array(pull_Eg); raw_eta = np.array(raw_eta); fit_eta = np.array(fit_eta)

    print(f"events fit: {n}   converged: {conv.mean():.1%}")
    print(f"fit chi2 (converged): mean {chi2s[conv].mean():.2f}  (expect ~6)")
    print(f"pull eta_gamma1 E: mean {pull_Eg.mean():+.3f}  width {pull_Eg.std():.3f}"
          f"  (expect 0 +- 1)")
    print(f"eta mass std: raw {raw_eta.std():.4f} -> fit {fit_eta.std():.4f}")
    print(f"eta mass mean: raw {raw_eta.mean():.4f} -> fit {fit_eta.mean():.4f}"
          f"  (nominal {M_ETA:.4f})")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(1, 3, figsize=(15, 4))
        ax[0].hist(chi2s[conv], bins=60, range=(0, 40)); ax[0].set_title("fit chi2 (ndf 6)")
        ax[1].hist(pull_Eg, bins=60, range=(-5, 5)); ax[1].set_title("pull eta_gamma1 E")
        ax[2].hist(raw_eta, bins=60, range=(0.45, 0.65), alpha=0.5, label="raw")
        ax[2].hist(fit_eta, bins=60, range=(0.45, 0.65), alpha=0.5, label="fit")
        ax[2].legend(); ax[2].set_title("M(eta)")
        fig.savefig(str(args.out_dir / "kinfit_validation.png"), dpi=130)
        print(f"wrote {args.out_dir / 'kinfit_validation.png'}")
    except ImportError:
        print("matplotlib not available, skipped the plot")


if __name__ == "__main__":
    main()
