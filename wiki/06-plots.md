# 06 — Plot

`06_plots/` è l'ultima fase della pipeline: prende i due alberi scritti
dalla ricostruzione (fase 7, [Analisi](03-analysis)) e disegna il Dalitz
plot M(η p) vs M(π⁰ p), colorato con `colz`, una volta per la ricostruzione
solo-chi2 e una per quella con gate BDT — così il confronto fra le due, che
è l'intero motivo per cui esistono due ricostruzioni, si vede direttamente.

## Il pacchetto: `kinematics.py` puro, `dalitz.py` con ROOT

La cartella espone due moduli con responsabilità nettamente separate, sullo
stesso principio già visto in [03 — Analisi](03-analysis) per
`reco_core.py`/`reco_physics.py`:

- **`kinematics.py`** — nessun `import ROOT`, nessun I/O: aritmetica su
  array numpy `(4,)` `[px, py, pz, E]`. Espone `invariant_mass`, `sqrt_s`,
  `dalitz_limit`, e le costanti `M_PI0`, `M_ETA`, `M_PROTON` — che un test
  (`test_constants_match_the_reconstruction`) verifica essere identiche a
  quelle di `03_analysis/reco_physics.py`, perché un plot in disaccordo con
  la ricostruzione sulla massa dell'η sarebbe peggio di nessun plot.
- **`dalitz.py`** — apre i file ROOT, riempie gli istogrammi, disegna. Fa
  `import ROOT`.

La separazione esiste per lo stesso motivo spiegato in
[Testing](testing): la suite pytest non deve dipendere da un'installazione
di ROOT. `06_plots/tests/test_kinematics.py` testa solo `kinematics.py`, ed
è incluso in `testpaths` di `pyproject.toml` insieme alle altre tre
cartelle di test. `dalitz.py`, come `reco_core.py` e
`02_event_selector/select_events.py`, resta fuori da questa copertura per
lo stesso motivo: è un guscio di I/O attorno a fisica già testata altrove.

## CLI

```bash
python -m plots.dalitz --chi2 data/analyzed/reco_eta_pi0_chi2.root \
                        --bdt  data/analyzed/reco_eta_pi0_bdt.root \
                        [--out-dir 06_plots/plots]
```

| Flag | Effetto | Default |
|---|---|---|
| `--chi2` | file di `reconstruct_eta_pi0_chi2` (obbligatorio) | — |
| `--bdt` | file di `reconstruct_eta_pi0_bdt` (obbligatorio) | — |
| `--out-dir` | cartella di destinazione per figure e `.root` | `06_plots/plots` |

Entrambi i file devono avere almeno un evento: `_open_tree` solleva
`RuntimeError` su un albero vuoto — "un istogramma vuoto si disegna lo
stesso, e sembra un risultato. Non lo è" (dal commento nel codice) — e
`FileNotFoundError` se il file non esiste, o `RuntimeError` con l'elenco
delle chiavi trovate se l'albero cercato non c'è. Nessun fallimento è
silenzioso.

## Cosa disegna, e cosa scrive

Per ogni evento di ciascun albero, `_collect` calcola quattro masse
invarianti (`kinematics.invariant_mass`) combinando η e π⁰ ricostruiti con
il protone in due modi — vedi sezione sotto — più le masse η/π⁰ già scritte
dalla ricostruzione (`eta_mass`, `pi0_mass`) e un flag booleano,
`over_limit`, contato ma mai usato per scartare eventi.

| File | Contenuto | Perché questo formato |
|---|---|---|
| `dalitz_chi2_misurato.{png,pdf}` | Dalitz chi2, protone misurato | — |
| `dalitz_chi2_implicito.{png,pdf}` | Dalitz chi2, protone da `missing` | — |
| `dalitz_bdt_misurato.{png,pdf}` | Dalitz gate BDT, protone misurato | — |
| `dalitz_bdt_implicito.{png,pdf}` | Dalitz gate BDT, protone da `missing` | — |
| `dalitz_confronto.{png,pdf}` | i quattro Dalitz sopra, un canvas 2×2 (`TCanvas::Divide(2,2)`) | confronto diretto a colpo d'occhio |
| `massa_eta.{png,pdf}` | massa invariante η, chi2 e BDT sovrapposti, con la massa vera come linea rossa tratteggiata | — |
| `massa_pi0.{png,pdf}` | come sopra, per il π⁰ | — |
| `masse_2d_chi2.{png,pdf}` | M(η) vs M(π⁰) in `colz`, campione chi2 | — |
| `masse_2d_bdt.{png,pdf}` | come sopra, campione con gate BDT | — |
| `masse_2d_confronto.{png,pdf}` | i due affiancati (`TCanvas::Divide(2,1)`) | — |
| `istogrammi.root` | tutti gli istogrammi (`TH1F`/`TH2F`), scritti con `Write()` | ristilizzare i plot senza rifare il loop sugli alberi |

I `masse_2d_*` sono le **stesse identiche masse** dei due plot 1D qui sopra,
incrociate: gli array che riempiono `massa_eta` e `massa_pi0` sono quelli che
riempiono gli assi X e Y. Per questo condividono le finestre dei plot 1D
(`_ETA_MASS_MIN/MAX` = 0.3–0.8, `_PI0_MASS_MIN/MAX` = 0.05–0.25, costanti
proprio per non poter divergere): una figura leggibile contro le altre due solo
se gli assi coincidono. Due linee rosse tratteggiate si incrociano su
(m_η, m_π⁰), dove il segnale deve stare.

Su questa vista il gate BDT si legge in modo diverso dai plot 1D: non come una
mediana che si sposta, ma come la nube che si centra sull'incrocio. Sui dati
reali lo spostamento è quasi tutto **orizzontale** — il π⁰ era già quasi al
posto giusto, l'η no. Coerente col fatto che il fondo combinatorio sporcava
molto più l'η del π⁰.

Ogni figura esce sia in **PNG** (per guardarla) sia in **PDF** (vettoriale,
per le slide) — `_save` scrive entrambi da uno stesso canvas. Il range
dell'asse Dalitz è `[1.0, 2.8]` GeV su 90 bin per lato: più largo del limite
fisico inferiore (M(η p) ≥ m_η + m_p ≈ 1.486 GeV) apposta, così qualunque
evento fuori dai limiti cinematici resta visibile invece di finire
compresso nel bin di bordo.

## I due protoni non sono equivalenti

Ogni Dalitz viene disegnato due volte, con due definizioni diverse di
"protone", ed è la parte che conta di più di questa pagina perché le due
non portano la stessa informazione.

- **`misurato`** usa il ramo `proton` scritto dalla ricostruzione: il
  quadrimpulso del barione di rinculo **misurato** dal rivelatore,
  indipendente dai fotoni. È l'unica delle due variabili che può essere in
  disaccordo con il fascio.
- **`implicito`** usa il ramo `missing`, definito in
  `03_analysis/reco_core.py` come `missing = (beam + target) - (eta + pi0)`
  (confermato anche in [Formati dati](data-formats)). Da qui l'identità
  algebrica

  ```
  eta + missing = beam + target - pi0
  ```

  cioè il Dalitz "implicito" **non dipende né dal protone misurato né
  dall'η misurata**: è un plot di massa mancante, pulito per costruzione,
  ma non porta informazione indipendente rispetto a fascio, bersaglio e π⁰.

Questo è anche perché solo la variante `misurato` può mostrare un problema
reale. `_collect` calcola, per ogni evento,

```python
limit = kin.dalitz_limit(kin.sqrt_s(beam, target), kin.M_PI0)
over_limit.append(mep_meas[-1] > limit)
```

cioè confronta M(η p) **misurata** contro il limite cinematico W − m_π⁰ (W
= massa invariante fascio+bersaglio). Il conteggio è **contato, non
tagliato** — il commento nel codice lo dice esplicitamente — e viene
stampato a fine run.

Un evento oltre questo limite non è necessariamente un errore di misurazione:
è il segnale che qualcosa nella cinematica misurata dell'evento non torna con
fascio e bersaglio nominali. In gran parte è risoluzione al bordo del Dalitz,
ed è per questo che resta **contato e non tagliato**.

Il caso davvero impossibile è un altro, e ora è **tagliato**: un mesone
ricostruito con più energia del fotone di tagging. Il bersaglio è fermo e
contribuisce solo la propria massa, quindi in γp → pηπ⁰ non può succedere. Non
è un evento misurato male, è un evento sbagliato — quasi sempre il tagger che
associa al trigger il fotone di fascio sbagliato, cosa che né il chi2 né il
gate BDT possono riparare, perché entrambi guardano i fotoni e il protone e mai
quella associazione. La ricostruzione li scarta dentro il percorso condiviso da
entrambi i run (vedi [Ricostruzione chi2](03-analysis-chi2)), così le due
analisi perdono esattamente gli stessi eventi e l'unica differenza fra loro
resta il gate.

Il contatore `eta con energia maggiore del fotone di fascio` resta nel
riepilogo e deve leggere **0**: se non lo fa, quegli alberi sono stati
ricostruiti prima che il taglio esistesse, e la fase 8 lo dice invece di
lasciarlo passare.

## Fase 8 in `run_pipeline.sh`

```bash
python -m plots.dalitz \
    --chi2    "${ANALYZED_DIR}/reco_eta_pi0_chi2.root" \
    --bdt     "${ANALYZED_DIR}/reco_eta_pi0_bdt.root" \
    --out-dir "06_plots/plots"
```

Salta con `--skip-plots`. Se anche uno solo dei due file ricostruiti manca
in `ANALYZED_DIR/`, la fase si salta **automaticamente**, senza errore:

```
[8/8] Plot — saltato: manca almeno un file ricostruito in analyzed/
    (i plot confrontano le due analisi: servono entrambi)
```

Non è un fallimento silenzioso mascherato da skip: è deliberato, perché il
plot esiste solo per confrontare le due ricostruzioni fra loro — un solo
file ricostruito non basta a produrre nulla di sensato, e bloccare l'intera
pipeline con un errore fatale solo perché, per esempio, si è passato
`--skip-reco` in un run di prova sarebbe peggio che saltare la fase con un
messaggio chiaro sul motivo.

## Dove andare da qui

- [Pipeline](pipeline) — fase 8 nel contesto delle altre sette, tutti i
  flag di `run_pipeline.sh`.
- [Formati dati](data-formats) — lo schema di `reco_eta_pi0_chi2` /
  `reco_eta_pi0_bdt`, da cui questa fase legge.
- [03 — Analisi](03-analysis) — dove `eta`, `pi0`, `proton` e `missing`
  vengono scritti.
- [Testing](testing) — perché `dalitz.py` non è coperto da pytest e
  `kinematics.py` sì.
