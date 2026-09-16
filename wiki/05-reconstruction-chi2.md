# χ² photon pairing

`graal_common.physics.pairing` owns pairing used by Stage-1 features and
reconstruction.

## Pairing generation

Four photons have three disjoint partitions:

```text
(01|23), (02|13), (03|12)
```

For two different mesons each partition has both heavy/light assignments,
giving six pairings. Degenerate 2π⁰ hypothesis has three because swapping
identical mesons is not distinct.

## Score

For heavy and light pair masses:

```text
χ² = ((m_heavy - M_heavy) / (0.08 M_heavy))²
   + ((m_light - M_light) / (0.08 M_light))²
```

Mass targets come from `Hypothesis`; no table or copied mass list exists.
`best_pairing` returns lowest-scoring assignment. Default event cut is
`χ² < 10`.

## Following decisions

Selected pairing orders photons as heavy pair then light pair. Event logic
constructs mesons, rejects impossible meson energy, calculates

```text
missing = beam + target - heavy - light
```

and either fits event or applies missing-mass fallback.

Same shared implementation calculates Stage-1 best-χ² feature, preventing
training/reconstruction drift.
