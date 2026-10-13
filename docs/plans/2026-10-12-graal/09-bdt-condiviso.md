# 9 — un BDT condiviso fra UV e VIS

> Diagnostica eseguita il 13 ottobre 2026 con `superpowers:executing-plans`; validazione fisica finale sospesa. [Report e artefatti](../../reports/2026-10-13-shared-bdt.md).

**Obiettivo:** confronto leale tra modello unico e due modelli attuali, senza contaminazione tra train, tuning e test.

**Architettura:** riusare feature e motore `fit_stage1`; estendere identità/split del dataset e contratto di compatibilità del bundle. Non far passare un modello UV come VIS rinominandolo. **Stack:** XGBoost, scikit-learn, NumPy, PyROOT. **Spec:** [README](README.md), [training attuale](00-stato-verificato.md).

## Già fatto e limiti

Launcher di produzione conserva due rami e percorso legacy 80/20. Studio diagnostico separato ora disponibile: schema con origini/split, tre bundle e contratto multi-profilo esplicito. Utente ha approvato pesi correnti, miscela UV/VIS 50/50, domini nominali e soglia unica validation F1. Nessun bundle di produzione sostituito.

## Invarianti e dipendenze

Stesso input fisico/feature, stessi fondi e stessi budget di tuning per entrambe le strategie. Tutte le copie di un evento MC, anche reweighted o con photon-loss diverso, appartengono allo stesso split. Nessun run dati usato per tuning entra nella validazione finale dichiarata indipendente; separare anche misura dello spettro usata per training dai dati hold-out quando la validazione lo richiede.

Baseline senza 6C; punto 5 fissa fondi, punto 8 fissa dominio (può essere nominale se studio energia non avviato), punto 1 per differenze Σ. Polarizzazione/calibrazione restano specifiche di UV/VIS anche con classifier comune.

## File candidati

`04_bdt_training/dataset/mc_samples.py`, `stage1_dataset.py`, `build_background_features.py`, `training/stage1_training.py`, `grid_search_stage1.py`, `train_bdt_stage1.py`; `00_common/stage1/artifacts.py`, `05_reconstruction/runtime/stage1_gate.py`, `scripts/run_pipeline.py`, `scripts/artifact_manifest.py`. Test dataset/training/bundle/gate e `tests/test_stage1_contracts.py`.

## Passi e metodo

- [x] Persistire identità evento originario (file/hash+entry), canale, profilo/energia, variante detector e indici split in dataset/versione compatibile. Vecchi NPZ senza identità non certificano assenza leakage: rigenerare da origini se necessario.
- [ ] Separare train, validation per iperparametri/soglia e test intatto, stratificando compatibilmente con gruppi di origine e canali. Audit assert di intersezioni vuote; tuning ripetuto non deve consumare test. Tre partizioni e audit completati; per meno di cinque origini per strato rifiuto esplicito. Validazione annidata per piccoli campioni ancora da implementare.
- [x] Allenare baseline UV e VIS e modello unico sugli stessi eventi eleggibili per split. Fissare miscela/prior UV-VIS e pesi; evitare che numerosità di un profilo domini senza scelta esplicita. `beam_E` resta feature documentata; non introdurre etichetta fascio per simulare due modelli senza chiamarlo variante distinta.
- [x] Confronto primario proposto: unico modello e unica soglia scelta su validation con criterio per entrambi i profili. Eventuale unico modello con due soglie è confronto secondario etichettato; decidere prima di aprire test.
- [x] Misurare AUC e precision-recall ponderate, efficienza/rigetto per profilo/energia/canale, stabilità score e sculpting masse/φ. Confrontare anche a pari efficienza segnale, non soltanto soglie F1 diverse.
- [ ] Applicare a hold-out reale/MC coerente, estrarre Σ senza 6C, verificare bias con segnali iniettati e ΔΣ/covarianza appaiata. Soglia non ottimizzata sulla somiglianza ad asimmetria nota. Eseguiti hold-out MC e toy appaiato del momento; estrazione Σ di produzione e validazione fisica restano sospese, come concordato.
- [x] Bundle unico deve dichiarare profili/range supportati, miscela, training provenance e schema; gate rifiuta range non coperto. Conservare bundle e risultati dei due modelli separati.

## Verifica e risultato

Test duplicati tra profili/varianti raggruppati, seed riproducibile, pesi validi, profilo unsupported, bundle legacy letto secondo contratto, nessun dato test usato per soglia. Test pertinenti: `test_stage1_dataset.py`, `test_stage1_training.py`, `test_stage1_artifacts.py`, `tests/test_stage1_contracts.py`, `tests/test_run_pipeline.py` nei rispettivi stadi.

**Consegna:** tre bundle, split auditabile, metriche su test e confronto fisico con incertezze. Possibile esito: modello comune non equivalente o dati insufficienti. Non sostituire modelli correnti senza evidenza; AUC alta da sola non valida Σ.
