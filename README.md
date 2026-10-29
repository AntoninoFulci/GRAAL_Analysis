# GRAAL Analysis

Analysis of γp → pηπ⁰ with η, π⁰ → γγ. The pipeline compares χ² photon pairing with a Stage-1 BDT gate followed by the same pairing and missing-mass selection, then extracts beam asymmetry from measured calibrated flux. Stage 09 theory was retired on 26 October 2026; see the [restart boundary](wiki/09-theory.md).

The [GitHub Wiki](https://github.com/AntoninoFulci/GRAAL_Analysis/wiki) is the current technical guide; its [source index](wiki/Home.md) is versioned here. Start with [setup](wiki/getting-started.md), [workflow](wiki/workflow.md), [commands](wiki/commands-and-configuration.md), and [scientific status](wiki/status.md).

Use Python ≥3.10 compatible with CERN ROOT/PyROOT. Load ROOT, then:

```bash
./scripts/setup.sh --mode local
source .venv/bin/activate
python scripts/run_pipeline.py --help
```

For a farm use `--mode farm --python /path/to/pyroot-compatible-python --raw-target /farm/path/graal_data`. Setup validates imports and input links. See the wiki for user-site installation and wheel checkout requirements.

```bash
python scripts/run_pipeline.py --mode test_data
python scripts/run_pipeline.py --mode production --output-dir results/my-campaign
python scripts/run_pipeline.py config/pipeline.yaml --output-dir results/my-campaign
```

The [YAML example](config/pipeline.yaml) exposes explicit stage switches and external products. See the complete [stage configuration guide](#pipeline-configurabile-per-stage) below; legacy CLI and flat YAML remain supported.

These commands run scientific campaigns after preflight and confirmation. Restore missing local inputs first; see [availability after cleanup](wiki/data-and-artifacts.md#local-availability-after-cleanup). Their UV and VIS extractions include the reproducible [core-versus-tail candle test](wiki/core-tail-candle-test.md) with a `±0.05 GeV` raw-mass window. `--phi-bins 8|12|16` defaults to 12; `--best-binning` chooses per point. [Finite-bin correction](wiki/finite-bin-correction.md) applies only to the ratio estimator. The reduced UV+VIS input is diagnostic, not a normalized production dataset. Optional flux recovery remains experimental.

| Path | Contents |
| --- | --- |
| `00_common/`–`08_observable_extraction/` | Shared contracts and numbered analysis components |
| `graal_workflow/`, `scripts/`, `plots/` | Orchestration, entry points and output rendering |
| `config/`, `config/support/` | YAML di lancio; catalogo run, esclusioni e riferimenti verificati agli input |
| `data/`, `data_test/` | Production inputs, local raw/h80 test sources and reserved reduced-cohort path |
| `results/`, `results/_cache/` | Production campaigns and validated reusable products |
| `results_test/` | Tests, diagnostics, reports and explicit temporary/build roots |
| `wiki/` | Current technical documentation |
| `docs/papers/`, `docs/plans/`, `docs/reference/` | Original papers, active plans and scientific evidence |

See [maintenance and tests](wiki/maintenance.md) for isolated verification commands and wiki synchronization. Scientific sources and historical results retain their provenance; software tests do not establish detector acceptance, theory convergence or a complete uncertainty budget.

## Come è organizzata la cartella config

I file che modifichi per lanciare un’analisi restano subito visibili:

```text
config/
├── pipeline.yaml
├── pipeline_trima_uv_vis_ajaka.yaml
└── support/
    ├── common_inputs.json
    ├── run_manifest.csv
    └── run_quality_exclusions.json
```

Nei **YAML** scegli stage, percorsi, energia, tagli e risorse. Le opzioni facoltative restano commentate, così puoi riattivarle senza cercarle altrove.

I file in **support/** servono ancora: `run_manifest.csv` descrive i run e le loro classificazioni; `run_quality_exclusions.json` conserva le esclusioni già stabilite e le relative prove; `common_inputs.json` indica quali file usare e ne verifica l’integrità tramite SHA256. Non sono copie delle impostazioni di lancio e non vanno eliminati quando cambi il YAML.

La vecchia cartella `energy/` è stata rimossa: scegli le griglie in `profiles.uv.energy_edges_gev` e `profiles.vis.energy_edges_gev`. Le griglie nominali, divise in due e UV a bassa energia sono conservate nel YAML principale, come valori attivi o esempi commentati. La CLI `--energy-config` resta disponibile per leggere un JSON fornito esplicitamente dall’utente.

Il file di conteggi `inclusive_counts_local_1998uv_1999vis.json` è in `data_test/reference/`: contiene dati diagnostici già calcolati, non opzioni di lancio. Rimane versionato e non diventa un input di produzione. [Spostamenti e hash](wiki/data-and-artifacts.md#configuration-layout-migration-29-october-2026) documentano la conservazione dei contenuti. Se hai copie personali di configurazioni con percorsi espliciti verso i vecchi JSON o CSV, aggiornale a `config/support/`. Le firme della cache includono percorsi e codice: dopo questo aggiornamento la pipeline può dover rigenerare alcuni prodotti riutilizzabili; i risultati delle campagne precedenti non vengono modificati.

## Pipeline configurabile per stage

Il [file completo commentato](config/pipeline.yaml) usa `schema_version: 1` e rende esplicita l'attivazione di ogni stage. L'esempio parte dagli h80 inclusivi già disponibili, esegue entrambi i profili e lascia spenti preanalisi e studio flussi. Prima di lanciarlo scegliere una nuova destinazione e verificare gli input:

```bash
python scripts/run_pipeline.py config/pipeline.yaml --check
python scripts/run_pipeline.py config/pipeline.yaml --output-dir results/nuova-campagna
# Stessa interfaccia per gli entrypoint installati:
python -m graal_workflow config/pipeline.yaml --repo-root /percorso/checkout --check
graal-workflow config/pipeline.yaml --repo-root /percorso/checkout --check
```

`--check` valida configurazione, dipendenze, compatibilità e destinazioni e mostra il piano senza job, conferma interattiva o creazione della campagna. Gli errori restano bloccanti e restituiscono un codice diverso da zero. Controlla solo gli input e i runtime richiesti dagli stage attivi; un prodotto ancora da generare viene validato al confine prima del suo consumatore. L'esecuzione normale richiede la conferma dopo il riepilogo.

### ON/OFF, force e dipendenze

Usare booleani YAML `true` e `false`. **ON non accende altri stage** e OFF non cerca automaticamente prodotti nelle campagne precedenti. Ogni dipendenza arriva da un produttore ON oppure da un percorso esplicito in `inputs` con produttore OFF. Dichiarare entrambe le fonti è un errore. Un profilo OFF esclude i suoi stage; il confronto ON richiede entrambi i profili attivi.

La griglia `enabled`/`force` vale per `selection`, `monte_carlo` e `bdt`; gli altri stage non accettano `force`:

| `enabled` | `force` | Comportamento |
| --- | --- | --- |
| `false` | `false` | Stage spento; gli eventuali prodotti esterni necessari vanno dichiarati in `inputs`. |
| `true` | `false` | Stage attivo; riuso di cache compatibile se consentito, altrimenti esecuzione. |
| `true` | `true` | Rigenerazione della cache gestita dello stage. |
| `false` | `true` | Errore: una forzatura richiede stage e profilo attivi. |

| Stage ON | Dipendenze effettive |
| --- | --- |
| `preanalysis` | Raw h70 e tagli detector per periodo; scrive nuovi h80. |
| `selection` | h80 del profilo. |
| `monte_carlo` | Generatori e configurazione energetica/canali; non richiede selected. |
| `bdt` | Selected h85 e MC dei canali richiesti. |
| `reconstruction` | Selected e bundle BDT certificato; produce χ² e BDT+χ². |
| `calibration` | h80 inclusivi, flusso grezzo, catalogo e policy autenticati. |
| `flux_study` | Flusso grezzo, calibrazione/QA, catalogo ed eventuali metadati. |
| `extraction` | Entrambi i ricostruiti, flusso calibrato e contabilità inclusiva run/stato. |
| `plots` | Entrambi i ricostruiti compatibili; nessuna estrazione richiesta. |
| `comparison` | Estratti UV/VIS compatibili e riferimento pubblicato. |

Il confronto UV/VIS richiede definizioni compatibili: stesso `best_binning`, stesso `phi_bins` quando il binning non è adattivo, stesso `candle_enabled` e, quando il candle è attivo, stessa semiampiezza delle masse. Si possono eseguire estrazioni UV e VIS con binning φ differenti, spegnendo `comparison`; per combinarle occorrono estrazioni con definizioni compatibili. I validatori dei prodotti controllano inoltre le convenzioni registrate.

Gli h85 selezionati non sostituiscono gli h80 inclusivi nella calibrazione e non permettono di dedurre l'esposizione dalle sole rese. Gli input esterni sono di sola lettura: force, pubblicazione e cleanup non li sovrascrivono. Un input dichiarato ma non consumato viene segnalato; la mancanza o incompatibilità di un input necessario ferma il piano.

### Sezioni, opzioni e valori predefiniti

Tutti gli stage devono avere una sezione. Per gli stage comuni serve `enabled` direttamente; per ogni profilo attivo serve `enabled` direttamente o ereditato da `common`. Anche `profiles.uv.enabled` e `profiles.vis.enabled` sono espliciti. Non usare `null` per spegnere uno stage o per indicare un percorso assente: omettere i campi facoltativi.

| Sezione | Campi e significato |
| --- | --- |
| `campaign` | `mode`: `production` (default) o `test_data`; `repo_root`: checkout; `output_dir`: campagna, default `results/production` o `results_test/test_data`; `compare_to`: campagna precedente facoltativa per il confronto di configurazione. |
| `execution` | `cpus`: budget totale ≥1, default CPU disponibili; `seed: 42` per MC/feature; `color: auto` (`auto`, `always`, `never`); `check_only: false`, equivalente a `--check`. |
| `profiles.uv`, `profiles.vis` | `enabled` obbligatorio; `energy_edges_gev`: bordi crescenti compatibili con il profilo. Default UV `[1.10, 1.20, 1.30, 1.40, 1.50]`, VIS `[0.9313, 1.10]` GeV. Un'unica griglia alimenta i consumatori del profilo. |
| `inputs` | Percorsi dei prodotti esterni elencati nella tabella seguente; obbligatori solo quando consumati con il produttore OFF. |
| `stages` | Switch e opzioni dei dieci stage elencati sotto. |

| Campo in `inputs` | Tipo di prodotto esterno |
| --- | --- |
| `raw_dir` | Directory raw h70 per preanalisi ON. |
| `preanalysis_dir` | Directory h80 inclusivi quando preanalisi OFF. |
| `selected.uv`, `selected.vis` | Directory h85 quando selezione del profilo OFF. |
| `mc.uv`, `mc.vis` | Directory MC quando generazione OFF e training ON. |
| `bdt.uv`, `bdt.vis` | Directory del modello BDT certificato (`artifacts/stage1`, con modello, soglia e provenienza), quando training OFF e ricostruzione ON; non la directory superiore delle feature. |
| `calibration.root`, `calibration.qa` | Coppia flusso calibrato ROOT e QA quando calibrazione OFF. |
| `reconstruction.uv.chi2`, `.uv.bdt`, `.vis.chi2`, `.vis.bdt` | ROOT ricostruiti quando ricostruzione OFF ed estrazione o diagnostica ON. |
| `extraction.uv`, `extraction.vis` | ROOT di estrazione quando estrazione OFF e confronto ON. |

Gli stage `selection`, `monte_carlo`, `bdt`, `reconstruction`, `extraction` e `plots` accettano `common`, `uv` e `vis`. Gli altri quattro hanno le opzioni direttamente nella propria sezione.

| Stage | Opzioni oltre a `enabled` e default |
| --- | --- |
| `preanalysis` | `output_dir`: nuova directory h80, separata dai raw e dal campione immutabile; `cuts_dir`: tagli per periodo facoltativi, altrimenti quelli del proprietario. |
| `selection` | `force: false`; `pattern`: `pre_analisi_*uv*.root` o `pre_analisi_*vis*.root`; `require_current_preanalysis: false`, controllo dei marker tagger/raw aggiornati. |
| `monte_carlo` | `force: false`; `events_per_channel`: 1.000.000 in produzione, 100.000 in test_data se omesso; `channels`: canali nominali del profilo con soglia accessibile, oppure lista esplicita validata. `eta_pi0` è richiesto per MC/training attivi. |
| `bdt` | `force: false`; `hyperparams`: JSON facoltativo, altrimenti bundle versionato; `validation_fraction: 0.2` (tra 0 e 1); `training_seed: 42`; `feature_diagnostics: false`. |
| `reconstruction` | `chi2_cut: 10.0`, limite superiore del χ² di pairing; `missing_mass_window_gev: 0.06`, **semiampiezza** in GeV. Provenienza schema 2 / `pairing_missing_mass`. |
| `calibration` | `common_inputs`: manifest autenticato, default `config/support/common_inputs.json`; `min_events_per_strip: 1`, minimo di eventi per accettare una strip; `max_mad_gev: 0.005`, massima deviazione assoluta mediana delle energie; `monotonic_tolerance_gev: 0.002`, tolleranza di monotonia energetica tra strip (anche zero); `samples_per_run_strip: 256`, massimo campioni energetici conservati per run/strip. Flusso, catalogo e policy mantengono i loro contratti. |
| `flux_study` | `mode: audit` oppure `study`; `metadata`: JSON facoltativo. OFF si esprime con `enabled: false`; nessuna adozione automatica del flusso recuperato. |
| `extraction` | `estimator: both`, scelta dello stimatore di asimmetria (`ratio`, `likelihood`, `both`); `phi_bins: 12`, bin azimutali uniformi su [0, 2π] (`8`, `12`, `16`); `best_binning: false`, se attivo sceglie ogni punto ratio dai fit 8/12/16 prevalendo sul binning fisso; `mass_bins: 10`, bin delle masse di coppia pη, pπ⁰, ηπ⁰; `by_period: true`, estrazioni per periodi esatti del catalogo e campione unito; `workers: 1`, processi per fit/repliche indipendenti (≤ `execution.cpus`); `bootstrap_replicas: 0`, numero di ricampionamenti, zero disabilita; `bootstrap_seed: 1208`, seed dei ricampionamenti; `candle_enabled: true`, confronto core/code bilanciati in numerosità; `candle_mass_half_width_gev: 0.05`, **semiampiezza** del rettangolo sulle masse raw η/π⁰; `candle_balance_seed: 20261024`, seed del sottocampionamento del core. |
| `plots` | `mass: true`, masse η/π⁰ e correlazioni; `quality_controls: true`, controlli cinematici e fit gaussiano diagnostico η; `dalitz: false`, masse di coppia e residui dell’identità di Dalitz. Sono diagnostiche dei ricostruiti. I grafici propri dell'estrazione rimangono parte di `extraction`. |
| `comparison` | `published_reference`: CSV facoltativo, default `08_observable_extraction/references/ajaka2008_figure4_digitized.csv`; composizione/confronto UV/VIS separato dalla diagnostica. |

Le quantità numeriche devono avere il tipo richiesto; conteggi e budget sono positivi, bootstrap può essere zero, `execution.seed` è un intero in `[1, 2**32)`; `training_seed`, `bootstrap_seed` e `candle_balance_seed` ammettono anche zero, quindi `[0, 2**32)`. La correzione di bin finito resta propria dell'estimatore ratio; nessun override modifica implicitamente le convenzioni scientifiche. Grid search, sideband, signal-MC, priors, tuning dei singoli istogrammi e diagnostica GEANT4 restano nelle CLI specialistiche. Stage 09 rimane ritirato.

### Ereditarietà, CLI e percorsi

La precedenza è **default < common < profilo < flag CLI espliciti < `--set`**. Gli override di profilo cambiano solo i campi dichiarati; le liste sostituiscono la lista intera. Per esempio:

```yaml
monte_carlo:
  common: {enabled: true, force: false, events_per_channel: 1000000}
  uv: {force: true}
  vis: {events_per_channel: 200000}
```

Questo frammento va dentro `stages`: UV rigenera un milione di eventi per canale, VIS permette il riuso compatibile di 200.000. I flag generali applicabili ai profili modificano entrambi; `--set` può poi cambiare una singola foglia:

```bash
python scripts/run_pipeline.py config/pipeline.yaml --cpus 8 --phi-bins 12 \
  --set stages.extraction.vis.phi_bins=16 \
  --set stages.comparison.enabled=false \
  --set stages.monte_carlo.uv.force=true --check
```

Restano disponibili `--mode`, `--repo-root`, `--output-dir`, `--cpus`, `--seed`, `--color`, `--preanalysis-dir`, `--require-current-preanalysis`, `--force-selected`, `--force-mc`, `--force-bdt`, `--phi-bins`, `--best-binning`, `--extraction-workers`, `--energy-config`, `--flux-study` e `--flux-study-metadata`. I booleani hanno anche la forma negativa, per esempio `--no-force-mc` e `--no-best-binning`. `--energy-config` resta un JSON UV/VIS; `--flux-study off` spegne lo studio. Le nuove foglie si impostano con `--set chiave.puntata=valore`; `--set` richiede YAML strutturato. Chiavi sconosciute/duplicate, tipi errati, oggetti interi al posto di foglie e override ripetuti sulla stessa chiave sono errori.

I percorsi YAML sono relativi alla directory del file; quelli dei flag e di `--set` sono relativi alla directory corrente. `~` viene espanso; variabili d'ambiente, include e tag eseguibili non vengono interpretati. Spostando un YAML bisogna aggiornare i suoi percorsi relativi. Il vecchio YAML piatto senza `schema_version` e la CLI senza YAML mantengono la sequenza storica da h80; non mescolare chiavi piatte e strutturate.

### Cache, confronti e protezione degli output

In produzione, selection/MC/BDT riusano `results/_cache/` solo entro dieci giorni e con firme e prodotti validi. In `test_data` gli stage ON rigenerano questi prodotti sotto `artifacts/` della campagna. La calibrazione conserva la propria cache ROOT+QA legata al contenuto, senza TTL. Un prodotto esterno con produttore OFF non viene rigenerato per anzianità: deve comunque superare i controlli necessari al consumatore. Se si rigenera un upstream, la decisione di cache downstream viene rivalutata dopo la sua validazione.

Esistono limiti espliciti dei metadati storici. Per h80/selected, un profilo accertato errato (metadati incorporati o classificazione manuale del catalogo) è un errore; classificazione assente, automatica o non disponibile produce un avviso di profilo non certificabile, senza dedurlo dal nome del file. Per estrazioni esterne, il contratto verifica profilo, binning energetico/φ/masse, estimatore, correzione di bin finito e parametri candle registrati. Non certifica `by_period`, `bootstrap_replicas` e `bootstrap_seed`: il riuso è consentito con avvisi per questi campi, oppure si rigenera extraction per ottenere il comportamento richiesto. I risultati storici non vengono riscritti per colmare tali informazioni.

Una campagna contiene `root/`, `plots/` e `metadata/`. Nel percorso strutturato i PDF di ricostruzione sono in `plots/<profilo>/reconstruction/` e il relativo `istogrammi.root` in `root/<profilo>/reconstruction/`; i PDF di estrazione restano in `plots/<profilo>/`, quelli di confronto in `plots/common/`. La CLI legacy mantiene il proprio layout. La produzione richiede una destinazione assente o vuota: un cambio YAML non autorizza la sovrascrittura. `test_data` conserva la sostituzione protetta con ripristino in caso di errore. In `metadata/` vengono registrati `source_configuration.yaml` (testo sorgente), `effective_configuration.json` (valori effettivi), `configuration_overrides.json`, `stage_plan.json`, `stage_warnings.json` e `stage_artifacts.json` (identità di input, sorgenti e output, esiti di esecuzione).

Per confrontare una nuova configurazione con una precedente campagna usare:

```bash
python scripts/run_pipeline.py config/pipeline.yaml \
  --set campaign.compare_to=results/campagna-precedente \
  --output-dir results/campagna-nuova --check
```

`compare_to` legge `metadata/effective_configuration.json` della campagna indicata e mostra chiavi e valori diversi. Un riferimento assente o illeggibile è un errore; non viene cercata automaticamente l'ultima analisi e non vengono aggiunti metadati artificiali ai risultati storici. Senza `compare_to`, il controllo riguarda input/cache effettivamente riutilizzati. Le differenze di configurazione integrano i validatori scientifici: non rendono compatibile un prodotto che non lo è. Gli avvisi distinguono, per esempio, un cambio di `phi_bins` che richiede nuova estrazione da un cambio di finestra missing mass che richiede ricostruiti coerenti.

### Esempi di partenza

**Da raw:** nel file completo impostare `stages.preanalysis.enabled: true`, indicare `inputs.raw_dir` e una nuova `stages.preanalysis.output_dir`, rimuovere `inputs.preanalysis_dir`; lasciare esplicitamente ON i consumatori desiderati. La preanalisi non viene attivata dalla sola presenza dei raw.

**Da selected:** con l'esempio completo spegnere selection e fornire gli h85; MC e training restano attivi. Gli h80 inclusivi dell'esempio restano necessari alla calibrazione ON:

```bash
python scripts/run_pipeline.py config/pipeline.yaml \
  --set stages.selection.common.enabled=false \
  --set inputs.selected.uv=data/external/selected/uv \
  --set inputs.selected.vis=data/external/selected/vis \
  --output-dir results/da-selected --check
```

Per usare anche MC o BDT esistenti, spegnere il relativo produttore e compilare `inputs.mc.<profilo>` o `inputs.bdt.<profilo>`. Con calibrazione OFF occorre la coppia certificata ROOT+QA; gli selected non diventano una sorgente di esposizione.

**Sola estrazione UV:** salvare il seguente YAML nella radice del checkout, adattando i percorsi ai prodotti certificati disponibili. Non richiede training, MC o grafici di ricostruzione; resta obbligatoria la contabilità inclusiva prevista dal contratto di estrazione.

```yaml
schema_version: 1
campaign: {mode: production, repo_root: ., output_dir: results/sola-estrazione}
execution: {cpus: 2}
inputs:
  reconstruction:
    uv:
      chi2: data/external/uv/reco_eta_pi0_chi2.root
      bdt: data/external/uv/reco_eta_pi0_bdt.root
  calibration:
    root: data/external/flux_calibrated.root
    qa: data/external/flux_calibrated.qa.json
profiles:
  uv: {enabled: true}
  vis: {enabled: false}
stages:
  preanalysis: {enabled: false}
  selection: {common: {enabled: false}}
  monte_carlo: {common: {enabled: false}}
  bdt: {common: {enabled: false}}
  reconstruction: {common: {enabled: false}}
  calibration: {enabled: false}
  flux_study: {enabled: false}
  extraction: {common: {enabled: true, phi_bins: 16, workers: 2}}
  plots: {common: {enabled: false}}
  comparison: {enabled: false}
```

```bash
python scripts/run_pipeline.py sola-estrazione.yaml --check
python scripts/run_pipeline.py sola-estrazione.yaml
```

Per la **sola diagnostica** degli stessi ricostruiti impostare extraction OFF e plots ON; non occorre calibrazione se nessun consumatore la usa. L'interfaccia autonoma equivalente è:

```bash
python scripts/plot_campaign.py --reconstruction-only --profile uv \
  --chi2 data/external/uv/reco_eta_pi0_chi2.root \
  --bdt data/external/uv/reco_eta_pi0_bdt.root \
  --output-dir results_test/diagnostica-uv \
  --mass --quality-controls --no-dalitz
```

I tre interruttori accettano anche `--no-mass`, `--no-quality-controls` e `--dalitz`. Per il **solo confronto** attivare entrambi i profili, lasciare extraction OFF, indicare `inputs.extraction.uv` e `.vis` e attivare `comparison`. Tutti gli altri stage restano esplicitamente OFF. La diagnostica non avvia implicitamente il confronto.

### Preset trima: UV nei bin Ajaka e confronto UV/VIS nella fascia bassa

Il [preset dedicato](config/pipeline_trima_uv_vis_ajaka.yaml) esegue una sola campagna di produzione da `data/02_pre_analyzed`, con queste griglie:

| Profilo | Intervalli di energia [GeV] |
|---|---|
| UV | 0,930–1,100; 1,100–1,200; 1,200–1,300; 1,300–1,400; 1,400–1,500 |
| VIS | 0,930–1,100 |

I quattro intervalli UV sopra 1,100 GeV coincidono con quelli di Ajaka Figure 4. Il primo intervallo UV e quello VIS hanno gli stessi bordi per consentire il confronto diretto. Il riferimento digitalizzato disponibile **non contiene punti Ajaka tra 0,930 e 1,100 GeV**: il pannello lo indica esplicitamente, senza spostare punti da energie diverse. Il bordo inferiore riguarda l'energia misurata; la generazione rispetta comunque la soglia fisica ηπ⁰, circa 0,931311 GeV.

Selezione, MC, BDT, ricostruzione, calibrazione, estrazione, plot e confronto sono ON. Preanalisi raw e studio flussi sono OFF. Tagli, candle e statistica di un milione di eventi MC per canale restano invariati. Ogni profilo sceglie automaticamente i canali fisicamente accessibili nel proprio dominio energetico.

Dal checkout aggiornato su trima, nell'ambiente Python/ROOT del progetto:

```bash
python scripts/run_pipeline.py config/pipeline_trima_uv_vis_ajaka.yaml --check
python scripts/run_pipeline.py config/pipeline_trima_uv_vis_ajaka.yaml
```

Il YAML imposta `execution.cpus: 40` e `stages.extraction.common.workers: 40`. Il parallelismo effettivo dipende dalle attività disponibili; alcune diagnostiche sono seriali. Tutte le opzioni facoltative restano commentate con spiegazione ed esempi; gli switch obbligatori restano espliciti.

Lo stage `comparison` usa le stesse estrazioni per produrre in `plots/common/`:

- `asymmetry_uv_ajaka.pdf`: UV nei cinque intervalli, con Ajaka nei quattro intervalli pubblicati.
- `asymmetry_comparison.pdf`: stessa figura con VIS sovrapposto a UV nel pannello 0,930–1,100 GeV; UV nero, VIS blu, Ajaka rosso. Errori asimmetrici, bande sistematiche, simboli del binning φ e indicazione dei fit fallback sono conservati. Intervalli diversi restano su righe separate: il confronto non esegue un nuovo binning.
- Le diagnostiche degli stimatori, dei fit e del candle già previste.

Le due figure di asimmetria usano il campione `raw_bdt` e lo stimatore `ratio`; con `estimator: both` il confronto ratio/likelihood resta nella diagnostica dedicata. Non si ripetono MC, training o estrazione per ottenere la seconda figura.

Output in `results/trima_uv_vis_ajaka`, che deve essere assente o vuota. Questo preset sostituisce il precedente `pipeline_trima_uv_093_110.yaml`; i risultati preesistenti restano nella loro cartella. Per una nuova variante scegliere un altro `--output-dir`; `campaign.compare_to` permette di segnalare differenze rispetto a una campagna precedente. `force: false` consente il riuso compatibile; il dominio energetico cambiato invalida MC/BDT incompatibili nella cache gestita `results/_cache`.

I percorsi usano i link dati del checkout su trima: eseguire `--check` sul server prima del lancio. La verifica locale copre configurazione, piano e composizione dei grafici con dati sintetici; non costituisce un'esecuzione scientifica o una verifica dei dati sul server.

## Geant4 quick start

`03_mc_simulation/geant4` builds the preserved GRAAL geometry, runs diagnostic transport of particles or exported generator truth, and opens a Qt viewer. It needs **Python ≥3.10, CMake ≥3.16, a C++17 compiler, Geant4 ≥11.4 with GDML/Xerces-C and its physics datasets**. Qt 6/OpenGL are needed only for the viewer. ROOT/PyROOT is needed only to generate/export ROOT truth; geometry, smoke, replay and viewer need no ROOT or installed Geant4 examples. Tested locally with Geant4 11.4.3 on macOS arm64; Linux and Windows commands below have not been executed here.

From the repository root, after selecting an installation as described below:

```bash
python3 -B 03_mc_simulation/geant4/run.py geometry
python3 -B 03_mc_simulation/geant4/run.py smoke
python3 -B 03_mc_simulation/geant4/run.py view
```

Each command creates a new `results_test/geant4-<mode>-<timestamp>/` directory, builds there, and regenerates GDML from the frozen snapshot. `geometry` checks sampled overlaps; `smoke` transports ten 200 MeV photons toward the BGO and writes `events/events.csv`, material composition, random-engine state and a diagnostic summary. `view` opens the interactive detector. Logs and SHA-256 provenance are in the run directory. Existing output directories are refused; select a new one with `--work-dir results_test/my-new-check`. Once reviewed, remove disposable build/test directories; retain only needed diagnostic evidence.

Use `--geant4-prefix /path/to/install` to select Geant4 explicitly, `--gdml /path/to/geometry.gdml` to reuse a geometry, or `smoke --macro /path/to/run.mac` for another diagnostic. An explicit GDML bypasses conversion/overlap checking. `bash 03_mc_simulation/geant4/view_native.sh [geometry.gdml]` remains available on Unix. Paths with spaces are supported. Batch execution needs no display.

### macOS — external Spack

Install Xcode command-line tools (`xcode-select --install`), CMake, Python and [Spack](https://spack.readthedocs.io/en/latest/getting_started.html). Keep Spack itself and its environments outside the checkout. On this workstation the existing environment was moved, with file hashes verified, to `~/.local/share/graal/spack-macos-qt`; installed packages were preserved:

```bash
export SPACK_BIN="$HOME/Software/spack/bin/spack"  # adjust to your installation
export SPACK_ENV="$HOME/.local/share/graal/spack-macos-qt"
python3 -B 03_mc_simulation/geant4/run.py smoke
python3 -B 03_mc_simulation/geant4/run.py view
```

For a **new** installation, load Spack's shell setup and create an external environment from the portable recipe:

```bash
source /path/to/spack/share/spack/setup-env.sh
spack repo add "$PWD/03_mc_simulation/geant4/spack-repo/spack_repo/graal"
spack env create -d "$HOME/.local/share/graal/spack-macos-qt" 03_mc_simulation/geant4/spack.yaml
spack -e "$HOME/.local/share/graal/spack-macos-qt" install
export SPACK_ENV="$HOME/.local/share/graal/spack-macos-qt"
```

The recipe includes Qt and datasets. Its small package override selects Apple's native OpenGL framework rather than XQuartz, avoiding incompatible Cocoa contexts. The checkout contains only this recipe/package source, not a concretized environment or lockfile. If multiple installations match, set `SPACK_SPEC=/your-installation-hash`, or use `--geant4-prefix`. `Geant4_DIR` and `GEANT4_PREFIX` are also accepted.

### Linux

Use an existing Geant4 11.4 installation with GDML and datasets, or build the [official Geant4 source](https://geant4.web.cern.ch/download/) outside this repository. On Debian/Ubuntu, base build dependencies are `build-essential cmake python3 libxerces-c-dev`; add `qt6-base-dev libgl1-mesa-dev libxmu-dev libxi-dev` for the viewer. For example, after extracting the source into `$HOME/src/geant4-v11.4.3`:

```bash
cmake -S "$HOME/src/geant4-v11.4.3" -B "$HOME/build/geant4" \
  -DCMAKE_INSTALL_PREFIX="$HOME/.local/geant4-11.4.3" \
  -DCMAKE_BUILD_TYPE=Release -DGEANT4_USE_GDML=ON \
  -DGEANT4_INSTALL_DATA=ON -DGEANT4_USE_QT=ON
cmake --build "$HOME/build/geant4" --parallel 4
cmake --install "$HOME/build/geant4"
source "$HOME/.local/geant4-11.4.3/bin/geant4.sh"
export GEANT4_PREFIX="$HOME/.local/geant4-11.4.3"
python3 -B 03_mc_simulation/geant4/run.py smoke
```

For servers, omit Qt packages and set `-DGEANT4_USE_QT=OFF`; `geometry` and `smoke` still work. For `view`, use a graphical session with functioning Qt/OpenGL. `Geant4_DIR` supports installations with a nonstandard CMake package directory, including `lib64`.

### Windows — native PowerShell

Install Python ≥3.10, CMake, Visual Studio 2022 with **Desktop development with C++**, and an x64 Xerces-C build. Use Geant4 11.4.x and dependencies built for the same MSVC architecture/runtime; Qt 6 MSVC is optional. In Developer PowerShell, build the [official source](https://geant4.web.cern.ch/documentation/pipelines/master/ig_html/InstallationGuide/installguide.html), adjusting these paths:

```powershell
cmake -S C:/src/geant4-v11.4.3 -B C:/build/geant4 -A x64 `
  -DCMAKE_INSTALL_PREFIX=C:/Geant4/11.4.3 -DGEANT4_USE_GDML=ON `
  -DGEANT4_INSTALL_DATA=ON -DGEANT4_USE_QT=OFF `
  -DCMAKE_PREFIX_PATH=C:/deps/xerces
cmake --build C:/build/geant4 --config Release --parallel 4
cmake --install C:/build/geant4 --config Release
$env:GEANT4_PREFIX = 'C:/Geant4/11.4.3'
$env:PATH = "C:/Geant4/11.4.3/bin;C:/deps/xerces/bin;$env:PATH"
py -3 -B 03_mc_simulation/geant4/run.py smoke
```

For the viewer, rebuild Geant4 with `-DGEANT4_USE_QT=ON` and `'-DCMAKE_PREFIX_PATH=C:/deps/xerces;C:/Qt/6.x/msvc2022_64'`; add Qt's `bin` to `PATH`, then run `py -3 -B 03_mc_simulation/geant4/run.py view`. The launcher handles `.exe` and `Release/` output directories. Bash/Spack are not required. WSL follows the Linux instructions.

All platforms need datasets from the **same Geant4 release**. Missing-data errors require fixing the installation, not disabling processes: source `geant4.sh` on Unix, or set `GEANT4_DATA_DIR` to the directory containing the installed `G4NDL*`, `G4EMLOW*`, etc. Existing per-dataset `G4…DATA` variables take precedence and must not point to another release. Qt/DLL errors require matching dependency paths; `Geant4_DIR` must contain `Geant4Config.cmake`.

### ROOT truth → Geant4

All nine nominal generators now retain unsmeared beam, proton and photon four-vectors. Existing smeared branches and seeded random streams are preserved. Old background files without truth must be regenerated into a **new diagnostic directory**; the exporter refuses smeared-only input. Existing signal truth is accepted when its generator metadata is valid.

With ROOT/PyROOT loaded and this checkout installed (`python3 -m pip install -e . --no-deps` after the normal setup), generate ten signal events and export them on macOS/Linux:

```bash
mkdir -p results_test/g4-example
root -l -b -q '03_mc_simulation/generators/generate_eta_pi0_dataset.C(10,1.5,1.6,"results_test/g4-example/eta_pi0_mc.root",71)'
python3 -B 03_mc_simulation/geant4/export_truth.py results_test/g4-example/eta_pi0_mc.root results_test/g4-example/truth --max-events 10
python3 -B 03_mc_simulation/geant4/run.py replay --truth-dir results_test/g4-example/truth --work-dir results_test/g4-example/transport
```

Choose a fresh example directory on reruns: export/transport refuse existing output directories, while the ROOT generator itself can overwrite its output file. Substitute another `generate_<channel>_dataset.C` and `<channel>_mc.root` for backgrounds. `--channel` allows a nonstandard ROOT filename. Export defaults to at most ten events, checks generator metadata, on-shell four-vectors and four-momentum conservation, and never applies detector smearing.

Windows can replay the same exported `truth/` directory without ROOT:

```powershell
py -3 -B 03_mc_simulation/geant4/run.py replay --truth-dir C:/inputs/truth --work-dir results_test/g4-replay-windows
```

Native Windows export additionally needs compatible CERN ROOT/PyROOT and the installed Python project; use the same `export_truth.py` arguments with `py -3`. WSL follows the Linux example. Transport uses Geant4's HEPEvt reader, fixed seed 20261026 and origin/time-zero vertices. `truth/manifest.json` records source SHA-256/UUID and generator metadata; `truth.csv` maps Geant4 event IDs to ROOT entries. `events/events.csv` contains all completed events, including zero BGO deposits; `events/bgo_hits.csv` contains positive deposits per crystal (IDs 1–480), with earliest depositing pre-step time in ns. These are energy deposits, not calibrated signals or reconstructed photons. Exported events have unit generation weights, without flux, cross-section or branching-ratio normalization; polarization is not modeled.

### Physics and the ROOT replacement boundary

The diagnostic uses **FTFP_BERT_HP + electromagnetic option4 (`FTFP_BERT_HP_EMZ`)**, with 0.1 mm γ/e⁻/e⁺ production range cuts and zero proton range cut. This is an accuracy-oriented starting point for photon calorimetry and secondary neutron transport, not a demonstrated universally “most accurate” choice. Range cuts are secondary-production thresholds, not track-length or detector thresholds. Cut convergence and physics-model comparisons remain required.

**Do not replace the current ROOT-generated analysis samples yet.** The ROOT → Geant4 diagnostic bridge works for signal and backgrounds; production still needs period-specific geometry/material validation, beam/vertex/polarization and normalization, calibrated response, trigger, digitization and analysis event format. The frozen geometry has a **deuterium** target, while the generators describe a free proton. Runtime material interpretation is explicit and diagnostic; the original snapshot remains unchanged. ROOT remains useful for generation and I/O, with Geant4 supplying transport. See [material policy, verification and migration requirements](wiki/03-monte-carlo-simulation.md).
