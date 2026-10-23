# Stage 09: explicit theory calculations

[09_theory](https://github.com/AntoninoFulci/GRAAL_Analysis/blob/main/09_theory) is the standalone `graal-theory` package, imported as `graal_theory`. It is installed separately and runs only on explicit request after stage 08. Native comparison requires declared stage-08 data, reconstruction, measured calibrated flux and run manifest; the analysis launcher never starts it automatically.

```bash
graal-theory predict --help
graal-theory validate --help
graal-theory pilot-panel5 --help
graal-theory figure4-full --help
graal-theory figure4-basis-build --help
graal-theory figure4-fit --help
```

`predict`, `validate` and `pilot-panel5` use the partial Eq. (43) tree model. `figure4-full` integrates seven coherent amplitude families and checks numerical/physical gates. `figure4-basis-build --target native` takes `--data-root`, `--reco-root`, `--flux-root` and `--run-manifest`; `--target ajaka` builds the publication comparison basis. Both require `--output` and can resume with `--resume`. `figure4-fit` requires `--data-root`, `--basis-native`, `--basis-ajaka`, and `--output`; `--require-final` enforces final-input requirements. Outputs belong under a named `results/` or diagnostic `results_test/` campaign.

The native input contract retains per-point ratio binning, rounded divisors, diagnostic fallback and covariance row ordering. Measured-flux pilot `sigma_phi_fit` is a raw center-fit quantity; compare with corrected experimental Sigma only after matching the [finite-bin convention](finite-bin-correction). Continuous theory Sigma and a histogram center fit are not automatically identical observables.

Passing software tests does not certify a reproduced Figure 4. As of the recorded 23 October snapshot, **0/12 complete panels are certified**. Individual-bin numerical successes and the angular diagnostic pilot do not close the full convergence, cross-bin covariance or physical-comparison gates. Strong amplitudes are bounded at W ≤ 1.80 GeV; the source's qualitative scattering agreement through about 1.60 GeV is distinct from its use up to 1.80 GeV, with no quantified uncertainty implied.

The last preserved farm snapshot is **2026-10-23T13:02:26Z**: pilot `diagnostic_converged`, array 23 launched, `fit_status=not_started`. This is historical evidence, not live queue state and not a completed native fit. See [status](status).

[Model scope](https://github.com/AntoninoFulci/GRAAL_Analysis/blob/main/09_theory/references/model_scope.md), [parameter provenance](https://github.com/AntoninoFulci/GRAAL_Analysis/blob/main/09_theory/references/parameter_provenance.md), [amplitude inventory](https://github.com/AntoninoFulci/GRAAL_Analysis/blob/main/09_theory/references/figure4_amplitude_inventory.md), [historical convergence evidence](https://github.com/AntoninoFulci/GRAAL_Analysis/blob/main/09_theory/references/full_production_validation.md), and [bibliography](https://github.com/AntoninoFulci/GRAAL_Analysis/blob/main/09_theory/references/sources.json) retain the scientific source trail. Original PDFs are in [docs/papers](https://github.com/AntoninoFulci/GRAAL_Analysis/blob/main/docs/papers). Experimental Ajaka points use the stage-08 CSV; stage-09 theory-stroke digitization remains separately authenticated.
