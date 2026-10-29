# Commands and configuration

Eseguire dal checkout con l'ambiente compatibile con PyROOT attivo. Il [file completo commentato](https://github.com/AntoninoFulci/GRAAL_Analysis/blob/main/config/pipeline.yaml) usa lo schema per stage; il [README](https://github.com/AntoninoFulci/GRAAL_Analysis/blob/main/README.md#pipeline-configurabile-per-stage) descrive ogni campo, valore predefinito, dipendenza ed esempio da raw, selected o soli ricostruiti.

```bash
python scripts/run_pipeline.py config/pipeline.yaml --check
python scripts/run_pipeline.py config/pipeline.yaml --output-dir results/nuova-campagna --cpus 8
python -m graal_workflow config/pipeline.yaml --repo-root /path/to/checkout --check
graal-workflow config/pipeline.yaml --repo-root /path/to/checkout --check
```

`--check` controlla il piano senza avviare job, chiedere conferma o creare una campagna. Gli input mancanti/incompatibili e le destinazioni non valide restano errori. Un prodotto futuro viene validato dopo il suo produttore, prima del consumatore. I lanci senza check richiedono preflight e conferma.

## YAML strutturato: schema_version 1

Le sezioni sono `campaign`, `execution`, `inputs`, `profiles` e `stages`. Tutti i dieci stage devono comparire e dichiarare `enabled`; entrambi i profili dichiarano `enabled`. Le sezioni `selection`, `monte_carlo`, `bdt`, `reconstruction`, `extraction` e `plots` usano `common` con override `uv`/`vis`. `preanalysis`, `calibration`, `flux_study` e `comparison` sono comuni e hanno le opzioni direttamente nella sezione.

Un ON non accende dipendenze. Un OFF può alimentare i consumatori soltanto con prodotti espliciti in `inputs`. Un prodotto esterno e il suo produttore ON sono fonti ambigue e vengono rifiutati. I prodotti esterni sono di sola lettura; quelli non consumati vengono segnalati. Non si cercano automaticamente artefatti di campagne precedenti.

| `enabled` | `force` | Selection / MC / BDT |
| --- | --- | --- |
| `false` | `false` | Spento; eventuale prodotto esterno esplicito. |
| `true` | `false` | Riuso compatibile secondo policy, altrimenti esecuzione. |
| `true` | `true` | Rigenerazione della cache gestita. |
| `false` | `true` | Errore; anche il profilo deve essere attivo. |

Gli altri stage non hanno `force`. In produzione selection/MC/BDT riusano prodotti validi entro dieci giorni; in test_data rigenerano. La cache di calibrazione mantiene il contratto legato al contenuto senza TTL. La validità di cache downstream viene rivalutata dopo una rigenerazione upstream.

`inputs` accetta `raw_dir`, `preanalysis_dir`, directory `selected.uv|vis`, `mc.uv|vis`, bundle `bdt.uv|vis`, coppia `calibration.root`/`qa`, ROOT `reconstruction.<profilo>.chi2|bdt` e `extraction.uv|vis`. I percorsi sono necessari solo per i consumatori attivi. Calibrazione ON richiede h80 inclusivi; gli selected non sono una misura dell'esposizione. Estrazione richiede ricostruiti e calibrazione certificati, con contabilità inclusiva run/stato. Plots richiede soltanto i ricostruiti; comparison richiede entrambi i profili attivi e gli estratti compatibili.

La precedenza è **default < common < profilo < flag CLI espliciti < --set**. Liste sostituite interamente; i flag generali applicabili ai profili modificano entrambi. `--set` modifica una foglia conosciuta dello schema e richiede YAML strutturato:

```bash
python scripts/run_pipeline.py config/pipeline.yaml --phi-bins 12 \
  --set stages.extraction.vis.phi_bins=16 \
  --set stages.comparison.enabled=false \
  --set stages.monte_carlo.uv.force=true --check
```

`comparison` richiede lo stesso `best_binning` UV/VIS, lo stesso `phi_bins` se il binning non è adattivo, lo stesso `candle_enabled` e la stessa semiampiezza quando il candle è attivo. L’esempio spegne il confronto perché richiede φ differenti: tali estrazioni possono essere eseguite separatamente, ma non combinate con definizioni incompatibili.

`execution.seed` ammette interi da 1 a `2**32-1`; i seed training, bootstrap e candle ammettono anche zero. `execution.check_only: true` equivale a `--check`. I percorsi YAML sono relativi alla directory del file, quelli dei flag e di `--set` al cwd. `~` è espanso; nessuna interpolazione di variabili, include o tag eseguibili. Percorsi facoltativi omessi, mai `null`. Chiavi sconosciute/duplicate, tipi errati, oggetti interi negli override e duplicati della stessa chiave `--set` sono errori. I booleani CLI hanno forme negative, per esempio `--no-force-mc` e `--no-best-binning`.

`campaign.compare_to` indica una campagna dotata di `metadata/effective_configuration.json`. Il confronto mostra le chiavi cambiate; il riferimento assente/illeggibile è bloccante. Non cerca l'ultima campagna e non modifica risultati storici privi di metadati. Senza questo campo, i controlli riguardano gli input/cache usati. La produzione richiede una destinazione nuova o vuota; gli avvisi sulle differenze non autorizzano la sovrascrittura. Il launcher conserva YAML sorgente, configurazione effettiva, override, piano, avvisi e identità dei prodotti in `metadata/`.

Per h80/selected, un profilo accertato errato nei metadati o nel catalogo manuale blocca il riuso; classificazioni mancanti, automatiche o non disponibili producono un avviso di profilo non certificabile. Per estrazioni esterne il contratto controlla profilo, binning, estimatore, correzione finita e parametri candle registrati; `by_period`, `bootstrap_replicas` e `bootstrap_seed` non sono certificabili da quel contratto. Per questi campi il riuso è consentito con avvisi espliciti, oppure si rigenera extraction. Non vengono modificati i metadati storici.

## Compatibilità con CLI e YAML piatto

La CLI senza YAML mantiene il percorso storico dagli h80:

```bash
python scripts/run_pipeline.py --mode test_data --phi-bins 12
python scripts/run_pipeline.py --mode production --output-dir results/my-campaign --cpus 4 --extraction-workers 2 --seed 42
```

Un YAML senza `schema_version` mantiene il contratto piatto legacy. Per esempio, salvato nella radice del checkout:

```yaml
mode: production
output_dir: results/my-campaign
cpus: 4
extraction_workers: 2
seed: 42
phi_bins: 12
best_binning: false
flux_study: off
```

Avviare con `python scripts/run_pipeline.py config.yaml`. Le chiavi legacy corrispondono ai flag lunghi con underscore: `repo_root`, `mode`, `output_dir`, `cpus`, `extraction_workers`, `seed`, `color`, `preanalysis_dir`, `require_current_preanalysis`, `force_selected`, `force_mc`, `force_bdt`, `phi_bins`, `best_binning`, `energy_config`, `flux_study`, `flux_study_metadata`. Non mescolare chiavi piatte e strutturate. I flag espliciti prevalgono sul file; `mode` deve arrivare da una delle due fonti. Restano i controlli sui tipi, sulle chiavi duplicate/sconosciute e sui null. `off` è la stringa legacy per lo studio flussi.

Gli entrypoint installati accettano anche `repo_root` dal file; il checkout script usa il proprio repository solo se né YAML né CLI lo indicano. `energy_config` e `flux_study_metadata` conservano i formati JSON esistenti. Nello schema strutturato le griglie energetiche sono direttamente sotto `profiles`, e `flux_study.enabled: false` spegne lo studio.

## CLI specialistiche

`--phi-bins` accepts 8, 12 or 16 (default 12); `--best-binning` selects each ratio point among all three fits and overrides that fixed choice. `--energy-config` reads explicit UV/VIS grids. The default grids remain UV `[1.10,1.20,1.30,1.40,1.50]` GeV and VIS `[0.9313,1.10]` GeV. The planner also enables the [core-versus-tail candle test](core-tail-candle-test) for both profiles with a `0.05 GeV` half-width and seed `20261024`. The [common input manifest](https://github.com/AntoninoFulci/GRAAL_Analysis/blob/main/config/support/common_inputs.json) and [run quality policy](https://github.com/AntoninoFulci/GRAAL_Analysis/blob/main/config/support/run_quality_exclusions.json) are validated, not inferred from selected event counts.

Inspect supported interfaces without starting jobs:

```bash
python scripts/run_preanalysis.py --help
python -m event_selector.select_events --help
python -m bdt_training.build_background_features --help
python 05_reconstruction/reconstruct_eta_pi0_chi2.py --help
python 06_calibration/build_run_manifest.py --help
python 06_calibration/build_strip_energy_flux.py --help
python -m flux_studies.audit_flux --help
python 08_observable_extraction/beam_asymmetry.py --help
python scripts/plot_campaign.py --help
```

To change azimuth binning without rebuilding earlier stages, give stage 08 a completed, compatible campaign's reconstruction and calibrated flux. The following VIS example assumes `results/my-campaign` already contains compatible reconstructed products and a UV extraction with fixed **16-bin φ**, the same estimator/finite-bin definitions and **candle disabled**, matching this specialist command. A default 12-bin/candle-enabled UV extraction must be regenerated consistently before combination. The command writes a new diagnostic extraction:

```bash
python 08_observable_extraction/beam_asymmetry.py   \
  --raw results/my-campaign/root/vis/reco/reco_eta_pi0_chi2.root   \
  --raw-bdt results/my-campaign/root/vis/reco/reco_eta_pi0_bdt.root   \
  --profile vis   \
  --flux-file results/my-campaign/root/common/flux_calibrated.root   \
  --run-manifest config/support/run_manifest.csv   \
  --run-quality config/support/run_quality_exclusions.json   \
  --output-dir results_test/vis-phi16/beam_asymmetry   \
  --estimator both \
  --phi-bins 16 \
  --bootstrap-replicas 0
```

Combine that exact output with the existing UV result:

```bash
python -m observable_extraction.combine_profiles   \
  --uv-root results/my-campaign/root/uv/beam_asymmetry/beam_asymmetry.root   \
  --vis-root results_test/vis-phi16/beam_asymmetry/beam_asymmetry.root   \
  --published-csv 08_observable_extraction/references/ajaka2008_figure4_digitized.csv   \
  --output-dir results_test/vis-phi16/combined
```

Composition validates profile and finite-bin conventions; historical incompatible files must be regenerated from compatible inputs. `--by-period` produces exact catalog-period and pooled extractions using inclusive run accounting. [Stage 09](09-theory) records retirement and prerequisites for a future theory implementation.
