# Core/Tail Candle Test on Current Main — Design Specification

## Intent

Port the validated eta/pi0 candle stability test onto the repository's current
Stage-08 observable-extraction architecture.  The result must let UV and VIS
campaigns compare final beam-asymmetry points from equal-size, disjoint core
and tail samples without changing the nominal `raw_bdt` result.

## Scientific definition

- Start from the post-exposure/profile-selected `raw_bdt` events.
- The core is the inclusive rectangle
  `|M(eta)-M_ETA| <= 0.05 GeV` **and**
  `|M(pi0)-M_PI0| <= 0.05 GeV`, using raw pre-fit candidate masses.
- The tails are the finite-mass OR-complement: at least one candidate mass is
  outside its window. Events with either non-finite mass enter neither sample.
- Keep every tail event. Randomly sample the full core without replacement to
  the tail count using seed `20261024`, preserving original event order.
- Fail with explicit core/tail counts if either region is empty or the core is
  smaller than the tails.

## Integration on current `main`

- Add the pure split contract to
  `08_observable_extraction/io/reconstructed_events.py`.
- Add optional extraction CLI flags to `beam_asymmetry.py`; integrate candle
  samples in `workflow.py` after standard event selection and before fitting.
  Candle mode requires nominal `raw_bdt` and remains incompatible with
  sideband correction. The nominal sample is still extracted unchanged.
- Store strict, count-bearing candle provenance in the existing ROOT output.
  Extend `root_input.py` without weakening its current energy-grid,
  best-binning, covariance, or legacy validation.
- Add `plotting/candle.py` for the complete raw mass plane and core-versus-tail
  ratio/likelihood plots. Extend profile combination and campaign replotting
  only when both core and tail samples and valid provenance are present.
- Enable width `0.05` and seed `20261024` in the current workflow planner for
  both UV and VIS extraction stages.
- Document the operational definition and generated artifacts. Do not commit
  ROOT data, PDFs, virtual environments, or campaign results.

## Compatibility and failure behavior

No candle flags means current extraction and plotting behavior is unchanged.
Incomplete, duplicated, unknown, or physically inconsistent candle provenance
is rejected. UV and VIS combination requires identical scientific semantics,
while allowing their event counts to differ. Core and tails must each yield at
least one fitted point overall; individual fit bins may be absent independently.

## Testing

Use test-first coverage for inclusive boundaries, finite-only tails,
deterministic order-preserving balance, invalid/imbalanced samples, CLI and
workflow flags, strict ROOT round trips/rejection, plotting with unmatched bins,
UV/VIS compatibility, and campaign regeneration. Run focused tests and the
complete repository suite before committing and opening the PR.

## Approaches considered

1. **Focused port onto current `main` (selected):** integrate only the candle
   behavior into Stage 08 and the current workflow graph. This produces a
   reviewable PR and preserves the refactor.
2. Target a historical pre-refactor revision: less adaptation, but the result
   would not merge cleanly into current `main`.
3. Import the complete old local tree: rejected because it would overwrite the
   repository refactor and mix unrelated changes with the candle test.

## Non-goals

This PR does not publish the local UV/VIS campaign outputs, compute a formal
significance, introduce a shared-systematic covariance model, or alter nominal
physics selections outside candle mode.
