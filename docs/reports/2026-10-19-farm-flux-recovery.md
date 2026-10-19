# Studio dei flussi sulla farm: statistica completa e run anomale

Campagna avviata il 19 ottobre 2026 su `trimax` (`ssh trima`). **Calcoli in corso: nessun risultato finale e nessun modello scelto.**

La nomenclatura scientifica e i criteri di accettazione restano quelli del [report locale](2026-10-19-native-flux-recovery.md). Qui “job” indica un processo affidato al gestore di calcolo Slurm; “snapshot” indica una copia separata del codice con l'impronta SHA-256 di ogni file.

## Campione e confronto

Si riusa la campagna completa su protone `production_full_proton_20261016T092133Z`: 13 periodi, 199 GiB di h80, flussi calibrati ed eventi ricostruiti UV/VIS. Sono compresi 1998 UV, 1999 UV/VIS, 2000 FUV/UV1/UV2/VIS, 2001 UV, 2002 UV1/UV2/VIS1/VIS2 e 2003 VIS. Il deuterio resta fuori dal dominio del confronto su protone.

I conteggi inclusivi provengono dagli h80 della stessa campagna di produzione, in `data/02_pre_analyzed_full_proton_20261016T092133Z`, senza selezioni di canale aggiuntive. Questi h80 applicano già la rimozione degli eventi senza tagger. Il pilot locale usava file storici: nel confronto bisogna distinguere l'effetto di questa convenzione da quello dei periodi aggiuntivi. Non si mescolano conteggi storici con la ricostruzione corrente.

Restano invariati durata assunta di 15 minuti, ipotesi di stabilità dell'apparato, rappresentazione sulle 128 strip e calibrazione energetica separata. Si confrontano interpolazione, Extra Trees, Kernel Ridge, MLP e CNN 1D con le stesse griglie; Ridge rimane un controllo aggiuntivo nei benchmark. Il disegno delle lacune viene ricostruito sul campione completo, senza riusare quello locale.

Sono previsti confronto sulle lacune realistiche, prova a blocchi di tre run, curve di apprendimento, sovrapposizioni con gli spettri misurati e 64 repliche correlate per il confronto sulla misura. Gli stimatori di Σ e la soglia di scelta della funzione di fit restano quelli esistenti. La scelta del modello avverrà dopo la revisione dei risultati.

## Run anomale trattate come mancanti

Per ogni periodo e stato si calcola il rapporto fra flusso integrato ed eventi inclusivi. Se il rapporto con la mediana dei valori positivi e finiti dello stesso periodo/stato è **minore di 0,01 oppure maggiore di 100**, l'intera run viene esclusa da addestramento, donatori, verità di riferimento e confronto di Σ sulle run note. Gli estremi 0,01 e 100 sono ammessi.

Tutti e tre gli stati delle run così identificate diventano richieste di ricostruzione. Sono incluse le tre run già diagnosticate con questo criterio, **1322, 1482, 1970**, anche se una variazione dei conteggi cambiasse la nuova diagnosi. Le altre cinque esclusioni precedenti — **1441, 1454, 1988, 2055, 2064** — restano separate: non vengono chiamate anomalie di fattore 100 senza evidenza. Qualora una di esse soddisfi ora anche quel criterio, diventa anch'essa una richiesta di ricostruzione.

La policy originale non viene modificata: la campagna salva una propria copia con evidenze e impronte degli input. I flussi anomali non servono né come variabili né come verità per misurare l'errore. Un'intera run non viene reinserita automaticamente nell'estrazione degli osservabili.

Le richieste senza conteggi o senza due donatori restano nell'inventario con il motivo. Le previsioni calcolabili sono tutte conservate in `candidate_attempts.csv` e `candidate_attempt_spectra.npz`; la colonna `supported` indica se conteggio e geometria dei vicini sono compresi nel dominio verificato. `candidate_predictions.csv` conserva soltanto quelle supportate. I grafici includono anche i tentativi fuori dominio, chiaramente segnalati. Nessuno di questi file modifica il flusso di produzione.

## Esecuzione e monitoraggio

Directory sulla farm:

```text
/data/graal/GRAAL_Analysis/results/flux-recovery-full-20261019
```

| Job Slurm | Compito | Dipendenza |
|---|---|---|
| 2 | Conteggi completi, impronte degli input, diagnosi, policy e disegno delle lacune | Nessuna |
| 3 | Confronto realistico, repliche, Σ, ricostruzione dei mancanti e grafici | Successo del job 2 |
| 4 | Confronto a blocchi di tre run e grafici | Successo del job 2 |

Ogni job richiede 2 CPU e 16 GiB, con limite di 48 ore; i modelli limitano a uno i thread delle librerie numeriche. Il gestore avvia i confronti soltanto se la preparazione termina correttamente. Un file `*.exit_code` registra la conclusione di ciascuno stadio; zero indica successo.

```bash
ssh trima 'squeue -j 2,3,4 -o "%.18i %.22j %.10T %.10M %R"'
ssh trima 'tail -n 30 /data/graal/GRAAL_Analysis/results/flux-recovery-full-20261019/prepare-2.log'
ssh trima 'tail -n 30 /data/graal/GRAAL_Analysis/results/flux-recovery-full-20261019/realistic-3.log'
ssh trima 'tail -n 30 /data/graal/GRAAL_Analysis/results/flux-recovery-full-20261019/block3-4.log'
ssh trima 'sacct -j 2,3,4 --format=JobID,JobName,State,ExitCode,Elapsed,MaxRSS'
```

Gli output finali saranno `prepared/`, `realistic/` e `block3/`. Durante il calcolo si trovano in directory temporanee nascoste; vengono pubblicati solo al completamento dello stadio e dopo la verifica delle impronte degli input. `jobs.json`, `job.sh`, `graal-farm-source-manifest.json` e i log conservano i dettagli per riprendere il lavoro.

## Verifiche prima del lancio

Snapshot di 383 file, verificati sulla farm prima della sottomissione; checkout operativo della farm preservato, comprese le modifiche preesistenti ai grafici. Manifest locale e manifest della campagna completa identici per SHA-256. Ambiente isolato: Python 3.14.8, ROOT 6.40.04, PyTorch 2.14.1 CPU, NumPy 2.5.4, scikit-learn 1.9.1, uproot 5.7.4. Le differenze di versione rispetto al pilot locale vengono conservate nella provenienza.

Suite locale: **1.271 test superati**, un avviso Matplotlib preesistente. Due test aggiunti successivamente verificano la preparazione completa su una fixture ROOT e il grafico con fit neurale indisponibile; entrambi superati. Sulla farm: **25 test mirati superati**, comprendenti le nuove esclusioni e il confronto dell'osservabile. La revisione indipendente ha verificato l'assenza di contaminazione delle run anomale nel training e segnalato il caso del fit indisponibile, corretto prima del lancio.

Queste verifiche riguardano software e avvio. Bias, copertura, beneficio sulla misura e gerarchia dei modelli richiedono i risultati della campagna; restano da valutare.
