# Geant4 e BDT — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: usare `superpowers:executing-plans` per eseguire questo piano task per task. Le checkbox tracciano deliverable verificati, non intenzioni. Non avviare implementazione o campagne durante il solo brainstorming.

**Goal:** ottenere efficienze/risposta e fondo residuo validati per la stima delle sezioni d'urto; usare benchmark PID cariche per validare il detector, confrontare il training BDT e studiare separatamente la discriminazione γ/neutrone.

**Architecture:** GENBOD con pesi conservati e distribuzioni fisiche da tabelle/modelli; identità truth condivisa fra risposta veloce e Geant4. Riusare clustering `prean`, validare lettura/PID/trigger e propagare pesi/denominatori fino a efficienze, migrazioni e fondo. Training e inferenza mantengono i loro proprietari.

**Tech Stack:** ROOT/PyROOT, Geant4 ≥11.4, C++17, CMake ≥3.16, Python ≥3.10, NumPy e stack XGBoost già presenti. Spack esterno su macOS.

**Spec:** [decisione e architettura](2026-10-26-geant4-bdt-design.md), aggiornata il 27 ottobre; [requisiti e benchmark del responsabile](../../wiki/geant4-validation.md). Sorgenti originali ora disponibili in `docs/reference/fortran/prog`; le dipendenze dati/librerie esterne vanno inventariate. Nessuna promozione scientifica implicita.

## Global Constraints

- Conservare raw, campioni storici, snapshot/manifest, bundle BDT, seed policy, tagli di periodo, 26 feature, weighting/flux/exposure, binnings, ratio/likelihood e divisori di bin finito.
- Nuova ricostruzione: `schema=2`, `selection_algorithm="pairing_missing_mass"`. Nessuna riscrittura retroattiva di metadata storici.
- Verifiche in `results_test/<campaign>/`; impostare `PYTHONDONTWRITEBYTECODE=1`, `TMPDIR`/`MPLCONFIGDIR` assoluti, pytest `--basetemp` e `cache_dir` nella campagna. Rimuovere build/cache/fixture al termine, mantenendo solo prove motivate.
- Dati sorgente/link in `data/` o `data_test/`; configurazioni curate in `config/`; prodotti approvati in `results/` o `results/_cache/`. Nessun lancio lungo o modifica alla farm come effetto collaterale.
- Un solo README alla root. Questo piano attivo vive in `docs/plans/`; aggiornare `wiki/status.md` a ogni gate, poi ritirare il piano completato salvando conclusioni uniche nella wiki.
- Stage 09 resta inattivo. Nessuna nuova teoria implicita, nessun tuning sul risultato finale dell'asimmetria.
- Git integrazione/pubblicazione appartengono all'integratore. Ogni task produce un diff revisionabile; non prescrive commit/push automatici.

## Review Focus

1. Repliche veloce/G4 dello stesso truth attraversano split diversi: test di origine condivisa in T1/T7.
2. Campioni già selezionati cancellano inefficienze o usano come denominatore l'intero ROOT di un export parziale: ledger e test in T1/T6.
3. Detector configurato per periodo sbagliato, materiale o calibrazione mancanti: rifiuto esplicito in T2/T5, senza default “plausibili”.
4. Clustering/PID leggono truth oppure viene applicato due volte smearing/loss: confine osservato e test in T5/T6.
5. Campione scarso, bin senza supporto o test riusato dopo tuning vengono dichiarati equivalenti: esito `inconclusive`, gestione test e gate in T7/T8.

## Sequenza e disponibilità

| Task | Dipende da | Deliverable | Eseguibile con input attuali |
| --- | --- | --- | --- |
| T0 | — | Inventario e baseline congelata | Sì, senza campagna lunga |
| T1 | T0 | Contratti di simulazione/identità/contabilità | Sì, su fixture |
| T2 | T0, T1 | Detector Fortran confermato; LH₂/LD₂ × 6/12 cm nominali | Audit lunghezze attive/densità e mappa run |
| T3 | T1, T2 | Beam, vertice e truth riproducibili | Software sì; profili fisici dopo G0 |
| T3a | T0, T1, T3 | GENBOD pesato, tabelle totali/differenziali e modelli | Sorgenti disponibili; verificare dati esterni e convenzioni |
| T4 | T2, T3 | Hit necessari a fotoni/protone/trigger | Dopo mappa detector verificata |
| T5 | T4 | Risposta calibrata e ricostruzione | Richiede calibrazioni e controlli |
| T5a | T5 | Benchmark obbligatori dE/dx–E BGO e dE/dx–TOF π/p | Richiede dati cariche indipendenti |
| T5b | T5 | Studio esplorativo γ/n | Non blocca gli altri deliverable |
| T6 | T1, T3a, T5a | Adapter per selezione, feature e pesi | Su fixture prima, su detector dopo G1 |
| T7 | T6 | Confronto BDT incrociato e dati | Dopo G0–G2 |
| T8 | T3a, T6; T7 per eventuale BDT nuovo | Efficienze/risposta, fondo e closure yield/sezioni d'urto | Con input fisici, luminosità e controlli validi |
| T9 | Pilot T4–T6; gate fisici/operativi per promozione, G3 se cambia BDT | Calcolo riproducibile e rilascio reversibile | Benchmark breve prima; produzione dopo gate |

T0–T1 sono il primo blocco concreto. Le fasi successive non assegnano valori inventati agli input assenti: l'inventario registra la dipendenza e consente lavoro indipendente sui contratti. I moduli indicati come nuovi sono proposte di responsabilità; confermare la granularità al task, evitando classi/interfacce senza necessità.

Il 27 ottobre il responsabile conferma che datafile esterni LAGGEN e database/calibrazioni PREAN non sono attualmente disponibili e saranno forniti successivamente. Il [registro di recupero](../../wiki/geant4-validation.md#input-da-ricevere-e-procedura-di-ripresa) definisce cosa verificare alla consegna. Intanto eseguire mappatura/audit di sorgente e contratti su fixture; non sostituire le tabelle mancanti con valori spacciati per misurati.

## T0 — Inventario del detector, controlli e baseline

**Files:** aggiornare `wiki/03-monte-carlo-simulation.md`, `wiki/04-bdt-training.md`, `wiki/status.md` e `wiki/geant4-validation.md`; usare `wiki/legacy-fortran-map.md` e `wiki/geant4-cross-section-sources.md`. Leggere `config/support/run_manifest.csv`, `00_common/physics/beam_profiles.py`, `config/support/common_inputs.json`, artefatti stage 04 e originali `docs/reference/fortran/prog/{laggen,laggen_vale,lagdig,prean,include}` senza modificarli.

**Interface:** inventario con `item, period, source_path, sha256, physical_units, validity, owner, status`; status `available|missing|unverified`. Baseline report: sorgenti/generatori, beam profile, feature contract, loss/smearing, pesi, modello, soglia, split e versioni. Non creare sostituti di bundle assenti.

- [ ] Registrare conferma scientifica del detector Fortran e quattro profili LH₂/LD₂ × cella nominale 6/12 cm; distinguere lunghezza attiva nel sorgente, densità nominale scelta con fonte e mappa UV/VIS/run. Inventariare calibrazioni, canali morti, trigger, PID e beam spot/vertice.
- [ ] Definire controlli dati, purezza/fondo e separazione per run tra tuning e validazione. Registrare esplicitamente se serve un nuovo cohort e il relativo intervento separato.
- [ ] Catalogare i processi inclusi e quelli plausibilmente omessi, con reazione/stato stabile, BR e possibili doppi conteggi. Prima di dichiarare fondo totale, assegnare a cariche malidentificate, neutroni, nuclei/finestre e accidentali pertinenti una simulazione, esclusione motivata o limite dai controlli. I nove canali correnti non sono automaticamente completi.
- [ ] Congelare baseline disponibile con hash; registrare assenze senza avviare rigenerazione massiva. Correggere nella documentazione la confusione tra fotoni generati e rami smeared letti da `mc_samples.py`.
- [ ] Fissare precisione richiesta a efficienze/fondo e sezioni d'urto per bin, più tolleranze dei benchmark cariche. La precedente proposta `0.2 σ_stat` per asimmetria resta non approvata e complementare.
- [ ] Verificare links/documenti con `tests/test_wiki.py` e `tests/test_wiki_sync.py`; revisionare inventario. Output: stato G0 e elenco di input mancanti, ciascuno associato al task bloccato.

## T1 — Identità, ledger e manifest della simulazione

**Files:** creare `03_mc_simulation/geant4/contracts.py`, `03_mc_simulation/geant4/tests/test_simulation_contracts.py`; estendere `export_truth.py`, `run.py`, rispettivi test; riusare `04_bdt_training/dataset/stage1_dataset.py` e `grouped_split.py`.

**Interfaces:** `validate_simulation_manifest(manifest: dict) -> None`; `validate_event_ledger(rows: list[dict], manifest: dict) -> None`. Manifest versionato con `source_sha256`, intervallo/entry esportate, `n_generated`, convenzione pesi/densità di proposta e sezioni d'urto/BR, profilo detector/beam e hash, Geant4/dataset/physics/cut, seed policy e hash degli artefatti. Ledger una riga per origine: `origin_id`, `source_entry`, pesi GENBOD/componenti fisiche, `transport_status`, `trigger_status`, `selection_status`; somme w/w² prima/dopo ogni selezione e stati non ancora valutati espliciti.

- [ ] Scrivere test: `test_partial_export_denominator`, `test_zero_hits_preserves_origin`, `test_aborted_campaign_is_not_efficiency`, `test_duplicate_origin_rejected`, `test_detector_variants_share_split`. Un export di 10 entry su 100 ha `n_generated=10` e conserva `source_events=100` separatamente.
- [ ] Verificare fallimento dei nuovi contratti prima dell'implementazione; estendere i proprietari attuali senza introdurre un secondo registro canali.
- [ ] Preservare lettura degli export diagnostici schema 1; i nuovi campi necessari alla produzione non si inferiscono dagli output vecchi. Conflitti tra input/configurazione/hash falliscono.
- [ ] Aggiungere `test_weighted_efficiency_uses_all_generated_weights`, `test_genbod_weight_not_applied_after_unweighting`, `test_missing_weight_convention_rejected`; fixture pesata con pesi `[1,3]` e solo secondo evento accettato dà efficienza `0.75`, non `0.5`.
- [ ] Verificare test nuovi più `test_truth_export.py`, `tests/test_geant4_launcher.py` e `04_bdt_training/tests/test_stage1_dataset.py`. Nessun evento perduto o duplicato; schema/errore documentati.

## T2 — Geometria e materiali per periodo

**Files:** estendere `src/geometry.cc`, `src/TransportMaterials.hh`, `run.py`; aggiungere `config/geant4/detector_profiles.json` soltanto con valori documentati; test `geant4/tests/test_detector_profiles.py` e audit nativo esistente.

**Interface:** `--detector-profile <id>` seleziona profilo immutabile `LH2-6`, `LH2-12`, `LD2-6` o `LD2-12`, con periodo/run, lunghezza nominale e attiva separate, densità nominale del liquido puro con fonte/condizioni e materiali confermati dal Fortran. Snapshot storico separato `diagnostic_only`. Verificare convenzioni nel sorgente: `lagdata.F` assegna oggi 6.12 e 11.1 cm, non assumere uguaglianza con le etichette nominali.

- [ ] Test `test_period_target_mismatch_rejected`, `test_missing_material_source_rejected`, `test_frozen_snapshot_unchanged`: profilo incompatibile viene rifiutato e hash storici restano identici.
- [ ] Implementare override/costruzione del profilo solo dai dati di T0, con separazione tra snapshot di equivalenza e nuova geometria fisica. Non allentare il guard sul deuterio per far passare un test.
- [ ] Verificare overlap campionati, mappe copie, navigazione/bordi e round-trip GDML per ogni profilo; aggiungere scansioni di materiale attraversato lungo traiettorie rilevanti, incluse regioni del protone.
- [ ] Revisionare differenze di materiale/posizione contro fonti. Esito: profilo utilizzabile per pilot, limiti documentati; nessuna dichiarazione di equivalenza GEANT3 senza riferimenti indipendenti.

## T3 — Beam e vertice; truth comune ai due modelli

**Files:** estendere `export_truth.py`, `run.py`, `src/transport.cc`, `geant4/tests/test_truth_export.py`; aggiungere `geant4/tests/test_beam_vertex.py`. Riusare generatori, registro canali e `beam_profiles.py`.

**Interface:** sidecar versionato per entry con origine, vertice in mm, tempo in ns, beam vero, identificatore di profilo/stato; nessun campo di questo sidecar diventa feature osservata. HEPEvt continua a descrivere final state in GeV. Seed distinti e registrati per generazione, vertice, trasporto, digitizzazione.

- [ ] Test `test_profile_threshold_support`, `test_vertex_units_and_bounds`, `test_truth_and_measured_tagger_separated`, `test_same_truth_identity_across_backends`.
- [ ] Conservare baseline uniforme/unweighted per regressioni, introdurre percorso GENBOD pesato in T3a. Allineare supporto energetico ai profili reali e documentare il taglio di soglia; non riusare lo smoke 1.5–1.6 GeV come campione VIS.
- [ ] Aggiungere vertice/beam spot da profilo con sorgenti di T0. Tenere origine/time-zero come modalità diagnostica esplicita. Per stato/polarizzazione separare generazione cinematica, modulazione fisica dell'evento e risposta del tagger; non attribuire alle particelle secondarie la polarizzazione del beam per convenienza.
- [ ] Verificare conservazione del quadrimpulso, assenza di smearing all'ingresso G4 e ripetibilità nella configurazione dichiarata; le nuove varianti non alterano lo stream legacy.
- [ ] Per D dichiarare reazione nucleare e trattamento spettatore/Fermi/legame/FSI; auditare il percorso legacy prima di riusarlo. Materiale LD₂ con truth libero γp resta un test di trasporto, non un'efficienza fisica su D.

## T3a — Pesi GENBOD e distribuzioni di produzione

**Files:** nuova modalità nei generatori `03_mc_simulation/generators/`, `generator_runtime.h`, `export_truth.py`; import curato di tabelle in `data/00_external/` con manifest/versioni in `config/geant4/`; consumatore responsabile `00_common/physics/cross_sections.py` esteso senza cambiare la baseline. Test `03_mc_simulation/tests/test_generator_weights.py`, `00_common/tests/test_cross_section_tables.py`. Sorgenti legacy e [ricerca delle fonti](../../wiki/geant4-cross-section-sources.md) guidano l'import, non sono promosse automaticamente a dati validati.

**Interface:** evento con peso GENBOD originale, convenzione/normalizzazione, proposta e componenti dei decadimenti separati. Tabella con reazione/target, tipo totale/differenziale, Eγ/W, variabili/frame, bordi/unità/Jacobiani, BR, errori, provenienza e dominio. Densità fisica e rate costruiti senza duplicare fattori già nel campionamento.

- [ ] Tracciare `GENBOD→WT→output→consumatore` anche nelle catene di decadimento; verificare se WT viene sovrascritto o combinato. Auditare `channeldef.F`, `channelex.F`, `gen_init.F`, `blockdata.F`, `totalsect.F`: commenti e ID canale possono divergere. Cercare file esterni letti via `INP_LAGGEN` prima di dichiarare complete le tabelle.
- [ ] Test `test_native_weight_roundtrip`, `test_decay_weight_composition`, `test_weighted_unweighted_agree_within_mc_error`, `test_differential_integrates_to_total`, `test_branching_applied_once`, `test_outside_table_support_rejected`. Documentare normalizzazione e campionamento prima di fissare le attese numeriche.
- [ ] Preferire misure della reazione esatta nel dominio; usare modelli identificati/versionati per input mancanti con variazioni d'incertezza. Una differenziale proiettata non determina tutte le correlazioni di molti corpi. Nessun MAID di singolo mesone viene esteso implicitamente a canali multipli.
- [ ] Separare uso di dati esterni del segnale come proposta/forma dall'estrazione della sua normalizzazione. I modelli di produzione per simulazione non riattivano l'implementazione teorica stage 09.

## T4 — Hit sufficienti a ricostruire il detector

**Files:** estendere `src/transport.cc`; estrarre, se necessario per responsabilità, `src/DetectorHits.hh` e `src/DetectorHits.cc`; aggiornare CMake; aggiungere `geant4/tests/test_detector_hits.py`.

**Interface:** eventi/ledger separati da hit con `origin_id, detector, channel_id, edep_MeV, time_ns` e posizione/informazione temporale richiesta. Per scintillatori carichi includere step energy/length/materiale, oppure `visible_energy_MeV` calcolata nello stepping con modello/parametri versionati: fissare una di queste modalità prima di aggregare. Conservare edep grezzo per controlli e non pretendere di ricostruire quenching dalla sola somma. Informazioni fisiche necessarie al modello di scintillazione non sono feature/PID truth della ricostruzione. Il mapping detector è quello verificato in T2.

- [ ] Test `test_hit_sum_matches_bgo_total`, `test_empty_event_has_ledger_row`, `test_proton_detector_coverage`, `test_repeated_hit_aggregation`, `test_no_unknown_channel_id`, `test_quenching_before_aggregation_preserves_step_dependence`.
- [ ] Aggiungere hit dei sottosistemi necessari a protone, charged-track veto e trigger, usando `G4VSensitiveDetector`/collezioni native quando opportuno. Non obbligare un refactor se lo scoring esistente basta al confine dichiarato.
- [ ] Definire prima della raccolta la risoluzione temporale necessaria: il solo primo tempo e somma per cristallo non bastano per qualunque pile-up/elettronica. Estendere l'output solo per osservabili richieste; rifiutare modelli che chiedono informazione non salvata.
- [ ] Pilot piccolo di gamma/protoni e due canali esclusivi; controllare contabilità, unità, topologie e costo. Gli hit truth-tagged di debugging restano separati dagli input di ricostruzione.
- [ ] Per benchmark di particella singola usare GPS già disponibile, inclusi pioni/neutroni; non forzarli nell'export esclusivo corrente, che ammette protone+fotoni. Eventuali nuovi canali esclusivi/nucleari richiedono schema e validazione propri prima di estendere il reader.

## T5 — Risposta, clustering, protone e trigger

**Files:** creare `03_mc_simulation/response/` con `__init__.py`, `digitization.py`, `reconstruction.py` e `tests/test_detector_response.py`; profili curati in `config/geant4/`. Il package dovrà essere registrato nel packaging esistente con il proprio task, senza installazioni globali.

**Interfaces:** `digitize(hits, response_profile: dict, *, seed: int) -> dict` produce letture osservate e decisione trigger; `reconstruct(readout: dict, detector_profile: dict) -> dict` produce candidati osservati photon/proton/charged-track/PID. Nessun parametro truth nelle due firme. Dizionari validati con schema, unità e canali del profilo; il dettaglio ADC/TDC segue T0.

- [ ] Test `test_missing_calibration_rejected`, `test_threshold_and_dead_channels`, `test_cluster_merge_split`, `test_proton_pid_and_topology`, `test_trigger_zero_event`, `test_truth_unavailable_to_reconstruction`.
- [ ] Implementare risposta sui depositi con calibrazione, fluttuazioni residue, rumore, soglie, timing e inefficienze giustificate dai dati; evitare doppio conteggio della risoluzione. Nessun valore nominale inventato per dati mancanti.
- [ ] Recuperare gli algoritmi di clustering originali da `prean`, con routine, pilot, adiacenza, soglie e dipendenze libreria. Portarli/adattarli con equivalenza verificata su fixture; non sostituirli con un algoritmo nuovo non confrontato. Misurare merging/splitting e risoluzioni; ricostruire protone e carichi/veto senza PID vero.
- [ ] Confrontare controlli di T0: scale/risoluzioni, molteplicità, distribuzioni angolari/tempi, efficienze e trigger, separando periodi/topologie. Congelare calibrazioni prima dei controlli held-out.
- [ ] Provare convergenza delle range cut e modelli EM/hadronici pertinenti con budget preregistrato. Trasporto ottico solo con motivazione misurata e parametri disponibili. Esito G1 per i soli domini coperti.

## T5a — Benchmark obbligatori pioni/protoni

**Files:** creare `03_mc_simulation/response/validate_charged_pid.py` e `response/tests/test_charged_pid_benchmark.py`; leggere tagli di periodo e routine `track_centr_classify.F`, `track_forw_classify.F`, `prean`/`lagdig` originali.

**Interface:** report per run/profilo e specie con mappe 2D, centroidi/larghezze/code delle bande e matrice di confusione, prima/dopo identici tagli. Centro: x=`Eclusc_track`, y=`Dedx_track`; avanti: x=`Tof_trf`, y=`De_trf`; unità e calibrazione dal sorgente, non da assunzioni su dE/dx ideale.

- [ ] Test `test_central_pid_axes_and_units`, `test_forward_pid_axes_and_time_zero`, `test_pion_proton_confusion_from_truth_only_in_metrics`, `test_period_cuts_preserved`.
- [ ] Confrontare dati indipendenti dal tuning e MC con risposta di scintillazione/quenching, cammino e timing appropriati. Dichiarare tolleranze e supporto statistico prima del test; non dimostrare accordo con i soli grafici.
- [ ] Accettare G1 fisico solo nei domini dove entrambi i benchmark pertinenti e trigger/clustering sono verificati. Questo task precede la certificazione di efficienze e fondo.

## T5b — Studio γ/neutrone nel BGO, esplorativo

**Files:** creare `03_mc_simulation/response/study_neutral_pid.py`, `response/tests/test_neutral_pid_study.py`; estendere scoring solo per osservabili che l'elettronica può misurare. Modello/feature separati dalle 26 feature del BDT stage 1.

**Interface:** mappe ε_gamma, ε_neutron e contaminazione a working point fissati in energia/angolo, con controllo delle distribuzioni di energia visibile e incertezza detector/modello. Esito ammesso `useful|insufficient|inconclusive`, senza gate forzato sugli altri task.

- [ ] Test `test_incident_and_visible_energy_distinguished`, `test_truth_labels_excluded_from_features`, `test_timing_requires_readout_model`, `test_neutral_domain_support_and_confusion`.
- [ ] Studiare gamma e neutroni singoli su griglie comuni e poi topologie fisiche/controlli cinematici indipendenti. Confrontare tempo, molteplicità sopra soglia, Emax/Ecluster e momenti/estensione; una differenza dovuta solo ai priors energetici del campione non è PID.
- [ ] Variare modello neutronico, timing/soglie/quenching; usare neutroni truth come etichetta solo per valutazione. Nessun waveform/PID ottico inferito dai tempi dei depositi. Una discriminazione insufficiente è risultato valido.

## T6 — Confine comune con selezione e BDT

**Files:** creare `03_mc_simulation/response/export_observed.py`, estendere `04_bdt_training/dataset/mc_samples.py`, `build_background_features.py` e metadata/provenienza nei proprietari `dataset/stage1_dataset.py`, `00_common/stage1/artifacts.py`; test `03_mc_simulation/response/tests/test_observed_contract.py`, `04_bdt_training/tests/test_detector_backend.py`. Riusare selector e feature esistenti.

**Interfaces:** output osservato compatibile con i campi h80 necessari al selector, poi h85 e ricostruzione standard; metadata MC identificano stato/run simulato senza falsificare run/esposizioni reali. CLI proposta `--detector-backend fast|geant4`, default `fast`. G4 fornisce candidati ricostruiti e ledger; non passa dal sampler `photon_loss`.

- [ ] Test `test_same_observed_event_same_26_features`, `test_geant4_skips_legacy_loss`, `test_no_truth_proton_fallback`, `test_four_photons_not_forced`, `test_generated_denominator_includes_failed_selection`, `test_backend_provenance_roundtrip`.
- [ ] Riutilizzare esattamente selezione quattro fotoni/un protone/veto e regola charged-track centrale/forward. Nessuna scelta dei “migliori quattro” se non esiste nella selezione dati. Preservare ledger anche per eventi scartati.
- [ ] Aggiungere il ramo di caricamento per osservati G4 nel proprietario `mc_samples.py`; riusare shuffle, `compute_stage1_features`, `channel_yield`, `compute_shares`. Il denominatore viene dal ledger, non dal numero di righe selezionate.
- [ ] Estendere esplicitamente la provenienza dei bundle: il validatore attuale rifiuta chiavi ignote. Compatibilità con bundle legacy resta esplicita; un bundle vecchio non diventa G4 per inferenza.
- [ ] Test di selezione stage 02 e stage 05, dataset/pesi/split e artefatti stage 04 passano; schema 2 di ricostruzione rimane invariato. Esito G2.

## T7 — Esperimento BDT e confronto MC–dati

**Files:** creare `04_bdt_training/evaluate_detector_backends.py`, `04_bdt_training/tests/test_detector_comparison.py`; riusare `training/stage1_training.py`, `training/feature_reporting.py`, `dataset/grouped_split.py`. Contratto del report in `wiki/geant4-validation.md`.

**Interface:** comparatore consuma dataset identificati e bundle congelati, produce report con matrice train/test veloce–G4, intervalli/statistiche per dominio, audit origini, configurazione/soglia/hash e stato `pass|fail|inconclusive`. Nessuna ottimizzazione dentro il test finale.

- [ ] Test `test_shared_origin_never_crosses_split`, `test_test_labels_do_not_change_threshold`, `test_missing_domain_is_inconclusive`, `test_weighted_statistics_and_denominator`, `test_detector_variant_not_a_feature`.
- [ ] Assegnare una sola volta split 60/20/20 alle origini comuni, prima delle repliche e delle selezioni. Aggiungere supporto di pianificazione split sull'intero truth se l'API attuale vede solo sopravvissuti; riusare l'audit esistente.
- [ ] Allenare veloce/G4 con budget uguale; confrontare prima iperparametri fissati. Soglie su validation, risultati finali su test separato. Dopo una modifica guidata dal test, quel test diventa sviluppo: serve un nuovo hold-out per una nuova decisione finale.
- [ ] Confrontare a pari efficienza di segnale, soglia legacy congelata e soglia candidata scelta senza test; riportare rejection per canale, AUC pesata, masse/feature/score, dipendenze in energia e azimut, centrale/forward UV/VIS. Supporto scarso produce `inconclusive`.
- [ ] Confrontare con controlli dati indipendenti e contaminazione documentata. Non usare retention sui dati come efficienza vera. Esito G3 e decisione motivata sul candidato; nessun upgrade automatico per sola AUC.

## T8 — Efficienze, migrazioni, fondo residuo e closure

**Files:** creare `03_mc_simulation/efficiency.py`, `03_mc_simulation/tests/test_weighted_efficiency.py`, `08_observable_extraction/validate_mc_selection.py`, `08_observable_extraction/tests/test_mc_selection_closure.py`; riusare input calibrati di flusso/esposizione e bootstrap. `core/ratio_fit.py` e `core/conditional_likelihood.py` servono al controllo complementare dell'asimmetria; nessuna modifica a stage 09.

**Interface:** `estimate_efficiency(truth, ledger, selection, binning) -> dict` produce efficienza pesata `Σw_pass/Σw_gen`, risposta truth→reco, cutflow di conteggi/w/w² e covarianze per profilo/target/canale. `validate_mc_selection` consuma prodotti, selezione congelata, tabelle/modelli e luminosità dichiarata; produce closure di yield/sezioni d'urto, fondo residuo per canale/shape e gate G4. Esposizione, nuclei bersaglio, unità, BR e normalizzazione restano separati e verificabili; i prior di training non sono rate assoluti.

- [ ] Test `test_weighted_efficiency_and_migrations`, `test_known_cross_section_recovered`, `test_background_absolute_normalization`, `test_branching_and_target_nuclei_once`, `test_zero_selected_exposure_preserved`, `test_insufficient_mc_cannot_pass`; aggiungere closure nulla/non nulla dell'asimmetria e accettanze comuni/differenziali tra stati.
- [ ] Congelare binning, precisione di efficienze/fondo e pseudoesperimenti prima del test; usare yield/sezione nota e fondi noti. Variare detector, forme differenziali non misurate, normalizzazioni, densità/lunghezza target e luminosità con correlazioni. Il modello usato per generare il segnale non impone la normalizzazione estratta.
- [ ] Eseguire ratio e likelihood nei loro contratti, con relativi divisori/correzioni previsti. Riportare anche incertezza della closure e bin non supportati; non interpretare un p-value grande come prova di equivalenza.
- [ ] Validare efficienze/risposta e fondo come prodotti principali, anche con BDT legacy congelato. Retraining T7 è una decisione separata; non è prerequisito per stimare l'efficienza di una selezione esistente. G4 richiede benchmark esterni oltre alla closure del simulatore con sé stesso.
- [ ] Report di fondo separa componenti simulate, limiti da controlli e processi non vincolati. Test `test_partial_background_not_labeled_total` rifiuta la qualifica di fondo totale quando manca l'audit di completezza T0; propagare normalizzazioni e correlazioni delle componenti incluse.
- [ ] Se accettanza differenziale o migrazioni richiedono una nuova correzione degli stimatori dell'asimmetria, registrare il relativo gate aperto e specificare un progetto separato con derivazione e covarianze. Questo non esclude i prodotti di efficienza/risposta per sezioni d'urto già richiesti da T8.

## T9 — Calcolo, portabilità e promozione

**Files:** estendere `03_mc_simulation/geant4/run.py`, `export_truth.py` e test launcher/replay; documentare benchmark e decisione in `wiki/geant4-validation.md`, aggiornare README e `wiki/status.md` dopo il gate. Eventuale configurazione campagna in `config/geant4/`.

**Interface:** manifest di partizioni disgiunte con origini, seed, quantità generate/completate e hash; merge verifica unicità, completezza e denominatori. Budget dichiarato prima del lancio, nessuna selezione del default produttivo implicita.

- [ ] Test `test_partition_origins_disjoint`, `test_retry_does_not_duplicate`, `test_merge_rejects_incomplete_campaign`, `test_seed_policy_replay`; scegliere stato RNG/evento o derivazione deterministica documentata. Il seed fisso del replay diagnostico non basta come politica di campagne indipendenti.
- [ ] Eseguire benchmark breve sul server **trima**, designato dal responsabile senza limite di budget imposto: rilevare setup, CPU/memoria/spazio, costo/evento per canale/profilo e selezione. Convertire precisione richiesta in numerosità, mantenendo controlli di quota e completezza operativi; nessuna statistica infinita implicita.
- [ ] Verificare ambiente/build/replay reale di trima; Linux se quello è il sistema effettivo, Windows se richiesto per altro uso. Prima parallelizzare processi seriali con input disgiunti. Multithreading richiede un task separato se introduce lettore condiviso o merge/RNG nuovi.
- [ ] Preparare prodotti/bundle candidato e confronto con baseline, senza sovrascrivere riferimenti. Efficienze/fondo richiedono G0/G1/G2/G4/G5; G3 si aggiunge quando cambia il BDT. Registrare la decisione scientifica; rollback è selezione del vecchio bundle/configurazione preservati.
- [ ] Conservare il MC veloce per test rapidi e studi di sensibilità. Un eventuale surrogato calibrato o training misto richiede validazione propria, non entra automaticamente nel rilascio G4.

## Verifica e chiusura di ogni task

Creare soltanto la campagna di verifica necessaria; impostare variabili e directory temporanee come da vincoli. Eseguire i test citati dal task con `python -B -m pytest <test> --basetemp=<campaign>/pytest -o cache_dir=<campaign>/cache`; i nuovi test funzionali devono fallire prima della modifica e passare dopo. Non creare test che certificano valori fisici non misurati.

Prima di handoff: controllare diff e integrazioni interessate, salvare risultati/limiti e hash rilevanti, rimuovere artefatti riproducibili dopo fine dei job. Per release del ponte eseguire i test Geant4, generatori, dataset/training, selezione, ricostruzione/provenienza e closure interessati, oltre a wiki/layout/packaging. Successo software e validazione scientifica rimangono due esiti separati.

**Prima azione:** T0 sui sorgenti ritrovati, poi T1/T3a e profili target T2; recuperare clustering/calibrazioni, chiudere benchmark cariche T5a, quindi T6/T8 per efficienze e fondo. Conservare il BDT veloce come riferimento e confrontare candidato G4 solo dopo risposta/contratti validati. Studio γ/n T5b separato. Nessun job esteso su trima prima del benchmark concordato.
