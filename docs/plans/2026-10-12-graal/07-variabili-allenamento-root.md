# 7 — istogrammi delle variabili di allenamento in ROOT

> Implementato il 13 ottobre 2026 con `superpowers:executing-plans`; verifica iniziale tramite graphify. Consegna reale VIS, input UV assente. [Relazione e limiti](../../reports/2026-10-13-training-features.md).

**Obiettivo:** salvare distribuzioni di tutte le 26 feature e documentazione interna al ROOT, oltre ai plot.

**Architettura:** leggere `Stage1Dataset` validato, nomi/calcolo dal contratto comune; aggiungere exporter diagnostico nello stadio training. **Stack:** NumPy, PyROOT, matplotlib già presenti. **Spec:** [README](README.md), [variabili verificate](00-stato-verificato.md).

## Già fatto e invarianti

Esistono ROC, importance delle prime 20 feature e score distribution PNG; non equivalgono a istogrammi delle 26 feature. `training/stage1_reporting.py` non esporta queste distribuzioni in ROOT. Non modificare valori feature, ordine, modello o soglia per fare plot.

Un istogramma ponderato conserva `Σw`, errore `sqrt(Σw²)`, under/overflow e numero eventi. Istogramma normalizzato a area unitaria è copia separata; non cancellare yield originale. Unità e definizione fisica devono essere esplicite; non usare etichetta generica “GeV” per contatori, coseni o rapporti.

## File candidati

`04_bdt_training/training/stage1_reporting.py`, `train_bdt_stage1.py`, `dataset/stage1_dataset.py`; nuovo `04_bdt_training/plot_training_features.py` se serve entrypoint standalone riutilizzabile. Contratto da `00_common/stage1/features.py`. Test `04_bdt_training/tests/test_stage1_reporting.py`, nuovo `test_training_feature_root.py` per serializzazione. Documentazione dentro ROOT e nota in `wiki/04-training-artifacts.md`.

## Passi e metodo

- [x] Inventario NPZ/modello: nomi e ordine, shape X/y/w, provenance, profilo/energia, ipotesi e pesi. NPZ assente → segnalare, non simulare distribuzioni del training reale.
- [x] Definire dizionario delle 26 feature con formula, unità, tipo discreto/continuo, famiglia fisica e range. Derivare schema dal codice; annotare che `missing_mass` delle feature usa beam+target−proton, diverso dal rinculo in ricostruzione.
- [x] Istogrammi segnale/fondo, UV/VIS separati, ponderati e non ponderati; per-canale solo se identità canale realmente disponibile. Per split train/validation/test usare indici persistiti del training, non nuovo split casuale presentato come quello originale. Se vecchio dataset non conserva indici/canale, limitare plot a categorie recuperabili e dichiararlo.
- [x] Fissare bordi comuni per confronto classi/profili usando dominio fisico o solo train; bin centrati su interi per contatori. Salvare overflow/NaN e trattare errori dati esplicitamente. Non troncare code per migliorare figura.
- [x] Scrivere `training_features.root`: TH1 di yield e shape, `TNamed`/oggetto testuale con dizionario, normalizzazioni, input/hash, tagli photon-loss, seed, split, prior, versione schema e massa/ipotesi. Output separato dal bundle modello.
- [x] Render multipagina leggibile; verificare integral/Σw² contro NPZ, nomi univoci, unità e round-trip ROOT. Toy con pesi non unitari, bin discreti, overflow, feature costante, dataset/schema invalido.

```bash
python3 -m pytest -q 04_bdt_training/tests/test_stage1_reporting.py \
  04_bdt_training/tests/test_stage1_dataset.py tests/test_stage1_contracts.py
```

**Consegna:** ROOT, PDF e dizionario incorporato. Non sono nuove variabili né retraining. Split/provenance migliorati del punto 9 potranno ampliare categorie, senza bloccare l'export di ciò che è già documentabile.

## Esito del 13 ottobre 2026

Exporter riutilizzabile e CLI standalone disponibili; hook training opzionale `--feature-diagnostics-dir` in directory separata. Generati ROOT, PDF di 27 pagine e JSON dal NPZ VIS reale (1.628.169 eventi), senza retraining. I 26 nomi e le definizioni seguono il contratto condiviso; yield, Σw², eventi, flow e NaN verificati con round-trip ROOT. UV non disponibile localmente. Canale per evento, split persistiti e configurazione photon-loss assenti nel NPZ: categorie non inventate, limiti incorporati negli output.
