# Stage 08: observable extraction

`python 08_observable_extraction/beam_asymmetry.py --help` exposes the standalone CLI. `scripts/run_pipeline.py` invokes it after reconstruction and measured calibration. The loader accepts compatible `raw` and `raw_bdt` products, selected beam profile, curated manifest, quality policy and calibrated flux. POL1 is vertical, POL2 horizontal; BREM is an unpolarized control. A usable run requires the validated flux triplet.

The default profiles are UV `[1.10,1.20,1.30,1.40,1.50]` GeV and VIS `[0.9313,1.10]` GeV, with explicit energy configuration supported. Pair masses and laboratory azimuths are formed for pπ⁰, pη and ηπ⁰. The same event contributes to all three projections.

For normalized yields yV=NV/FV and yH=NH/FH, the ratio is `(yV−yH)/(PH*yV+PV*yH)`. The nominal cosine fit and its low-p-value offset/sine diagnostic retain the existing conventions. The [finite-bin correction](finite-bin-correction) scales ratio Sigma and its errors exactly once by the approved divisor for 8/12/16 bins. `--best-binning` selects among those fits per point.

The conditional likelihood retains event run/strip exposure strata, physical Sigma domain and asymmetric intervals. It is not rescaled by the finite-bin divisor. Zero-yield exposures in the inclusive run universe must remain represented; `--by-period` uses reconstruction cutflow or an explicit universe manifest to compose exact catalog periods and pooled results.

Sideband/signal-MC inputs support background-fraction correction. Systematic components and run bootstrap can produce covariance products, but available machinery is not a completed uncertainty budget. The default launcher uses zero bootstrap replicas. Paired diagnostic bootstrap is distinct from covariance adopted for publication. Non-estimable bins remain marked, not zero-filled.

[Application owners](https://github.com/AntoninoFulci/GRAAL_Analysis/blob/main/08_observable_extraction) separate `workflow`, `period_workflow`, `extraction`, `extraction_background`, `extraction_systematics`, `core`, `io` and `plotting`. Outputs include `beam_asymmetry.root`, point/covariance metadata and diagnostic/publication PDFs. Use [manual extraction and composition](commands-and-configuration) to rerun this stage on compatible saved inputs. Theory follows through an [explicit stage 09 handoff](09-theory).
