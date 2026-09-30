# Standalone Chiral-Unitary Theory Model Design

## Goal

Create an isolated Python subproject that reproduces the leading theoretical
description of

\[
\gamma p \rightarrow \eta \pi^0 p
\]

from Döring, Oset, and Strottman. The first scientific milestone is to
reproduce the published total cross section and invariant-mass distributions
using the central parameter values of the dominant
\(\Delta^*(1700)\rightarrow\eta\Delta(1232)\rightarrow\eta\pi^0p\) mechanism.

This work establishes a trustworthy numerical foundation for a later
calculation of the beam asymmetry \(\Sigma\) and eventual comparison with the
twelve panels of Ajaka et al. Figure 4. That plotting integration is not part
of this phase.

## Source Material

The implementation is based on these primary sources:

1. M. Döring, E. Oset, and D. Strottman, “Chiral dynamics in the
   \(\gamma p\rightarrow\pi^0\eta p\) and
   \(\gamma p\rightarrow\pi^0K^0\Sigma^+\) reactions,” *Physical Review C*
   **73**, 045209 (2006), DOI
   [`10.1103/PhysRevC.73.045209`](https://doi.org/10.1103/PhysRevC.73.045209).
2. M. Döring, E. Oset, and D. Strottman, “Clues to the nature of the
   \(\Delta^*(1700)\) resonance from pion- and photon-induced reactions,”
   *Physics Letters B* **639**, 59–67 (2006), DOI
   [`10.1016/j.physletb.2006.06.022`](https://doi.org/10.1016/j.physletb.2006.06.022).

Ajaka et al., *Physical Review Letters* **100**, 052003 (2008), DOI
[`10.1103/PhysRevLett.100.052003`](https://doi.org/10.1103/PhysRevLett.100.052003),
is the eventual comparison target, not the first validation target.

The supplied PDFs remain under `tmp/pdfs/`. The new subproject records DOI,
equation, table, figure, and page provenance, but does not duplicate the PDFs.
If an equation or parameter depends on another cited paper, that dependency
must be obtained and recorded before the corresponding term is implemented.
No missing value may be inferred or tuned silently.

## Scope

### Included in the first implementation

- relativistic three-body kinematics for \(\eta\pi^0p\);
- deterministic quasi-Monte Carlo integration using Sobol sequences;
- central parameter values with explicit units and source locations;
- the dominant \(\Delta^*(1700)\) production and decay chain;
- total cross section as a function of laboratory photon energy;
- \(M_{\eta p}\), \(M_{\pi^0p}\), and \(M_{\eta\pi^0}\) distributions;
- numerical convergence reports;
- comparisons with the relevant predictions in the first source paper;
- an independent command-line interface and test suite.

### Explicitly deferred

- beam asymmetry \(\Sigma\);
- the full set of chiral contact, Kroll–Ruderman, meson-pole, rescattering,
  \(N^*(1535)\), and \(N^*(1520)\) terms;
- uncertainty propagation and theoretical bands;
- fitting or tuning to GRAAL data;
- support for a second physical channel;
- changes to `07_observable_extraction/`;
- renaming pipeline stages;
- overlays on Ajaka et al. Figure 4;
- imports between the theory subproject and the current analysis packages.

## Isolation Boundary

The model lives in an unnumbered top-level `theory/` directory. It is an
autonomous Python subproject with its own `pyproject.toml`, package, tests,
commands, dependencies, and generated outputs. The repository root
`pyproject.toml` and existing analysis stages remain unchanged during this
phase.

The planned structure is:

```text
theory/
├── pyproject.toml
├── README.md
├── src/
│   └── graal_theory/
│       ├── constants.py
│       ├── particles.py
│       ├── kinematics.py
│       ├── phase_space.py
│       ├── amplitudes/
│       │   └── delta1700.py
│       ├── models/
│       │   └── eta_pi0_p.py
│       ├── observables.py
│       ├── validation.py
│       └── cli.py
├── tests/
├── references/
└── outputs/
```

`outputs/` contains generated, unversioned run directories. Code,
configuration examples, bibliographic metadata, and digitized regression
targets are versioned.

## Component Responsibilities

### Constants and particles

`constants.py` defines unit conversions and numerical constants.
`particles.py` defines immutable particle and resonance records. Every physical
parameter carries a unit and a source locator. Parameters without adequate
provenance cannot enter a validated model configuration.

### Kinematics

`kinematics.py` owns four-vectors, Lorentz products, boosts, two-body breakup
momenta, invariant masses, and laboratory-to-center-of-mass conversion. It has
no knowledge of a specific reaction amplitude.

### Phase space

`phase_space.py` maps Sobol points to physical three-body final states and
returns the corresponding invariant phase-space weights. Its contract is
generic over initial invariant mass and final-state masses. It must preserve
on-shell conditions and four-momentum conservation by construction, with
runtime checks exposing numerical violations.

Sample sizes use powers of two. The Sobol configuration is persisted so a run
is reproducible. Convergence is measured by repeating calculations at
\(2^N\) and \(2^{N+1}\) points.

### Amplitude

`amplitudes/delta1700.py` implements the dominant resonance chain and its
published propagators, vertices, spin structures, and couplings. It consumes
kinematic arrays and an immutable central parameter set and returns complex
event amplitudes. No experimental fit or plotting behavior belongs here.

### Reaction model

`models/eta_pi0_p.py` assembles particle definitions, the allowed mechanism,
spin/polarization averaging, and reaction-specific normalization. This is the
only first-version component that knows the complete
\(\gamma p\rightarrow\eta\pi^0p\) reaction.

The initial implementation uses functions and small dataclasses. Abstract
plugin interfaces, a reaction-description language, and speculative extension
points are deliberately excluded. Reusable abstractions will be extracted
when a second implemented mechanism or channel demonstrates the common
contract.

### Observables and validation

`observables.py` integrates weighted amplitudes into total cross sections and
the three invariant-mass spectra. `validation.py` compares generated results
with analytic checks and versioned targets digitized from the source paper. It
records both the numerical comparison and the acceptance decision.

### Command line

`cli.py` provides commands to generate predictions and run validation without
requiring notebooks. Notebooks may be used for exploration, but cannot become
the authoritative calculation or the sole record of any parameter.

## Numerical Conventions

- internal energies and masses: GeV;
- natural units: \(\hbar=c=1\);
- metric signature: \(+---\);
- real arrays: `float64`;
- amplitudes: `complex128`;
- input beam energy: laboratory photon energy \(E_\gamma\);
- invariant energy: \(s=m_p^2+2m_pE_\gamma\);
- spin and polarization averages: explicit in the reaction model and recorded
  in run metadata;
- final-state sums: explicit and recorded;
- randomization: no implicit process-global random state.

## Calculation Flow

For each requested photon energy, the program:

1. loads the central parameter set and verifies provenance and units;
2. calculates \(s\) and returns a physical zero below threshold;
3. generates a reproducible Sobol sample of three-body phase space;
4. validates on-shell conditions and four-momentum conservation;
5. evaluates the dominant complex amplitude for every phase-space point;
6. computes the spin/polarization-averaged squared amplitude;
7. applies invariant phase-space and initial-state flux factors;
8. integrates the total cross section;
9. fills the three invariant-mass spectra using the same weighted events;
10. repeats at the next Sobol resolution for convergence assessment;
11. writes results, provenance, convergence, and validation artifacts.

Using the same event sample for all first-version observables keeps their
normalization and statistical convergence correlated and auditable.

## Validation Requirements

The first version is considered scientifically usable only when all applicable
checks pass:

- four-momentum conservation residual below \(10^{-12}\) GeV;
- final particles on shell within the corresponding floating-point tolerance;
- constant-amplitude phase-space integral agrees with an independent analytic
  reference within 0.5%;
- total cross section changes by less than 1% between \(2^N\) and
  \(2^{N+1}\) samples;
- populated invariant-mass bins change by less than 3% under the same
  refinement, apart from explicitly reported low-statistics edge bins;
- predicted normalization and shape agree with digitized central curves from
  the source paper within approximately 20%, matching the precision claimed
  for the calculation;
- no parameter is adjusted against experimental data to obtain that agreement.

Digitization uncertainty and binning differences must be recorded in the
comparison metadata. Validation reports distinguish implementation failures,
integration non-convergence, digitization limitations, and known model
limitations.

## Output Contract

Each execution writes an isolated directory:

```text
theory/outputs/<run-id>/
├── results.npz
├── manifest.json
├── convergence.json
└── validation/
    ├── total_cross_section.pdf
    ├── invariant_masses.pdf
    └── comparison.json
```

`results.npz` contains arrays and bin definitions. `manifest.json` contains
schema version, code revision when available, physical parameters, units,
source locators, energy grid, Sobol configuration, normalization conventions,
configuration hash, and validation state. `convergence.json` records sample
sizes and resolution-to-resolution changes. `comparison.json` records target
provenance, differences, tolerances, and pass/fail results.

Generated run products are not committed. A later Stage 08 contract may either
consume a stable version of this bundle or depend on the package directly, but
that choice is intentionally deferred until the theoretical model passes its
standalone validation.

## Failure Behavior

- Missing parameter provenance is fatal.
- Energy below physical threshold produces a documented zero result.
- Nonphysical masses, widths, couplings, or sampling configuration are fatal.
- On-shell or conservation violations above tolerance are fatal.
- A nonfinite amplitude is fatal and reports the offending phase-space point.
- Failed convergence writes diagnostic artifacts but cannot produce a result
  marked as validated.
- Missing theory dependencies leave the affected term visibly unimplemented;
  they are never replaced by guessed constants or silent approximations.
- Partial outputs are not presented as completed validation runs.

## Testing Strategy

The independent test suite covers:

- Lorentz products, boosts, invariant masses, and threshold behavior;
- two-body and three-body kinematic identities;
- conservation and on-shell properties across generated Sobol samples;
- reproducibility for identical configurations;
- analytic constant-amplitude phase space;
- propagator behavior and published limiting cases;
- total-cross-section and histogram normalization;
- convergence classification;
- invalid configuration and nonfinite-amplitude failures;
- regression against versioned, source-linked digitized theory curves.

Tests should remain ROOT-free. The smallest sufficient test groups run without
generating publication artifacts; full validation is a separate explicit
command.

## Future Evolution

After standalone validation, the next scientific work may add the remaining
mechanisms from the source papers one at a time. Each addition must identify
its source equations, add focused tests, and demonstrate its effect on an
intermediate published observable before it becomes part of a combined
amplitude.

Beam asymmetry \(\Sigma\) begins only after unpolarized cross sections and
mass spectra pass. A second channel, when selected, will be used to identify
which existing functions are genuinely channel-independent. Integration with
the current observable-extraction code and any stage renumbering remain a
separate design task.
