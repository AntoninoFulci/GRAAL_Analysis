# 02 — Selezione eventi

`02_event_selector/select_events.py` è la seconda fase della pipeline:
legge l'output della pre-analisi (`h80`) e tiene solo gli eventi che hanno
una possibilità concreta di essere ricostruiti come γp → p η π⁰ (o come
2π⁰), scartando il resto prima che arrivi alla fase più costosa.

## La selezione

```python
if (
    event.gammas.size() > 1 and
    event.fcharged_theta.size() == 1
):
    selected_tree.Fill()
```

Due condizioni, entrambe necessarie:

- **più di un fotone** (`gammas.size() > 1`) — un evento con 0 o 1 fotone
  non può fornire i quattro fotoni che la ricostruzione a due mesoni
  richiede;
- **esattamente una traccia carica forward** (`fcharged_theta.size() == 1`)
  — il barione di rinculo così come lo vede il rivelatore forward, contato
  dalle sue tracce cariche: non zero (nessun rinculo) e non due o più
  (evento ambiguo o doppio conteggio).

`fcharged_theta` è uno dei rami di servizio di `h80` (angoli delle tracce
cariche forward, vedi [Formati dati](data-formats)). Il taglio è sul numero
di quelle tracce, non sui rami `protons`/`neutrons`/`deuterons`: un rinculo
neutro (neutrone) non lascia una traccia carica forward e quindi non entra
in questo conteggio.

## Perché `h80` diventa `h85`

```python
selected_tree = tree.CloneTree(0)
selected_tree.SetName(OUTPUT_TREE)   # "h85"
selected_tree.SetTitle(OUTPUT_TREE)
```

`CloneTree(0)` copia lo schema dei rami ma non gli eventi (il `0` è il
numero di entry clonate subito); gli eventi vengono aggiunti uno a uno con
`Fill()` dentro il loop di selezione. Il punto delicato è che `CloneTree`
eredita il nome dell'albero sorgente: senza la chiamata esplicita a
`SetName`, il clone si chiamerebbe ancora `h80`, e un file "pre-analizzato"
e uno "selezionato" conterrebbero entrambi un albero chiamato `h80`,
indistinguibili senza aprire il file e controllare gli eventi. Lo schema
dei rami non cambia — nessuna colonna aggiunta o rimossa, solo eventi
filtrati — quindi `h85` non descrive un contenuto diverso, descrive lo
stesso schema dopo un filtro reso riconoscibile dal nome. Dettagli completi
dello schema in [Formati dati](data-formats).

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

Per ogni file di input (`pre_<run>.root`), lo script legge l'albero `h80`,
filtra, e scrive `selected/<run>.root` — il prefisso `pre_` viene tolto dal
nome (`filename.replace("pre_", "", 1)`).

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

Se `--input-dir` non contiene nessun file `pre_*.root`, lo script si ferma
con un `RuntimeError` invece di scrivere silenziosamente zero file in
output. Il messaggio elenca cosa ha trovato invece (fino a 10 voci) per
facilitare la diagnosi — cartella sbagliata, fase 1 non ancora girata,
prefisso sbagliato.

Questo controllo esiste perché un run silenziosamente vuoto è più
pericoloso di un run che si ferma: se `select_events.py` avesse scritto
zero file senza protestare, la fase successiva (ricostruzione) avrebbe
letto qualunque cosa fosse rimasta in `selected/` da un'esecuzione
precedente — cioè i file del mese scorso — e prodotto risultati che
sembrano validi ma vengono da dati vecchi. Fallire subito, con un messaggio
che dice esplicitamente "sto rifiutando di far girare la fase successiva su
file vecchi", rende quell'errore impossibile da non notare.

## Apertura file: fail loud anche lì

Ogni file viene aperto con un controllo esplicito (`IsZombie()`, presenza
dell'albero `h80`): un file corrotto o senza l'albero atteso fa fallire
subito con un `RuntimeError` che elenca le chiavi trovate nel file, invece
di proseguire silenziosamente con un albero vuoto o `None`.
