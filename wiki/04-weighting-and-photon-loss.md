# 04 — Weighting and Photon Loss

All channels pass through the same photon-loss and detector-acceptance model.
Background shares combine beam-spectrum weights, energy-dependent cross
sections, generated counts, and survival fractions; signal share remains an
explicit training prior.

This page explains those distinctions and the numerical safeguards that keep
physics weights meaningful to XGBoost.
