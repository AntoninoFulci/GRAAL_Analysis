# Stage 09: retired theory and restart

The previous stage 09 implementation was retired on **26 October 2026**, at the user's request, to restart theory and theoretical cross-section calculations from zero. Its Python package, CLI, models, numerical routines, fit/probe scripts and tests are no longer active in this checkout. A new, separate `graal_theory` package now provides verified input recovery, inventory inspection and three-body kinematics. It does **not** yet calculate amplitudes, cross sections or Sigma; the retired code remains inactive.

Experimental beam-asymmetry extraction in [stage 08](08-observable-extraction) remains active, including its calibration, estimators, covariance and plotting contracts. The common cross-section reference weights used for BDT backgrounds also remain active; they are separate from the retired theory model. The analysis launcher ends with experimental products and plots.

## Fix 2010 components delivered, 6 November 2026

Execution of the [implementation plan](../docs/plans/2026-11-06-fix2010-model-implementation.md) recovered 80 vertices of the **solid solution-I helicity ratio** from the authenticated vector source. Measured support is **[1.0, 1.394805194805] GeV**: the final 0.005195 GeV of the requested domain is absent, so `evaluate(1.4)` fails. Conservative vertical reading envelope is **0.0150204 in rho**, exceeding the diagnostic 0.01 target; it is not a physical parameter uncertainty.

Available: immutable ratio reader, checked Table-II inventory with incomplete-input rejection, canonical three-body momenta and invariant phase-space density. Conservation/invariant checks use 1e-10 absolute tolerance; phase volume is checked independently using Dalitz area and a massless analytic limit. These checks do not validate the full model.

**G0 remains incomplete.** Total/isobar width prescriptions, Born adaptation and relative normalization, coupling normalization and a printed angular-translation ambiguity need closure. T4–T6 and `predict` are unavailable. See [derivation and gap matrix](../docs/reference/theory/fix2010-derivation.md). No experimental data, production output, farm jobs or fit were used.

After installing the package using the repository mapping, inspection requires explicit paths:

```bash
python -m graal_theory inspect --parameters /ABS/REPO/data/theory/fix2010/parameters_solution_i.json --helicity /ABS/REPO/data/theory/fix2010/helicity_ratio_fig6_solution_i.json
```

This command reports `prediction_available: false`, input hashes, support and gaps. It has no implicit repository lookup. The extractor is explicit and refuses existing output:

```bash
python scripts/extract_fix2010_helicity.py docs/reference_papers/Fix_2010_1004.5240v1_source.tar.gz results_test/fix2010-rebuild/recovered.json results_test/fix2010-rebuild
```

Curated sources/inputs and hashes: `data/theory/fix2010/source_manifest.json`. Compact verification evidence and visual overlay: `results_test/fix2010-rebuild/`; see [verification record](../docs/reference/theory/fix2010-benchmarks.md). The active plan stays open because scientific gates are unresolved.

## Preserved evidence

Original papers remain in [docs/papers](https://github.com/AntoninoFulci/GRAAL_Analysis/blob/main/docs/reference_papers). Bibliography, digitized targets, parameter provenance and historical comparison notes are preserved under [docs/reference/theory](https://github.com/AntoninoFulci/GRAAL_Analysis/blob/main/docs/reference/theory/index.md). These records describe the retired attempt; they do not establish accepted parameters, a validated model or current operating commands.

The complete local source snapshot, including uncommitted changes and generated package metadata, is preserved in `results_test/theory-reset-20261026/theory-before-reset.tar.gz` and `results_test/theory-reset-20261026/archive/09_theory/`. The archive was checked against every recorded file hash before retirement. Its manifest is local diagnostic evidence, not a promise that ignored archives are available in a fresh clone. Tracked source history is also retained in Git.

Last historical status: **0/12 certified complete Figure 4 panels**. The preserved farm snapshot dated **2026-10-23T13:02:26Z** recorded a `diagnostic_converged` pilot, array 23 launched and `fit_status=not_started`. Retirement neither changes that evidence nor reports current queue state; no remote campaign was modified.

## Restart boundary

Later on **6 November 2026**, the user authorized recovering the helicity ratio from the original figure and researching the remaining inputs in the papers, narrowed the current laboratory energy domain to **1.0–1.4 GeV** (also for eventual fits), and deferred experimental-data integration. The [Fix 2010 implementation plan](../docs/plans/2026-11-06-fix2010-model-implementation.md) is a handoff to another agent, as requested. It specifies a new standalone reconstruction and evidence gates; writing the plan itself did not implement extraction or a model. Subsequent execution delivered the limited components described above; no data fit was performed.

On **6 November 2026**, the user requested reconstruction of the Fix/Mainz πη model from public resources and specified a laboratory photon-energy range of **0.93–1.50 GeV**. The [Fix source audit](theory-fix-inputs.md) records the candidate versions, downloaded preprints and unresolved numerical inputs. This extends the source research; it does not activate a replacement implementation.

On **5 November 2026**, the user requested a gradual research restart to implement the published model and calculate beam-asymmetry predictions in the experiment's own bins. The [source and ingredient map](theory-restart-ajaka.md) records that scope, the P73/B639 model-version issue and open inputs. This is source research only: the archived implementation remains inactive, and no new numerical contract or model validation is claimed.

Future work starts with an explicit request defining the observable, primary model source, conventions, units, normalization and independently checkable benchmark. Agree that scientific contract before introducing a new implementation. Old fitted parameters, numerical kernels and convergence claims are not default inputs to the restart.

A comparison with measured Sigma must declare stage-08 products, reconstruction, measured flux and run manifest, and match the [finite-bin convention](finite-bin-correction). A theoretical cross-section prediction and an experimental absolute cross-section extraction are distinct tasks. Acceptance, efficiency, luminosity and uncertainty requirements must be declared for the latter. Passing software tests alone cannot establish either measurement validity or model reproduction.
