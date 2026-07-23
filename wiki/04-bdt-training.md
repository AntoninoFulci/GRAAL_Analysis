# 04 — Training BDT

`04_bdt_training/` addestra il classificatore che il gate di
[`05_reconstruction/stage1_gate.py`](05-reconstruction-bdt-gate) applica prima della
combinatoria chi2: un BDT binario (XGBoost) che impara a distinguere il
segnale η π⁰ dal fondo fisico prima ancora che si tenti di ricostruirlo.

## A cosa serve

Rigettare eventi di fondo palesemente non-segnale *prima* della
ricostruzione, riducendo la contaminazione nel campione finale rispetto al
solo taglio chi2. Il modello non sostituisce il chi2 — lavora a monte:
`reconstruct_eta_pi0_bdt.py` applica prima il gate, poi la stessa
combinatoria chi2 che usa `reconstruct_eta_pi0_chi2.py` (vedi
[05 — Ricostruzione](05-reconstruction)).

## Dati di addestramento

Costruiti da `build_background_features.py` (vedi
[Feature stage-1](04-bdt-training-features) per il dettaglio delle 26
feature) a partire dai nove canali Monte Carlo di
[03 — Simulazione MC](03-mc-simulation): segnale = il canale scelto con
`--signal-channel` (etichetta 1, default `eta_pi0`), fondo = gli altri otto
(etichetta 0). Fra questi, tre sono stati aggiunti a questo campione:
`eta_via_3pi0` (un η vero che cade sul minimo del chi2 del segnale, il più
importante dei tre — vedi [03 — Simulazione MC](03-mc-simulation)),
`4pi0` e `eta_pi0_via_3pi0` (la reazione di segnale con l'η che decade a
3π⁰ invece che a 2γ, vincolato al segnale via i branching ratio PDG anziché
avere una sezione d'urto propria).

Tutti pesati non per la sezione d'urto piatta del registry, ma per quella
sezione d'urto **integrata sul flusso del fascio misurato**, sulla forma
`sigma(E)` del canale, e sull'accettanza del rivelatore — vedi
[03 — Simulazione MC](03-mc-simulation) per la formula e per la ragione di
dividere per il conteggio generato (`n_gen`) invece che per il totale dei
sopravvissuti. `--beam-spectrum` è **obbligatorio**: senza uno spettro
misurato non c'è integrale di flusso su cui basare i pesi.

**Tutti e nove passano per lo stesso modello di perdita fotoni**, segnale
incluso. Prima il segnale lo saltava, con la motivazione che η→γγ e π⁰→γγ danno
già esattamente 4 fotoni: ma la perdita non è solo il conteggio, è l'accettanza
del rivelatore. Saltarla lasciava il 15% dei fotoni di segnale a θ<25°, dentro
il buco del fascio, dove il BGO non vede niente e dove i dati veri hanno
esattamente zero fotoni — mentre ogni fotone di fondo era già stato filtrato
sull'accettanza. Il modello di rivelatore diventava così funzione dell'etichetta
di classe, e il BDT poteva separare su *quale* modello di perdita fosse stato
applicato invece che sulla fisica. Solo il 28% del segnale MC sopravvive
all'accettanza a cui i fondi sono sottoposti: l'altro 72% erano eventi che
l'esperimento non poteva registrare come 4γ.

## Metriche correnti

Da `04_bdt_training/model/stage1_metrics.txt` (valori reali, non da fidarsi
di numeri citati altrove — questo file è la fonte):

```
Signal:    eta_pi0
Hypothesis:eta_pi0
Prior:     0.5  (a training choice, not a cross-section)
Beam rewt: True
AUC:       0.9991
Threshold: 0.9654
Precision: 0.8558
Recall:    0.9073
F1:        0.8808
N_train:   2112953
N_val:     528239
```

La soglia operativa (`04_bdt_training/model/stage1_threshold.txt`) è scelta
massimizzando l'F1 su un set di validazione (`_find_best_threshold` in
`train_bdt_stage1.py`, ricerca su 200 punti tra 0.01 e 0.99) — non è un valore
fissato a mano, viene ricalcolata a ogni training.

Vale la pena registrare cosa il passaggio ai nove canali con pesi integrati
sul flusso ha fatto alle metriche. L'AUC è rimasta altissima (0.9991), ma
precision e recall sono **scese** rispetto a prima (0.86/0.91 contro 0.94/0.96),
e la soglia operativa è salita a 0.965. Non è un peggioramento: è onestà. Il
nuovo fondo dominante è `eta_pi0_via_3pi0` — la stessa reazione del segnale con
l'η che decade in 3π⁰ invece che in 2γ — e un suo evento a 8 fotoni che ne
perde 4 si ricostruisce con una massa η e una massa π⁰ reali, cadendo *sul*
minimo del χ² del segnale invece che nelle code. Sono eventi genuinamente
confondibili che il vecchio campione semplicemente non conteneva; le metriche
di prima erano ottimistiche perché non vedevano mai la contaminazione più
pericolosa.

## Dimensione efficace del campione

Il riepilogo della fase 4 stampa la **Kish effective sample size**: quanti
eventi di peso uguale vale il campione riponderato.

```
Effective sample size: 475512 of 2641192 (18.0%)
Dropped by reweighting: 212726 events (8.05%)
```

Non è una curiosità. Riponderare costa sempre un po' di potere statistico, ma
una prima versione della riponderazione lo aveva ridotto all'**1.2%**: 128
eventi su 1.9M portavano il 3.3% di tutto il peso, perché al bordo di soglia il
MC ha solo la coda di smearing del tagger e il rapporto p_data/p_mc arrivava a
1994 (vedi `beam_spectrum.reweight`). Un campione così sembra fatto di milioni
di eventi e si comporta come se ne avesse migliaia, e nient'altro nella catena
lo direbbe. Se questo numero scende sotto il 10%, la fase 4 avverte.

## Perché i pesi hanno media 1

I pesi finiscono normalizzati a media 1, conservando ogni rapporto fra loro.
Solo i rapporti portano fisica, quindi la scala assoluta dovrebbe essere
irrilevante — e non lo è: XGBoost misura `min_child_weight` in somma di
hessiane, che scala col peso dell'evento. Con le quote per canale che sommavano
a 1 sull'intero campione (~5e-7 per evento) nessuno split raggiungeva mai
`min_child_weight >= 1`, xgboost restituiva un moncone, e tutte e 30 le
configurazioni della grid search tornavano ad **AUC 0.5000**. Senza errori.
Sembrava che le feature non valessero nulla, e invece erano i pesi troppo
piccoli.

## Grid search

```bash
python -m bdt_training.grid_search_stage1 \
    --features 04_bdt_training/data/features_stage1.npz \
    --out-dir  04_bdt_training/model \
    --n-iter   30
```

Cerca su una griglia di iperparametri:

```python
_PARAM_GRID = {
    "max_depth":        [3, 4, 5, 6],
    "learning_rate":    [0.05, 0.10, 0.15, 0.20],
    "subsample":        [0.7, 0.8, 1.0],
    "colsample_bytree": [0.7, 0.8, 1.0],
    "min_child_weight": [1, 5, 20],
    "gamma":            [0.0, 0.1, 0.3],
}
```

La griglia completa (prodotto dei sei elenchi sopra) è 4×4×3×3×3×3 = 1296
combinazioni — più delle "108 combos" citate nel docstring del modulo, che
è rimasto indietro rispetto alla griglia effettiva. Di default esegue una
ricerca randomizzata (`--n-iter` configurazioni campionate a caso, 30 di
default), con `--full-grid` per enumerarle tutte. Ogni configurazione usa
XGBoost early stopping (`_EARLY_STOPPING_ROUNDS = 20`, cap a
`_N_ESTIMATORS_MAX = 400` alberi) per restare veloce. Il risultato migliore
va in `best_hyperparams.json`, il riepilogo completo in
`grid_search_results.csv`.

## Training

```bash
python -m bdt_training.train_bdt_stage1 \
    --features 04_bdt_training/data/features_stage1.npz \
    --out-dir  04_bdt_training/model \
    [--hyperparams 04_bdt_training/model/best_hyperparams.json]
```

Se `--hyperparams` è passato, il JSON prodotto dalla grid search sovrascrive
`--n-estimators`, `--max-depth`, `--lr` e gli altri iperparametri di
default. Il training usa `sample_weight` dalle sezioni d'urto, valuta AUC su
un set di validazione (`--val-fraction`, 0.2 di default), sceglie la soglia
operativa per F1 massimo, e scrive:

| File | Contenuto |
|---|---|
| `bdt_stage1.json` | il booster XGBoost |
| `stage1_threshold.txt` | soglia operativa (scalare) |
| `stage1_metrics.txt` | AUC, soglia, precision, recall, F1, N_train, N_val |
| `stage1_roc.png` | curva ROC |
| `stage1_feature_importance.png` | importanza delle 26 feature (gain) |
| `stage1_score_dist.png` | distribuzione degli score, segnale vs fondo |

## Come ri-addestrare

`run_pipeline.sh` incatena le tre fasi (build feature → grid search →
training) come fasi 4-6 — vedi [Pipeline](pipeline) per i flag
(`--skip-features`, `--skip-grid-search`, `--grid-search-niter`,
`--skip-train`). Per rifare solo l'addestramento senza rigenerare l'MC o le
feature, i due comandi sopra bastano da soli, a patto che
`04_bdt_training/data/features_stage1.npz` esista già.

## Dove andare da qui

- [Feature stage-1](04-bdt-training-features) — le 26 feature nell'ordine
  reale del vettore, e la regola contro cui il bug del gate ha reagito.
