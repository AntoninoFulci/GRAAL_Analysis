# 02 — Event selector

`event_selector.select_events` performs lightweight topology preselection
between h80 pre-analysis and reconstruction.

## Selection

```python
event.gammas.size() > 1 and event.fcharged_theta.size() == 1
```

Predicate requires more than one reconstructed photon and exactly one forward
charged track. It does not prove particle identity; later reconstruction
requires at least four photons and exactly one reconstructed proton.

## Storage behavior

For every `pre_*.root` input:

- open tree `h80`;
- clone branch schema with `CloneTree(0)`;
- rename clone to `h85`;
- fill entries passing predicate;
- drop `pre_` filename prefix.

```bash
python -m event_selector.select_events \
  --input-dir data/pre_analyzed \
  --output-dir data/selected
```

Command fails when input directory has no matching files, input ROOT file is
invalid, or h80 is absent. Empty discovery never permits stale selected files
to masquerade as fresh output.
