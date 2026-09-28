# Testing

La repository combina test unitari, test contrattuali, test degli adapter e
validazioni d'integrazione su dati ROOT reali.

## Suite automatica

```bash
pytest -q
```

`pyproject.toml` raccoglie i test da:

```text
tests/
00_common/tests/
03_mc_simulation/tests/
04_bdt_training/tests/
05_reconstruction/tests/
06_plots/tests/
06_observable_extraction/tests/
```

`--import-mode=importlib` impedisce collisioni fra i package `tests` presenti
nelle directory numerate.

## Aree coperte

| Area | Copertura principale |
|---|---|
| `tests/` | Packaging, configurazione, grafo della pipeline, checkpoint, planner, runner, CLI, wizard e contratti tra package |
| `00_common/tests/` | Registry fisico, pairing, manifest, schemi degli artifact e calcolo strip/flux |
| `03_mc_simulation/tests/` | Contratti dei generatori e stato dei campioni MC |
| `04_bdt_training/tests/` | Reweighting, feature, NPZ, training, report e facade CLI |
| `05_reconstruction/tests/` | Decisioni evento, pairing, fit cinematico, adapter ROOT e gate BDT |
| `06_plots/tests/` | Cinematica, adapter dati e orchestrazione dei grafici |
| `06_observable_extraction/tests/` | Join del flusso, estimatori Sigma, sideband, bootstrap, covarianze e prodotti ROOT/PDF |

La maggior parte dei test di fisica e degli schemi non richiede ROOT. I test
dei bordi ROOT usano fixture minime generate localmente quando verificano un
contratto isolato. La generazione MC su scala di produzione e la scansione dei
dati del rivelatore non fanno parte della suite ordinaria.

## Test dell'orchestratore

I test `tests/test_pipeline_*.py` verificano in particolare:

- risoluzione dei path rispetto alla root della repository e rifiuto degli
  escape tramite `..` o link simbolici;
- grafo aciclico, ordine deterministico e dipendenze opzionali;
- fingerprint deterministici anche con Git assente o file responsabili sporchi;
- stati `FRESH`, `OLD`, `UNTRACKED`, `STALE`, `MISSING` e `INVALID`;
- policy interattive e non interattive;
- lock live e stale senza rimozione automatica;
- continuazione dei rami indipendenti dopo un fallimento;
- staging, validazione e pubblicazione atomica;
- recupero `UNTRACKED` dopo un crash tra pubblicazione e checkpoint;
- equivalenza fra `graal-pipeline` e `python -m graal_pipeline`;
- isolamento dei profili `smoke` e `farm`.

I vecchi test contrattuali dei runner shell restano temporaneamente presenti
finché il gate di migrazione non viene completato su dati reali ridotti.

## Smoke test con dati reali ridotti

Il profilo `smoke` richiede almeno un file ROOT reale rappresentativo sotto
`test_data/raw/`:

```bash
mkdir -p test_data/raw
# Copiare qui uno o più run ridotti dalla farm.

graal-pipeline validate beam-asymmetry \
  --final-state eta_pi0 \
  --profile smoke \
  --non-interactive \
  --old-policy rebuild \
  --stale-policy rebuild \
  --untracked-policy rebuild
```

Gli output vengono scritti in
`results/validation/smoke/<run-id>/`. Il profilo usa verifica `full`, riduce il
numero di eventi MC e le repliche bootstrap, ma non sostituisce input di fisica
con file sintetici. Il suo report dimostra integrazione software, non validità
fisica o calibrazione definitiva.

Se `test_data/raw/**/*.root` è assente, il comando termina prima della
pianificazione con istruzioni di copia e non crea output.

## Validazione completa sulla farm

```bash
graal-pipeline validate full \
  --final-state eta_pi0 \
  --profile farm \
  --non-interactive \
  --old-policy rebuild \
  --stale-policy rebuild \
  --untracked-policy rebuild
```

Il profilo `farm` usa il grafo di produzione, verifica completa, dimensioni
nominali per MC e bootstrap e output isolati in
`results/validation/farm/<run-id>/`. È un'operazione esplicita e potenzialmente
lunga; non viene avviata da `pytest`.

## Limiti delle prove

Una suite automatica verde dimostra contratti software e regressioni note. Lo
smoke test dimostra compatibilità dei file, dei tree, dei branch e degli entry
point su un campione reale ridotto. Solo una validazione farm completa, insieme
ai controlli scientifici dell'analisi, può sostenere l'uso dei risultati di
produzione.
