# Stage 02: event selection

[select_events.py](https://github.com/AntoninoFulci/GRAAL_Analysis/blob/main/02_event_selector/select_events.py) selects `h80` into `h85`, retaining input branches and publishing output atomically. It requires exactly four central photons, exactly one identified proton, and zero identified pion candidates. Proton/vector cardinalities are checked before indexing.

| Proton angle | Required forward charged tracks |
| --- | --- |
| θ < 25° | Exactly 1 |
| θ ≥ 25° | Exactly 0 |

The selection compares angles in radians. Proton and pion PID cuts are assumed disjoint; a veto on identified pions does not certify the absence of unidentified charges. Required branch failures are explicit.

```bash
python -m event_selector.select_events --help
```

Output goes to the campaign artifact root or production cache; input h80 remains immutable. The 23 October central-proton study demonstrated recovery in the selector, while VIS BDT acceptance of this topology remains an [open validation](status).
