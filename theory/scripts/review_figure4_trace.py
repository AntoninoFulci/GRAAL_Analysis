"""Render traced Ajaka Figure 4 theory lines for source-page review."""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from graal_theory.figure4_reference import PAIR_MASS_AXES, load_published_theory_curves


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT.parent / "tmp/pdfs/PhysRevLett.100.052003.pdf"
POINTS = load_published_theory_curves(
    ROOT / "references/ajaka2008_figure4_theory.csv",
    ROOT / "references/ajaka2008_figure4_theory.json",
    SOURCE if SOURCE.is_file() else None,
)
PAIRS = ("p_pi0", "p_eta", "eta_pi0")
fig, axes = plt.subplots(4, 3, figsize=(10, 10), sharex="col", sharey=True)
for energy_bin in range(4):
    for column, pair in enumerate(PAIRS):
        ax = axes[energy_bin, column]
        panel = [p for p in POINTS if p.pair == pair and p.energy_bin == energy_bin]
        x = [p.mass_gev for p in panel]
        y = [p.sigma for p in panel]
        error = [p.reading_error for p in panel]
        ax.errorbar(x, y, yerr=error, fmt="k.", markersize=3, capsize=1)
        ax.axhline(0, color="0.6", linewidth=0.5)
        ax.set_xlim(*PAIR_MASS_AXES[pair])
        ax.set_ylim(-0.8, 0.4)
        ax.set_title(f"{pair}, energy bin {energy_bin}")
        if energy_bin == 3:
            ax.set_xlabel("pair mass [GeV]")
        if column == 0:
            ax.set_ylabel("Sigma")
destination = ROOT / "outputs/figure4_reference_review.pdf"
destination.parent.mkdir(parents=True, exist_ok=True)
fig.tight_layout()
fig.savefig(destination)
plt.close(fig)
print(destination)
