# Final owner-review Wave B fix round 1

Base: `6b7da13`

Resolved findings:

- selected N2 events now fail the whole S4 count projection unless every
  required response observable maps to exactly one reconstructed mass and phi
  cell; diagnostics identify run, authenticated file hash, tree entry and
  observable, and all cells are validated before bootstrap/count mutation;
- Gate 0 flux rows are reduced once to the authenticated N3 response
  `(target, beam_group, energy)` universe before state, Compton, period
  coverage and exposure validation; valid unrelated Gate 0 groups or energy
  bins cannot block S4, while every retained row remains subject to exact
  authority and completeness gates;
- diagnostic Figure-4 layout now transports the frozen canonical
  `AngleConfig`; its exact reference axis and tolerance reach
  `reaction_plane_phi`, any degenerate reconstructed plane blocks before
  histogramming/publication, and an empty reconstructed event set is rejected.

TDD evidence:

- initial six focused regressions failed for missing AngleConfig transport,
  silent degenerate/empty diagnostic handling, unrelated flux retention, and
  skipped out-of-axis mass cells;
- explicit missing-phi regression failed when the phi rejection branch was
  removed, then passed after restoring fail-closed behavior;
- focused config/geometry/count suites: 98 passed before the explicit
  phi-specific regression; final paired mass/phi repro: 2 passed;
- Figure-4 PyROOT end-to-end suite: 5 passed, including no-publication
  degenerate-plane reproduction;
- full non-ROOT polarization suite: 501 passed before the added phi-specific
  regression.

Verification:

- `make verify PYTHON=python3`: 360 common/MC/BDT and 502 polarization tests
  passed; artifact inventory verification passed;
- `make test PYTHON=python3`: 991 tests passed with PyROOT;
- `git diff --check`: clean;
- no physics artifacts produced and no Wave C work performed.
