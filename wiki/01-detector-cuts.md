# 01 — Detector Cuts

Detector cuts are compiled C++ implementations selected through `CutManager`.
Separate files encode particle hypotheses, detector regions, acquisition
periods, and polarization configurations without embedding those variants in
the main selector.

This page explains cut families, naming, dispatch, and safe extension boundaries.
