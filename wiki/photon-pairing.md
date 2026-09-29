# Photon Pairing

Four observed photons admit three unique partitions into two unordered pairs.
The shared pairing code evaluates those partitions against a heavy/light meson
hypothesis and supplies a stable contract to feature construction and
reconstruction.

## Pairing Space

Photons are indexed 0 through 3. `PAIR_IDX` stores all six two-photon masses in
this order:

```text
(0,1), (0,2), (0,3), (1,2), (1,3), (2,3)
```

There are three disjoint partitions:

```text
(0,1) + (2,3)
(0,2) + (1,3)
(0,3) + (1,2)
```

For two different mesons, either pair can be the heavy meson, producing six
`Pairing` assignments. For a degenerate two-pi0 hypothesis, exchanging heavy
and light labels asks the same question, so only the three unique partitions
are scored.

`pair_masses` accepts one event with shape `(4, 4)` or a chunk with shape
`(N, 4, 4)`. The last axis is `[px, py, pz, E]`; the result contains the six
invariant masses in `PAIR_IDX` order. Small negative $m^2$ values caused by
resolution are clipped to zero before the square root.

## Heavy and Light Mesons

`Hypothesis` provides labels, pole masses, and counting windows. The eta-pi0
hypothesis assigns eta as heavy and pi0 as light. The two-pi0 hypothesis uses
equal masses and reports `is_degenerate=True`.

A `Pairing` stores photon-index pairs rather than four-vectors. This makes the
chosen assignment reusable by feature construction, raw reconstruction, and
the kinematic fit without recomputing a different matching convention.

## Chi-Square Definition

The analysis uses a mass resolution equal to 8% of each target pole mass:

$$
\chi^2 =
\left(\frac{m_H-M_H}{0.08M_H}\right)^2
+
\left(\frac{m_L-M_L}{0.08M_L}\right)^2.
$$

| Symbol | Code value |
|---|---|
| $m_H$, $m_L$ | measured pair masses selected from `pair_masses` |
| $M_H$, $M_L$ | `hypothesis.heavy_mass` and `hypothesis.light_mass` |
| 0.08 | `CHI2_RESOLUTION` |

`chi2_per_pairing` evaluates every valid assignment. `best_pairing` returns the
minimum assignment and score for one event; `best_chi2` returns minimum scores
for a batch; `best_pairing_indices` returns batched photon indices for feature
construction.

This is a ranking statistic based on a fixed resolution model. It is distinct
from the later constrained-fit chi-square and probability.

## Shared Contract

Stage-1 features and reconstruction import the same functions from
`00_common/physics/pairing.py`. Feature values must therefore be built on the
same assignment that the reported best chi-square scores. A second pairing
implementation would allow training and runtime to ask different questions of
the same photons.

The 6C fit receives the chosen pairing and adjusts measured four-vectors under
energy-momentum and pole-mass constraints. It does not replace raw pairing;
the assignment is selected first and then fitted.

Verification:

```bash
pytest 00_common/tests/test_pairing.py \
       04_bdt_training/tests/test_build_background_features.py \
       05_reconstruction/tests/test_reco_physics.py -q
```

See [Chi-square reconstruction](05-chi-square-pairing) and
[6C kinematic fit](05-kinematic-fit) for runtime use.
