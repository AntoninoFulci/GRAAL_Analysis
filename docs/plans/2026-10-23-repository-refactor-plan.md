# Repository Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Ogni worker riceve proprietà esplicita dei file e il divieto di sovrascrivere lavoro altrui.

**Goal:** consolidare baseline attuale e teoria su `main`, rimuovere il fit cinematico 6C, semplificare il codice e ricostruire wiki/grafo con stage numerati e separazione produzione/test.

**Architecture:** conservare package e contratti scientifici esistenti; introdurre un package installabile di orchestrazione e separare CLI da logica applicativa, IO nativo e rendering. Selezione e inferenza restano negli stage proprietari; teoria diventa `09_theory` con avvio esplicito dopo stage 08. Un solo README generale e una sola documentazione tecnica corrente nella wiki.

**Tech Stack:** Python >=3.10 compatibile con PyROOT, ROOT/C++, NumPy, uproot, XGBoost, setuptools, pytest, package autonomo graal-theory, Graphify installato.

**Spec:** [2026-10-23-repository-refactor-spec.md](2026-10-23-repository-refactor-spec.md).

## Global Constraints

- Decisioni utente: baseline attuale + teoria; branch storici in backup, senza importare `08_polarization`; un dataset ridotto UV+VIS; teoria su comando esplicito.
- Nessun `reset --hard`, `clean`, force push o rimozione di worktree con sorgenti non salvati. Verificare backup prima di cancellare ref Git.
- Unico README di progetto: `README.md` nella radice. Non crearne altri.
- `data/` e `data_test/` contengono input; output produzione in `results/`, prove/report/build temporanee in `results_test/`.
- `results/_cache/` contiene output riutilizzabili; test generano intermedi nella propria campagna `results_test/<campaign>/artifacts/`.
- `docs/` contiene soltanto `papers/`, `plans/`, `reference/`; vecchi runbook/spec/piani/wiki vengono sostituiti, non copiati come autorità correnti.
- Preservare Fortran, tagli per periodo, bibliografia, manifest, bundle BDT/provenienza e snapshot GEANT4. Non modificare gli output scientifici storici per far passare test.
- Conservare tagli attuali, 26 feature, flussi/esclusioni, ratio/likelihood, binnings e divisori `0.9003`, `0.9549`, `0.9745`; nessun flusso sintetico in produzione.
- Rimuovere fitter cinematico soltanto; conservare fit di calibrazione, inferenza azimutale e teoria. Nuova provenienza ricostruzione: `schema=2`, `selection_algorithm="pairing_missing_mass"`.
- Ogni task termina con verifica, revisione indipendente del diff e commit circoscritto. L'integratore possiede Git, manifest di packaging e modifiche condivise.
- Non avviare job scientifici lunghi o modificare campagne farm esistenti per eseguire questo refactor.
- Ogni worker crea `results_test/repository-refactor-20261023/<task>/` per log, JUnit, cache pytest e directory temporanee distinte. Eseguire Python con bytecode disabilitato (`-B` o `PYTHONDONTWRITEBYTECODE=1`); impostare `TMPDIR` alla sottodirectory temporanea del task e `MPLCONFIGDIR` alla sua cache matplotlib. Passare a pytest `--basetemp=<task>/pytest-tmp -o cache_dir=<task>/pytest-cache`; build/ROOT/CMake usano directory esplicite nello stesso albero. I comandi di prova abbreviati sotto ereditano sempre questo ambiente, non i default nella sorgente.

## Review Focus

1. Sorgenti dirty/untracked nel worktree teoria devono sopravvivere a merge, spostamento e cancellazione branch: Task 0–1 verificano ripristino e inventari.
2. Output storici con vettori raw ma selezione diversa devono essere rifiutati: Task 3 verifica provenienza positiva, non solo assenza di branch fitted.
3. Seed, gruppi cache e budget CPU devono restare invarianti dopo rinomina delle etichette: Task 5–6 verificano comandi e identità separate dai nomi visualizzati.
4. Symlink e destinazioni sovrapposte non devono permettere ai test di sostituire dati/produzione: Task 2 verifica path risolti, lock e rollback.
5. Risorse native, riferimenti teorici e fonti del grafo devono funzionare fuori dall'editable checkout e dopo rimozione docs: Task 7, 10–11 verificano wheel, link, fonti e corpus.

## Stato verificato all'inizio della pianificazione

- Checkout corrente: `codex/dalitz-completion`, `5ba89c0`; 158 cancellazioni locali già presenti e lavoro aggiuntivo GEANT4/selezione.
- `main` locale: `f568c6b`; `origin/main` verificato tramite connettore GitHub: `3afff75ead89be7e14ad6473ee1d0deff97e7094`. Riesaminare SHA live prima di scrivere sul remoto.
- 11 branch locali; remoto: `main`, `codex/dalitz-completion`, `feat/person2-polarization`, `old-version` al momento dell'audit.
- `feat/figure4-fit`: 11 commit esclusivi rispetto al checkout, più 27 file tracked modificati e 175 file untracked nell'inventario esteso. Classificare questi ultimi: sorgenti e output non vanno trattati allo stesso modo.
- Worktree `.work/standalone-theory` pulito e già antenato del checkout; worktree `.work/figure4-fit` contiene lavoro più recente da integrare.
- Branch storici `feat/person2-polarization`, `fix/block0-gate0`, `state-compton-contract` hanno una pipeline alternativa e grandi artefatti: backup, non reintroduzione.
- 164 test mirati eseguiti durante audit iniziale passati; non equivalgono alla futura verifica completa.
- Git via shell non risolveva `github.com` nel sandbox; connettore GitHub ha confermato branch e SHA. Risolvere accesso Git durante Task 1, non aggirarlo aggiornando `main` con file API non verificati.

## Regole di assegnazione ai sub-agent

L'integratore coordina e committa; worker diversi non modificano contemporaneamente
stessi file. Ogni prompt include specifica, task, interfacce, commit base e frase:
«Non sei solo nella repository; conserva modifiche altrui e adatta la tua patch».
Reviewer fresco, in sola lettura, controlla requisiti e regressioni sul diff di
ciascun task. Una scoperta che cambia contratto condiviso torna all'integratore.

Ordine principale: **0 → 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10 → 11**.
Task 7 e 8 possono essere assegnati in parallelo dopo Task 6, con proprietà
disgiunte; l'integratore applica e verifica qualsiasi modifica a `pyproject.toml`.
Non creare branch permanenti per i worker: fine progetto deve lasciare solo `main`.

## Task 0: Preservare sorgenti, riferimenti Git e baseline

**Owner:** integratore. Nessuna cancellazione Git in questo task.

**Files:** creare artefatti ignorati in `results_test/repository-refactor-20261023/{backup,baseline,inventory}/`; leggere tutti i worktree e gli input esistenti.

**Interfaces:** produce bundle Git verificato, inventario refs/SHA, patch binarie per modifiche tracked, archivio dei sorgenti untracked selezionati con elenco e hash, elenco separato degli output ignorati e baseline numerica.

- [ ] Rileggere `git status`, ref locali/remoti, log di divergenza, stato di ciascun worktree e processi/campagne che lo usano. Acquisire ref remoti aggiornati e SHA live prima di considerarli protetti dal backup; risolvere accesso Git prima di operazioni distruttive. Salvare inventario; aggiornare i numeri sopra se cambiati.
- [ ] Salvare tutti i ref in un bundle Git e verificarlo con `git bundle verify`; clonare il bundle in `results_test/repository-refactor-20261023/backup/restore-check/` e confrontare SHA di ogni branch. Il bundle da solo non salva dirty/untracked.
- [ ] Salvare separatamente patch binarie, cancellazioni tracked e sorgenti untracked di checkout e worktree teoria. Confrontare hash dell'archivio ripristinato. Inventariare anche ogni file ignorato e target dei symlink; nessuna directory worktree può essere rimossa finché contiene byte non protetti. Output grandi possono restare nel worktree conservato/detached oppure essere trasferiti in archivio con verifica byte per byte; non vanno inclusi alla cieca in commit o stash.
- [ ] Congelare baseline del codice corrente e del lavoro teoria in commit circoscritti, preservando cancellazioni già volute. Includere GEANT4 presente e selezione corrente; evitare output ignorati, ambienti e archivi. Aggiornare poi bundle e prova di ripristino per includere anche questi nuovi commit, non soltanto i ref precedenti ai checkpoint.
- [ ] Eseguire suite baseline analisi e teoria nei rispettivi worktree con log/JUnit/temporanei sotto `results_test/`. Registrare fallimenti precedenti al refactor, senza dichiararli corretti. Congelare fixture esistenti e contratti; la baseline numerica sul nuovo campione si acquisisce in Task 2, dopo creazione del campione ma prima di modificare implementazioni o percorsi.

**Proof:** refs ripristinabili; hash sorgenti identici; nessun dato locale cancellato; output baseline individuabile per comando/input/revisione. Esempio suite analisi: `.venv-flux/bin/python -m pytest -q --basetemp=results_test/repository-refactor-20261023/baseline/pytest-tmp --junitxml=results_test/repository-refactor-20261023/baseline/analysis.xml`. Per teoria usare `-c theory/pyproject.toml theory/tests` nel checkout appropriato.

## Task 1: Consolidare baseline e teoria su main

**Owner:** integratore, Git e conflitti esclusivi.

**Files:** merge dei sorgenti teoria e loro test; nessuna importazione della pipeline alternativa storica.

**Interfaces:** produce commit di baseline unico su `main`, contenente lavoro attuale e teoria selezionata, con inventario provenienza dei merge. Consuma backup verificato di Task 0.

- [ ] Riesaminare remoto live e confermare relazione di antenati. Integrare snapshot del checkout corrente su `main`, poi il lavoro committato di `figure4-fit`; risolvere rinomina vecchia estrazione 07→08 conservando codice corrente. Non importare copie vecchie degli stage presenti nel worktree teoria.
- [ ] Verificare i nuovi moduli angolari, CLI basis/fit e test non presenti nel `theory/` iniziale. Conservare i job farm e i loro snapshot immutabili; nessun cambio di source path in job già avviati.
- [ ] Eseguire suite analisi e teoria e verificare che i sorgenti selezionati del worktree siano presenti. Registrare ogni conflitto e risoluzione nel report di integrazione in `results_test/`.
- [ ] Pubblicare `main` con push normale. Verificare SHA effettivo del remoto e backup recuperabile, poi rimuovere branch remoti diversi da `main` e branch locali superflui. I worktree possono essere detached e conservati: cancellare il branch non richiede cancellare i file. Vietato `git worktree remove --force`; rimozione fisica solo dopo salvataggio verificato di tutti i file, anche ignorati, e indipendenza dei processi. Se un processo usa ancora il vecchio path, conservare directory e contenuto finché termina.
- [ ] Confrontare nuovo insieme dei branch locali e live remoti: esattamente `main`. Il default remoto resta `main`. Un rifiuto di push o protezione branch resta errore da risolvere, non autorizza force push.

**Proof:** SHA remoto uguale a `main` locale; sorgenti più recenti integrati; vecchi ref recuperabili dal bundle. La rimozione dei branch non riscrive la storia Git né reintroduce i vecchi artefatti.

## Task 2: Migrare dati, output e teoria nello stage 09

**Owner:** worker-layout; integratore per packaging. Task seriale: tocca percorsi usati da tutti gli altri.

**Files:** spostare `theory/`→`09_theory/`; modificare `scripts/{setup.sh,run_pipeline.py,run_preanalysis.py,plot_campaign.py}`, default CLI negli stage/plots/teoria, `.gitignore`, `pyproject.toml`, test percorsi e script farm; creare `scripts/prepare_test_sample.py` e test del suo contratto.

**Interfaces:** `PipelinePaths` mantiene metodi esistenti ma `selected_dir`, `mc_dir`, `bdt_dir` usano un `artifact_root`: `results/_cache/` in produzione, `<output_root>/artifacts/` in modalità `test_data`. Input test `data_test/sample/`; default output test `results_test/test_data/`. Nome modalità CLI `test_data` resta invariato: cambia percorso, non serve un alias nuovo.

Gli studi opzionali del launcher, anche in produzione, scrivono sotto `results_test/diagnostics/<campaign>/`; consumano gli input di produzione per path esplicito. Default standalone di strumenti diagnostici, script farm di studio e calibrazione di prova usano `results_test/`. Campagne di produzione e cache condivisa conservano lock compatibili fra loro; nessun lock test può autorizzare sostituzione di una cache di produzione.

- [ ] Aggiungere test che fissano input/output: due ROOT UV/VIS più manifest in `data_test/sample/`; nessun output scritto nel campione. Asserire radici distinte, rifiuto di output test sotto `data/` o `results/`, rifiuto di alias/symlink pericolosi, lock distinti, rollback su errore e sopravvivenza degli input.
- [ ] Aggiungere test per `--flux-study` in modalità produzione: lo studio legge la calibrazione della campagna ma ogni proprio output/report va in `results_test/diagnostics/<campaign>/`, senza alterare input o campagna. Verificare anche i default degli script farm di studio.
- [ ] Preparare, prima di modificare il codice, un solo campione riproducibile di massimo 100.000 eventi per profilo dagli h80 locali. Ordinare gruppi reali run/stato/strip stabilmente, includere gli stati accoppiati necessari e riservare copertura minima della calibrazione: almeno cinque strip distinte comprese 1 e 128 per gruppo run/polarizzazione utilizzato. Completare la quota con selezione deterministica su identità sorgente/entry; conservare tutti i branch. Se copertura richiesta non esiste, registrare gruppo non disponibile senza allentare il gate né inventare eventi.
- [ ] Manifest del campione: `diagnostic_only=true`, SHA sorgenti/input/manifest flusso, identità entry, conteggi originali e campionati separati, regola di inclusione e `exposure_policy="original_source_exposure"`. Usare esposizioni sorgente originali identificate soltanto per il sottoinsieme reale di run/stati dichiarato: non scalarle dalla frazione di eventi. Questi risultati provano regressione software, non una misura fisica normalizzata. Nuovo preflight di produzione rifiuta campioni marcati diagnostici, anche quando passati con override del path.
- [ ] Congelare hash di campione, riferimenti e dipendenze di calibrazione/esposizione. Eseguire il codice originale con CLI di stage e path espliciti in `results_test/repository-refactor-20261023/sample-baseline/`, prima di rename o refactor. Il vecchio launcher non accetta `results_test/`: usare le CLI esistenti, senza aggirare la sua protezione o scrivere prove in produzione. Salvare struttura ROOT, identità, selezioni, cutflow, punti/covarianze e semi; Task 11 usa esattamente questa coorte.
- [ ] Aggiornare setup per collegamenti espliciti ai dati farm, mantenendo rifiuto di sovrascrittura di path/link esistenti. Spostare output prodotti in `data/` e `test_data/` solo dopo inventario; nessun file ROOT originale viene eliminato perché troppo grande. Conservare input storici necessari in area dati inventariata; rimuovere `test_data/` finale solo dopo evacuazione verificata.
- [ ] Classificare campagne esistenti: produzione resta `results/`; studi, prove, report, build e QA vanno in `results_test/`. Verificare symlink e input richiamati dai manifest. Hash/manifest storici restano immutati; registrare relocation e preservare eventuali sorgenti ancora necessarie prima di rimuovere vecchi percorsi.
- [ ] Inventariare separatamente artefatti esclusivi del fitter rimosso (ROOT fitted, confronti raw/fitted, risoluzione, grafici e report). Ritirarli dalle campagne attive verso archivio verificato sotto `results_test/`; conservare interi i bundle storici indivisibili e rigenerare prodotti raw correnti dove necessari. Nessuna cancellazione per glob generico `fit*`: fit azimutali, calibrazione e teoria restano.
- [ ] Spostare teoria e aggiornare installazione indipendente, percorsi script farm, riferimenti e test. `graal-theory` mantiene le sue opzioni scientifiche; nessuna esecuzione automatica dal launcher. Output nuovi teoria/studi diagnostici usano le due radici risultati, non `09_theory/outputs/`.
- [ ] Centralizzare dipendenze analisi in `pyproject.toml`, distinguendo dipendenze runtime e test. Aggiornare setup; rimuovere requisito generale su `04_bdt_training/requirements.txt` dopo verifica. La teoria conserva proprio `pyproject.toml` e risorse package.

**Proof:** `tests/test_setup_script.py`, `test_run_pipeline.py`, `test_repository_layout.py`, test nuovo campione e `09_theory/tests/test_packaged_references.py`; CLI `graal-theory --help` e installazione indipendente riuscite. Sorgenti originali e file migrati verificati tramite hash; nessuna cancellazione di dati implicita nel rename.

## Task 3: Eliminare fitter cinematico e contratti dipendenti

**Owner:** worker-reconstruction, con proprietà temporanea dei consumer coinvolti. Nessun altro worker modifica ricostruzione, reader, estrazione o plotting durante questo task.

**Delete:** `05_reconstruction/core/kinematic_fit.py`, `05_reconstruction/validate_kinematic_fit.py`, relativo test; `plots/{kinfit_resolution.py,mass_comparison.py}` e relativi test esclusivi.

**Modify:** `05_reconstruction/core/{event_logic.py,reco_physics.py,__init__.py}`, `runtime/{reco_core.py,cli_options.py,provenance.py}`, quattro CLI di ricostruzione; reader e metadati in `plots/core/`; `plots/dalitz.py`; `scripts/{run_pipeline.py,plot_campaign.py}`; `08_observable_extraction/{beam_asymmetry.py,compare_gate.py}`, `core/{systematics.py,gate_comparison.py}`, `io/reconstructed_events.py`, `plotting/diagnostics.py`, consumer stage 07 e test corrispondenti.

**Interfaces:** `RecoConfig` conserva solo selezioni raw; `validate_reconstruction_selection(source, tree) -> dict` accetta esclusivamente provenienza `schema=2`, `selection_algorithm="pairing_missing_mass"`. Reader certificati usano questa funzione e non espongono `vector_mode="fit"`. `SAMPLES` conserva solo `raw` e `raw_bdt`.

- [ ] Scrivere regressioni per schema nuovo, rifiuto schema vecchio/non certificato, raw vectors invariati, missing-mass pass/fail, cutflow/identità seriale-parallelo e assenza branch fitted. Conservare oracle numerici di pairing e test gate BDT.
- [ ] Rimuovere tipi/funzioni del fitter, `do_fit`, `fit_cl`, covariance/reaction/fit_fn e ramo di selezione FIT. Eliminare opzioni `--with-kinematic-fit`, `--no-fit`, `--fit-cl` e relativo plumbing, compresi argomenti del launcher.
- [ ] Eliminare campione `raw_bdt_fit`, vettori fitted, comparazioni raw/fitted, sistematico `raw_vs_kinematic_fit` e reader a doppia modalità. Nuovi ROOT reco non scrivono `eta_fit`, `pi0_fit`, `proton_fit`, fotoni fitted, `fit_chi2/fit_ndf/fit_converged` del fitter; i campi omonimi dell'inferenza azimutale restano.
- [ ] Aggiornare prove ROOT/plot/estrazione e fixture con contratto positivo. Nessun workaround che accetta vecchi output perché contengono vettori raw. Conservare truth MC, tagli attuali, metadati raw-track e modifiche della preselezione protonica.
- [ ] Eseguire suite stage 05, stage 08, plots, closure stage 07 e test pipeline/metadata. Confrontare baseline senza fitter di Task 0 sullo stesso campione; rimuovere solo test del comportamento eliminato.

**Proof:** `.venv-flux/bin/python -m pytest -q 05_reconstruction/tests 08_observable_extraction/tests plots/tests 07_flux_studies/tests/test_flux_observable_closure.py tests/test_plot_campaign.py tests/test_run_pipeline.py tests/test_raw_track_metadata.py tests/test_energy_contract.py`. Ricerca dei simboli rimossi senza match nei sorgenti attivi; fixture di rifiuto possono contenere dati storici esplicitamente negativi. Non usare parola generica `fit` come criterio di cancellazione.

## Task 4: Rendere pubblico riuso di estrazione e plotting

**Owner:** worker-public-api. Consuma contratto raw-only di Task 3.

**Create:** `08_observable_extraction/{extraction.py,samples.py}`, `plots/mass_histograms.py`. **Modify:** CLI estrazione, `compare_gate.py`, `compare_mass_selection.py`, `compare_track_selection.py`, closure stage 07 e `plots/dalitz.py`; test pertinenti.

**Interfaces:** spostare `ExtractionBundle` senza cambiare quattro campi tuple (`points`, `ratio_objects`, `binning_candidates`, `candidate_ratio_objects`). Esporre:

```python
def extract_sample(*, sample_name: str, events: EventArrays,
                   exposures: Mapping[tuple[int, int], FluxExposure],
                   estimator: str, retain_ratio_objects: bool,
                   energy_edges: np.ndarray, phi_edges: np.ndarray = PHI_EDGES_RAD,
                   best_binning: bool = False,
                   selected_phi_bins: dict[tuple[str, int, int], int] | None = None,
                   workers: int = 1) -> ExtractionBundle: ...

def mass2d_hist(name: str, title: str,
                eta: np.ndarray, pi0: np.ndarray) -> ROOT.TH2F: ...

def draw_truth_cross() -> list: ...
```

- [ ] Fissare test comparativi su punti ordinati, mappe dei bin phi, candidati best-binning, ratio objects e bin mancanti. Per istogrammi: assi/bin/entry invariati e riferimenti `TLine` vivi dopo rendering.
- [ ] Spostare `_extract_sample` e soli adapter necessari in `extraction.py`, rinominandolo `extract_sample`; `SAMPLES` in `samples.py`. Nessuna `argparse.Namespace` nell'API pubblica.
- [ ] Spostare helper istogramma/croce dal modulo CLI Dalitz in `plots/mass_histograms.py`; entrambi i consumer importano funzioni pubbliche. Mantenere ROOT ownership degli oggetti disegnati.
- [ ] Aggiornare tutti i consumer e test; ricerca import privati deve restituire zero per dipendenze da `beam_asymmetry` e `plots.dalitz` nei consumer indicati.

**Proof:** suite `test_best_binning.py`, `test_gate_comparison.py`, `test_mass_comparison.py`, `test_track_selection.py`, `test_flux_observable_closure.py`, `plots/tests/test_dalitz.py` e test dei nuovi moduli. Stessi risultati numerici della baseline; unico motore di estrazione usato da CLI e studi.

## Task 5: Portare orchestrazione nel package installabile

**Owner:** worker-workflow; integratore per `pyproject.toml` e test condivisi.

**Create:** `graal_workflow/{__init__.py,__main__.py,models.py,paths.py,planning.py,execution.py,artifact_manifest.py,resources.py,logging.py,cli.py}`. **Modify:** `scripts/{run_pipeline.py,run_preanalysis.py,plot_campaign.py}`, test e packaging. **Remove:** helper `scripts/{artifact_manifest.py,parallel_pipeline.py,pipeline_logging.py}` dopo aggiornamento consumer.

**Interfaces:** conservare inizialmente firme di `mode_config`, `build_paths`, `preflight`, `build_pipeline_plan`, `execute_cached_plan`, `configure_resources`; tipi esistenti in `models.py`. `main(argv: Sequence[str] | None = None) -> int` in `cli.py`; `python -m graal_workflow` e script launcher sottile chiamano stessa funzione.

Radice esplicita: `resolve_repo_root(explicit: Path | None) -> Path` in `paths.py` valida `pyproject.toml`, config e risorse native/stage necessarie. `--repo-root PATH` la fornisce da installazione wheel; fallback solo a checkout sorgente con sentinelle verificate, mai a `site-packages` o cwd casuale. Il wrapper conosce la propria radice e la passa. Stage/manifest ricevono path espliciti; inventari provenienza includono sorgenti effettivamente eseguiti (moduli installati via `__file__`, driver/macros/config dal checkout dichiarato), senza glob vuoti accettati silenziosamente.

- [ ] Aggiungere test che importano launcher installato da directory esterna e confrontano piani/comandi normalizzati con baseline di Task 2–4. Coprire entrambe modalità, UV/VIS, forza cache, quoting ed errori. Con wheel, `--repo-root` esplicito deve risolvere risorse; radice mancante/incompleta deve fallire contestualmente. Una piccola esecuzione reale deve produrre inventari di provenienza non vuoti, inclusi sorgenti installati e risorse native usate.
- [ ] Spostare responsabilità senza riscrivere algoritmi: modelli, percorsi/preflight/lock, pianificazione, esecuzione/cache, risorse, logging e CLI. Aggiornare tutti gli import da `scripts.*` ai moduli installati.
- [ ] Aggiornare fingerprint: tutte le dipendenze rilevanti del nuovo package devono invalidare cache quando cambiano; modifiche puramente al layout non autorizzano riuso non certificato. Conservare staging/rollback e scadenza attuale di dieci giorni.
- [ ] Correggere `reconstruction.runtime.reco_core._snapshot_inputs` affinché registri moduli effettivi anche da wheel e rifiuti inventario sorgenti vuoto; non inferire directory numerate dalla posizione in `site-packages`.
- [ ] Eseguire test packaging, launcher, logging, artifact manifest, parallelo e setup. Script launcher contiene soltanto adattamento entrypoint; la logica non viene duplicata per compatibilità.

**Proof:** `.venv-flux/bin/python -m pytest -q tests/test_packaging.py tests/test_run_pipeline.py tests/test_artifact_manifest.py tests/test_parallel_pipeline.py tests/test_pipeline_logging.py tests/test_parallel_preanalysis.py tests/test_setup_script.py`; help sia modulo sia script, anche da cwd diverso.

## Task 6: Rendere espliciti gruppi artefatti e risorse

**Owner:** worker-workflow, in continuità con Task 5.

**Files:** `graal_workflow/{models.py,planning.py,execution.py,resources.py}` e test pipeline/cache/parallelismo.

**Interfaces:** `Stage` conserva `name`, `argv` e aggiunge `kind`, `profile`, `channel`, `seed_key` espliciti. `ArtifactGroup` contiene `kind` (`selected|mc|bdt`), `profile`, `stages: tuple[Stage, ...]`, `destination: Path`, `channel: str | None`, `energy_range: tuple[float,float] | None`. `PipelinePlan = tuple[Stage | ArtifactGroup, ...]`; stessi nomi pubblici di builder/executor, ora consumano questo piano.

- [ ] Scrivere test: rinominare `Stage.name` non cambia gruppi cache/seed; cambiare `seed_key` cambia seme; BDT contiene esattamente beam-spectrum/features/train nello stesso gruppo; ogni canale MC ha gruppo proprio; budget non viene superato.
- [ ] Costruire gruppi nel planner al momento della creazione, invece di ricostruirli leggendo nomi e posizioni nel runner. Conservare ordine comune→UV→VIS→plot, inclusa diagnostica opzionale.
- [ ] Risorse e cache usano `kind/profile/channel`; `seed_key` mantiene esattamente vecchia stringa identificativa usata da SHA256 `seed:stage.name`. Tutte le trasformazioni usano `dataclasses.replace`, preservando metadati.
- [ ] Eliminare `split(':')`, match `':generate:'` e slicing implicito dei tre comandi BDT come meccanismi di controllo. Etichette testuali restano solo per log. Non introdurre scheduler/DAG.
- [ ] Verificare comandi, semi, cache hit/miss, force, invalidazione upstream, manifest e rollback con le stesse prove di Task 5.

**Proof:** test di rename etichetta verdi; seed derivati uguali a baseline per stessa policy; gruppi incompleti rifiutati esplicitamente. Ogni task MC pubblica soltanto il proprio output.

## Task 7: Separare calibrazione, IO nativo e CLI

**Owner:** worker-calibration. Nessun altro worker modifica `06_calibration/`; integratore applica package-data.

**Create:** `06_calibration/{strip_energy_root.py,calibrated_flux_root.py,flux_build.py,native/strip_energy_rdf.hxx}`. **Modify:** `strip_energy_flux.py`, `build_strip_energy_flux.py`, test e risorse package in `pyproject.toml`.

**Interfaces:** conservare firme di `read_h80_lookup`, `read_calibration_cells`, `read_flux_histograms`, `write_calibrated_flux_root`; spostare `CalibrationCell/CalibrationEnergyBin` nel proprietario dominio. `flux_build.run(args) -> int` resta coordinatore interno; CLI fa parsing/gestione errore. Conservare i due tipi distinti di EnergyBinning esistenti.

- [ ] Fissare test numerici e di pubblicazione: record lookup/celle uguali a 1 e più thread; stessi coefficienti/bordi, istogrammi, QA; input mutato durante scansione rifiutato; output precedente salvo su errore.
- [ ] Spostare `_RDF_HELPER_CODE` invariato nell'header package. Caricarlo con risorse installate e dichiararlo una sola volta per processo; includerlo in wheel, sdist e fingerprint di cache.
- [ ] Separare lettura ROOT, calibrazione/scrittura ROOT e coordinamento. Conservare fit polinomiale, test di monotonicità, 129 bordi fitted, pesi e gestione bin negativi.
- [ ] Aggiornare test che caricavano il file CLI con `importlib` per riferirsi al modulo proprietario; conservare prove CLI sui soli contratti esterni.

**Proof:** `.venv-flux/bin/python -m pytest -q 06_calibration/tests`; installazione wheel in area isolata sotto `results_test/`, caricamento della risorsa e piccola operazione nativa reale su fixture h80 da cwd esterno, dichiarazione ROOT ripetuta sicura e provenienza non vuota. Nessuna necessità di ricostruire un'intera calibrazione farm per provare spostamento meccanico.

## Task 8: Semplificare coordinamento dell'estrazione

**Owner:** worker-observables. Consuma `extraction.py` di Task 4; non modifica stage 06 o workflow generale.

**Create:** `08_observable_extraction/{extraction_background.py,extraction_systematics.py,workflow.py,period_workflow.py}`. **Modify:** `beam_asymmetry.py` e test delle responsabilità spostate.

**Interfaces:** engine pubblico resta `extract_sample` di Task 4. `workflow.run_single(args, ...) -> int` coordina un'estrazione; `period_workflow.run_periods(args) -> int` possiede partizione/chiusura. Funzioni numeriche esistenti restano in `core/`, reader/writer in `io/`. `beam_asymmetry.main(argv) -> int` fa parsing e dispatch. Namespace resta solo nell'applicazione interna.

- [ ] Scrivere confronto su stessi punti ordinati, errori, inventario dei sistematici, covarianze/bootstrap appaiati, cutflow e chiusura per periodo. Bin non stimabili restano mancanti, non diventano zero.
- [ ] Spostare coordinamento dei fondi in `extraction_background.py`, composizione/bootstrap dei sistematici in `extraction_systematics.py`, pubblicazione singola in `workflow.py` e workflow periodi in `period_workflow.py`.
- [ ] Eliminare dipendenze circolari tra i nuovi moduli; costanti/modelli condivisi appartengono a `samples.py`, `extraction.py` o `core` esistente. Non duplicare letture ROOT o calcoli per aggirare gli import.
- [ ] Ridurre CLI a parsing/dispatch e aggiornare test verso proprietari reali. Conservare prove end-to-end CLI e closure stage 07.

**Proof:** `.venv-flux/bin/python -m pytest -q 08_observable_extraction/tests 07_flux_studies/tests/test_flux_observable_closure.py tests/test_energy_contract.py tests/test_pipeline_run_quality.py`; confronto baseline numerica, stesso universo degli eventi e delle esposizioni.

## Task 9: Ricostruire wiki e ordinare documenti

**Owner:** worker-docs; integratore per `AGENTS.md` e test globali. Consuma comportamento finale Task 2–8.

**Delete/replace:** vecchie pagine wiki, `docs/superpowers/`, `docs/plans/2026-10-12-graal/`, vecchi report/research/runbook normativi, `09_theory/docs/`, README annidati, `.superpowers/` e placeholder teoria di stage 08.

**Preserve/move:** Fortran in `docs/reference/fortran/`, paper in `docs/papers/`, report generati in `results_test/`; mantenere riferimenti macchina nei rispettivi package quando necessari a runtime/provenienza. Unificare CSV Ajaka identici sulla copia stage 08 aggiornando consumatori.

**Interfaces:** wiki sorgente corrente in `wiki/`, pubblicabile con `scripts/sync-wiki.sh`. Unico README radice contiene introduzione, setup, comandi essenziali, layout e collegamento wiki. `AGENTS.md` contiene soltanto istruzioni correnti di manutenzione e sicurezza dei dati.

- [ ] Inventariare documenti e classificare completato/obsoleto/aperto/fonte scientifica. Estrarre questioni aperte elencate nella specifica in `wiki/status.md` con evidenza, data e limite; nessuna implementazione scientifica aggiuntiva nel task.
- [ ] Riscrivere wiki con pagine per avvio, architettura/workflow, dati/contratti, stage 01–09, plotting, manutenzione/test e stato scientifico; accorpare dettagli quando migliorano consultazione. Nessun numero fisso di pagine imposto dai test.
- [ ] Portare spiegazione/citazione finite-bin nella wiki; aggiornare riferimento in `08_observable_extraction/core/binning.py`. Spostare prove persistenti necessarie in `docs/reference/` o report in `results_test/` con hash e link aggiornati, poi eliminare vecchie direttive.
- [ ] Eliminare README annidati del progetto e `.superpowers/` dopo aver verificato che non contengano l'unica copia di lavoro utile. Ambiente, dipendenze e backup non rientrano nel conteggio README di progetto.
- [ ] Sostituire test wiki che impongono 37 nomi/titoli con controlli di link, navigazione unica, percorsi/comandi supportati e assenza riferimenti attivi a funzionalità rimosse. Aggiornare test pipeline che leggevano vecchi runbook.
- [ ] Verificare script sync verso un remoto Git locale di prova. Pubblicare poi le pagine effettive su GitHub Wiki e verificare insieme dei file: nessun vecchio documento rimane pubblicato come corrente.

**Proof:** `.venv-flux/bin/python -m pytest -q tests/test_wiki.py tests/test_wiki_sync.py tests/test_run_pipeline.py`; un solo README nei sorgenti di progetto, tutti i link wiki risolvono e CLI documentate funzionano. Confrontare inventario delle attività aperte con specifica prima della cancellazione definitiva.

## Task 10: Ricostruire Graphify dal corpus corrente

**Owner:** worker-graph, dopo documentazione. Nessuna modifica scientifica.

**Files:** creare `scripts/rebuild_graph.sh` e manifest corpus in `docs/reference/graph-corpus.json`; sostituire soltanto output attivi `graphify-out/`. Diagnostica e backup precedenti in `results_test/repository-refactor-20261023/graph/`.

**Interfaces:** corpus esplicito di source/test/config, README/AGENTS, nuova wiki e riferimenti testuali selezionati. Tutti i `source_file` del grafo sono relativi alla radice corrente e risolvono a file presenti nel manifest.

- [ ] Leggere skill Graphify installata e seguirne build da zero, con nuova estrazione AST/semantica. Non usare `--update`, memorie vecchie o soli cluster. Lo script registra versione effettiva, lista/hash del corpus, tempo e comandi riproducibili.
- [ ] Escludere `.git`, `.work`, `.superpowers`, ambienti, dipendenze, build, `data`, `data_test`, `results`, `results_test`, `09_theory/outputs`, `docs/plans` e qualsiasi `graphify-out`/memoria/cache/reflection. Conservare sorgenti di `plots/`; non scansionare immagini generate. Paper completi non entrano automaticamente nel corpus tecnico. Anche questo piano di migrazione resta fuori dal grafo operativo: descrive intenzionalmente simboli e percorsi rimossi.
- [ ] Ispezionare detection manifest prima di estrarre. Se corpus supera limiti della skill, suddividerlo per stage/tema e unirlo con stesso path base; non ridurre silenziosamente copertura. Sub-agent semantici ricevono file disgiunti e specifica ufficiale di estrazione.
- [ ] Validare endpoint degli archi e, per ogni `source_file` non vuoto, esistenza del file e appartenenza al corpus; nodi esterni/builtin possono essere privi di file. Verificare assenza prefissi esclusi e vecchi percorsi `theory/`/documenti rimossi, conteggi coerenti fra JSON/report e percorso stage 09. Rigenerare tutti i derivati attivi insieme; nessuna copia datata o vecchio health report mischiato al nuovo grafo.
- [ ] Smoke-query: ordine workflow, selezione corrente, engine pubblico, dipendenze stage 09, limite geometria/risposta e recovery non ammesso in produzione. Le risposte devono citare solo fonti correnti, non memorie di query.
- [ ] Pubblicare output attivi soltanto dopo verifiche; per HTML oltre 5.000 nodi comunicare costo di visualizzazione previsto prima del rendering.

**Proof:** tutte le fonti del grafo appartengono al corpus e sono presenti; nessun nodo generato dal grafo stesso; conteggi/manifest/report allineati. Query sopra restituiscono contratti attuali. `graphify-out/` resta artefatto rigenerabile, non nuova fonte normativa.

## Task 11: Verifica completa e chiusura su main/origin

**Owner:** integratore + reviewer finale fresco. Reviewer legge specifica, piano e diff cumulativo; non si limita ai resoconti dei worker.

**Files:** soltanto correzioni motivate, stato checkbox di questo piano e report finale in `results_test/repository-refactor-20261023/verification/`.

- [ ] Eseguire suite analisi completa, suite `09_theory` completa e test geometrici Python; aggiungere verifiche native GEANT4 pertinenti alle sole modifiche fatte. Output, JUnit, cache e basetemp sotto `results_test/`. Un test non eseguibile è limite registrato, non successo o skip inventato.
- [ ] Eseguire un flusso ridotto UV+VIS dal dataset fissato, con selezione, generazione MC ridotta, BDT, ricostruzione, calibrazione/estrazione e grafici. Fissare parametri/seed nel manifest della prova; verificare ROOT reali e provenienza. Riavviare dove previsto per provare cache e iniettare un errore per verificare preservazione dell'output valido.
- [ ] Confrontare con baseline: identità eventi/feature, tagli, esposizioni, bin stimabili, risultati e covarianze; tolleranze esistenti e differenze dovute esclusivamente al nuovo schema/path documentate. Confermare che campione e input non sono mutati.
- [ ] Provare installazione wheel/risorse, comandi documentati e stage 09 esplicito senza lanciare calcoli scientifici lunghi. Da cwd esterno, con wheel e checkout dichiarato tramite `--repo-root`, eseguire piccola operazione ROOT/nativa e verificare inventari sorgente non vuoti. Confermare che estrazione normale non avvia teoria.
- [ ] Eseguire `git diff --check`, controlli strutturali, assenza fitter nei sorgenti attivi, un solo README, cartelle docs consentite, assenza output test in produzione e grafo pulito. Eventuali termini storici nelle fixture negative e nel piano di rimozione non rappresentano funzionalità rimaste.
- [ ] Risolvere rilievi del reviewer; ripetere solo verifiche interessate dalle correzioni. Aggiornare wiki/grafo se cambia comportamento o struttura dopo Task 10.
- [ ] Push normale del risultato finale su `origin/main`; verificare SHA remoto, stato locale pulito e solo `main` fra branch del repository. Verificare anche pubblicazione wiki. Conservare backup e report sotto `results_test/`.

**Proof commands principali:**

```bash
.venv-flux/bin/python -m pytest -q --basetemp=results_test/repository-refactor-20261023/verification/analysis-tmp --junitxml=results_test/repository-refactor-20261023/verification/analysis.xml
.venv-flux/bin/python -m pytest -q -c 09_theory/pyproject.toml 09_theory/tests --basetemp=results_test/repository-refactor-20261023/verification/theory-tmp --junitxml=results_test/repository-refactor-20261023/verification/theory.xml
.venv-flux/bin/python -m pytest -q 03_mc_simulation/geant4/tests --basetemp=results_test/repository-refactor-20261023/verification/geometry-tmp
.venv-flux/bin/python -m graal_workflow --help
.venv-flux/bin/python -m observable_extraction.beam_asymmetry --help
.venv-flux/bin/python -m graal_theory.cli --help
git diff --check
```

## Confini di completamento

Il refactor è completo quando criteri della specifica e prove sopra sono soddisfatti.
Non richiede una nuova campagna scientifica di produzione, completamento della
simulazione GEANT4, accettazione dei flussi ricostruiti o certificazione dell'intero
modello teorico. Questi restano esplicitamente aperti nella wiki, con fonti e stato.
Il piano documenta la rimozione storica richiesta; i vecchi piani operativi non
rimangono nel checkout come direttive concorrenti.

## Task 6a: Config comuni, calibrazione riutilizzabile e build root (addendum utente)

**Owner:** worker `common_configuration`; Git, review indipendente e commit
all'integratore. Task inserito dopo6 e prima della documentazione/verifica finale.
**Spec:** addendum Task6a nella specifica corrente; brief esecutivo in
`results_test/repository-refactor-20261023/execution/task-6a-brief.md`.

**Files:** `config/common_inputs.json`, bundle conteggi locale esplicito,
`06_calibration/{common_inputs,calibration_cache}.py`, produttori Stage06/07,
consumer `graal_workflow`, test pertinenti, default viewer GEANT4.
**Interfaces:** `load_common_inputs(checkout, path=None, cache=None, verify=True)`;
`run_cached_calibration(args, builder, driver=...)`; existing
`load_cached_counts(path, expected_paths=None, checkout=None, require_content=False)`.
Gruppi espliciti e `Stage.seed_key` restano invariati.

- [x] Tracciare produttori/validator e congelare SHA dei cinque config attivi.
- [x] Implementare riferimenti comuni portabili, validazione e protezione catalogo.
- [x] Implementare cache content-bound ROOT+QA, lock/rollback, ricevuta per campagna,
  separazione diagnostica e controlli sorgenti/input durante pubblicazione.
- [x] Esporre conteggi inclusivi esistenti senza rescan eventi; coorte e hash obbligatori
  per bundle comuni, nessuna adozione scientifica implicita.
- [x] Redirect default viewer sotto `results_test/build`.
- [x] Completare prove native ROOT, riuso/invalidation/relocation/tampering/rollback,
  policy/config immutati e wheel da cwd esterno. Log nella campagna Task6a.
- [ ] Congelare sorgenti, review indipendente e commit circoscritto dell'integratore.
