# 2 — asimmetrie per periodo

> Piano eseguito il 13 ottobre 2026 con `superpowers:executing-plans`.

**Obiettivo:** salvare Σ, errori e diagnostica per tutti i periodi presenti, conservando aggregati.

**Architettura:** usare `RunRecord.source_period` e stesso motore Stage 07 con maschera condivisa su eventi/esposizioni. Preferire stesso schema ROOT in directory per periodo, evitando una seconda implementazione dello stimatore. **Stack:** Python, NumPy, PyROOT. **Spec:** [README](README.md), [audit](00-stato-verificato.md).

## Già fatto, invarianti e dipendenze

`config/run_manifest.csv` contiene periodi precisi (`1998_uv`, `1999_uv`, `1999_vis`, ecc.). Gli output Σ verificati non hanno identificazione di periodo. “1999” resta eventualmente gruppo annuale esplicito; non unire UV/VIS o P/D implicitamente.

Dipende da baseline senza 6C; per significatività di differenze usa punto 1. Eventi, triplette flusso e periodo devono condividere stesso universo di run. Bin e convenzioni fissi rendono confrontabili i periodi. Aggregato è nuova estrazione su unione di eventi/esposizioni, non media semplice delle Σ.

## File candidati

- `07_observable_extraction/beam_asymmetry.py`: selezione periodi, iterazione sui gruppi effettivi e produzione aggregata.
- `07_observable_extraction/calibration/flux_v2.py`: restrizione coerente dei run, riuso dei controlli esistenti.
- `io/root_output.py`, `io/root_input.py`: metadati periodo, universo run e mappa punti; non introdurre ramo se directory+provenance soddisfano contratto.
- `scripts/run_pipeline.py`, `scripts/plot_campaign.py`, `plotting/diagnostics.py`: integrazione output e stabilità.
- Test `test_beam_asymmetry_cli.py`, `test_calibration_io.py`, `test_root_output.py`; nuovo `test_period_extraction.py` solo se separa responsabilità utile.

## Passi e prove

- [x] Join run degli input al manifest. Tabella per periodo: disponibili, selezionati, esclusi, stati, flussi, missing; errore su run ambiguo/sconosciuto invece di classificazione dal nome del file.
- [x] Estrarre periodo con stesso selettore usato dall'aggregato; mantenere strati a zero yield nell'universo definito. Salvare `periods/<source_period>/beam_asymmetry.root`, più ROOT aggregato e indice dei periodi con stato.
- [x] Salvare per periodo conteggi V/H/BREM, esposizioni, polarizzazioni effettive, chiavi bin, covarianze e cutflow. Periodo senza fit valido deve comparire come non stimabile, non sparire o avere Σ=0.
- [x] Ricostruire aggregato dall'unione disgiunta di run e confrontarlo con percorso nominale: stessi eventi/esposizioni, Σ entro tolleranza numerica e stesso insieme di bin stimabili.
- [x] Grafici stabilità a bin confrontabili. Se confrontato periodo con aggregato che lo contiene, usare covarianza incrociata o confronto leave-one-period-out. Nuisance globali restano correlati tra periodi.
- [x] Test due periodi con Σ diverse, uno senza POL2, uno senza eventi, run sconosciuto e confini energetici; round-trip ROOT. Non richiedere uguaglianza fra media aritmetica delle Σ e aggregato.

```bash
python3 -m pytest -q 06_calibration/tests/test_run_manifest.py \
  07_observable_extraction/tests/test_calibration_io.py \
  07_observable_extraction/tests/test_beam_asymmetry_cli.py \
  07_observable_extraction/tests/test_root_output.py \
  07_observable_extraction/tests/test_period_extraction.py
```

**Consegna:** ROOT aggregato/per-periodo, indice e relazione con conteggi e differenze. Limite attuale: manifest inventariato, ma non tutti i periodi hanno input locali verificati. Nessuna promessa di risultato per periodi privi di dati o statistica.

## Esito del 13 ottobre 2026

Implementazione e campagna locale completate; [relazione, prove e limiti](../../reports/2026-10-13-period-extraction.md). Disponibili 1998_uv e 1999_vis, altri periodi indicizzati come assenti. Chiusura unione/aggregato esatta; confronto multiperiodo verificato con toy. Inferenza finale del punto 01 resta sospesa.
