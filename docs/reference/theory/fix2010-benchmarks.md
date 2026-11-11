# Fix 2010: component verification, 6 November 2026

**Partial reconstruction, not a validated complete model.** T4–T6 have not been executed because G0 remains open. There are no predictions of sigma or Sigma. Requested domain remains [1.0,1.4] GeV; measured helicity support is smaller.

## Checks actually performed

| Source/version | Quantity / domain | Contributions | Units | Integration / precision | Result | Limits |
|---|---|---|---|---|---|---|
| 2010v1 Fig.6, hash-pinned fig6.ps | Solid I ratio; 80 vertices, E=1.0–1.394805194805 | Input only | GeV, dimensionless rho | Linear axes and interpolation; conservative vertical envelope .0150204 | pass: path recovery; fail: full requested support and .01 precision objective | Not an observable benchmark; no extrapolation |
| Lorentz identities, seed1905, 150 points at E=1.0,1.2,1.4 | On-shell masses and momentum conservation | Kinematics only | GeV² / GeV | Maximum residuals 4.44e-16 / 4.44e-16; test atol1e-10 | pass | Independent of amplitude normalization |
| Sum of pair invariants | s_pi_p+s_eta_p+s_pi_eta=W²+sum masses² | Kinematics only | GeV² | Maximum residual2.22e-15; test atol1e-10 | pass | No dynamic validation |
| Invariant measure, canonical phase coordinates | Constant integrand, E=1.2 | Phase volume | GeV² | Gauss-Legendre orders32,64,96; full remaining angles | pass | Not a cross section |
| Independent Dalitz-area integration | Same phase volume, E=1.2 | Phase volume | GeV² | Smoothed s integration, order96: 4.597842928195153e-6; canonical order96: 4.597845593125594e-6; relative discrepancy5.796e-7 <1e-6 | pass | Applies to invariant convention, not source t amplitude |
| Analytic massless limit | Φ3=W²/(256π³), W=2 | Phase volume | GeV² | Gauss-Legendre order20, relative tolerance1e-13 | pass | Diagnostic limit, not physical particle masses |
| 2010v1 Fig.8 | Total/contribution cross sections | Full baseline required | μb | Not computed, G0 open | inconclusive | No invented width/Born normalization |
| 2010v1 Fig.9 | Sigma, 1.1–1.2 /1.2–1.3 /1.3–1.4 | Full baseline required | 1 | Not computed; energy weights unresolved | inconclusive | Neither bin center nor arbitrary weights used as exact bin average |
| Plan T6 diagnostic targets | Successive-refinement change in Sigma ≤.005; sigma ≤max(.005 abs(sigma),1e-6 μb) | Full baseline required | 1 / μb | Not evaluated | inconclusive | Targets unchanged; no convergence claim for observables |

`results_test/fix2010-rebuild/numerical-checks.json` preserves quantitative residuals.
The PNG overlay was inspected against rendered PDF p.8 at the left edge, minimum,
curve crossing around 1.25 GeV and right edge. Reproducible SVG output retains all
source segments; red overlay identifies the selected solid path. The .0150204
reading envelope includes line width, integer coordinate quantization, independent
axis-check residuals and correlated axis offset/scale. No benchmark sensitivity
propagation is available until amplitudes exist.

## Software and install verification

TDD evidence: T1 16 failures before implementation →16 passed; T2 11→11;
T3 13→13; inspection CLI3→3. Fresh-context review found a missing type check
for allowed-helicity `rho_at_mass.value`: five invalid-type regressions failed
before correction, then passed; a negative-ratio control remained valid.

**Final result: 73 passed in 14.53 seconds** (49 theory checks, 24 packaging/integration checks). `git diff --check` passed. Final focused command (executed using the temporary environment):

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 \
TMPDIR="$PWD/results_test/fix2010-rebuild/tmp" \
MPLCONFIGDIR="$PWD/results_test/fix2010-rebuild/mplconfig" \
XDG_CACHE_HOME="$PWD/results_test/fix2010-rebuild/tmp/cache" \
results_test/fix2010-rebuild/venv/bin/python -m pytest \
  09_theory/tests tests/test_packaging.py tests/test_workflow_installed.py \
  --basetemp="$PWD/results_test/fix2010-rebuild/pytest-final" \
  -o cache_dir="$PWD/results_test/fix2010-rebuild/pytest-cache"
```

The environment was created with `python3 -m venv --system-site-packages`, then
editable installation with `pip install --no-deps --no-build-isolation --no-cache-dir -e .`.
Setting `PYTHONNOUSERSITE=1` excluded an older user installation that shadowed
numbered packages. `pytest`, `setuptools`, `uproot==5.7.4` and `awkward==2.9.1`
were installed in the disposable environment for packaging integration checks;
project dependencies were not changed.

The existing `tests/test_workflow_installed.py` fixture built wheel and sdist
from a copied source tree under the explicit pytest campaign root, with
`pip wheel --no-deps --no-build-isolation --no-cache-dir`. That wheel was also
installed into a second disposable environment with
`pip install --no-compile --no-deps --no-cache-dir <wheel>`.
From `/private/tmp`, `python -m graal_theory inspect` with absolute input paths
and a kinematic point calculation passed. Module origins were asserted to be
inside the installed environment, not the checkout. See `wheel-smoke.log`.

Earlier checks are retained as environment diagnostics, not code regressions:
`integration.log` recorded one stale-user-install path failure (66 passed);
`integration-clean.log` recorded two missing-uproot failures after excluding
that user environment (71 passed). No scientific output or test expectation
was changed to hide either failure.

## Retained evidence and cleanup

Campaign retains compact RED/GREEN logs, final verification/install logs,
source-boundary review/decision ledger, numerical residuals and one overlay PNG
plus the reproducible SVG. They explain incomplete gates and verification history.
Extracted paper text, PDF renders, source copies, build trees, wheel/sdist,
pytest caches, bytecode/cache directories and both virtual environments are
removed after jobs finish. Maintained tests, curated inputs and original papers
remain. No repository-wide scientific campaign was launched.
