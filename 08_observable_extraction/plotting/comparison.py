"""Comparison PDFs with plotting initialized only when requested."""

from observable_extraction.core.binning import PAIR_NAMES


def write_comparison_pdf(path, report):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages

    first, second = report.get("sample_names", ("pairing", "bdt"))
    with PdfPages(path) as pdf:
        for estimator in ("ratio", "likelihood"):
            for energy_bin in range(len(report["energy_edges_gev"]) - 1):
                fig, axes = plt.subplots(2, 3, figsize=(12, 6), sharex="col", constrained_layout=True)
                for column, pair in enumerate(PAIR_NAMES):
                    rows = [row for row in report["rows"] if row["estimator"] == estimator
                            and row["energy_bin"] == energy_bin and row["pair"] == pair]
                    for sample, offset, color in ((first, -.001, "tab:blue"), (second, .001, "tab:orange")):
                        valid = [row for row in rows if row[sample] and row[sample]["point"]["diagnostics"]["converged"]]
                        points = [row[sample]["point"] for row in valid]
                        if valid:
                            axes[0, column].errorbar([(row["mass_low"] + row["mass_high"]) / 2 + offset for row in valid],
                                                    [point["sigma"] for point in points],
                                                    yerr=[[point[name] for point in points] for name in ("stat_low", "stat_high")],
                                                    fmt="o", ms=3, label=sample, color=color)
                    for row in rows:
                        if row["delta"] is not None:
                            x = (row["mass_low"] + row["mass_high"]) / 2
                            error = row.get("delta_run_error")
                            axes[1, column].errorbar(x, row["delta"], yerr=error, fmt="o" if error is not None else "x",
                                                    color="black", ms=4)
                    axes[0, column].set(title=pair, ylim=(-1.15, 1.15), ylabel="Sigma (conditional stat.)")
                    axes[0, column].legend(fontsize=8)
                    axes[1, column].axhline(0, color="grey", linewidth=.7)
                    axes[1, column].set(xlabel="Invariant mass [GeV]", ylabel=f"{second} - {first}")
                lo, hi = report["energy_edges_gev"][energy_bin:energy_bin + 2]
                fig.suptitle(f"{report['profile'].upper()} {lo:g}–{hi:g} GeV | {estimator} | uncorrected background\n"
                             "Delta errors: paired run diagnostic; x: covariance unavailable; no final inference", fontsize=10)
                pdf.savefig(fig)
                plt.close(fig)
