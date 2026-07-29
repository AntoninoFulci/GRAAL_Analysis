# Run Manifest Design

## Goal

Build a deterministic manifest mapping every raw GRAAL run to its source
period, target, beam type, and analysis group. The generator runs on the farm,
where the complete raw directory tree is available. The curated manifest then
returns to this repository and becomes the authoritative grouping input for
flux integration and observable extraction.

## Scope

This work covers manifest generation and validation only. It does not implement
strip-to-energy lookup, flux integration, background subtraction, acceptance,
or cross-section extraction.

## Inputs and outputs

The generator scans one raw-data root containing period directories and ROOT
files named `runNNNN.root`.

Command:

```bash
python scripts/build_run_manifest.py \
  --input-dir /path/to/graal_data \
  --output run_manifest.generated.csv
```

After manual classification of deuterium beam types, the user places the
curated file at:

```text
config/run_manifest.csv
```

Validation command:

```bash
python scripts/build_run_manifest.py \
  --validate config/run_manifest.csv
```

## Schema

CSV columns, in fixed order:

```text
run_number,source_period,target,beam_type,group,classification_source,source_file
```

Allowed values:

- `target`: `P`, `D`, `UNKNOWN`
- `beam_type`: `UV`, `VIS`, `UNKNOWN`
- `group`: `P_UV`, `P_VIS`, `D_UV`, `D_VIS`, `UNASSIGNED`
- `classification_source`: `automatic`, `manual`, `unresolved`

`source_file` is relative to the supplied input directory. This preserves
provenance without embedding farm-specific absolute paths.

## Automatic classification

Classification uses the period-directory name, case-insensitively:

- a proton period containing `uv` or `fuv` becomes `target=P`,
  `beam_type=UV`, `group=P_UV`, `classification_source=automatic`;
- a proton period containing `vis` becomes `target=P`,
  `beam_type=VIS`, `group=P_VIS`, `classification_source=automatic`;
- a period whose suffix starts with `d` (for example `2001_d`, `2002_d1`,
  or `2005_d2`) becomes `target=D`, `beam_type=UNKNOWN`,
  `group=UNASSIGNED`, `classification_source=unresolved`;
- every unrecognized period becomes fully unresolved rather than being
  guessed or omitted.

Deuterium UV/VIS assignment remains manual because existing directory names do
not encode the beam type reliably.

## Generation behavior

The generator:

1. recursively finds `runNNNN.root` files below the input directory;
2. extracts the run number from the complete filename;
3. takes the file's parent directory name as `source_period`;
4. classifies the period using the rules above;
5. rejects a run number appearing under more than one source path;
6. writes rows in ascending numerical run order;
7. writes the exact fixed schema and stable line endings.

Missing input directories, an empty scan, malformed filenames that start with
`run` and end with `.root`, duplicate runs, and an unwritable output path are
fatal errors. Unrelated files are ignored because they are outside the manifest
contract.

## Manual curation

The generated file is an intermediate artifact. For deuterium rows, the user
sets `beam_type`, `group`, and `classification_source=manual`. Other fields
retain generated provenance.

Generation does not merge with or overwrite a curated manifest implicitly.
The user selects the output path explicitly.

## Validation

Validation checks:

- exact required columns, with no missing or duplicate column names;
- integer, positive, unique `run_number`;
- nonempty `source_period` and `source_file`;
- values belong to the allowed enums;
- no `UNKNOWN`, `UNASSIGNED`, or `unresolved` remains;
- `group` agrees with `target` and `beam_type`;
- rows are ordered by increasing run number;
- `source_file` is relative, not absolute;
- basename of `source_file` matches `run<run_number>.root`.

Any violation produces a nonzero exit code and a concise row-specific error.
Successful validation reports row and group counts.

## Downstream contract

Future strip-to-energy and observable modules will join events and fluxes to
this manifest by `RunNumber`. They must fail if an input run has no manifest
row. Aggregation occurs only inside one of the four explicit groups; UV and VIS
or proton and deuterium data are never mixed implicitly.

## Tests

Automated tests use temporary directory trees and real CSV files. Coverage:

- P-UV and P-VIS automatic classification;
- deuterium rows remain unresolved;
- unknown period remains unresolved;
- duplicate run rejection;
- numerical row ordering;
- relative source provenance;
- generated CSV round trip;
- successful validation of a complete manifest;
- rejection of unresolved, inconsistent, malformed, unsorted, or duplicate
  rows;
- CLI exit status for generation and validation failures.

## Non-goals

- Inferring deuterium UV/VIS from neighboring run numbers.
- Reading ROOT event contents.
- Editing a curated manifest automatically.
- Calculating photon flux, efficiencies, or physical observables.
