# Pipeline ed entry point

L'entry point principale è l'orchestratore Python checkpoint-aware:

```bash
graal-pipeline
python -m graal_pipeline
```

Senza argomenti apre il wizard in italiano. La CLI non interattiva consente di
ispezionare gli artifact, costruire un piano riproducibile, eseguire
l'estrazione e validare la stessa pipeline con profili isolati.

La guida completa è [Orchestratore della pipeline](pipeline-orchestrator).

## Flusso principale

| Area | Stadi | Output principale |
|---|---|---|
| Preparazione dati | preanalisi, selezione eventi | tree `h80` e `h85` |
| Preparazione modello | generazione MC, spettro, feature, grid search, training | NPZ e bundle Stage-1 |
| Calibrazione | energia degli strip e flusso per run | bundle CSV/JSON validato |
| Ricostruzione dati | χ², BDT raw, BDT con fit, sideband | ROOT sotto `results/<final-state>/reconstruction/` |
| Ricostruzione MC segnale | generazione, adapter h85, sideband | ROOT di controllo del segnale |
| Osservabile | prima passata e asimmetria completa | ROOT e PDF sotto `results/<final-state>/observables/` |

Il planner parte dal target finale e risale il grafo. Un artifact `FRESH` viene
riutilizzato; uno `MISSING` viene prodotto; un artifact `INVALID`, `STALE`,
`OLD` o `UNTRACKED` segue le regole documentate nella guida. Non occorre
scegliere manualmente lo stadio da cui iniziare.

## Esempi

Controllare lo stato senza modificare file:

```bash
graal-pipeline status --final-state eta_pi0
```

Preparare un piano esplicito per un job batch:

```bash
graal-pipeline plan extract beam-asymmetry \
  --final-state eta_pi0 \
  --non-interactive \
  --old-policy reuse \
  --stale-policy rebuild \
  --untracked-policy rebuild
```

Eseguire la produzione:

```bash
graal-pipeline extract beam-asymmetry \
  --final-state eta_pi0 \
  --non-interactive --yes \
  --old-policy reuse \
  --stale-policy rebuild \
  --untracked-policy rebuild
```

## Entry point dei singoli componenti

I moduli sottostanti restano utilizzabili per sviluppo e diagnosi mirate:

```bash
python -m mc_simulation.mc_status --data-dir 03_mc_simulation/data
python -m bdt_training.beam_spectrum --help
python -m bdt_training.build_background_features --help
python -m bdt_training.grid_search_stage1 --help
python -m bdt_training.train_bdt_stage1 --help
python -m reconstruction.reconstruct_eta_pi0_chi2 --help
python -m reconstruction.reconstruct_eta_pi0_bdt --help
python -m reconstruction.reconstruct_2pi0 --help
python -m observable_extraction.beam_asymmetry --help
```

Un'esecuzione diretta non crea i checkpoint dell'orchestratore. Per produzione
e validazione integrata è quindi preferibile `graal-pipeline`.

## Migrazione

I precedenti runner shell restano temporaneamente nella repository perché il
gate di rimozione richiede uno smoke test completo su fixture ROOT reali
ridotte. Il fixture `test_data/raw/**/*.root` non è attualmente disponibile.
Per nuovi job e nuova documentazione operativa va utilizzata l'interfaccia
Python; i dettagli del gate sono riportati nella guida dell'orchestratore.
