# Stage 07 — flussi mancanti: implementazione e audit locale

Data: 13 ottobre 2026.

## Software consegnato

Nuovo package `flux_studies` in `07_flux_studies/`; osservabili spostati in
`08_observable_extraction/`, mantenendo gli import `observable_extraction`.
Sono stati preservati i 52 file presenti nella vecchia directory, inclusi file
non tracciati. Mapping editable locale aggiornato senza scaricare dipendenze.

Audit ROOT conserva cicli, difetti, contenuti per strip, assi e motivi multipli.
Calibrazione salva un sidecar QA legato all'hash del ROOT e agli input. Sidecar
assente o non corrispondente non autorizza deduzioni sulla copertura h80.
Studio include donor vicino, template medio/mediano, interpolazione e Ridge;
split temporali per run, tuning annidato, intervalli esplorativi da bootstrap
e residui training-only, repliche allineate e metriche appaiate con denominatori.
ROOT di studio e sintetici hanno namespace separati dalla produzione.

Launcher: `--flux-study off|audit|study`, default off; metadati tramite
`--flux-study-metadata`. CLI standalone funziona anche senza calibrato.
Guida: [missing-flux](../runbooks/missing-flux.md).

## Risultato sui dati locali

Comando eseguito:

```bash
python -m flux_studies.study_missing_flux \
  --manifest config/run_manifest.csv \
  --raw-flux data/00_external/flux.root \
  --calibrated-flux data/00_external/flux_calibrated.root \
  --output-dir results/missing-flux-study-20261013/missing_flux
```

- 1.831 run P selezionati, 5.493 righe run/stato.
- Tutti i run hanno una chiave grezza per POL1/POL2/BREM: nessun missing raw.
- 1.290 run hanno tripletto calibrato completo; 541 almeno uno stato assente.
- Mancano 842 istogrammi nel calibrato locale. Non sono flussi grezzi mancanti.
- 299 istogrammi grezzi, distribuiti su 257 run, contengono valori negativi.
  Audit li conserva e segnala; non li trasforma in candidati sintetici.
- QA storica non fornita: cause di mancata copertura non certificate.
- Metadati acquisizione assenti: `status=not_executable`; nessuna predizione
  sperimentale e nessun `synthetic_flux.root` prodotti sui dati reali.
- Hash di manifest, grezzo e calibrato identici prima/dopo (`input_integrity.json`).

I conteggi si riferiscono ai file indicati e alle loro identità registrate,
non a una nuova produzione. I conteggi per run coincidono con l'audit storico,
ma questa esecuzione distingue anche stati e contenuti.

| Periodo | Run | Triplette calibrate complete | Istogrammi raw negativi |
|---|---:|---:|---:|
| 1998_uv | 179 | 170 | 29 |
| 1999_uv | 339 | 282 | 30 |
| 1999_vis | 110 | 109 | 44 |
| 2000_fuv | 147 | 92 | 6 |
| 2000_uv1 | 204 | 203 | 13 |
| 2000_uv2 | 102 | 53 | 5 |
| 2000_vis | 129 | 55 | 96 |
| 2001_uv | 137 | 0 | 3 |
| 2002_uv1 | 128 | 106 | 8 |
| 2002_uv2 | 190 | 115 | 4 |
| 2002_vis1 | 94 | 83 | 29 |
| 2002_vis2 | 25 | 16 | 12 |
| 2003_vis | 47 | 6 | 20 |

## Verifica e limiti

Test dei nuovi moduli includono difetti ROOT, protezione output/input, metadati
incompatibili, BREM zero, interpolazione, causalità, esclusione della verità
mascherata dal tuning, covarianza da esposizione condivisa, coverage su un
ensemble controllato, ROOT riaperto e assenza di output sintetico senza metadati.
Grafici delle fixture ispezionati visivamente. Fixture numeriche non costituiscono
validazione sperimentale sui run GRAAL. Stato sempre esplorativo, nessuna adozione
fisica automatica e nessuna propagazione dei sintetici a Σ.

Le modifiche preesistenti sono rimaste nel working tree. Copie iniziali e registro
operativo sono in `.superpowers/sdd/2026-10-13-flux-studies/` durante la lavorazione.
La verifica iniziale della suite si è sovrapposta alla rinumerazione: quel log
non viene presentato come baseline pulita. Risultati finali e revisione indipendente
sono riportati a chiusura della verifica.

## Revisione indipendente

Revisione read-only con contesto separato: nessun rilievo Critical, cinque
Important riprodotti tramite test RED e corretti. Coprono target incompleti,
appartenenza esatta ai gruppi nei fold, nuisance comuni tra contesti, incertezza
dei donor effettivamente ricampionati e ordine temporale del bootstrap. Aggiunta
anche regressione sulla separazione delle configurazioni nel cache delle
repliche. Commento storico Stage-07 preservato. Nessun rilievo materiale
del revisore è stato lasciato aperto. La validazione fisica resta fuori giudizio
per assenza dei metadati reali, non perché i test software la dimostrino.

## Prove finali

`python -m pytest -q` nell'ambiente PyROOT compatibile: **1.014 passed**,
1 warning matplotlib relativo alla legenda di un test di confronto gate
preesistente, 141,44 secondi. Dopo gli ultimi aggiornamenti documentali, test wiki
rieseguiti. Test aggiuntivo di esclusione del ROOT sintetico dall'adapter
produttivo eseguito separatamente. Log conservati sotto
`results/missing-flux-study-20261013/verification/`.

Audit standalone disponibile anche in
`results/missing-flux-audit-20261013/missing_flux/`; conteggi concordanti con lo
studio. Nessun file sorgente preesistente perso; le modifiche che precedevano
questa attività restano preservate. Consegna nel working tree: nessun merge,
push o commit cumulativo delle modifiche preesistenti.
