# Angular native-fit integration and farm preparation

User-approved scope: connect the validated angular integrator to the existing
physical two-coupling fit, complete p_pi0, prepare a resumable farm precompute
and subsequent pilot fit. Existing October 6 fit design remains the spec;
October 19/21 angular evidence supplies the source-equivalent quadrature.

## Decisions
- Reuse existing BasisBinMoment, quadratic forms, native measured exposure,
  checkpoint and optimizer contracts. Keep historical diagnostic sources
  frozen so archived hashes remain verifiable.
- Add one packaged angular geometry/reconstruction owner and one angular
  basis integrator; existing Sobol path stays the independent oracle.
- Three source/unit-offset models determine the exact g1/g2 basis. Sum
  complete complex families before forming interference matrices. Test
  off-source contractions and native 12-bin estimator counts.
- Native pilot: full nominal UV production, measured selected-run flux only.
  Verify actual provenance and covariance; do not call pilot data final.
- New deterministic checks give bounded diagnostic convergence, not the
  existing Sobol certificate. Fit trials must obey measured refinement
  bounds; no silent exclusion to improve residuals. Domain limit 1.80 GeV
  and all fixed physics remain unchanged.
- Farm preparation uses isolated snapshot, content hashes, per-bin atomic
  checkpoints, explicit masks and a pilot before any full campaign.
- No commits requested. Preserve all pre-existing dirty files.

## Task 1: Packaged three-pair geometry
RED: p_pi0 and eta_pi0 mass clipping/knots from actual four-vectors;
internal-azimuth cosine against explicit azimuth; phase-space normalization.
GREEN: reuse validated fixed-p_eta construction and family reconstruction;
generalize spectator cone and Dalitz clipping to all three pair observables.
Proof: focused geometry plus original probe regressions.

## Task 2: Native angular EM basis
RED: complex coherent matrix contractions, both azimuth harmonics, 12-bin
state counts, native onset/full-exposure normalization, physical source and
off-source oracle comparisons; reject unsupported support before amplitudes.
GREEN: integrate exact source/unit-offset families with reused anchors;
return the existing immutable BasisBinMoment contract.
Proof: independent Sobol/tree and direct physical off-axis checks, focused
basis/flux/fit regressions, bounded real p_pi0 pilot.

## Task 3: Resumable precompute and pilot fit
RED: changed inputs refuse resume; corrupt/incomplete bin cannot be fitted;
all requested bins recorded including masks; refinements gate source and
shifted parameters and matrix/state forms; fit evaluation rejects unresolved
trial predictions. Fit labeled pilot and retains data/parameter provenance.
GREEN: extend existing checkpoint/fit contracts with a separate angular
workflow and declarative resolution policy; avoid fabricated certificates.
Proof: synthetic identified fit, failure cases and small executable workflow.

## Task 4: Farm package and handoff
Read-only farm/input audit; snapshot source/tests/references with SHA manifest;
prepare commands for preflight, bounded timing pilot, per-bin computation,
collection and fit. Inspect full-run cost from pilot before scaling.
Proof: local focused suite, farm environment/import/tests and real pilot;
report exact commands, measured timings, inputs, outputs and remaining gates.

## Progress ledger
- Setup: existing isolated worktree .work/figure4-fit, branch feat/figure4-fit,
  HEAD 56302c8. Existing fit infrastructure already implemented; do not redo
  original tasks from stale unchecked boxes.
- Ruling: approved user sequence supplies scope; routine numerical and
  implementation choices follow existing spec without another approval round.
- Preflight: geometry feeds basis; basis returns BasisBinMoment consumed by
  existing checkpoint/optimizer. Native finite-phi counts need both harmonic
  matrices, not only the intrinsic cosine numerator.
- Farm read-only audit: ssh trima works with network escalation; queue empty.
  Existing scientific venv has scipy 1.18.1, numpy 2.5.4, uproot 5.7.4.
- Geometry: seven independent four-vector/cone tests passed. All three pairs
  implemented; frozen historical probes unchanged.
- Farm nominal production is best-binning (8/12/16), ratio-only rounded
  divisors .9003/.9549/.9745, with per-point diagnostic fallback. The prior
  reference to a universal 12-bin estimator is superseded by this audited
  contract. Loader and prediction now carry these fields in selected-row order.
- Native input tests: seven RED failures then GREEN; explicit suspended final
  inference remains pilot even if other prerequisites happen to be present.
- Harmonics: retained both cosine and H/V-interference sine matrices, tested
  against explicit symmetric internal azimuths for all three phi-bin counts.
- Shared integration driver: Sobol and angular backends now reuse identical
  onset/exposure/accounting. Complete upper-energy support is checked before
  amplitudes. Angular anchors cached across refinements, all seven complex
  families summed for source and both unit-offset models.
- Independent angular checks: all three pair measures/asymmetries compared
  with selected-pair Sobol; physical direct64/48 off-source amplitudes agree
  at rtol 2e-9. Six angular tests passed in 21.69s including physical oracle.
- Diagnostic fit contract: distinct AngularBinCheck, checkpoint roundtrip,
  matrix/refinement guards at every parameter trial; synthetic two-coupling
  fit and metadata/covariance slicing tests pass (12 focused tests).
- Farm capacity audit: LocalQ one idle 48-core, 120000 MB node. No jobs
  submitted yet. Nominal asymmetry input 9.8 MB; selected reco input 46 MB.
- Review fixes: bind recorded paths to executing workflow/imported package;
  validate source/data before each checkpoint publication; persist numerical
  ValueError/FloatingPointError as masks while interruptions remain retryable.
  Targeted regression suite passed (17 tests); reviewer confirmed both fixes.
- Actual flux identity corrected from raw data/00_external/flux.root to nominal
  common/flux_calibrated.root, as recorded in run.sh and inputs.sha256.
- Native --by-period production uses reconstruction_cutflow run universe:
  1425 inclusive vs 1396 survivor runs. Added opt-in inclusive flux selection,
  preserving old callers, with strict cutflow checks (four RED then GREEN).
  Extraction periods/index.json is now a hashed input and policy gate.
- Farm v2 preflight passed exact V/H flux and polarization comparisons for all
  102 selected ratio points. Snapshot and commands recorded in
  2026-10-21-angular-farm-runbook.md. Farm numerical tests currently running;
  no physical precompute job launched as of this ledger entry.
- Farm preflight complete: 65 tests passed in 93.33 s. Exact input/exposure
  audit passed all 102 rows. Final local targeted suite: 28 passed in .88 s;
  bash syntax and git diff --check clean.
- Pilot submitted with 1 CPU / 4 GB / 2 h wall limit. Job19 stopped at source
  lookup because Slurm spooled the script; no amplitude work occurred. Wrapped
  submission job20 is RUNNING; base and result manifests initialized, no errors
  at the first check (00:22 elapsed). Complete mass/angular/energy/inner results
  and the full-campaign resource decision are still pending. No fit claimed.
- October23: job20 timed out after2h; verified base/angular/mass checkpoints
  (1519/1.9/3030s), energy incomplete. Angular maximum |delta Sigma|1.33e-5;
  mass maximum .0043564 versus data-derived .00445438 limit, so near threshold.
  No complete diagnostic and no full fit yet.
- Resumed frozen campaign as job22 with1CPU/4GB/4h, verified RUNNING with no
  stderr at00:22. Job21 failed before compute due to stderr path typo; corrected.
  Signal-aware external supervisor tested for exit0/1/143; old job20 exit0
  conflicts with scheduler TIME_LIMIT and is explicitly not completion proof.
  No numerical code or frozen farm source changed during this continuation.
- October23 later: job22 completed energy(2806.39s) and inner(2755.01s),
  final checkpoint diagnostic_converged and source/off-source predict guards
  independently rerun successfully. Pilot now complete, not running.
- User requested all bins in parallel; authorized broad wall limits (>=24h).
  Array23 submitted101 remaining native keys, concurrency48,1CPU/2GB per task,
  24h/task. Verified48RUNNING, no stderr startup failures. Completed pilot reused.
  Existing coarse diagnostic policy retained; nonconverged bins require further
  refinement before fit. Full fit has not been started.
