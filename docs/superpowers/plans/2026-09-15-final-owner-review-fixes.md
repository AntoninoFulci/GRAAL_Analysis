# Final Two-Owner Review Fix Plan

**Base:** `4c7c37b`

**Goal:** close all seven Persona 1 and five Persona 2 Important findings before PR #9 is pushed or merged. No real N3/S4/S5/S6 physics artifact is produced.

## Joint decisions

1. V1 reaction-plane azimuth is computed from authenticated event beam momentum and reconstructed proton momentum, relative to lab `+x`, mapped to `[0, pi)`. Degenerate planes reject the event publication; they are never silently kept. Exact config keys are `observable=reaction_plane_phi`, `period_radians=pi`, `range_radians=[0,pi]`, `reference_axis_lab=[1,0,0]`, `reaction_momentum=proton`, and an approved positive tolerance. N3 schema authority carries the same convention.
2. Before any real N3 release exists, schema v1 may receive its final pre-release contract. Its joint approval becomes `N3-MASS-PHI-RESPONSE-V1-2026-09-15`; canonical config pins its path/hash/reviewers while top-level and acceptance release remain blocked. Acceptance approval requires schema approval, but schema approval does not require an existing acceptance release.
3. N3 QA contains canonical `response_period_coverage`, exactly one record per response beam group. Each record lists exact covered source periods, `coverage_valid=true`, and SHA-256 identities for detector conditions, MC configuration, and selection. CountAuthority requires exact equality between declared and used periods and binds the QA snapshot.
4. Every selected N2 event must map uniquely to state, authenticated strip lookup, energy bin, and positive flux exposure. `Xstrip` uses the repository half-up normalization rule and beam energy must lie inside the authenticated strip-energy interval within the approved numerical tolerance. Missing/ambiguous mapping rejects S4; no silent `continue`.
5. Flux-exposure statistical covariance is derived from authenticated `pol1`, `pol2`, and shared `brem` counts under the published independent-Poisson raw-count model: `Var(pol1-brem)=pol1+brem`, `Var(pol2-brem)=pol2+brem`, `Cov(pol1-brem,pol2-brem)=brem`; independent run/energy cells add. It is propagated by deterministic refits and named `flux_exposure_statistics`.
6. Compton node covariance is projected into all period/energy-bin polarization values with exact interpolation/integration weights, preserving within-period correlations and independence across source periods. Deterministic refits produce named `compton_polarization_statistics`.
7. S5 closure uses the same joint mass-phi forward model/private numeric core as S4, the authenticated N3 response and exact S4 layout. Deterministic injected full-Sigma vectors, fitted vectors, bias/pull and sign-swap results are embedded in immutable `sigma_fit_qa.json` and replayed by its reader and S6. Legacy scalar closure remains diagnostic only and cannot return release success for blocked config.
8. Releasable S4/S6 QA requires exact `status=approved`, `valid=true`, and `blocked_reasons=[]`. Inventory may record a structurally valid blocked bundle as `valid=false`, but never labels arbitrary filenames as valid physics.

## Wave A — shared authorities and repository integrity

- Separate schema approval from acceptance release approval in `AnalysisConfig`; pin approved schema authority in blocked canonical config.
- Extend response schema authority with canonical channel, angle convention, and N3 QA period-coverage contract; reject non-`eta_pi0` response/S6 rows.
- Add exact S4/S6 status fields and mutation tests.
- Make N2 inventory publication kernel/no-replace or hard-link exclusive, preserving foreign destinations.
- Make artifact inventory discover exact N3/S4/S6 bundles, reject symlinks/incomplete/extra bundles, verify internal hashes/state, and never mark unvalidated garbage valid.

Gate: focused tests, `make verify`, independent shared-interface review.

## Wave B — event geometry, normalization completeness, period coverage

- Parse frozen `AngleConfig`; retain beam four-vector in `EventSample`; compute one reaction-plane phi per event from beam and proton for all three mass observables.
- Parse authenticated strip lookup; validate every event's normalized strip and energy interval; require unique state/flux mapping and positive selected exposure.
- Parse and seal response period coverage from N3 QA; transport through CountAuthority; require exact used-period equality.
- Update S4 evidence authority payload/replay for new identities.

Gate: tilted-beam, degeneracy, lookup/flux omission, period mismatch, ROOT integration, coupled Task 1–8 tests, independent scientific review.

## Wave C — closure and missing nuisance propagation

- Add exact Compton bin-average weights and deterministic full-vector covariance propagation.
- Add flux-exposure covariance authority from authenticated raw flux components and deterministic full-vector propagation.
- Add forward-folded S5 closure on S4 layout, embed in S4 QA, independently replay all closure/nuisance arrays.
- Require S6 named response, Compton, and flux-exposure matrices to equal S4 replay; recompute systematic and total covariance. Inline unbound closure is rejected.
- Keep S4 exact triplet and S6 exact triplet unchanged.

Gate: analytic covariance references, cross-bin correlations, tamper tests, closure migration/sign tests, full S4/S6 replay, independent scientific review.

## Wave D — final public contract and release gates

- Update roadmap, physics docs, artifact policy, exact contract tests, Graphify semantics, graph health/historical hyperedges, and ARTIFACTS inventory.
- Run `git diff --check`, `make verify`, full `make test` with PyROOT, CLI smoke from foreign cwd with `PYTHONPATH` unset, machine-path/cache scan, and byte/SHA inventory audit.
- Run fresh Persona 1 and Persona 2 full-range reviews. Resolve every finding before push. Update PR #9 only after both are clean; merge only when remote checks and mergeability are clean.
