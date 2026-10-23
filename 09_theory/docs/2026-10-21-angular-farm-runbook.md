# Angular native pilot: exact inputs and reproducible farm execution

This workflow produces deterministic refinement diagnostics and an exploratory
fit. It does not produce a Sobol certificate or final physics inference.

## Frozen farm snapshot

- Source: `/data/graal/GRAAL_Analysis/results/angular-native-pilot-20261021-v2/source`
- Timing campaign: sibling `timing/` directory.
- Snapshot archive SHA256: `bb0eb87e2c02049f5a28ae1e1e0e64e8eb44871bf50e19a38f3cda6f670cc7e1`.
- Campaign fingerprint: `f0f8645788af81cd05f98f81c84b2e3410b4274690218cf67f5a3a66aecf0325`.
- Scientific interpreter:
  `/data/graal/GRAAL_Analysis/results/flux-recovery-full-20261019/venv/bin/python`.
- NumPy 2.5.4, SciPy 1.18.1, uproot 5.7.4. Each job uses one BLAS/OpenMP thread.
- `SNAPSHOT.sha256` verifies every packaged source/reference/test file before jobs.
- Shared farm checkout remains untouched.

The archive includes source and tests, but not `theory/pyproject.toml`. Run tests
with `--rootdir=theory --import-mode=importlib` and
`PYTHONPATH="$PWD/theory/src:$PWD/theory"` to reproduce local pytest configuration.
Include the pyproject when preparing subsequent snapshots.

## Actual nominal inputs

Base: `/data/graal/GRAAL_Analysis/results/production_best_binning_nominal`.

- `uv/beam_asymmetry/beam_asymmetry.root`: 102 raw_bdt/ratio points.
- `uv/beam_asymmetry/periods/index.json`: `reconstruction_cutflow` universe;
  included in campaign identity.
- `uv/reco/reco_eta_pi0_bdt.root`: survivor events and inclusive run cutflow.
- `common/flux_calibrated.root`: calibrated flux used by nominal production.
- `config/run_manifest.csv`: P/UV run classification.

The uncalibrated `data/00_external/flux.root` is not a valid replacement.
The nominal production's `run.sh` and `inputs.sha256` identify the calibrated
file. Its recorded SHA256 is
`f8c9f2329e0747fb802b8be60cb890205b7d73f07b76f6c627bc3a8d0e75e647`.

There are 1425 inclusive runs versus 1396 runs with surviving events. Selecting
only survivors gave first-bin vertical exposure 221700567428.171 rather than
226715643293.237 (about 2.2% low). The inclusive-cutflow policy fixes the mismatch.
Incomplete/duplicate flux triplets remain excluded atomically per run.
Preparation verifies both fluxes and both polarizations against every selected
ROOT row at relative tolerance 1e-9. All 102 points passed this audit.

Each point retains its measured 8/12/16 azimuth-bin count, rounded divisor
.9003/.9549/.9745, and nominal versus diagnostic (constant+cosine+sine) fit.
The estimator choice is frozen from data and is not reselected during theory fits.

## Compute and resume

From the frozen source directory, set `GRAAL_PYTHON` to the interpreter above:

```sh
bash theory/scripts/run_farm_angular_fit.sh ../timing p_pi0:0:3
```

Slurm invokes the original script through a wrapper, with partition LocalQ,
one CPU, 4 GB memory and a two-hour time limit:

```sh
sbatch --partition=LocalQ --cpus-per-task=1 --mem=4G --time=02:00:00 \
  --wrap="bash /data/graal/GRAAL_Analysis/results/angular-native-pilot-20261021-v2/source/theory/scripts/run_farm_angular_fit.sh /data/graal/GRAAL_Analysis/results/angular-native-pilot-20261021-v2/timing p_pi0:0:3"
```

Use the wrapper: direct submission copies the script into Slurm's spool and
breaks its relative source-root lookup. Job 19 stopped at this snapshot check,
before amplitude calculations. Corrected job 20 uses the explicit original path.
Farm focused preflight: **65 tests passed in 93.33 seconds**.
 A bin lock prevents duplicate concurrent
writers. Each bin has separate manifests, so different bin tasks share no writes.

Timing resolution: energy2 / mass4 / angular4, direct production64/48.
Stages: base; angular8; mass8; energy4; inner production96/72.
Source/unit-offset Cartesian anchors are reused for angular refinement.
Each completed stage is an atomic, hashed checkpoint. Interruptions repeat only
unfinished stages; numerical failures persist as explicit masks. Source and input
identity are rechecked before publishing each stage and final diagnostic result.

Do not promote this timing resolution to a production setting. Use measured stage
cost and convergence to choose subsequent campaign resolution. A new resolution
requires a new campaign directory and fingerprint.

## Fit gate

```sh
"$GRAAL_PYTHON" theory/scripts/figure4_angular_fit.py fit --campaign ../timing
```

This deliberately refuses an incomplete campaign, including a one-bin timing
pilot. A record is required for every actual data key, including numerical masks.
At least three numerically resolved points are needed. Inclusion is selected
before looking at residuals. GLS slices the full covariance in ROOT row order.
Every optimizer trial repeats angular/mass/energy/inner prediction and matrix
checks; unresolved trials fail rather than becoming accepted parameters.

Even successful fits remain pilot-only: nominal background is uncorrected,
run-bootstrap covariance is absent, and final inference is suspended.

## October 23 checkpoint audit and continuation

Job20 reached its two-hour wall limit. Three content-hash-verified checkpoints
survived: base 1518.996 s, angular 1.912 s, mass 3030.066 s. Energy is incomplete;
inner and final diagnostic have not completed. The old job20 `.exit` file says
zero despite Slurm's TIME_LIMIT message; that exit file is not completion evidence.
Require the final manifest to be complete and all expected checkpoint hashes valid.

At the source parameters, angular refinement changes native Sigma by
-0.0000125339; mass4→8 changes it by +0.00420778. Across the three source/off-source
controls, the largest mass shift is 0.00435640, just below the data-derived limit
0.00445438 (0.2 times statistical error 0.02227192). Mass refinement matrix drifts
are at most 0.6045% under the declared scaling. This is partial evidence only;
energy and inner-loop checks remain necessary, including checks at every fit trial.

Resume job22 runs the unchanged v2 source and campaign with 1 CPU / 4 GB / 4 h.
Job21 failed before computation because its stderr directory contained a typo;
job22 supplies both log paths from the verified campaign root. New supervisor
records TERM as143 and INT as130, separately from the historical runner's exit
record. Success, failure, and TERM recording were tested locally: 0/1/143.

Job22 was verified RUNNING at00:22, CPU about97%, with empty error log. It reuses
base/angular/mass and recomputes only unfinished energy/inner stages.
Logs: `logs/ppi-resume-22.out` and `logs/ppi-resume-22.err`.
Submission: `submit/resume-20261023-r2.sbatch` outside the frozen source.
Local evidence: `theory/outputs/angular-native-20261023/checkpoint-audit.json`,
`pilot-status.json`, and `supervisor-checks.json`.

## Full native diagnostic array — October 23

User requested verification of all bins in parallel and established a preference
for generous farm wall limits (at least24h for long tasks; server used only by us).
After verifying job22's final checkpoint and source/off-source refinement checks,
submitted **array23**,101 remaining bins, maximum48 concurrent tasks, one CPU and
2GB requested per task, **24h per task**. Initial observation:48 RUNNING and40
PENDING;13 submitted tasks already finished. Their final diagnostic/mask statuses
are recorded in the local `all-native-status.json`, not inferred from exit codes.

Snapshot and numerical policy remain unchanged. This expands diagnostic coverage
at energy2/mass4/angular4 with doubled-axis and inner96/72 checks; it does not
promote the timing resolution to certified production. Bins failing convergence
will need further refinement. Kinematically unsupported data bins receive
explicit masks. No optimizer is automatically launched before reviewing results.

External submission assets:
`submit/all-native-20261023/{all-native.sbatch,keys.txt,submission-plan.json,array_job_id.txt}`.
The immutable pending-key list is hashed and checked by each task. Per-bin locks
and independent stage manifests prevent duplicate or shared-manifest writes.
Logs: `logs/native-23_<task>.out` and `.err`.

Source/reference fingerprint remains
`f0f8645788af81cd05f98f81c84b2e3410b4274690218cf67f5a3a66aecf0325`.
Local submission and verified status artifacts:
`theory/outputs/angular-native-20261023/all-native-*`.
