# Geant4 e BDT — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: usare `superpowers:executing-plans` per eseguire questo piano task per task. Le checkbox tracciano deliverable verificati, non intenzioni. Non avviare implementazione o campagne durante il solo brainstorming.

**Goal:** ottenere un detector MC validato e decidere con prove riproducibili se sostituire il modello veloce nel training BDT e, separatamente, negli studi di accettanza.

**Architecture:** mantenere il generatore ROOT e l'identità del truth; confrontare risposta veloce e risposta Geant4 su contratti osservati comuni. La digitizzazione e la ricostruzione precedono le 26 feature; training, pesi e inferenza restano nei proprietari esistenti.

**Tech Stack:** ROOT/PyROOT, Geant4 ≥11.4, C++17, CMake ≥3.16, Python ≥3.10, NumPy e stack XGBoost già presenti. Spack esterno su macOS.

**Spec:** [decisione e architettura](2026-10-26-geant4-bdt-design.md). Stato: proposta esecutiva, da aggiornare con gli input di detector; non autorizza una promozione in produzione.

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
| T2 | T0, T1 | Profili detector con target corretto | Contratto sì; valori fisici richiedono fonti |
| T3 | T1, T2 | Beam, vertice e truth riproducibili | Software sì; profili fisici dopo G0 |
| T4 | T2, T3 | Hit necessari a fotoni/protone/trigger | Dopo mappa detector verificata |
| T5 | T4 | Risposta calibrata e ricostruzione | Richiede calibrazioni e controlli |
| T6 | T1, T5 | Adapter per selezione, feature e pesi | Su fixture prima, su detector dopo G1 |
| T7 | T6 | Confronto BDT incrociato e dati | Dopo G0–G2 |
| T8 | T7 | Closure e budget dell'osservabile | Con flussi/polarizzazioni e controlli validi |
| T9 | Pilot T4–T6; G3–G4 per promozione | Calcolo riproducibile e rilascio reversibile | Benchmark breve prima; produzione dopo gate |

T0–T1 sono il primo blocco concreto. Le fasi successive non assegnano valori inventati agli input assenti: l'inventario registra la dipendenza e consente lavoro indipendente sui contratti. I moduli indicati come nuovi sono proposte di responsabilità; confermare la granularità al task, evitando classi/interfacce senza necessità.

## T0 — Inventario del detector, controlli e baseline

**Files:** aggiornare `wiki/03-monte-carlo-simulation.md`, `wiki/04-bdt-training.md`, `wiki/status.md`; creare `wiki/geant4-validation.md`. Leggere `config/run_manifest.csv`, `00_common/physics/beam_profiles.py`, `config/common_inputs.json`, artefatti stage 04 e sorgenti detector/Fortran preservati.

**Interface:** inventario con `item, period, source_path, sha256, physical_units, validity, owner, status`; status `available|missing|unverified`. Baseline report: sorgenti/generatori, beam profile, feature contract, loss/smearing, pesi, modello, soglia, split e versioni. Non creare sostituti di bundle assenti.

- [ ] Registrare per UV/VIS target/cella/finestre, materiali e posizioni, mappe canali, calibrazioni, canali morti, elettronica/trigger, PID e beam spot/vertice; distinguere fatto documentato da ipotesi.
- [ ] Definire controlli dati, purezza/fondo e separazione per run tra tuning e validazione. Registrare esplicitamente se serve un nuovo cohort e il relativo intervento separato.
- [ ] Congelare baseline disponibile con hash; registrare assenze senza avviare rigenerazione massiva. Correggere nella documentazione la confusione tra fotoni generati e rami smeared letti da `mc_samples.py`.
- [ ] Dichiarare metrica primaria, domini e budget fisico prima di aprire test finale. La proposta `0.2 σ_stat` del design non diventa automaticamente requisito approvato.
- [ ] Verificare links/documenti con `tests/test_wiki.py` e `tests/test_wiki_sync.py`; revisionare inventario. Output: stato G0 e elenco di input mancanti, ciascuno associato al task bloccato.

## T1 — Identità, ledger e manifest della simulazione

**Files:** creare `03_mc_simulation/geant4/contracts.py`, `03_mc_simulation/geant4/tests/test_simulation_contracts.py`; estendere `export_truth.py`, `run.py`, rispettivi test; riusare `04_bdt_training/dataset/stage1_dataset.py` e `grouped_split.py`.

**Interfaces:** `validate_simulation_manifest(manifest: dict) -> None`; `validate_event_ledger(rows: list[dict], manifest: dict) -> None`. Manifest versionato con `source_sha256`, intervallo/entry esportate, `n_generated`, profilo detector/beam e hash, Geant4/dataset/physics/cut, seed policy, stato diagnostico/validato e hash degli artefatti. Ledger una riga per origine simulata: `origin_id`, `source_entry`, `transport_status`, `trigger_status`, `selection_status`; stati non ancora valutati espliciti.

- [ ] Scrivere test: `test_partial_export_denominator`, `test_zero_hits_preserves_origin`, `test_aborted_campaign_is_not_efficiency`, `test_duplicate_origin_rejected`, `test_detector_variants_share_split`. Un export di 10 entry su 100 ha `n_generated=10` e conserva `source_events=100` separatamente.
- [ ] Verificare fallimento dei nuovi contratti prima dell'implementazione; estendere i proprietari attuali senza introdurre un secondo registro canali.
- [ ] Preservare lettura degli export diagnostici schema 1; i nuovi campi necessari alla produzione non si inferiscono dagli output vecchi. Conflitti tra input/configurazione/hash falliscono.
- [ ] Verificare test nuovi più `test_truth_export.py`, `tests/test_geant4_launcher.py` e `04_bdt_training/tests/test_stage1_dataset.py`. Nessun evento perduto o duplicato; schema/errore documentati.

## T2 — Geometria e materiali per periodo

**Files:** estendere `src/geometry.cc`, `src/TransportMaterials.hh`, `run.py`; aggiungere `config/geant4/detector_profiles.json` soltanto con valori documentati; test `geant4/tests/test_detector_profiles.py` e audit nativo esistente.

**Interface:** `--detector-profile <id>` seleziona profilo immutabile con periodo/target, fonti/hash, geometria e material policy; profilo storico esplicito `diagnostic_only`. Il target `P` del manifest non autorizza inferenze su densità o cella.

- [ ] Test `test_period_target_mismatch_rejected`, `test_missing_material_source_rejected`, `test_frozen_snapshot_unchanged`: profilo incompatibile viene rifiutato e hash storici restano identici.
- [ ] Implementare override/costruzione del profilo solo dai dati di T0, con separazione tra snapshot di equivalenza e nuova geometria fisica. Non allentare il guard sul deuterio per far passare un test.
- [ ] Verificare overlap campionati, mappe copie, navigazione/bordi e round-trip GDML per ogni profilo; aggiungere scansioni di materiale attraversato lungo traiettorie rilevanti, incluse regioni del protone.
- [ ] Revisionare differenze di materiale/posizione contro fonti. Esito: profilo utilizzabile per pilot, limiti documentati; nessuna dichiarazione di equivalenza GEANT3 senza riferimenti indipendenti.

## T3 — Beam e vertice; truth comune ai due modelli

**Files:** estendere `export_truth.py`, `run.py`, `src/transport.cc`, `geant4/tests/test_truth_export.py`; aggiungere `geant4/tests/test_beam_vertex.py`. Riusare generatori, registro canali e `beam_profiles.py`.

**Interface:** sidecar versionato per entry con origine, vertice in mm, tempo in ns, beam vero, identificatore di profilo/stato; nessun campo di questo sidecar diventa feature osservata. HEPEvt continua a descrivere final state in GeV. Seed distinti e registrati per generazione, vertice, trasporto, digitizzazione.

- [ ] Test `test_profile_threshold_support`, `test_vertex_units_and_bounds`, `test_truth_and_measured_tagger_separated`, `test_same_truth_identity_across_backends`.
- [ ] Conservare generazione uniforme con reweighting corrente nella prima comparazione. Allineare supporto energetico ai profili reali e documentare il taglio di soglia; non riusare lo smoke 1.5–1.6 GeV come campione VIS.
- [ ] Aggiungere vertice/beam spot da profilo con sorgenti di T0. Tenere origine/time-zero come modalità diagnostica esplicita. Per stato/polarizzazione separare generazione cinematica, modulazione fisica dell'evento e risposta del tagger; non attribuire alle particelle secondarie la polarizzazione del beam per convenienza.
- [ ] Verificare conservazione del quadrimpulso, assenza di smearing all'ingresso G4 e ripetibilità nella configurazione dichiarata; le nuove varianti non alterano lo stream legacy.

## T4 — Hit sufficienti a ricostruire il detector

**Files:** estendere `src/transport.cc`; estrarre, se necessario per responsabilità, `src/DetectorHits.hh` e `src/DetectorHits.cc`; aggiornare CMake; aggiungere `geant4/tests/test_detector_hits.py`.

**Interface:** eventi/ledger separati da hit con `origin_id, detector, channel_id, edep_MeV, time_ns` e posizione/informazione temporale richiesta dal modello di risposta. Il mapping detector è quello verificato in T2. Conservare energia BGO per cristallo come controllo integrale.

- [ ] Test `test_hit_sum_matches_bgo_total`, `test_empty_event_has_ledger_row`, `test_proton_detector_coverage`, `test_repeated_hit_aggregation`, `test_no_unknown_channel_id`.
- [ ] Aggiungere hit dei sottosistemi necessari a protone, charged-track veto e trigger, usando `G4VSensitiveDetector`/collezioni native quando opportuno. Non obbligare un refactor se lo scoring esistente basta al confine dichiarato.
- [ ] Definire prima della raccolta la risoluzione temporale necessaria: il solo primo tempo e somma per cristallo non bastano per qualunque pile-up/elettronica. Estendere l'output solo per osservabili richieste; rifiutare modelli che chiedono informazione non salvata.
- [ ] Pilot piccolo di gamma/protoni e due canali esclusivi; controllare contabilità, unità, topologie e costo. Gli hit truth-tagged di debugging restano separati dagli input di ricostruzione.

## T5 — Risposta, clustering, protone e trigger

**Files:** creare `03_mc_simulation/response/` con `__init__.py`, `digitization.py`, `reconstruction.py` e `tests/test_detector_response.py`; profili curati in `config/geant4/`. Il package dovrà essere registrato nel packaging esistente con il proprio task, senza installazioni globali.

**Interfaces:** `digitize(hits, response_profile: dict, *, seed: int) -> dict` produce letture osservate e decisione trigger; `reconstruct(readout: dict, detector_profile: dict) -> dict` produce candidati osservati photon/proton/charged-track/PID. Nessun parametro truth nelle due firme. Dizionari validati con schema, unità e canali del profilo; il dettaglio ADC/TDC segue T0.

- [ ] Test `test_missing_calibration_rejected`, `test_threshold_and_dead_channels`, `test_cluster_merge_split`, `test_proton_pid_and_topology`, `test_trigger_zero_event`, `test_truth_unavailable_to_reconstruction`.
- [ ] Implementare risposta sui depositi con calibrazione, fluttuazioni residue, rumore, soglie, timing e inefficienze giustificate dai dati; evitare doppio conteggio della risoluzione. Nessun valore nominale inventato per dati mancanti.
- [ ] Ricostruire cluster usando geometria/adiacenza e algoritmi condivisibili con i dati; misurare merging/splitting e risoluzioni. Ricostruire protone e candidati carichi/veto senza PID vero. Esplicitare i limiti di qualunque sottosistema parametrizzato.
- [ ] Confrontare controlli di T0: scale/risoluzioni, molteplicità, distribuzioni angolari/tempi, efficienze e trigger, separando periodi/topologie. Congelare calibrazioni prima dei controlli held-out.
- [ ] Provare convergenza delle range cut e modelli EM/hadronici pertinenti con budget preregistrato. Trasporto ottico solo con motivazione misurata e parametri disponibili. Esito G1 per i soli domini coperti.

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

## T8 — Closure dell'osservabile e accettanza

**Files:** creare `08_observable_extraction/validate_mc_selection.py`, `08_observable_extraction/tests/test_mc_selection_closure.py`; riusare `core/ratio_fit.py`, `core/conditional_likelihood.py`, flussi/polarizzazioni e strumenti di bootstrap già disponibili. Nessuna modifica a stage 09.

**Interface:** `validate_mc_selection` consuma truth, ledger, selezioni/modelli congelati e specifica versionata dei pseudoesperimenti; produce mappe diagnostiche di efficienza/risposta, bias/pull/copertura per bin e dominio, componenti d'incertezza e gate G4. Le modulazioni iniettate rispettano segno, polarizzazione e binning già definiti dall'analisi. Gli stimatori esistenti restano invariati: nessun nuovo input di correzione dell'accettanza e nessuna divisione automatica dei dati per una mappa MC.

- [ ] Test `test_null_asymmetry_closure`, `test_injected_asymmetry_recovery`, `test_common_acceptance_cancellation`, `test_state_dependent_acceptance_bias_detected`, `test_kinematic_migration_bias_detected`, `test_zero_selected_exposure_preserved`, `test_insufficient_mc_cannot_pass`.
- [ ] Congelare budget e pseudoesperimenti prima del test: modulazione nulla/non nulla ammissibile, flussi/stati noti, nuisance detector/generatore/normalizzazione e variazioni indipendenti dal tuning nominale. Conservare correlazioni tra varianti dello stesso evento.
- [ ] Eseguire ratio e likelihood nei loro contratti, con relativi divisori/correzioni previsti. Riportare anche incertezza della closure e bin non supportati; non interpretare un p-value grande come prova di equivalenza.
- [ ] Valutare adozione BDT e accettanza come decisioni distinte: un training utile non certifica automaticamente una mappa di efficienza. G4 richiede evidenza esterna oltre alla closure del simulatore con sé stesso.
- [ ] Se accettanza differenziale o migrazioni richiedono una nuova correzione dell'osservabile, registrare fallimento/apertura del gate e specificare un progetto separato con derivazione e covarianze. T8 non modifica gli stimatori per far chiudere il test.

## T9 — Calcolo, portabilità e promozione

**Files:** estendere `03_mc_simulation/geant4/run.py`, `export_truth.py` e test launcher/replay; documentare benchmark e decisione in `wiki/geant4-validation.md`, aggiornare README e `wiki/status.md` dopo il gate. Eventuale configurazione campagna in `config/geant4/`.

**Interface:** manifest di partizioni disgiunte con origini, seed, quantità generate/completate e hash; merge verifica unicità, completezza e denominatori. Budget dichiarato prima del lancio, nessuna selezione del default produttivo implicita.

- [ ] Test `test_partition_origins_disjoint`, `test_retry_does_not_duplicate`, `test_merge_rejects_incomplete_campaign`, `test_seed_policy_replay`; scegliere stato RNG/evento o derivazione deterministica documentata. Il seed fisso del replay diagnostico non basta come politica di campagne indipendenti.
- [ ] Benchmark breve per canale/profilo: setup, CPU/evento, memoria, spazio, selezione e code temporali; stimare numerosità dai target di precisione. Contratti, calibrazioni e test statistici precedono la produzione massiva.
- [ ] Provare build e replay su Linux; Windows se richiesto per uso effettivo. Prima parallelizzare processi seriali con input disgiunti. Multithreading richiede un task separato se introduce lettore condiviso o merge/RNG nuovi.
- [ ] Preparare bundle candidato e confronto con baseline, senza sovrascrivere riferimenti. Promuovere solo dopo G0–G5 e decisione scientifica registrata; rollback è selezione del vecchio bundle/configurazione preservati.
- [ ] Conservare il MC veloce per test rapidi e studi di sensibilità. Un eventuale surrogato calibrato o training misto richiede validazione propria, non entra automaticamente nel rilascio G4.

## Verifica e chiusura di ogni task

Creare soltanto la campagna di verifica necessaria; impostare variabili e directory temporanee come da vincoli. Eseguire i test citati dal task con `python -B -m pytest <test> --basetemp=<campaign>/pytest -o cache_dir=<campaign>/cache`; i nuovi test funzionali devono fallire prima della modifica e passare dopo. Non creare test che certificano valori fisici non misurati.

Prima di handoff: controllare diff e integrazioni interessate, salvare risultati/limiti e hash rilevanti, rimuovere artefatti riproducibili dopo fine dei job. Per release del ponte eseguire i test Geant4, generatori, dataset/training, selezione, ricostruzione/provenienza e closure interessati, oltre a wiki/layout/packaging. Successo software e validazione scientifica rimangono due esiti separati.

**Prima azione proposta:** T0, seguito da T1. **Prima scelta sul BDT:** conservare il riferimento veloce fino a G3–G4; costruire il candidato G4 dopo G1–G2. Nessuna stima di giorni o campagne milionarie prima dell'inventario e del benchmark.
