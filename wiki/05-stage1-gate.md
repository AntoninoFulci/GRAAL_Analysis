# 05 — Stage-1 Gate

The Stage-1 gate loads the versioned classifier bundle, computes features in
the training order, returns signal probabilities, and applies the persisted
threshold. It rejects incompatible reconstruction hypotheses before processing
events.

This page documents load-time checks, score semantics, batch behavior, and the
single intended difference from standard reconstruction.
