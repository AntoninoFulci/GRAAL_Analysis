# Known Limitations

These are present implementation boundaries, not implied roadmap promises.
They should be considered when designing production campaigns, interpreting
plots, or reusing an artifact outside the supported eta-pi0 analysis.

## Execution Model

- There is no central scheduler, DAG executor, freshness database, or automatic
  resume. Operators run stage entry points in order and decide when an existing
  artifact is still valid.
- Stage ordering is communicated by directories and file contracts, not
  enforced globally. A consumer validates its local inputs but cannot prove
  every upstream command used the intended source revision.
- Resource management is per command. ROOT thread counts, training threads,
  seeds, bootstrap replicas, and farm scheduling are not coordinated centrally.
- Some publishers are atomic at directory or file level; reconstruction and
  plotting generally write directly. Interruption can leave incomplete direct
  outputs that must be validated before reuse.
- GitHub Wiki publication is not automatic. The repository provides a sync
  script, but a human must run it deliberately with a configured remote.

## Environment Dependencies

- CERN ROOT and a compatible PyROOT/Python ABI are external requirements.
  Standard Python dependency installation cannot repair an ABI mismatch.
- Setup assumes a POSIX shell and uses symbolic links for farm data.
- ROOT serialization details, `TLorentzVector`, `RDataFrame`, and PyROOT object
  lifetime behavior are part of several adapters.
- Training depends on the versions of XGBoost, scikit-learn, NumPy, uproot,
  awkward, and matplotlib listed in the requirements file. Exact environment
  lockfiles or containers are not currently provided.
- C++ pre-analysis and ROOT generator macros remain outside the editable Python
  package and need a working ROOT/C++ environment.

## Data Availability

- Raw detector data, pre-analysis data, most MC ROOT files, and production flux
  inputs are not downloaded by the repository.
- Farm paths are site-specific and must be supplied to setup. Local mode creates
  directory structure only.
- Large ROOT, NPZ, selected-data, calibration, reconstruction, observable, and
  plot outputs are ignored by Git. Git history is not an artifact archive.
- There is no built-in remote data acquisition, checksum catalog, object-store
  upload, retention policy, or provenance database for generated files.
- The small external flux path may be versioned when supplied, and the Stage-1
  model bundle is currently tracked, but this does not make all production
  inputs reproducible from the checkout alone.
- Full scientific reproduction requires exact external inputs, command lines,
  seeds, software environment, and source revision in addition to the code.

## Scope Boundaries

- The primary workflow supports `gamma p -> eta pi0 p` with eta and pi0
  decaying to two photons. The two-pi0 path is a reconstruction/control path,
  not a complete parallel observable analysis.
- The checked-in Stage-1 model is tied to its declared signal channel,
  hypothesis, feature order, signal prior, and beam-reweighting provenance.
- The photon-loss model is a simplified independent acceptance model, not a
  full detector simulation.
- The 6C fit currently uses a default resolution model; calibrated detector
  covariance is not the default production input. Some richer fit diagnostics
  exist in memory but are not persisted in reconstruction trees.
- Reconstruction pairs only the first four photons. `n_photons_input` records
  higher multiplicity, and Stage 07 studies exactly-four versus inclusive, but
  best-quartet resolution is not implemented.
- Observable energy, phi, and mass bin counts are fixed for the nominal Figure
  4 workflow. CLI options expose phi/mass counts but reject non-nominal values.
- Run bootstrap is disabled by default and the code does not prescribe a
  production replica count.
- Background templates factorize three mass-pull marginals. Correlated
  background shapes are not fitted by the current implementation.
- The systematics module declares a broader required-analysis catalog than the
  components automatically materialized by the CLI. Missing named studies are
  not silently written as zero covariance.
- Randomized polarization-label support exists as a tested helper, but the
  public CLI currently writes BREM controls rather than a randomized-label
  product.
- Original executable Ajaka et al. theory curves are unavailable. Figure 4
  contains experimental points only; digitized curves are regression targets,
  not validated calculated theory.
- Plot labels and some runtime messages retain Italian terminology inherited
  from the analysis code. This does not change stored numerical contracts.

## Consequences for Users

Treat each result directory as a release candidate: validate QA, tests,
provenance, source revision, and inputs before publication. Do not infer that a
file is current merely because it exists. When extending another reaction,
hypothesis, estimator, or deployment platform, add explicit registry/schema
support and tests instead of relying on accidental compatibility.
