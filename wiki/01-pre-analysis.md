# 01 — Pre-Analysis

Pre-analysis is the detector-level ROOT stage. The `PreAnalysis` selector reads
raw acquisition trees, applies configured event and particle cuts, and writes
the normalized `h80` tree consumed by selection and calibration.

This page documents the selector lifecycle, data boundary, implementation
files, and relationship to the period-specific [detector cuts](01-detector-cuts).
