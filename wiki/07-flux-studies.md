# Stage 07: optional flux studies

`--flux-study off` is the workflow default. `audit` checks missing/invalid coverage after calibration; `study` runs the declared offline study. `--flux-study-metadata` supplies acquisition conditions and independent exposure metadata and is rejected when studies are off.

[07_flux_studies](https://github.com/AntoninoFulci/GRAAL_Analysis/blob/main/07_flux_studies) contains `audit_flux.py`, `study_missing_flux.py`, native-recovery preparation/studies, calibrated-neighbor studies, realistic-gap/observable closure and acceptance-scan tools. These products diagnose support, uncertainty and possible bias; they do not replace measured production flux automatically.

A missing calibrated histogram can reflect missing calibration coverage even when raw flux exists. Distinguish absent raw data, invalid/anomalous input, strip-energy calibration failure and incomplete cohort coverage. Retain run/state cutflows, the frozen exclusion policy, explicit donor support and independent energy-axis provenance.

The optional authenticated inclusive-count bundle avoids a new event scan only for its exact original local UV/VIS cohort. Consumers inspect ROOT headers and reject mismatched identities. Counts are not a good-run list. A different production cohort needs its own measured evidence.

Recovery remains experimental. Energy-axis independence, uncertainty/coverage calibration, correlated donors and residuals, and observable bias must be validated before adoption. See [status](status) for dated evidence and unresolved acceptance-policy results.
