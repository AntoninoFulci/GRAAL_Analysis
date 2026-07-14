# Dati di test

Una o due run grezze, per collaudare la catena intera su una macchina di
sviluppo senza toccare i dati di produzione.

Le sottocartelle hanno gli stessi nomi che hanno sul server: quello che provi
qui è letteralmente quello che girerà là, cambia solo la radice.

```
test_data/
    raw/            <- ci metti tu 1-2 run grezze
    pre_analyzed/   <- prodotto dallo stage 1 (albero h80)
    selected/       <- prodotto dallo stage 2 (albero h85)
    analyzed/       <- prodotto dallo stage 7 (reco chi2 + BDT)
```

## Cosa copiare

Da `/data/graal/graal_data/` sul server, prendi **una o due directory di run**
intere — non i singoli file:

```bash
scp -r <server>:/data/graal/graal_data/<nome_run> test_data/raw/
```

La struttura attesa è una cartella per run, con dentro i `.root` grezzi:

```
test_data/raw/
    <nome_run>/
        *.root
```

Scegli una run piccola: la pre-analisi le legge tutte.

## Come si lancia

```bash
./run_pipeline.sh --test-data --skip-mc --skip-train
```

Fa la catena intera — pre-analisi, selezione, ricostruzione chi2 e BDT — usando
il Monte Carlo e il modello BDT **veri**: duplicarli non proverebbe nulla di più
e costerebbe ore. Niente di quello che produce esce da `test_data/`.

## Nota su git

Il contenuto di queste cartelle non è versionato: sono file di dati, pesanti, e
ognuno usa le proprie run. In git stanno solo questo README e lo scheletro delle
cartelle.
