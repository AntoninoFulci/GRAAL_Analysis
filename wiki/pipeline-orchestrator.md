# Orchestratore della pipeline

`graal-pipeline` è l'interfaccia principale per pianificare, eseguire,
riprendere e validare la pipeline GRAAL fino all'estrazione delle osservabili.
La stessa descrizione delle dipendenze viene utilizzata per le esecuzioni di
produzione, per lo smoke test ridotto e per la validazione completa sulla farm.

L'orchestratore non modifica gli algoritmi di fisica dei singoli stadi. Avvia
gli entry point esistenti, controlla i loro input e output, registra checkpoint
riproducibili e pubblica un risultato solo dopo che il relativo validatore ha
avuto esito positivo.

## Installazione e avvio

Caricare prima l'ambiente ROOT compatibile con PyROOT, quindi eseguire il setup
della repository oppure installare il progetto in modalità editable:

```bash
./scripts/setup.sh --mode local
# oppure
python -m pip install -e .
```

Sono disponibili due entry point equivalenti:

```bash
graal-pipeline --help
python -m graal_pipeline --help
```

L'esecuzione senza argomenti apre il wizard interattivo in italiano:

```bash
graal-pipeline
```

I nomi dei comandi, delle opzioni, degli stati e dei token nei log rimangono in
inglese per poter essere utilizzati in script e report automatici.

## Struttura del wizard

Il menu principale propone:

1. **Continua ultima esecuzione**: riparte dal primo checkpoint incompleto o
   scelto per il rifacimento.
2. **Prepara dati e modelli**: prepara preanalisi, selezione, Monte Carlo,
   feature e modello BDT richiesti dal target.
3. **Ricostruisci final state**: produce i campioni di ricostruzione necessari
   per lo stato finale selezionato.
4. **Estrai osservabile**: apre prima la scelta dello stato finale, poi quella
   dell'osservabile.
5. **Valida pipeline**: seleziona un profilo di integrazione isolato.
6. **Controlla checkpoint e output**: mostra validità, età e motivi dello stato
   di ogni prodotto richiesto.
7. **Esci**: termina senza modificare output.

Nel percorso **Estrai osservabile → eta pi0 → Asimmetria del fascio** sono
disponibili:

1. **Estrazione finale**: esegue correzioni, sideband e covarianze complete.
2. **Prima passata non corretta**: controlla rapidamente flusso e campione BDT
   non corretto.
3. **Valida estrazione**: utilizza il profilo `smoke` o `farm` in una directory
   isolata.
4. **Configurazione avanzata**: espone estimatore, bootstrap, binning e seed.
5. **Stato**: ispeziona checkpoint e output senza eseguire stadi.
6. **Indietro**: torna al menu precedente.

Ogni voce contiene una breve descrizione. Il carattere `?` mostra ulteriori
informazioni contestuali. Le funzionalità non implementate sono visibili con
l'indicazione `[non disponibile]` e non possono essere selezionate.

## Comandi CLI

### Riprendere un'esecuzione

```bash
graal-pipeline resume
```

`resume` legge `latest.json` nella directory di stato, ricostruisce lo stesso
target e pianifica nuovamente gli stadi in base agli artifact presenti. Non
considera automaticamente valido un prodotto parziale lasciato da un processo
interrotto.

### Controllare stato e checkpoint

```bash
graal-pipeline status --final-state eta_pi0
```

Il comando è di sola lettura. Per ogni stadio stampa uno stato stabile in
inglese e i motivi che lo determinano.

### Preparare un piano

```bash
graal-pipeline plan extract beam-asymmetry \
  --final-state eta_pi0 \
  --non-interactive \
  --old-policy reuse \
  --stale-policy rebuild \
  --untracked-policy rebuild
```

Il planner parte dal risultato richiesto, percorre le dipendenze a ritroso e
seleziona il primo stadio effettivamente necessario. Il piano usa le azioni
`REUSE`, `ADOPT`, `RUN`, `REBUILD` e `BLOCKED`.

### Estrarre l'asimmetria del fascio

```bash
graal-pipeline extract beam-asymmetry --final-state eta_pi0
```

In modalità interattiva vengono richieste le decisioni relative agli artifact
vecchi, obsoleti o senza checkpoint, quindi viene mostrato il piano prima della
conferma. Per un job non interattivo occorre specificare politiche complete:

```bash
graal-pipeline extract beam-asymmetry \
  --final-state eta_pi0 \
  --non-interactive --yes \
  --old-policy reuse \
  --stale-policy rebuild \
  --untracked-policy rebuild
```

### Validare l'integrazione

Smoke test su un campione reale ridotto:

```bash
graal-pipeline validate beam-asymmetry \
  --final-state eta_pi0 \
  --profile smoke \
  --non-interactive \
  --old-policy rebuild \
  --stale-policy rebuild \
  --untracked-policy rebuild
```

Validazione completa destinata alla farm:

```bash
graal-pipeline validate full \
  --final-state eta_pi0 \
  --profile farm \
  --non-interactive \
  --old-policy rebuild \
  --stale-policy rebuild \
  --untracked-policy rebuild
```

Il comando `validate beam-asymmetry` verifica il percorso necessario
all'osservabile. `validate full` rappresenta la validazione completa prevista
dal profilo selezionato; entrambi usano lo stesso grafo della produzione.

### Dry run

`--dry-run` esegue scoperta, validazione e pianificazione, ma non avvia processi
né pubblica output:

```bash
graal-pipeline extract beam-asymmetry \
  --final-state eta_pi0 \
  --dry-run \
  --non-interactive \
  --old-policy reuse \
  --stale-policy rebuild \
  --untracked-policy rebuild
```

## Opzioni comuni

| Opzione | Funzione |
|---|---|
| `--config PATH` | Usa un file TOML alternativo. |
| `--profile NAME` | Seleziona `production`, `smoke`, `farm` o un profilo definito nel TOML. |
| `--state-dir PATH` | Cambia la directory di checkpoint, log e report. |
| `--dry-run` | Mostra il piano senza eseguirlo. |
| `--non-interactive` | Disabilita tutte le richieste interattive. |
| `--yes` | Conferma il piano finale; non decide le politiche semantiche. |
| `--force-stage STAGE` | Forza il rifacimento di uno stadio; l'opzione è ripetibile. |
| `--old-policy ask\|rebuild\|reuse\|fail` | Decide come trattare output semanticamente validi ma vecchi. |
| `--stale-policy ask\|rebuild\|reuse\|fail` | Decide come trattare output incompatibili con input, codice o configurazione correnti. |
| `--untracked-policy ask\|adopt\|rebuild\|fail` | Decide come trattare output validi senza checkpoint compatibile. |
| `--verify fast\|full` | Seleziona il livello di fingerprint e validazione. |
| `--keep-failed-work` | Conserva la directory staged di uno stadio fallito per il debug. |
| `--final-state KEY` | Seleziona lo stato finale del comando. |

Le opzioni possono essere consultate sul comando foglia interessato, per
esempio:

```bash
graal-pipeline extract beam-asymmetry --help
```

## Stati finali e osservabili

| Stato finale | Ricostruzione | Asimmetria del fascio | Sezione d'urto |
|---|---|---|---|
| `eta_pi0` | disponibile | disponibile | visibile, non disponibile |
| `2pi0` | ricostruzione di base disponibile | visibile, non disponibile | visibile, non disponibile |

I canali Monte Carlo non compaiono nel menu degli stati finali: descrivono
campioni di training e non analisi indipendenti. Una combinazione non supportata
richiesta da CLI termina prima di qualsiasi mutazione con exit code 2.

## Grafo di esecuzione

L'estrazione completa di `eta_pi0` collega i seguenti rami:

```text
preanalysis → event_selection → beam_spectrum → feature_build
                                               ├→ grid_search
                                               └→ bdt_training

preanalysis → flux_calibration
event_selection + bdt_training → ricostruzioni dati
signal_mc_generation → signal_mc_adapter → ricostruzione sideband MC

flux_calibration + ricostruzioni dati + sideband MC
└→ beam_asymmetry_full
```

`grid_search` è una dipendenza soltanto quando la configurazione di training ne
usa il risultato. Un fallimento blocca i discendenti, mentre i rami indipendenti
continuano; il riepilogo finale resta non valido se uno stadio richiesto è
fallito o bloccato.

## Stati degli artifact

| Stato | Significato | Comportamento predefinito |
|---|---|---|
| `FRESH` | Validatore e checkpoint coincidono con input, configurazione e codice. | Riutilizzo. |
| `OLD` | Artifact semanticamente valido, ma oltre la soglia di età. | Richiesta all'utente. |
| `UNTRACKED` | Output valido privo di checkpoint compatibile. | Richiesta di adozione o rifacimento. |
| `STALE` | Input, configurazione, codice, schema o provenienza sono cambiati. | Rifacimento consigliato. |
| `MISSING` | Output richiesto assente. | Esecuzione dello stadio. |
| `INVALID` | Output presente ma non conforme al contratto. | Rifacimento; mai riutilizzo. |

La soglia predefinita per i prodotti derivati è 30 giorni e viene calcolata
dalla conclusione registrata nel checkpoint. Gli input sorgente non diventano
vecchi per il solo trascorrere del tempo. Una differenza semantica produce
sempre `STALE`, anche per un file appena creato.

In modalità non interattiva, una policy `ask` richiesta da uno stato presente
causa exit code 2 prima dell'esecuzione. `--yes` non sostituisce una policy:
conferma soltanto un piano già determinato.

## Configurazione TOML

La configurazione versionata è `config/pipeline.toml`. La precedenza è:

```text
opzione CLI > profilo selezionato > valori TOML generali > default nel codice
```

Le sezioni principali sono:

- `[paths]`: input, output intermedi, modello e directory dei risultati;
- `[checkpoint]`: età massima, livello di verifica e politiche;
- `[runtime]`: eseguibili, numero di eventi MC, grid search, thread,
  bootstrap, seed ed estimatore;
- `[profiles.<nome>]`: override specifici del profilo.

Tutti i path relativi vengono risolti rispetto alla root della repository,
indipendentemente dalla directory corrente. I path assoluti sono ammessi per
configurazioni esplicite sulla farm. Un path relativo che esce dalla root
tramite `..` o link simbolici viene rifiutato prima di qualsiasi mutazione.

I default principali sono:

```toml
[paths]
raw_dir = "data/01_raw/graal_data"
preanalysis_dir = "data/02_pre_analyzed/pre_analisi"
selected_dir = "data/03_selected"
external_flux = "data/00_external/flux.root"
run_manifest = "config/run_manifest.csv"
results_dir = "results"
```

Il default dei dati selezionati è quindi `data/03_selected`, non `/data/...`.

## Profili

| Profilo | Verifica | Output | Affermazione consentita |
|---|---|---|---|
| `production` | `fast` | Percorsi canonici in `results/` | Produzione fisica, subordinata ai controlli dell'analisi. |
| `smoke` | `full` | `results/validation/smoke/<run-id>/` | Integrazione software soltanto. |
| `farm` | `full` | `results/validation/farm/<run-id>/` | Validazione funzionale completa sulla farm. |

Il profilo `smoke` riduce eventi MC e repliche bootstrap, ma usa comandi,
validatori e grafo di produzione. Richiede almeno un file ROOT reale ridotto
sotto `test_data/raw/`; non genera un sostituto sintetico. Se il fixture manca,
il comando termina con istruzioni per copiarlo e non crea directory di output.

Il profilo `farm` è il successore funzionale del precedente job overnight:
mantiene output isolati, verifica completa e continuazione dei rami
indipendenti.

## Layout di input, risultati e stato

```text
data/
├── 00_external/flux.root
├── 01_raw/graal_data/
├── 02_pre_analyzed/pre_analisi/
└── 03_selected/

results/
├── .pipeline/
├── shared/strip_energy_flux/
├── eta_pi0/
│   ├── reconstruction/
│   └── observables/beam_asymmetry/
└── 2pi0/
```

La directory di stato predefinita contiene:

```text
results/.pipeline/
├── checkpoints/shared/
├── checkpoints/<final-state>/
├── checkpoints/<final-state>/<observable>/
├── runs/<run-id>/plan.json
├── runs/<run-id>/summary.json
├── logs/<run-id>/<stage>.log
└── latest.json
```

I checkpoint condivisi, per stato finale e per osservabile hanno ambiti
distinti. Questo evita che due analisi attribuiscano stati diversi allo stesso
artifact fisico.

## Adozione di output esistenti

Un output valido prodotto prima dell'orchestratore compare come `UNTRACKED`.
L'utente può:

1. validarlo e adottarlo;
2. ricostruirlo;
3. vedere i dettagli della validazione;
4. interrompere.

L'adozione registra fingerprint, configurazione effettiva, versione del codice
e provenienza `adopted_legacy_output`. Se la configurazione originaria non può
essere ricostruita con certezza, il prodotto adottato rimane `STALE`: il sistema
non inventa una provenienza `FRESH`.

## Pubblicazione sicura e concorrenza

Ogni stadio scrive prima in una directory temporanea sullo stesso filesystem
della destinazione. Dopo il successo del comando, il validatore controlla il
prodotto staged. I file singoli vengono pubblicati con sostituzione atomica;
le directory utilizzano la pubblicazione atomica condivisa del progetto. Un
output precedente noto come valido rimane intatto se comando o validazione
falliscono.

Il checkpoint viene scritto per ultimo. Un'interruzione tra pubblicazione e
checkpoint lascia un artifact `UNTRACKED`, quindi recuperabile senza dichiarare
un successo inesistente.

È consentita una sola esecuzione mutante per directory di stato. Il lock
registra host, PID, run ID e data. Anche un lock apparentemente obsoleto viene
soltanto segnalato e non viene eliminato automaticamente. `status`, `plan` e
`--dry-run` restano disponibili perché non acquisiscono il lock di esecuzione.

## Log, report ed exit code

Ogni run conserva piano, log per stadio e riepilogo JSON. `latest.json` punta
all'ultimo riepilogo utilizzabile da `resume`.

| Exit code | Significato |
|---:|---|
| `0` | Piano, ispezione o esecuzione conclusi senza stadi falliti. |
| `1` | Uno o più stadi richiesti sono `FAILED`, `BLOCKED` o `SKIPPED`. |
| `2` | Errore di uso, capability non disponibile o decisione non risolta in modalità non interattiva. |
| `73` | Directory di stato già bloccata da un'altra esecuzione o da un lock da esaminare. |

## Risoluzione dei problemi

- **`no previous run is available to resume`**: controllare `--state-dir` e la
  presenza di `latest.json`.
- **Decisione richiesta in modalità non interattiva**: specificare le tre
  policy `--old-policy`, `--stale-policy` e `--untracked-policy`.
- **`state directory lock is ...`**: leggere `run.lock/owner.json`, verificare
  il processo proprietario e rimuovere manualmente il lock soltanto dopo una
  verifica operativa.
- **Artifact `INVALID`**: consultare i motivi stampati da `status` e il log
  dello stadio; non forzare il riutilizzo.
- **Fixture smoke assente**: copiare uno o più run ROOT rappresentativi sotto
  `test_data/raw/` mantenendo la struttura attesa.
- **Import o comando non trovato**: attivare l'ambiente corretto ed eseguire
  `python -m pip install -e .`.
- **Output staged da analizzare**: ripetere con `--keep-failed-work`.

## Stato della migrazione dagli script shell

L'interfaccia Python è quella raccomandata per nuovi run. I file
`run_pipeline.sh` e `scripts/run_beam_asymmetry_overnight.sh` sono mantenuti
temporaneamente perché nella repository corrente manca il fixture ROOT reale
richiesto dal gate `smoke` (`test_data/raw/**/*.root`). Non sono wrapper del
nuovo comando e non devono essere usati come base per nuove automazioni.

La rimozione avverrà soltanto dopo che il profilo `smoke` avrà completato con
successo l'intera integrazione su dati reali ridotti. Fino a quel momento i
test contrattuali degli script restano intenzionalmente presenti come rete di
sicurezza per la migrazione.
