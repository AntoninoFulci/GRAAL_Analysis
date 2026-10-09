# Full UV/VIS pipeline

## Inputs and setup

Place production `pre_analisi_*.root` files with usable `h80` trees directly in
`data/02_pre_analyzed/`. Place disposable subset files in
`test_data/02_pre_analyzed/`. The launcher does not create `h80` from raw `h70`.
Farm setup links only raw detector data:

```bash
./scripts/setup.sh --mode farm \
  --python /path/to/pyroot-compatible-python \
  --raw-target /path/to/graal_data
source .venv/bin/activate
```

Setup creates `data/02_pre_analyzed/` without moving, replacing, or linking its
contents. `data/00_external/flux.root`, `config/run_manifest.csv`, and checked-in
Stage-1 hyperparameters remain required.

## Production campaign

```bash
python scripts/run_pipeline.py --mode production \
  --output-dir results/october-uv-vis --phi-bins 12
```

`--phi-bins` accepts `8`, `12`, or `16` and defaults to `12`. Each launch
produces one azimuth binning, shared by UV and VIS, with the same output
layout. The choice controls the ratio fits and their azimuthal controls;
the conditional likelihood remains unbinned. Stage-07 ROOT files store
`binning/phi_edges` and `phi_bins` in provenance. Combined plots require
matching UV/VIS phi edges. Legacy ROOT files without phi metadata are read
as the previously enforced 12-bin case. For comparisons, launch separate
production campaigns, for example `results/phi8` and `results/phi16`.

Production requires a new empty campaign directory. No timestamp is added to
its name. Omit `--output-dir` to use `results/production/`, also only if empty.
After preflight, the launcher prints a table with inputs, paths, MC settings,
cache policy, force flags, and the ordered stages. A separate warning table
lists production `h80` files older than ten days. Tables wrap within the
terminal width; colors appear on compatible terminals unless `NO_COLOR` is set.
Answer `s` (or `si`, `sì`, `y`, `yes`) to start. Enter, any other answer,
or EOF cancels before output creation or replacement. Batch launchers must
provide an explicit answer.
Use `--force-selected`, `--force-mc`, or `--force-bdt` to rebuild that artifact
class. Otherwise a complete manifest and validated output can be reused for
up to ten 24-hour days after recorded completion. Changes to input identity,
options, relevant source, or output force a rebuild. Old `h80` inputs warn but
remain usable when valid. Missing or invalid inputs stop the run. A launcher
lock prevents concurrent campaigns from replacing shared artifacts.

Production intermediates live at stable paths:

```text
data/02_pre_analyzed/pre_analisi_*.root
data/03_selected/{uv,vis}/
data/04_mc/{uv,vis}/<channel>_mc.root
data/05_bdt/{uv,vis}/beam_spectrum.npz
data/05_bdt/{uv,vis}/features_stage1.npz
data/05_bdt/{uv,vis}/artifacts/stage1/
```

Adjacent `*.manifest.json` files record cache signatures, completion time, and
output identity. Selected, MC, and BDT output is validated in staging before
publication. A failed stage leaves its previous artifact in place.

## Disposable test campaign

```bash
python scripts/run_pipeline.py --mode test_data
python scripts/run_pipeline.py --mode test_data --output-dir results/test_subset
```

Test runs always rebuild selected data, every MC channel, beam spectrum,
features, and BDT in the parallel `test_data/{03_selected,04_mc,05_bdt}/`
layout. They overwrite the previous test artifacts and the named
`results/test_<campaign>/` directory. Output outside that namespace is refused.
Test files have no production cache eligibility or age warning. No automatic
timestamp enters a file or campaign name. The default is `results/test_data/`.

## Campaign output and plots

```text
results/<campaign>/
|-- common/flux_calibrated.root
|-- common/plots/                   UV/VIS and five-row comparisons
|-- uv/reco/                        chi2 and BDT ROOT files
|-- uv/beam_asymmetry/beam_asymmetry.root
|-- uv/plots/                       Dalitz, mass, asymmetry, diagnostics
|-- vis/reco/
|-- vis/beam_asymmetry/beam_asymmetry.root
|-- vis/plots/
|-- pipeline_artifacts.json         production cache outcomes and input identities
`-- pipeline_commands.log          RUN/SKIP reasons and commands
```

Profile and common plots include raw/6C-fit mass distributions for `M(p eta)`,
`M(p pi0)`, and `M(eta pi0)`, constrained eta/pi0 mass distributions, and
raw/fit asymmetry comparisons for ratio and likelihood estimators. Common
asymmetry figures use the five-row UV/VIS energy grid; mass figures use
separate UV/VIS panels with matching axes and per-profile normalization.

To regenerate plots from a completed campaign without rerunning selection,
MC, BDT, calibration, reconstruction, or extraction:

```bash
python -m scripts.plot_campaign --campaign results/october-uv-vis
```

This validates reconstructed and Stage-07 ROOT inputs before replacing
canonical plot directories. Legacy `combined/` and `beam_asymmetry/*.pdf`
files in older campaigns remain intact. Existing campaign ROOT results are
never modified by postprocessing.

## Failure checks

Launcher stops on first failed stage. Inspect `pipeline_commands.log` and
`pipeline_artifacts.json` for production cache decisions. Verify both profile
ROOT metadata and energy edges, then inspect PDFs under each `plots/` directory.
Run `python -m pytest -q` for repository checks.
