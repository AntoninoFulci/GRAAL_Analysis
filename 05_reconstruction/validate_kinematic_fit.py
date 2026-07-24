"""Validate kinematic-fit closure or an independently sourced calibration.

Default signal MC shares its smearing covariance with the fitter. Pulls from
that sample test implementation closure, not detector calibration. Calibration
mode therefore requires explicit independent-sample provenance. Both modes
report pull moments, chi2, confidence-level uniformity, condition numbers,
failure reasons, and fitted-vs-raw mass width.

    python -m reconstruction.validate_kinematic_fit \\
        --signal 03_mc_simulation/data/eta_pi0_mc.root --out-dir results/plots
"""
from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

import numpy as np
import uproot
from scipy.stats import chi2 as chi2_distribution
from scipy.stats import kstest

from graal_common.channels import ETA_PI0_HYP, M_ETA
from graal_common.pairing import Pairing
from graal_common.vectors import lorentz_array as _vec
from reconstruction.kinematic_fit import FitCovariance, fit_event

PAIRING = Pairing(heavy=(0, 1), light=(2, 3))


def validation_status(mode: str, provenance: str | None) -> str:
    """Describe what evidence this validation run can support."""
    if mode == "closure":
        return "VALIDATION STATUS: CLOSURE ONLY — covariance shared with generator"
    if mode == "calibration":
        if not provenance:
            raise ValueError(
                "calibration validation requires independent sample provenance"
            )
        return f"VALIDATION STATUS: INDEPENDENT CALIBRATION — {provenance}"
    raise ValueError(f"unknown validation mode: {mode}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--signal", type=Path,
                    default=Path("03_mc_simulation/data/eta_pi0_mc.root"))
    ap.add_argument("--out-dir", type=Path, default=Path("results/plots"))
    ap.add_argument("--n", type=int, default=20000, help="events to fit")
    ap.add_argument(
        "--validation-mode",
        choices=("closure", "calibration"),
        default="closure",
    )
    ap.add_argument(
        "--provenance",
        help="independent sample/calibration provenance; required in calibration mode",
    )
    args = ap.parse_args()
    print(validation_status(args.validation_mode, args.provenance))

    with uproot.open(args.signal) as f:
        t = f["mc"]
        names = ["eta_gamma1", "eta_gamma2", "pi0_gamma1", "pi0_gamma2",
                 "proton", "beam"]
        smeared = {n: _vec(t, n) for n in names}
        true = {n: _vec(t, n + "_true") for n in names}

    n = min(args.n, len(smeared["proton"]))
    cov = FitCovariance()
    chi2s, conv, raw_eta, fit_eta, pull_Eg = [], [], [], [], []
    condition_numbers = []
    failure_reasons: Counter[str] = Counter()

    for i in range(n):
        photons = np.stack([smeared["eta_gamma1"][i], smeared["eta_gamma2"][i],
                            smeared["pi0_gamma1"][i], smeared["pi0_gamma2"][i]])
        res = fit_event(photons, smeared["proton"][i], smeared["beam"][i],
                        PAIRING, ETA_PI0_HYP, cov)
        chi2s.append(res.chi2); conv.append(res.converged)
        condition_numbers.append(res.condition_number)
        if not res.converged:
            failure_reasons[res.failure_reason or "unknown"] += 1
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
    condition_numbers = np.asarray(condition_numbers)
    converged_chi2 = chi2s[conv]
    confidence_levels = chi2_distribution.sf(converged_chi2, 6)
    cl_ks = kstest(confidence_levels, "uniform")

    print(f"events fit: {n}   converged: {conv.mean():.1%}")
    print(f"fit chi2 (converged): mean {converged_chi2.mean():.2f}  (expect ~6)")
    print(f"pull eta_gamma1 E: mean {pull_Eg.mean():+.3f}  width {pull_Eg.std():.3f}"
          f"  (expect 0 +- 1)")
    print(f"eta mass std: raw {raw_eta.std():.4f} -> fit {fit_eta.std():.4f}")
    print(f"eta mass mean: raw {raw_eta.mean():.4f} -> fit {fit_eta.mean():.4f}"
          f"  (nominal {M_ETA:.4f})")
    print(
        f"CL uniformity KS: statistic {cl_ks.statistic:.4f}, "
        f"p-value {cl_ks.pvalue:.4g}"
    )
    finite_conditions = condition_numbers[np.isfinite(condition_numbers)]
    if finite_conditions.size:
        print(
            "constraint condition number: "
            f"median {np.median(finite_conditions):.3g}, "
            f"max {finite_conditions.max():.3g}"
        )
    print(f"fit failures: {dict(failure_reasons)}")

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
