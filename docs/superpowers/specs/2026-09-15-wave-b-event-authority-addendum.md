# Wave B event-authority addendum

This addendum freezes event geometry and normalization lookup semantics for
polarization-v1. It does not approve a physics release.

- `angle` has exactly seven keys: `observable=reaction_plane_phi`,
  `period_radians=pi`, `range_radians=[0,pi]`,
  `reference_axis_lab=[1,0,0]`, `reaction_momentum=proton`,
  `degenerate_plane_policy=invalid`, and a finite positive `tolerance`.
- N2 retains the authenticated beam four-vector. One event azimuth is computed
  from beam momentum, lab `+x`, and reconstructed proton momentum, then reused
  for all three pair-mass observables. A degenerate plane rejects publication.
- Every selected event uses shared half-up `Xstrip` normalization and must map
  uniquely to its authenticated strip-energy row, state interval, response
  energy/beam group, and positive flux component. Missing or ambiguous mappings
  reject publication; they are not dropped.
- N3 QA `response_period_coverage` is loader-sealed. Records and fields use
  schema order, one record exists per response beam group, periods are sorted
  and unique, `coverage_valid` is true, and all three authority hashes are
  lowercase SHA-256. Declared periods equal periods actually supported by
  response-key flux and each has state and Compton authority.
- S4 evidence replays both strip lookup identity and sealed coverage payload.

No global run-by-every-energy-bin completeness rule is introduced. Validation
is limited to selected events and declared response-period use.
