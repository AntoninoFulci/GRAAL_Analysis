# Server parallelism implementation plan

Goal: run the existing h70-to-observables analysis within an explicit CPU budget, without changing physics selections.

Architecture: bounded isolated processes for independent files, entry ranges, MC channels and fits; existing ROOT/XGBoost native pools for their stages. Each active stage owns the CPU budget, avoiding overlapping pools. Ordered reduction and exclusive/atomic publication preserve event identities, counters and paired bootstrap draws.

Constraints: Python >=3.10, ROOT/PyROOT compatible environment; no new physical selections; legacy serial calls remain available; never share live ROOT objects between processes. Existing user authorization covers implementation and tests, not a production campaign.

- [x] Common ordered process map: limit native pools to one; deterministic return ordering and exception propagation; real worker tests.
- [x] h70 driver: process separate raw files, merge deterministically by acquisition folder, sum skip counters, persist identities and hashes, publish new h80 directory atomically; serial/parallel ROOT comparison.
- [x] Launcher: explicit --cpus budget and MC seed, forward native threads/process workers, bounded concurrent MC channel execution, preserve cache transactions and failure handling.
- [x] MC/features: seeded ROOT RNG including phase space; channel-specific reproducible feature streams, bounded process map, serial/parallel equivalence tests.
- [x] Reconstruction: deterministic entry shards, isolated files, validated aggregation of provenance/counters and events, bounded inference threads, atomic publication.
- [x] Observables: independent fit and replica tasks, deterministic draws, no nested pools, parent-owned ROOT writing, serial/parallel covariance tests.
- [x] Server runbook: h70 preparation, smoke comparison, scaling benchmark, production commands and acceptance criteria. No timing promise without server measurements.
- [x] Integration: focused tests, full main suite, build, diff review; document remaining limits.

Review focus: empty raw files; all events rejected; process errors preserve previous outputs; order changes cannot change raw identities or bootstrap draws; CPU limits cover native pools as well as process counts. RAM/I/O scaling must be measured on the server.


Validation (2026-10-14, local ROOT 6.40.04 / Python 3.14):

- Main suite: 1125 passed, one existing empty-legend warning (177.08 s).
- Final worker-budget change: 55 focused tests passed, including real workers,
  features, reconstruction, flux holdouts and observable bootstrap equivalence.
  A 16-test debug run confirmed clean joblib worker recycling after importing
  ROOT increased RSS beyond its 300 MB growth guard; every task completed.
- ROOT merger regression: inherited implicit MT caused native TBB basket-write
  crashes after selector calls. Parent mergers now disable that pool and close
  outputs through their owning TFileMerger; the formerly failing cumulative
  sequence passed all 44 tests.
- Wheel build, Python compileall, Ruff critical checks and git diff --check passed.
- No server campaign launched. Throughput and peak job memory still require the
  documented server benchmarks. Flux predictive replicas remain serial.
