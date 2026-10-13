# 07 — Flux studies

## Inputs and Preconditions

Read measured raw flux and the run manifest. Calibrated ROOT and its identity-bound
QA sidecar add coverage information. Acquisition conditions and independent
exposures are external evidence; run numbers do not establish time proximity.
Use [the runbook](../docs/runbooks/missing-flux.md) for the metadata schema and commands.

## Audit and Study Modes

`python -m flux_studies.audit_flux` inventories every run/state, key cycle and
strip. `python -m flux_studies.study_missing_flux` compares compatible donors,
mean/median templates, interpolation and Ridge on blocked masked measurements.
Launcher option `--flux-study off|audit|study` defaults to off.

## Validation

Separate offline interpolation from causal prediction. Fit/scaling/tuning and
interval calibration exclude outer hold-outs. Paired metrics include failure
and availability denominators. Shared replicas preserve strip/target covariance.
Without independent exposure, reconstruction concerns shape only. Without
acquisition evidence, produce inventory and protocol without synthetic numbers.

## Products and Limits

`results/<campaign>/missing_flux/` contains audit CSV/JSON and, when feasible,
study ROOT, validation tables and diagnostic plots. Candidate flux stays in a
separate synthetic namespace. Originals are hash-checked and never overwritten.
Scientific outcomes can be negative. [Stage 08](08-observable-extraction)
continues using measured flux only; no automated synthetic propagation into Σ.
