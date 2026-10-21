# Studio dei flussi sulla farm: statistica completa e run anomale

Campagna avviata il 19 ottobre 2026 su `trimax` (`ssh trima`), **terminata il 20 ottobre alle 02:36, ora italiana**, con codice di uscita zero per tutti e tre gli stadi. Extra Trees e Kernel Ridge confermano le prestazioni migliori; il beneficio mediano sulla precisione di Σ resta circa il 10% nei periodi valutabili. La calibrazione delle incertezze non è invece adeguata in tutti i periodi. Nessun modello o flusso sintetico è stato adottato nella produzione.

La nomenclatura scientifica e i criteri di accettazione restano quelli del [report locale](2026-10-19-native-flux-recovery.md). Qui “job” indica un processo affidato al gestore di calcolo Slurm; “snapshot” indica una copia separata del codice con l'impronta SHA-256 di ogni file.

## Decisione operativa aggiornata, 20 ottobre

Questa sezione sostituisce la precedente scelta di tentare il recupero delle run
anomale. I risultati della campagna sotto restano un resoconto storico, non una
lista di flussi autorizzati per la produzione.

**Modelli attivi:** Extra Trees ibrido come prima scelta, Kernel Ridge ibrido come
confronto, interpolazione fra due vicini come riferimento. “Ibrido” significa
forma predetta dal modello e integrale fissato dall'interpolazione normalizzata
al numero di eventi. Rimossi dal percorso dei flussi calibrati Ridge semplice,
MLP e CNN 1D, con implementazione neurale, griglie e dipendenza PyTorch dedicata.
Restano i confronti diretto/ibrido e parametri fissi/ottimizzati per i due modelli
utili. I report e i lettori dei risultati storici restano consultabili. Lo studio
separato sui flussi grezzi conserva il proprio Ridge.

**Esclusioni definitive per questa analisi:** 1322, 1441, 1454, 1482, 1970, 1988,
2055, 2064, 2607, 2804, 3585, 3776. La
[policy condivisa](../../config/run_quality_exclusions.json) comprende ora tutte
le dodici run, con evidenza a statistica completa per le sette anomalie di
fattore 100 e motivazione distinta per le cinque esclusioni manuali. Nessuno
stato di queste run può essere usato per addestramento, riferimento,
ricostruzione dei flussi o estrazione degli osservabili. La selezione dei
bersagli rifiuta queste run anche quando legge un inventario storico che le
classificava come recuperabili. Nella produzione esaminata corrispondono a
12.126.582 eventi h80 e 891 eventi ηπ⁰ ricostruiti: entrambi esclusi dalla stima
seguente.

### Stima del recupero degli eventi

Un **donatore** (*donor*) è una run buona con flusso misurato, usata come
riferimento prima o dopo la run da ricostruire. Un **candidato** (*candidate*) è
uno stato con flusso mancante, conteggio h80 disponibile e due donatori.
**Supportato** significa che le distanze dai donatori sono state provate nel
confronto su run note e il conteggio è nell'intervallo osservato nelle run buone.
Non significa “validato fisicamente”. Una **run potenzialmente recuperabile**
ha tutti gli stati mancanti supportati. Una **run accettata** deve inoltre
superare i controlli indipendenti di calibrazione, incertezza e osservabile.

Il conteggio usa la stessa produzione completa della farm e verifica, per ogni
run/stato, che il numero h80 coincida con gli ingressi grezzi meno gli eventi
senza tagger della ricostruzione. Verifica inoltre gli eventi scritti contro le
entrate dell'albero ROOT. Non usa un campione ridotto e non mescola i vecchi h80.
Ogni evento viene contato una sola volta.

| Quantità | Conteggio |
|---|---:|
| Run realmente incomplete, escluse le anomalie | 541 |
| Stati realmente mancanti | 842 |
| Stati mancanti supportati per Extra Trees | 228 |
| Run con tutti gli stati mancanti supportati | **221** |
| Stati da ricostruire per completare queste 221 run | 224 |
| Eventi h80 nelle 221 run | **201.937.998** |
| Di cui negli stati con flusso mancante | 3.206.654 |
| Eventi ηπ⁰ ricostruiti nelle 221 run | **22.193** |
| Eventi POL1/POL2 nelle finestre energetiche dell'analisi | **22.191** |
| Eventi BREM nelle stesse finestre | 2 |
| Run/eventi di recupero già accettati per produzione | **0 / 0** |

I quattro stati supportati che non completano una run non contribuiscono al
recupero. Il loader attuale richiede il terzetto POL1/POL2/BREM completo e scarta
altrimenti tutta la run. Per questo il recupero potenziale include anche gli
eventi di stati già calibrati. Ben 206 delle 221 run mancano soltanto di BREM:
completare quel flusso potrebbe riammettere i loro eventi polarizzati.

| Periodo | Run potenziali | Eventi h80 | Eventi ηπ⁰ POL1/POL2 nella finestra |
|---|---:|---:|---:|
| 1998_uv | 5 | 1.150.295 | 158 |
| 1999_uv | 50 | 20.255.137 | 2.889 |
| 2000_fuv | 30 | 15.446.435 | 1.590 |
| 2000_uv2 | 25 | 23.500.454 | 2.649 |
| 2000_vis | 22 | 22.646.134 | 1.066 |
| 2002_uv1 | 16 | 19.159.224 | 1.876 |
| 2002_uv2 | 59 | 85.341.103 | 11.260 |
| 2002_vis1 | 10 | 9.074.699 | 439 |
| 2002_vis2 | 4 | 5.364.517 | 264 |

Le finestre sono 1,10–1,50 GeV per UV e 0,9313–1,10 GeV per VIS. Gli eventi
ηπ⁰ sono quelli sopravvissuti alla selezione della produzione; non sono rese di
segnale estratte da un fit. I 22.191 eventi polarizzati sono prima della verifica
finale delle esposizioni sulle strip e della suddivisione dell'osservabile. Sono
un limite potenziale basato sul supporto, non una promessa di guadagno statistico.

Il [bilancio completo](../../results/flux-recovery-budget-20261020-final/recovery_budget.json)
contiene motivi di sospensione e conteggi per ogni run;
[la tabella per run](../../results/flux-recovery-budget-20261020-final/recovery_runs.csv)
e [le verifiche degli input](../../results/flux-recovery-budget-20261020-final/input_integrity.json)
permettono di ripetere e controllare il conto. Comando riproducibile:

```bash
python -m flux_studies.recovery_budget \
  --study results/farm-flux-results-20261020 \
  --reco /path/to/uv/reco_eta_pi0_bdt.root /path/to/vis/reco_eta_pi0_bdt.root \
  --output-dir results/new-recovery-budget
```

### Cosa serve per concludere

1. Congelare Extra Trees e i criteri prima della conferma finale. Ridistribuire i
   blocchi di sviluppo per avere abbastanza run indipendenti con cui calibrare
   l'incertezza in ciascun periodo/stato; nessuna decisione positiva nei periodi
   che non permettono tale verifica. I test già ispezionati restano sviluppo.
2. Validare la conversione strip→energia per gli stati realmente mancanti e la
   copertura delle bande. Un accordo Extra Trees/Kernel Ridge è un controllo,
   non una misura indipendente della verità.
3. Eseguire il confronto su run note nascoste con i criteri concordati: effetto
   della rappresentazione ≤0,05 σ_stat; bias medio ≤0,10 σ_stat considerando
   l'incertezza sulla media; contributo del flusso ≤0,30 σ_stat; copertura 68/95%
   compatibile con i valori nominali e con il numero di run indipendenti.
4. Accettare soltanto run complete che superano quei controlli. Ripetere Σ con
   e senza le run ammesse, confrontando errore totale, stabilità e bias; il
   numero di eventi aggiunti da solo non dimostra un miglioramento della misura.

Le esclusioni sono applicate dal codice aggiornato e verificate nei confini di
lettura dei flussi e selezione degli eventi. I file di produzione e gli output
storici non sono stati riscritti. Il checkout di produzione principale sulla
farm non contiene ancora questa policy: la prossima estrazione deve usare uno
snapshot del codice aggiornato, non quel checkout precedente. Lo snapshot
isolato dello studio del 19 ottobre resta intatto per riproducibilità.

Verifica del codice aggiornato: **1.276 test superati**, con un avviso già
esistente relativo a una legenda vuota. Revisione indipendente senza problemi
bloccanti. [Log dei test](../../results/flux-recovery-budget-20261020-final/tests.log).

## Risultati finali, verificati il 20 ottobre

La scansione comprende **1.741.575.938 eventi h80**. Dopo le esclusioni e la richiesta di flussi validi in tutti e tre gli stati rimangono **1.278 run complete, 3.834 spettri**. I test realistici valutano 338 spettri noti mascherati: 56 POL1, 47 POL2 e 235 BREM. La prova a blocchi di tre ne valuta 705, 235 per stato. Le impronte degli input prima e dopo preparazione ed entrambi gli studi sono identiche.

### Accuratezza dei modelli

L1 spettrale è la somma degli scarti assoluti sulle 128 strip, divisa per l'integrale vero. L1 della forma applica prima una normalizzazione a integrale uno. La tabella usa gli stessi bersagli per tutti i modelli: 338 nel test realistico e 702 in quello a blocchi. Kernel Ridge non produce tre previsioni BREM del periodo 2002 VIS2 per training interno insufficiente; gli altri modelli ne producono 705. Quei tre casi restano documentati fra le indisponibilità, senza assegnare loro errore zero.

| Metodo | L1 spettrale mediana, realistico | L1 forma mediana, realistico | L1 spettrale mediana, blocchi di tre |
|---|---:|---:|---:|
| Interpolazione | 12,50% | 11,61% | 11,93% |
| Extra Trees ibrido | **10,41%** | **9,73%** | **9,72%** |
| Kernel Ridge ibrido | 10,46% | 9,74% | 9,76% |
| MLP ibrido | 12,38% | 11,52% | 12,04% |
| CNN 1D ibrido | 10,64% | 9,84% | 9,87% |

La gerarchia del pilot si conferma: Extra Trees e Kernel Ridge sono vicini, CNN competitiva, MLP senza un vantaggio convincente rispetto all'interpolazione. Extra Trees batte Kernel Ridge su 173/338 bersagli realistici e 410/702 bersagli comuni a blocchi: è una preferenza pratica ragionevole, non una superiorità universale o statisticamente dimostrata. Non è stata effettuata una nuova scelta dei parametri usando il test.

Il miglioramento mediano di Extra Trees sulla L1 spettrale rispetto all'interpolazione è circa il 17% nel realistico e il 18% nei blocchi. Le percentuali assolute non sono una prova di miglioramento rispetto al pilot: cambiano composizione dei periodi, maschere e convenzione h80.

L'errore assoluto mediano dell'integrale è 3,12% nel realistico e circa 2,66% nei blocchi. È identico fra interpolazione e modelli ibridi, per costruzione. Le code restano importanti: in blocchi di tre, BREM 2072 ha errore dell'integrale **+986,8%**, 2074 **+559,5%**, 1777 **+549,9%**. Sono fallimenti della ricostruzione sotto quella maschera; non sono nuove anomalie da escludere in base al criterio di fattore 100.

### Beneficio sulla misura e limiti delle incertezze

Con Extra Trees, sugli **otto periodi** con almeno due repliche complete, il rapporto mediano fra errore statistico più flusso dopo recupero ed errore statistico senza recupero è:

| Stimatore | Rapporto mediano | Riduzione mediana | Punti migliorati / confrontabili |
|---|---:|---:|---:|
| Rapporti | 0,8991 | 10,1% | 538 / 545 |
| Verosimiglianza | 0,8976 | 10,2% | 545 / 546 |

Questi conteggi aggregano punti correlati, non prove indipendenti. L'indicatore che aggiunge lo scostamento appaiato dall'oracle conserva gli stessi conteggi di punti migliorati. Il risultato riguarda run note nascoste; non misura ancora il beneficio delle sette run realmente anomale. Il periodo 2002 UV1 maschera soltanto BREM, che non entra direttamente nei due stimatori attuali: il suo guadagno deriva dagli eventi reintrodotti.

Non migliora ogni punto. Per UV 1998, nel bin ηπ0 con indici energia 2 e massa 1, l'errore di verosimiglianza passa da 0,0860 senza recupero a 0,2105 con recupero: rapporto **2,45**. L'oracle vale 0,2115 e il contributo del flusso è appena 0,00219: il peggioramento del rapporto non è dominato dall'incertezza di ricostruzione del flusso. Questo punto richiede un esame dello stimatore e del campione ridotto prima di interpretare il rapporto come beneficio fisico.

La sola rappresentazione nativa supera il criterio in tutti gli 11 periodi con un confronto realistico. Il massimo contributo del flusso osservato con Extra Trees nei periodi valutabili resta sotto 0,30 σ_stat; la calibrazione delle bande, tuttavia, mostra sottocopertura. “Sottocopertura” significa che una banda dichiarata al 95% contiene meno del 95% dei valori di riferimento. Esempi di copertura marginale delle strip, prima mediata entro ciascuno spettro:

| Campione Extra Trees | Copertura osservata della banda 95% | Intervallo descrittivo sulla copertura |
|---|---:|---:|
| 1998 UV, BREM | 90,2% | 85,6–94,1% |
| 2000 UV1, POL1 | 90,2% | 88,6–91,8% |
| 2002 UV2, BREM | **76,5%** | 74,2–78,8% |
| 2002 VIS1, BREM | **82,5%** | 68,5–90,8% |

Gli intervalli descrittivi ricampionano gruppi di bersagli con donatori/blocchi condivisi e non includono tutta la dipendenza dal modello e dal campione di residui comuni. Anche con questo limite, non giustificano una dichiarazione generale di copertura al 95%.

| Periodo | Repliche complete Extra Trees / 64 | Limite principale |
|---|---:|---|
| 1998 UV | 62 | Due repliche incomplete |
| 1999 UV | 62 | Due repliche incomplete |
| 1999 VIS | 62 | Due repliche incomplete |
| 2000 FUV | 22 | Solo 9 run / 8 blocchi nel campione di residui; molte repliche incomplete |
| 2000 UV1 | 38 | Repliche incomplete |
| 2000 UV2 | **0** | Solo 4 run / 3 blocchi per residui accoppiati: supporto insufficiente |
| 2000 VIS | **0** | Nessuna run di validazione collocabile |
| 2002 UV1 | 64 | Maschere BREM soltanto |
| 2002 UV2 | 58 | Solo 5 run / 5 blocchi per residui; sottocopertura marcata |
| 2002 VIS1 | 64 | Sottocopertura BREM |
| 2002 VIS2 | **0** | Una sola run / un blocco per residui: supporto insufficiente |

I tre periodi con zero repliche non hanno incertezze nulle: le loro incertezze e il guadagno complessivo non sono stimabili con questa procedura. I log dell'estrazione riportano valori non finiti perché le repliche indisponibili sono conservate come tali; la causa a monte è il campione di residui insufficiente, non una corruzione dei file ROOT.

La statistica completa di eventi non risolve automaticamente la carenza di **run di calibrazione indipendenti**. Il disegno attuale colloca prima il test e poi la validazione, riservando donatori affidabili: nei periodi con lacune estese rimangono poche finestre per la validazione. Nel 2001 UV non rimane alcuna run completa utilizzabile come donatrice; nel 2003 VIS le sei run complete rimaste non consentono di collocare le lacune richieste. Questi due periodi non hanno confronto realistico su Σ; sono esplicitamente fuori dalle medie sopra.

### Esito delle sette run anomale

“Supportato” indica soltanto che conteggio e geometria dei donatori rientrano nel dominio verificato; non equivale ad approvazione per la misura.

| Run | Esito della ricostruzione nei tre stati |
|---|---|
| **1322** | POL1, POL2 e BREM calcolati e supportati |
| **1482** | POL1, POL2 e BREM calcolati e supportati |
| **1970** | POL1, POL2 e BREM calcolati e supportati |
| **2607** | Tutti calcolati; POL1 e POL2 fuori dall'intervallo di conteggi del training, BREM supportato |
| **2804** | Tutti calcolati; POL1 e POL2 supportati, BREM fuori dall'intervallo di conteggi del training |
| **3585** | POL1, POL2 e BREM calcolati e supportati |
| **3776** | Nessuno calcolabile: mancano due donatori affidabili che delimitino la run |

Quindi **quattro run completamente supportate, due parzialmente supportate e una non ricostruibile con i due vicini disponibili**. Complessivamente, includendo anche i flussi realmente assenti e non solo queste anomalie, sono state calcolate 424 ricostruzioni di stato per ciascuno dei cinque metodi; 243 stati risultano supportati. L'inventario totale comprende 863 stati mancanti o trattati come tali: 424 candidati, 429 senza due donatori e 10 senza conteggio h80. Le previsioni degli stati anomali non sono state confrontate con i flussi scartati come se fossero verità.

### Valutazione e artefatti locali

**Extra Trees ibrido resta il candidato principale; Kernel Ridge è un controllo quasi equivalente.** Il confronto completo conferma l'accuratezza centrale, ma non autorizza ancora un recupero generalizzato: servono una procedura di validazione praticabile nei periodi scarsi, bande d'incertezza con copertura adeguata e controllo della normalizzazione. Il cambio di modello da solo non risolve questi limiti. Nessuna modifica metodologica o nuova esclusione è stata applicata dopo aver visto i risultati.

- [338 confronti fra flussi ricostruiti e misurati](../../results/farm-flux-results-20261020/realistic/energy_overlays.pdf).
- [Confronto dei modelli, lacune realistiche](../../results/farm-flux-results-20261020/realistic/block_native_realistic/model_comparison.pdf).
- [Confronto dei modelli, blocchi di tre](../../results/farm-flux-results-20261020/block3/block_3/model_comparison.pdf).
- [Precisione e covarianza di Σ](../../results/farm-flux-results-20261020/realistic/closure/recovery_precision.pdf).
- [Spettri mancanti e anomali ricostruiti, con indicazione del supporto](../../results/farm-flux-results-20261020/realistic/missing_native_candidates.pdf).
- [Riepilogo numerico riproducibile](../../results/farm-flux-results-20261020/review_summary.json).

La copia locale dei risultati numerici è in `results/farm-flux-results-20261020/`. Lo snapshot, tutti gli output e i log originali restano sulla farm nella directory indicata sotto.

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

Gli output finali `prepared/`, `realistic/` e `block3/` sono pubblicati. I tre file `*.exit_code` contengono zero. Il confronto a blocchi è terminato il 19 ottobre alle 17:58, quello realistico il 20 ottobre alle 02:36, ora italiana. L'accounting storico Slurm non è abilitato su questa farm: gli esiti vengono verificati tramite i log, i codici di uscita e gli output pubblicati, non tramite `sacct`. `jobs.json`, `job.sh`, `graal-farm-source-manifest.json` e i log conservano i dettagli dell'esecuzione.

## Verifiche prima del lancio

Snapshot di 383 file, verificati sulla farm prima della sottomissione; checkout operativo della farm preservato, comprese le modifiche preesistenti ai grafici. Manifest locale e manifest della campagna completa identici per SHA-256. Ambiente isolato: Python 3.14.8, ROOT 6.40.04, PyTorch 2.14.1 CPU, NumPy 2.5.4, scikit-learn 1.9.1, uproot 5.7.4. Le differenze di versione rispetto al pilot locale vengono conservate nella provenienza.

Suite locale: **1.271 test superati**, un avviso Matplotlib preesistente. Due test aggiunti successivamente verificano la preparazione completa su una fixture ROOT e il grafico con fit neurale indisponibile; entrambi superati. Sulla farm: **25 test mirati superati**, comprendenti le nuove esclusioni e il confronto dell'osservabile. La revisione indipendente ha verificato l'assenza di contaminazione delle run anomale nel training e segnalato il caso del fit indisponibile, corretto prima del lancio.

Le verifiche software sono distinte dall'accettazione scientifica. I risultati finali sopra confermano un beneficio condizionato e la gerarchia dei modelli, ma mostrano limiti di copertura e disponibilità delle incertezze. Bias medio indipendente e adozione nella misura restano non validati.
