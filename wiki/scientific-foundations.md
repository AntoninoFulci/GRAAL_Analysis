# Scientific Foundations

The primary analysis reconstructs gamma p -> p eta pi0 with eta and pi0
decaying to two photons each. A forward charged track supplies the recoil
candidate, while photon pairing and a constrained fit reconstruct the mesons.

## Reaction and Final State

The primary production reaction is

$$
\gamma p \rightarrow p\,\eta\,\pi^0,
\qquad
\eta \rightarrow \gamma\gamma,
\qquad
\pi^0 \rightarrow \gamma\gamma.
$$

The reconstructed final state therefore contains four neutral clusters treated
as photons and one recoil-proton candidate. Event selection requires more than
one photon and exactly one forward charged track; it does not prove the track's
particle identity. Reconstruction applies the physics hypothesis and event
guards later.

Masses and the tagger resolution live in `00_common/physics/channels.py`:

| Quantity | Value used by code | Unit |
|---|---:|---|
| pi0 mass | 0.134977 | GeV |
| eta mass | 0.547862 | GeV |
| proton mass | 0.938272 | GeV |
| tagger resolution | 0.016 FWHM, converted to sigma | GeV |

These constants are shared by pairing, cross-section thresholds, feature
construction, reconstruction, and fit code. They must not be copied into a
stage-local registry.

## Analysis Hypotheses

A **channel** and a **hypothesis** answer different questions:

- `MCChannel` describes which reaction generated a Monte Carlo file, how its
  photons are stored, its production masses, and how it is weighted.
- `Hypothesis` describes which two mesons a set of four observed photons is
  tested against.

The shared registry currently defines:

| Hypothesis | Heavy candidate | Light candidate | Degenerate? |
|---|---|---|---|
| `eta_pi0` | eta | pi0 | No |
| `2pi0` | pi0 | pi0 | Yes |

Some channels determine a hypothesis naturally: `eta_pi0` selects
`ETA_PI0_HYP`, and `pi0pi0` selects `TWO_PI0_HYP`. Higher-multiplicity
channels such as `3pi0` do not determine which two visible mesons four
surviving photons should represent. `resolve_hypothesis` fails instead of
guessing unless the caller supplies an explicit override.

The same hypothesis must govern Stage-1 feature construction and runtime
reconstruction. Model provenance records it, and the Stage-1 gate refuses a
mismatch.

## Reconstruction Comparison

The analysis creates two directly comparable eta-pi0 samples:

1. **Standard chi-square reconstruction** enumerates photon pairings, chooses
   the assignment closest to the eta and pi0 pole masses, applies shared event
   logic, and optionally performs the 6C kinematic fit.
2. **BDT-gated reconstruction** first evaluates the fixed Stage-1 feature
   vector and rejects events below the persisted classifier threshold, then
   runs the same reconstruction logic.

The classifier gate is intended to be the difference between these samples.
Pairing, masses, event cuts, and fit physics remain shared. This separation
allows any observed change to be attributed to the background gate rather than
to two independently implemented reconstructions.

The [photon-pairing](photon-pairing), [Stage-1 gate](05-stage1-gate), and
[kinematic-fit](05-kinematic-fit) pages describe those contracts in detail.

## Measured Observable

The downstream observable is the photon-beam asymmetry, conventionally denoted
$\Sigma$, extracted from the azimuthal modulation of yields recorded with
orthogonal linear-polarization settings. The code combines reconstructed event
angles with run/strip-dependent flux exposure and polarization information.

Two estimator families are implemented: a normalized-ratio fit and a
conditional likelihood over exposure strata. Background correction and
systematic covariance are applied after the nominal per-bin estimate. See
[Beam-asymmetry estimators](07-beam-asymmetry-estimators),
[Background correction](07-background-correction), and
[Systematics and outputs](07-systematics-and-outputs).

This documentation describes the implemented method and does not claim a
physics result or quote an extracted value of $\Sigma$.

## Implementation and Tests

- Constants, hypotheses, and channels: `00_common/physics/channels.py`
- Pairing mathematics: `00_common/physics/pairing.py`
- Reconstruction event logic: `05_reconstruction/core/event_logic.py`
- Observable models: `07_observable_extraction/core/models.py`
- Registry tests: `00_common/tests/test_channels.py`
- Cross-stage schema tests: `tests/test_stage1_contracts.py`
