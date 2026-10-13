# Piano 09 — confronto diagnostico BDT UV/VIS

13 ottobre 2026. **Piano non già implementato; ora completata la parte diagnostica autorizzata.** Tre nuovi bundle, origini e split persistiti, test MC intatto e confronto appaiato. Validazione fisica di Σ sospesa; nessun modello di produzione sostituito.

Decisione utente: pesi correnti, miscela UV/VIS **50/50**, domini nominali, soglia primaria unica su validation. Il risultato non dimostra equivalenza: a soglia primaria il modello comune accetta più fondo VIS, pur avendo AUC molto simile.

## Artefatti

Campagna: [`results/shared-bdt-20261013/`](../../results/shared-bdt-20261013/).

- Bundle [UV](../../results/shared-bdt-20261013/comparison/uv/), [VIS](../../results/shared-bdt-20261013/comparison/vis/), [comune](../../results/shared-bdt-20261013/comparison/shared/).
- [Protocollo](../../results/shared-bdt-20261013/comparison/protocol.json), [modelli e soglie bloccati prima del test](../../results/shared-bdt-20261013/comparison/training_locked.json), [audit split](../../results/shared-bdt-20261013/comparison/split_audit.json).
- [Metriche complete](../../results/shared-bdt-20261013/comparison/diagnostics_v2/test_metrics.json), score test con identità, istogrammi masse/φ, repliche e covarianze del toy nelle stesse directory.
- [ROC e score](../../results/shared-bdt-20261013/comparison/diagnostics_v2/classifier_comparison.png), [sculpting](../../results/shared-bdt-20261013/comparison/diagnostics_v2/sculpting_comparison.png), entrambi controllati visivamente.
- Dataset schema 2 in `comparison/inputs_uv/features.npz`, `inputs_vis/features.npz`, `shared_dataset.npz`; `split.npz` e split delle righe generate per ogni sorgente.
- Generazione, seed, SHA-256 e comandi in `diagnostic/generation.json`; sorgenti esatti, versioni e revisione in `comparison/execution.json` e `source_snapshot/`.

`diagnostics_v2` aggiunge stabilità degli score e differenze appaiate secondarie agli stessi modelli bloccati. Nessun nuovo fit o scelta di soglia; uguaglianza esatta delle metriche primarie verificata in `postprocessing.json`. Risultati originari conservati.

## Verifica iniziale e metodo

Graphify: grafo esistente di 2.480 nodi, query espansa dal vocabolario `dataset training split profile bundle gate validation`. Identificati `Stage1Dataset`, `fit_stage1`, `TrainingResult` e runtime; stato ricontrollato sui sorgenti correnti, perché il grafo risale al 29 settembre.

NPZ VIS preesistente: 1.628.169 righe, nessuna identità/split. Training e ricerca usavano split 80/20 di sviluppo; nessun test finale. Bundle limitati a un profilo/range. Sei MC VIS locali, nessun MC UV. Il test VIS del piano 05 era già stato aperto: non riusato come nuovo test intatto.

Riutilizzati feature canoniche, detector, `fit_stage1`, pesi/canali, pairing senza 6C, diagnostica appaiata e toy del piano 05. Context7 consultato sui limiti dello split per righe e sul raggruppamento delle origini in scikit-learn 1.9.0.

Generati **100.000 eventi per canale**, 9 canali UV e 6 VIS: 1.500.000 totali. Canali sopra soglia VIS esclusi per cinematica, identicamente nelle due strategie. Copie dei generatori nella campagna hanno seed espliciti per `TRandom3` e `gRandom`; originali invariati. Gli archivi MC con SHA permettono di ripetere la selezione; una nuova scrittura ROOT può avere hash diverso per metadati del file.

Origine = SHA-256 del ROOT genitore + entry originale, prima del photon-loss. Profilo, canale e variante detector separati. Copie ripesate o con photon-loss diverso conservano origine. Un nuovo ROOT con smearing differente richiede una mappa al genitore: il solo hash di due file diversi non prova se rappresentano le stesse origini fisiche.

Split 60/20/20 assegnato alle origini generate, stratificato per canale. Copie dello stesso sorgente nei due profili ricevono la medesima assegnazione. Il filtro detector non rinumera le righe. Audit globale dopo unione/caricamento rifiuta origini in split differenti. Test automatico copre copie fra profili/varianti e permutazione delle righe.

| Profilo | Sopravvissuti 4γ | Train | Validation | Test | Peso zero, tutti gli split |
|---|---:|---:|---:|---:|---:|
| UV | 265.073 | 159.254 | 52.942 | 52.877 | 5.634 |
| VIS | 163.073 | 97.762 | 32.540 | 32.771 | 5.216 |
| Totale | 428.146 | 257.016 | 85.482 | 85.648 | 10.850 |

**Intersezioni train/validation/test tutte zero.** I conteggi includono pesi zero; test a peso positivo: 51.719 UV e 31.721 VIS.

Spettro misurato solo su subset di run preselezionati: UV 106 run training / 72 riservati; VIS 66 / 44, intersezioni nulle. Questi run erano già presenti nelle analisi storiche: separazione prospettica per questo studio, non indipendenza dall'intera storia dell'analisi. Nessuna estrazione finale sui run riservati eseguita.

Densità MC, affidabilità dei bin, accettanze e quote dei canali stimate **solo sulle origini training**; medesima trasformazione su validation/test. Target: spettro dei preselezionati, non flusso incidente. Conservati convenzione di densità sui sopravvissuti, σ/BR e limiti fisici del [piano 05](2026-10-13-bdt-background-audit.md), senza correzioni implicite.

Prior segnale 0,5; peso dei profili esattamente 50/50 in ogni partizione comune. Baseline sulle stesse righe del rispettivo profilo. Pesi a media uno per partizione; quote dei canali derivate dal training. `beam_E` resta una delle 26 feature; nessuna etichetta UV/VIS aggiunta all'input.

Domini: UV [1,10; 1,50] GeV, VIS [0,9313; 1,10] GeV. Nessuna prova su UV basso. Tre fit con 100 alberi, profondità 5, learning rate 0,05, subsample/colsample 0,8, seed 20261013. Budget di ricerca zero per tutte le strategie: non confronto fra modelli massimamente ottimizzati.

## Risultati sul test intatto

Soglie F1 validation: UV **0,42366834**, VIS **0,52708543**, comune **0,44829146**. Quella comune è identica nei due profili.

| Profilo / modello | AUC pesata | Average precision | Efficienza segnale BDT | Rigetto fondo BDT |
|---|---:|---:|---:|---:|
| UV / separato | 0,995903 | 0,994785 | 0,991031 | 0,965711 |
| UV / comune | 0,995639 | 0,994187 | 0,989973 | 0,964395 |
| VIS / separato | 0,999428 | 0,999277 | 0,997920 | 0,992490 |
| VIS / comune | 0,999389 | 0,999285 | 0,999023 | 0,990347 |

Δ efficienza segnale comune−separato: UV −0,001058 ± 0,000508; VIS +0,001103 ± 0,000618. Aumento di accettazione del fondo: UV +0,001317 ± 0,000503; VIS +0,002144 ± 0,000296. Errori appaiati condizionati a pesi/modelli fissati, non incertezze fisiche totali.

Secondario fissato prima del test: per ogni modello/profilo, soglia con almeno 80% d'efficienza segnale **su validation**. Sul test:

| Profilo / modello | Efficienza segnale | Rigetto fondo |
|---|---:|---:|
| UV / separato | 0,794733 | 0,994009 |
| UV / comune | 0,798634 | 0,993590 |
| VIS / separato | 0,800109 | 0,999167 |
| VIS / comune | 0,797698 | 0,998997 |

Non si forza uguaglianza dell'efficienza sul test. Le soglie secondarie sono etichettate e non sostituiscono quella primaria del bundle.

RMS pesato della differenza di score: 0,02103 UV, 0,02141 VIS. Disaccordo decisioni primarie: 0,2702% UV, 0,2185% VIS. Metriche per energia/canale e distribuzioni prima/dopo disponibili negli artefatti.

## Selezione senza 6C e toy appaiato

Tagli: χ²<10, risoluzione relativa 0,08; energie mesoni ≤ fascio; |M(missing)−mₚ|<0,06 GeV. Efficienze condizionate agli eventi MC con quattro fotoni osservati, non efficienze assolute detector.

| Profilo / canale | BDT separato + tagli | BDT comune + tagli |
|---|---:|---:|
| UV / segnale ηπ⁰ | 0,617685 | 0,617685 |
| UV / π⁰π⁰ | 0,040255 | 0,040141 |
| UV / 3π⁰ | 0,026464 | 0,026460 |
| VIS / segnale ηπ⁰ | 0,766084 | 0,766260 |
| VIS / π⁰π⁰ | 0,022455 | 0,027038 |
| VIS / 3π⁰ | 0,007176 | 0,008472 |

VIS: Δ efficienza π⁰π⁰ = **+0,004584 ± 0,001043**; 3π⁰ = +0,001296 ± 0,000445. AUC elevata non rende equivalenti le selezioni. Zero sopravvissuti di alcuni fondi non certifica assenza fisica; errore empirico nullo fra maschere identiche non è un limite sulla contaminazione.

200 pseudoesperimenti appaiati per profilo, 2.000 eventi prima dei tagli, P=0,6, Σ segnale=0,3, Σ fondi=0. Stesse estrazioni casuali nelle strategie. Toy del momento in φη di laboratorio, condizionato a detector/miscela: **non** fit ratio/likelihood, polarizzazioni effettive, flussi o covarianze di produzione.

| Profilo / modello | Bias grezzo | Errore MC sul bias | Coverage nominale 68% |
|---|---:|---:|---:|
| UV / separato | −0,048358 | 0,005636 | 0,695 |
| UV / comune | −0,048213 | 0,005641 | 0,690 |
| VIS / separato | −0,100287 | 0,006064 | 0,400 |
| VIS / comune | −0,100612 | 0,006034 | 0,385 |

Δ toy comune−separato: UV +0,000146, deviazione standard fra repliche 0,003331; VIS −0,000325, deviazione standard 0,003319. Matrici 2×2 appaiate e repliche conservate. Queste deviazioni non sono errori sulla media delle 200 repliche. Risposta angolare MC circa 0,858 UV e 0,644 VIS; nessuna correzione del toy applicata ai dati. Bias e coverage non convalidano fisicamente né modello comune né baseline.

## Codice e prove

`Stage1Rows` aggiunge schema opzionale 2 preservando lettura legacy. Builder `--record-origins` salva hash/entry e detector; NPZ legacy utilizzabili dal percorso storico, non certificabili per questo confronto. `training_indices` serve fit e grid search; dataset identificati senza split persistito vengono rifiutati.

Bundle comune dichiara domini, miscela, digest dataset/split, seed, criterio soglia e stato `diagnostic_only`. Gate rifiuta range non coperti. Dominio attraversa provenienza ROOT e verifica dell'estrazione senza fallback legacy. Launcher/cache di produzione restano sui modelli separati; studio con comando dedicato e directory nuova.

Driver: [`scripts/compare_shared_bdt.py`](../../scripts/compare_shared_bdt.py).

```bash
python3 -m scripts.compare_shared_bdt \
  --uv-mc-dir results/shared-bdt-20261013/diagnostic/uv/mc \
  --vis-mc-dir results/shared-bdt-20261013/diagnostic/vis/mc \
  --uv-selected test_data/selected/analisi_1998_uv.root \
  --vis-selected test_data/vis/selected/analisi_1999_vis.root \
  --output results/shared-bdt-20261013/nuova-comparazione --nthread 4

python3 -m pytest -q -p no:cacheprovider
```

**257 test mirati passati; suite completa: 960 passati**, un warning preesistente di legenda vuota in `test_closed_gate_writes_full_coverage_report`. Dopo adeguamento digest del builder a Python 3.10 e rafforzamento del test sulle entry sopravvissute: ulteriori 29 test pertinenti passati. Smoke reale `--record-origins`: 162.692 righe VIS, non usato nel confronto.

Verificati seed/ordine, copie fra profili, canale incoerente per origine, intersezioni, round-trip NPZ/bundle, pesi invalidi, fit invariato cambiando test, riferimento MC congelato, soglie pesate e compatibilità legacy/runtime. Review indipendente: nessun problema concreto critico/importante. NumPy 2.5.0, scikit-learn 1.9.0, XGBoost 3.2.0, uproot 5.7.4.

## Decisioni e limiti residui

- Checkout corrente conservato: dipendenze precedenti non committate; nessuna modifica altrui annullata, nessun commit/merge. Copiare solo HEAD avrebbe omesso dipendenze necessarie.
- Nuovi MC con seed nelle sole copie archiviate: precisione limitata dai 100.000 eventi per canale, detector semplificato e pesi non validati.
- Iperparametri fissi senza ricerca: test protetto e confronto riproducibile, non prova di ottimalità. Nessun margine di equivalenza fisica inventato.
- Strati con meno di cinque origini rifiutati; validazione annidata per piccoli campioni **non implementata**. Campagna corrente ha statistica sufficiente per tre partizioni.
- Run riservati già osservati storicamente: nessuna certificazione retroattiva d'indipendenza. Servono disegno prospettico, fondi concordati, detector validato e injection negli stimatori Σ reali.
- Mancano confronto finale Σ sui dati reali e covarianza appaiata completa. Calibrazioni/polarizzazioni UV/VIS restano distinte; modelli correnti non sostituiti.

**Esito:** infrastruttura e confronto diagnostico consegnati. Modello comune utilizzabile nei domini dichiarati; equivalenza fisica e adozione in produzione non dimostrate.
