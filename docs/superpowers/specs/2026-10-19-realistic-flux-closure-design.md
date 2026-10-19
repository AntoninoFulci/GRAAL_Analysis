# Realistic missing-flux validation and observable closure

User approved the five-step next-stage proposal, omitting BREM failure investigation
and explicitly excluding whole runs 1441,1454,1988,2055,2064 in addition to
1322,1482,1970. Continue in current feature checkout, preserving all existing
uncommitted changes and production artifacts. No commits/pushes requested.

Deliverables: inventory all missing calibrated P run/states with local inclusive
counts, compatible clean donors and gap geometry; realistic masked validation
matching supported real missing patterns; Extra Trees and Kernel Ridge hybrid
versus normalized interpolation; observable closure on identical selected events
and exposure universe using existing extraction engine; separate candidate flux
artifacts only where inputs/geometry support prediction. No automatic adoption or
invented physical acceptance threshold. Missing raw and missing calibration remain
distinct. No new h80 acquisition assumed until local coverage inventory shows need.

Quality policy must represent user exclusions from prior development errors as
such, without claiming factor-100 evidence. Freeze exclusions before this round.
All periods used previously remain development data. Existing fit code, grids,
inner-fold donor isolation and shared observable selectors are reused.

Validation masks whole runs from training to prevent cross-state leakage, while
scoring/replacing only the states matching real missing patterns. Training,
validation and test assignments explicit, deterministic and shared by states.
Report unsupported patterns and donor distances; do not pretend representative
coverage of periods with no h80. Predictions on real missing states never use
unknown true spectrum/axis. Common-energy spectra are experimental; production
strip-axis compatibility must be established independently before adoption.

Closure uses native exposure engine and matched events, with fixed binning and
matched estimable outputs. Common-energy-to-strip projection requires independent
known energy axes for held-out calibrated runs and separate round-trip baseline
so discretization is not attributed to ML. No unpaired pull interpreted as
significance; covariance must be paired if estimated. Inadequate uncertainty
coverage or physical tolerance prevents automatic production use; explicit gate
status is an output, not permission to skip closure or candidate generation.
