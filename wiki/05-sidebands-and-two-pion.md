# 05 — Sidebands and Two-Pion Paths

Stage 05 includes three supporting paths: a broad eta-pi0 sideband sample, an
adapter that makes generated signal resemble selected detector input, and a
two-pi0 reconstruction. They reuse shared code but do not replace the primary
eta-pi0 observable inputs.

## Sideband Reconstruction

Run:

```bash
python -m reconstruction.reconstruct_eta_pi0_bdt_sideband \
  --input-dir data/03_selected \
  --model-dir 04_bdt_training/artifacts/stage1
```

The sideband path preserves the nominal topology guards, same Stage-1 model,
hypothesis check, and same best-pairing algorithm. Its defaults deliberately
broaden later selection:

```text
chi2_cut = infinity
do_fit = false
missing_mass_window = 0
```

It therefore preserves raw eta mass, pi0 mass, and proton missing-mass
sidebands after BDT selection. Output is
`results/reco/reco_eta_pi0_bdt_sideband.root`, tree
`reco_eta_pi0_bdt_sideband`. It has raw branches and `bdt_score`, but no fit
branch family.

This sample supports downstream background-template/sideband work. It is not a
drop-in substitute for nominal BDT reconstruction because it intentionally
omits nominal chi-square, fit-CL, and missing-mass restrictions.

## Signal-MC Adapter

`prepare_signal_mc_selected.py` converts the generated `eta_pi0_mc.root` tree
`mc` into detector-shaped tree `h85` so the normal reconstruction adapter can
read it.

Source requirements:

```text
beam, eta_gamma1, eta_gamma2, pi0_gamma1, pi0_gamma2, proton
```

Published branches:

```text
beam
gammas = [eta_gamma1, eta_gamma2, pi0_gamma1, pi0_gamma2]
protons = [proton]
neutrons = []
RunNumber = -1, Polarization = -1, Xstrip = -1
```

Run:

```bash
python -m reconstruction.prepare_signal_mc_selected \
  --input-file 03_mc_simulation/data/eta_pi0_mc.root \
  --output-dir data/signal_mc_selected \
  --threads 8
```

The fixed output name is `eta_pi0_mc_selected.root`. Source schema is validated,
thread counts must be positive, and the complete directory is published through
`atomic_output_directory`. Sentinel metadata makes clear that this file has no
real run/polarization/strip identity; it must not enter calibrated detector
observable extraction as ordinary data.

## Two-Pion Path

Run:

```bash
python -m reconstruction.reconstruct_2pi0 \
  --input-dir data/03_selected
```

This selects `TWO_PI0`, which has equal heavy/light masses. Only the three
unique photon partitions are scored. Raw branches use `pi0_1` and `pi0_2`
labels, and output is `results/reco/reco_2pi0.root`, tree `reco_2pi0`.

There is no two-pi0 BDT entry point: the versioned Stage-1 model treats two-pi0
as background, so using it to select the two-pi0 signal would be meaningless.
The CLI exposes the common chi-square, partner, and missing-mass arguments but
not `--no-fit` or `--fit-cl`. Because `RecoConfig` defaults remain active, the
current two-pi0 command runs the 6C fit with CL 0.01 by default.

Fit output branch names remain the shared historical `eta_fit`/`pi0_fit`
family even in this alternate channel. Consumers of two-pi0 output should rely
on the raw `pi0_1`/`pi0_2` family unless they deliberately account for that
labeling limitation.

## Boundaries

| Path | Primary eta-pi0 observable input? | Main purpose |
|---|---:|---|
| nominal eta-pi0 chi-square | yes, reference/raw modes | gate-independent comparison |
| nominal eta-pi0 BDT | yes, raw and fit modes | primary gated measurement |
| eta-pi0 BDT sideband | supporting input only | background sidebands/templates |
| adapted eta-pi0 signal MC | no | reconstruction and fit validation |
| two-pi0 reconstruction | no | alternate final state/control analysis |

All reconstruction outputs are direct ROOT `RECREATE` writes except the
signal-MC adapter's atomically published directory. Sideband and alternate
files should use distinct paths and tree names to avoid accidental mixing.

Relevant tests are `test_cli_contracts.py`,
`test_prepare_signal_mc_selected.py`, `test_reco_core.py`, and
`test_reco_physics.py` under `05_reconstruction/tests/`.

See [background correction](07-background-correction),
[kinematic fit](05-kinematic-fit), and [data and artifacts](data-and-artifacts).
