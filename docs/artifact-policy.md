# Published artifact policy

`ARTIFACTS.json` is the deterministic, commit-bound inventory of the explicit
published artifacts below `data/`, `results/`, and the portable part of
`graphify-out/`. It is fail-closed: raw detector, pre-analysis, selected,
cache, failed-run, clone-check, and other scratch paths are not inventory
inputs. Each record gives the path, byte count, SHA-256, role, validity, and
allowed use. Regenerate it after changing a published artifact:

```sh
python scripts/build_artifact_inventory.py \
  --repo-root . \
  --commit "$(git rev-parse HEAD)" \
  --output ARTIFACTS.json
```

## Authority and intended use

| Location | Authority / role | Allowed use |
| --- | --- | --- |
| `config/run_manifest.csv` | Authoritative curated run manifest | The source of truth for run selection and metadata. |
| `data/run_manifest.generated.csv` | Generated derived copy | Convenience input only; verify or regenerate from the authoritative manifest. |
| `data/flux/flux.root` | Published input | Compact flux input used by the checked-in analysis snapshot. |
| `results/strip_energy_flux/` | Derived source bundle | Input to rebuilding the observable-run bundle; inspect its QA before use. |
| `results/observable_runs/` | Accepted derived bundle | Use for normalization only when `observable_run_qa.json` reports `valid: true`. |
| `results/reco/` | Legacy reconstruction snapshots | Reproduce legacy plots only. These files predate required metadata propagation and are not valid for run-flux normalization. |
| `results/plots/` and `results/strip_energy_flux.run.log` | Diagnostic-only derived evidence | Visual and historical diagnostics; never a physics-normalization source. |

The inventory's `valid` field says whether the published file itself is an
accepted snapshot. It does not override the bundle-level QA gate: the
observable-run bundle is usable only when its QA file is valid and its recorded
hashes match the current files.

## Graphify portability

Portable Graphify artifacts are `GRAPH_REPORT.md`, `graph.json`, `graph.html`,
`.graphify_labels.json`, and `manifest.json` when present. They may be used to
query repository knowledge, but they are derived from the repository rather
than scientific authority. `.graphify_python`, `.graphify_root`, `cache/`,
`cost.json`, and temporary Graphify files are machine state and must remain
local. The inventory deliberately excludes them.

## Verify and rebuild

Fetch the binary objects before comparing inventory entries:

```sh
git lfs pull
shasum -a 256 results/reco/reco_eta_pi0_chi2.root
```

Compare the lowercase digest and byte count with the matching record in
`ARTIFACTS.json`. A mismatch means the file is not the published artifact for
the recorded commit; do not substitute it into the analysis.

Use `make verify` to read-only verify the saved inventory: it never regenerates
`ARTIFACTS.json`. It rejects missing, changed, or extra published artifacts,
Git LFS pointer text, an incomplete six-file observable bundle, invalid
observable QA, and disagreeing recorded input/output hashes. The source
`results/strip_energy_flux/strip_energy_flux_qa.json` intentionally remains
`valid: false` as a diagnostic source state; the accepted observable bundle's
QA is the separate required `valid: true` gate.

Rebuild the accepted observable bundle only from the authoritative manifest
and the checked-in source bundle:

```sh
python scripts/build_observable_run_database.py \
  --manifest config/run_manifest.csv \
  --strip-energy-dir results/strip_energy_flux \
  --output-dir results/observable_runs
```

After a rebuild, inspect `results/observable_runs/observable_run_qa.json`,
regenerate `ARTIFACTS.json`, and review the resulting diff before publishing.

## Rejection conditions

Reject an artifact or bundle when any of the following is true:

- Git LFS objects have not been fetched, or their digest/size differs from the
  matching inventory record;
- a candidate is outside the declared repository roots, is a symbolic link, or
  is omitted from the inventory;
- the observable-run QA says `valid: false`, required bundle files are missing,
  or their QA hashes do not match;
- a legacy reconstruction output is proposed for run-flux normalization;
- diagnostic plots, a run log, or local Graphify state is proposed as an input
  or scientific authority.
