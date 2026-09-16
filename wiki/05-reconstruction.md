# 05 — Reconstruction

Reconstruction reads selected ROOT files, applies common topology guards,
optionally applies Stage-1 BDT gate, chooses photon pairing by χ², and applies
default 6C kinematic fit.

## Structure

- `core/reco_physics.py`: channel definitions and missing-mass helpers;
- `core/event_logic.py`: ROOT-free event decisions and cut order;
- `core/kinematic_fit.py`: ROOT-free 6C fit;
- `runtime/cli_options.py`: shared command-line configuration;
- `runtime/reco_core.py`: ROOT chain, batched gate, branches, event loop;
- `runtime/stage1_gate.py`: model loading, provenance checks, scoring;
- `reconstruct_*.py`: channel-specific entry points.

## Entry points

```bash
python -m reconstruction.reconstruct_eta_pi0_chi2 --input-dir data/selected
python -m reconstruction.reconstruct_eta_pi0_bdt --input-dir data/selected
python -m reconstruction.reconstruct_2pi0 --input-dir data/selected
```

ηπ⁰ commands expose `--chi2-cut`, `--partner`,
`--missing-mass-window`, `--no-fit`, and `--fit-cl`. BDT command also
accepts `--model-dir`. Input tree defaults to auto detection.

## Common event path

1. require at least four photons and exactly one reconstructed proton;
2. optionally score event through BDT gate;
3. derive best pairing and require χ² below configured cut;
4. reject meson energy above tagged beam energy;
5. run 6C fit and apply confidence-level cut, or use missing-mass window when
   fit is disabled;
6. write retained event.

Common logic ensures χ² and BDT outputs differ intentionally only by gate.

See [χ² photon pairing](05-reconstruction-chi2),
[BDT gate](05-reconstruction-bdt-gate), and
[6C kinematic fit](05-reconstruction-kinematic-fit).
