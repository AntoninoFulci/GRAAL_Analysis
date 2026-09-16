# 03 — Monte Carlo simulation

ROOT macros under `03_mc_simulation/generators/` create channel samples used
for Stage-1 training and fit validation.

## Registry-driven channels

`graal_common.physics.channels.CHANNELS` defines nine generated channels:

`eta_pi0`, `pi0pi0`, `3pi0`, `eta_2pi0`, `omega_pi0`,
`etaprime`, `eta_via_3pi0`, `4pi0`, and
`eta_pi0_via_3pi0`.

Registry owns filename, production masses, threshold, photon layout, reference
cross-section metadata, optional signal branching ratio, and optional
two-meson hypothesis. Pipeline reads generation order directly from registry.

## Generation model

Each macro uses ROOT phase-space generation and common
`generators/smearing.h`. Beam energy is sampled flat from channel production
threshold to generator maximum, then smeared with tagger resolution. Stage 4
remeasures detector beam spectrum and reweights each MC sample onto it.

Signal sample has named four-photon branches plus unsmeared truth branches.
Backgrounds use `g0...` and `n_true_gamma`; downstream readers get photon
count from file.

Channels producing more than four photons pass through
`bdt_training.photon_loss`. Only events with exactly four surviving photons
enter Stage-1 feature calculation.

## Status and reuse

```bash
python -m mc_simulation.mc_status --data-dir 03_mc_simulation/data
```

Exit 0 means every registry file exists, exit 1 means one or more are missing,
and exit 2 means internal failure. Age beyond ten days is warning only.
Pipeline reuses complete set, regenerates missing set unless skipped, and
supports `--force-mc`.

## Output

Each macro writes `<channel>_mc.root` with tree `mc` into current working
directory. Pipeline runs macros from `03_mc_simulation/data/`.
