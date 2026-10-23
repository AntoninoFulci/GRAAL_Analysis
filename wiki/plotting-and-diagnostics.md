# Plotting and diagnostics

Plotting consumes completed products. `scripts/plot_campaign.py --campaign results/my-campaign` assembles UV/VIS and common figures; `--workers` controls isolated profile/common plotting processes. `plots/dalitz.py`, `plots/mass_histograms.py` and `plots/fig7_compton_polarization.py` expose their own `--help` interfaces.

[Plot adapters](https://github.com/AntoninoFulci/GRAAL_Analysis/blob/main/plots/core) use the reconstruction raw-vector contract. Dalitz and mass maps are event-density diagnostics, not acceptance-corrected distributions. Measured-proton and missing-proton constructions must remain identifiable. `observable_extraction.combine_profiles` validates compatible profile and finite-bin metadata before building combined figures; the [manual example](commands-and-configuration) connects the exact extraction output to composition.

Ratio ROOT azimuthal curves retain the observed center-fit amplitude while Sigma points carry the finite-bin correction. Plot regeneration reads existing metadata and never silently upgrades historical outputs. Ajaka published/digitized points are not rewritten. Their error information is limited to the recorded reference.

For an uncertainty claim inspect the plotted error fields and covariance components explicitly; an output named `stat` or a successful plotting command is not evidence of a complete systematic treatment. [Status](status) lists the remaining normalization, correlations and efficiency studies. Presentations are derived communication artifacts and do not define pipeline behavior.
