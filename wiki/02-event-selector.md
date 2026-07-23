# 02 — Selezione eventi

`02_event_selector/select_events.py` è la seconda fase della pipeline: legge l'output della pre-analisi (`h80`) e tiene solo gli eventi selezionati.
Per ora sono quelli che hanno una possibilità concreta di essere ricostruiti come γp → p η π⁰ scartando il resto prima che arrivi alla fase più costosa.

## La selezione

```python
if (
    event.gammas.size() > 1 and
    event.fcharged_theta.size() == 1
):
    selected_tree.Fill()
```

Due condizioni, entrambe necessarie:

- **più di un fotone** (`gammas.size() > 1`)
- **esattamente una traccia carica forward** (`fcharged_theta.size() == 1`)
  il barione di rinculo così come lo vede il rivelatore forward, contato dalle sue tracce cariche: non zero (nessun rinculo) e non due o più (evento ambiguo o doppio conteggio).
  Il taglio è sul numero di quelle tracce, non sui rami `protons`/`neutrons`/`deuterons`: un rinculo neutro (neutrone) non lascia una traccia carica forward e quindi non entra in questo conteggio.

## Perché `h80` diventa `h85`

```python
selected_tree = tree.CloneTree(0)
selected_tree.SetName(OUTPUT_TREE)   # "h85"
selected_tree.SetTitle(OUTPUT_TREE)
```

`CloneTree(0)` crea un nuovo `TTree` con lo stesso schema dei rami dell'originale, ma senza copiare gli eventi; questi vengono aggiunti successivamente con `Fill()` durante il loop di selezione. Poiché il clone mantiene inizialmente lo stesso nome del `TTree` sorgente, è necessario usare `SetName()` per distinguerlo. In questo caso il nome viene cambiato in `h85` per indicare che contiene gli stessi rami di `h80`, ma solo gli eventi che hanno superato il filtro.


## CLI

```bash
python -m event_selector.select_events \
    --input-dir  pre_analyzed \
    --output-dir selected
```

| Argomento | Default | Effetto |
|---|---|---|
| `--input-dir` | `pre_analyzed` | cartella con i file `pre_*.root` |
| `--output-dir` | `selected` | cartella di output (creata se non esiste) |


## Fail loud su zero file in input

```python
root_files = [
    f for f in os.listdir(args.input_dir)
    if f.endswith(".root") and f.startswith("pre_")
]
if not root_files:
    raise RuntimeError(
        f"no files matching 'pre_*.root' in {args.input_dir!r}; {found_desc}. "
        "Refusing to run stage 6 against stale files already in "
        f"{args.output_dir!r}."
    )
```

Se `--input-dir` non contiene alcun file `pre_*.root`, lo script termina con un `RuntimeError` anziché produrre un output vuoto. Questo evita che la fase successiva utilizzi inconsapevolmente file residui di esecuzioni precedenti, prevenendo risultati apparentemente validi ma basati su dati obsoleti.


Ogni file viene aperto con un controllo esplicito (`IsZombie()`, presenza dell'albero `h80`): un file corrotto o senza l'albero atteso fa fallire subito con un `RuntimeError` che elenca le chiavi trovate nel file, invece di proseguire silenziosamente con un albero vuoto o `None`.
