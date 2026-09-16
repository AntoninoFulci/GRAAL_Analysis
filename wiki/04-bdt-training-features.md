# Stage-1 features

`graal_common.stage1.features.compute_stage1_features` is single training and
inference implementation. Input arrays are photons `(N,4,4)`, proton
`(N,4)`, and beam `(N,4)`, each four-vector ordered `[px, py, pz, E]`.
Output is float32 `(N,26)`.

## Ordered schema

1. six γγ invariant masses;
2. counts near light and heavy meson poles;
3. best two-meson χ²;
4. missing mass, missing energy, missing longitudinal momentum, missing
   transverse momentum;
5. total photon energy and beam energy;
6. maximum, minimum, and RMS photon energy;
7. sum of opening angles;
8. minimum and maximum γγ mass;
9. total photon transverse momentum;
10. proton momentum and cosine of polar angle;
11. heavy-meson energy asymmetry;
12. opening angle between reconstructed heavy and light mesons.

Exact names and order come from `feature_names(hypothesis)`. Dataset and
provenance persist this order; runtime gate rejects incompatible hypothesis.

Pair masses and best χ² use `graal_common.physics.pairing`, same implementation
as reconstruction. Tests protect exact reference vector and identity of
training/inference functions.
