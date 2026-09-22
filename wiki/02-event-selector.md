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
- validate `RunNumber`, `Polarization`, and `Xstrip` metadata;
- filter entries with ROOT RDataFrame and implicit multithreading;
- snapshot every source branch into tree `h85`;
- drop `pre_` filename prefix.

```bash
python -m event_selector.select_events \
  --input-dir data/02_pre_analyzed/pre_analisi \
  --output-dir data/03_selected \
  --threads 48
```

`--threads` defaults to all CPU cores visible to process.

Command fails when input directory has no matching files, input ROOT file is
invalid, or h80 is absent. Empty discovery never permits stale selected files
to masquerade as fresh output.

Selection builds a complete dataset in a temporary sibling directory and
publishes it atomically. A successful run replaces the previous output, so
files without a current pre-analysis input cannot survive as stale data. A
failed run leaves the previous complete selected dataset unchanged.
