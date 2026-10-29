# Plotting and diagnostics

Plotting consumes completed products. `scripts/plot_campaign.py --campaign results/my-campaign` assembles UV/VIS and common figures; `--workers` controls isolated profile/common plotting processes. `plots/dalitz.py`, `plots/mass_histograms.py` and `plots/fig7_compton_polarization.py` expose their own `--help` interfaces.

New full-pipeline campaigns group outputs under three directories, preserving UV/VIS and period labels:

- `plots/`: diagnostic PDFs, with `common/asymmetry_comparison.pdf` for UV/VIS/Ajaka and `common/asymmetry_uv_ajaka.pdf` for UV/Ajaka. Matching energy intervals share a panel in the combined comparison; different intervals remain separate, without rebinning. Ajaka points are matched by energy boundaries, not by analysis bin number; the bundled reference covers only 1.10–1.20, 1.20–1.30, 1.30–1.40 and 1.40–1.50 GeV. Panels outside those intervals explicitly state that no Ajaka data are available. The duplicate experimental-only figure is omitted from full-pipeline publication; standalone extraction retains its own figure.
- `metadata/`: campaign JSON and command logs, including calibration QA, period indices and `output_layout.json` with relocation hashes. Period ROOT references are relative to the relocated index.
- `root/`: calibrated flux, reconstructions, pooled/period asymmetry outputs and diagnostic mass histograms.

The full pipeline calls diagnostics with `--mass-only --quality-controls`: no Dalitz figures or Dalitz histograms are generated. Each profile retains `massa_eta.pdf` and `massa_pi0.pdf`; duplicate raw and normalized mass overlays are omitted. The standalone Dalitz command remains available for explicit studies. Reusable BDT/MC bundles and their manifests retain their cache layout (`results/_cache/`, or campaign-local `artifacts/` in test mode).

## Reconstruction physical controls

Campaign regeneration includes the controls originally prototyped in `docs/reference/other/Qualityplot_etapi0.py`, using the existing reconstruction adapter. UV and VIS remain separate directories; each figure compares the chi2 and BDT samples without additional selection, weights or normalization corrections.

| PDF in `plots/<profile>/` | Physical quantity |
| --- | --- |
| `massa_eta.pdf`, `massa_pi0.pdf` | Existing raw meson mass distributions, keeping their established windows and binning |
| `theta_missing_proton.pdf` | Polar angle difference `theta(missing)-theta(measured proton)`; 100 bins, -10 to 10 degrees |
| `coplanarity.pdf` | Signed `wrap(phi(proton)-phi(eta+pi0)-180 degrees)` in [-180,180); 100 bins, -10 to 10 degrees; zero means back-to-back transverse directions |
| `missing_mass.pdf` | Signed invariant mass of `beam+target-eta-pi0`, matching `TLorentzVector.M()`; 100 bins, 0.8 to 1.1 GeV |
| `beam_energy_vs_proton_theta.pdf` | Measured proton theta versus beam energy; 50 by 50 bins, 0 to 40 degrees and 0.9 to 1.55 GeV |

The prototype's coplanarity histogram duplicated the polar-angle residual; the integrated version uses the azimuthal definition above. Missing mass is recomputed from the initial state and measured mesons. These are distributions **after reconstruction cuts**, including the existing missing-mass window; their shape is not an independent validation of the unselected spectrum.

Each eta histogram receives a diagnostic Gaussian fit in 0.50 to 0.60 GeV. Successful mu/sigma values appear in the existing eta PDF; `quality_metadata` in `root/<profile>/istogrammi.root` records parameters, errors, fit/covariance status and chi2/ndf. Empty or at most three occupied fit bins give `insufficient_data`; failed fits give `failed` without publishing parameter estimates. Fits do not alter histograms, reconstruction or cuts, and do not establish background-subtracted resolution.

The same ROOT product retains all control histograms (chi2/BDT names and unit-area copies), `histogram_dictionary` with visible/flow counts, and `dalitz_metadata` with input identities and reconstruction provenance. `quality_metadata` defines quantities and records undefined angular counts per sample: zero momentum has no polar direction; zero transverse momentum has no azimuth. Only the affected angular fill is omitted. Finite values outside display windows remain in under/overflow; nonfinite input four-vectors fail validation.

Regenerate a completed campaign with `python scripts/plot_campaign.py --campaign results/my-campaign`. For explicit standalone controls, add `--quality-controls` to `python -m plots.dalitz`; combine with `--mass-only` to omit Dalitz figures. The plotting layer performs no new scientific campaign or run-quality selection.

Report grouping happens after stage consumers finish. Scientific ROOT inputs remain byte-identical during plot regeneration. Older campaign input layouts remain readable; existing historical campaign directories are not migrated automatically. Repeated plot regeneration preserves period diagnostics.

[Plot adapters](https://github.com/AntoninoFulci/GRAAL_Analysis/blob/main/plots/core) use the reconstruction raw-vector contract. Dalitz and mass maps are event-density diagnostics, not acceptance-corrected distributions. Measured-proton and missing-proton constructions must remain identifiable. `observable_extraction.combine_profiles` validates compatible profile and finite-bin metadata before building combined figures; the [manual example](commands-and-configuration) connects the exact extraction output to composition.

Ratio ROOT azimuthal curves retain the observed center-fit amplitude while Sigma points carry the finite-bin correction. Plot regeneration reads existing metadata and never silently upgrades historical outputs. Ajaka published/digitized points are not rewritten. Their error information is limited to the recorded reference.

For an uncertainty claim inspect the plotted error fields and covariance components explicitly; an output named `stat` or a successful plotting command is not evidence of a complete systematic treatment. [Status](status) lists the remaining normalization, correlations and efficiency studies. Presentations are derived communication artifacts and do not define pipeline behavior.
