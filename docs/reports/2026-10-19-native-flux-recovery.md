# Ricostruzione nativa dei flussi e beneficio delle run recuperate

Studio locale completato il 19 ottobre 2026. Extra Trees e Kernel Ridge restano i riferimenti migliori; la CNN è vicina, mentre l'MLP non offre un vantaggio chiaro sull'interpolazione. Il recupero riduce l'incertezza mediana di Σ del **9–11%**, includendo il contributo stimato della ricostruzione, ma non migliora tutti i punti. La rappresentazione nativa supera il controllo richiesto; bias medio, copertura indipendente e beneficio fisico complessivo restano da validare. Gli spettri sperimentali non sono adottati nella produzione.

## Nomenclatura prima dei risultati

| Termine | Significato qui |
|---|---|
| Run; stato | Acquisizione di durata assunta pari a 15 minuti; POL1, POL2 e BREM sono i tre stati distinti. |
| Strip; rappresentazione nativa | Canale del tagger: il valore in posizione `i` rappresenta la strip `i+1`, fra 1 e 128. La calibrazione associa separatamente un'energia a ciascuna strip. |
| Donatore; donor | Run precedente o successiva con flusso misurato accettato, nello stesso periodo e stato. I donatori sono sempre due. |
| Bersaglio; target | Run/stato di cui ricostruire il flusso. Non indica il bersaglio fisico protonico. |
| Candidato; candidate | Spettro realmente mancante per cui esistono dati sufficienti a proporre una stima sperimentale. Non equivale a una run approvata per l'analisi finale. |
| Training; validazione; test | Campioni distinti per apprendere il modello, stimare gli errori di ricostruzione e misurarne le prestazioni. La scelta dei parametri usa soltanto suddivisioni interne del training. |
| Blocco di tre run; fold | Il primo raggruppa tre run consecutive da nascondere insieme. Un fold è invece una suddivisione del training per scegliere i parametri. Qui i fold interni sono tre: non sono tre donatori. |
| Lacuna realistica | Maschera che riproduce le assenze locali e le distanze dai due donatori, comprese le run escluse intermedie. Questo disegno è distinto dalla prova uniforme con blocchi di tre run. |
| Grid search | Confronto di una griglia prefissata di impostazioni del modello, senza usare il test per sceglierle. |
| Ridge; Kernel Ridge | Regressione con penalizzazione dei coefficienti; la variante Kernel Ridge permette relazioni non lineari attraverso una funzione di somiglianza fra esempi. |
| Extra Trees | Insieme di alberi di regressione con suddivisioni casuali; la previsione combina quelle dei singoli alberi. |
| MLP; CNN 1D | Rete con strati completamente connessi; rete con filtri che percorrono le strip adiacenti. Entrambe sono implementate in PyTorch. |
| Epoca; epoch; inizializzazione | Un passaggio sull'intero campione di training; un nuovo insieme di pesi iniziali casuali della rete. Si media la previsione di tre inizializzazioni. |
| Larghezza; width; canali | Numero di neuroni negli strati interni dell'MLP, oppure numero di filtri intermedi della CNN. |
| Penalizzazione dei pesi; weight decay | Termine che limita la crescita dei pesi della rete, per ridurre la tendenza ad adattarsi troppo al training. |
| Adam; passo di apprendimento | Algoritmo che aggiorna i pesi durante l'addestramento; il passo controlla l'ampiezza degli aggiornamenti. |
| Loss; KL | La loss è la quantità minimizzata durante il training. Qui è la divergenza di Kullback–Leibler fra forma vera e prevista: zero per forme identiche. Non coincide con L1 e non si interpreta come errore percentuale. |
| Ibrido; hybrid | La forma normalizzata proviene dal modello; l'integrale proviene dall'interpolazione dei due donatori, normalizzata con i conteggi inclusivi h80. |
| Replica; bootstrap | Ripetizione del calcolo dopo aver ricampionato con reinserimento i blocchi di training. Tutti gli stati di una run vengono ricampionati insieme. |
| Residuo | Differenza fra flusso noto e ricostruito su run di validazione. Viene campionato come vettore completo, senza rendere artificialmente indipendenti le strip. |
| Covarianza; correlazione | Misurano quanto due risultati variano insieme nelle repliche. La correlazione è la versione normalizzata della covarianza. |
| Oracle | Estrazione di riferimento che usa i flussi calibrati noti anche per le run nascoste nel test. Non significa conoscenza esatta del valore fisico dell'osservabile. |
| Σ; σ_stat | Asimmetria di fascio misurata; errore statistico della sua stima. Nei budget σ_stat è sempre quello dell'oracle. |
| Stimatore a rapporti; ratio | Estrae Σ dal rapporto dei conteggi nei due stati polarizzati, normalizzati con flusso e polarizzazione. |
| Massima verosimiglianza; likelihood | Stima Σ adattando il modello probabilistico ai dati. È il secondo stimatore già disponibile nell'analisi. |
| p-value; fit alternativo; fallback | Il p-value valuta la compatibilità del fit con i dati nel modello assunto. Lo stimatore a rapporti passa dal solo coseno a costante + coseno + seno quando il p-value del fit nominale scende sotto 0,01. Qui fallback indica questo cambio di funzione. |
| Bias; scostamento appaiato | Il bias è l'errore medio sistematico su prove ripetute. Lo scostamento appaiato confronta invece due estrazioni sugli stessi eventi. Una sola differenza appaiata non misura da sola il bias medio. |
| Copertura; coverage | Frequenza con cui un intervallo contiene il riferimento. Punti dello stesso spettro o dello stesso osservabile sono correlati; non sono altrettante prove indipendenti. |
| RMSE, indicatore appaiato | Qui è la radice di `errore_statistico² + errore_flusso² + scostamento_dall'oracle²`. È un indicatore descrittivo del compromesso precisione/scostamento, non una stima validata del bias medio. |
| Gate; adozione | Criteri per autorizzare l'uso nell'analisi fisica. `not_adopted` mantiene separati gli spettri sperimentali dalla produzione. |

## Campione, ipotesi e rappresentazione

Restano **271 run complete, 813 spettri**, nei periodi UV 1998 e VIS 1999. Sono escluse integralmente le otto run concordate: **1322, 1441, 1454, 1482, 1970, 1988, 2055, 2064**. Non vengono aggiunte esclusioni sulla base degli errori di questa nuova prova.

I conteggi inclusivi restano tutte le entry h80 per run/stato, senza selezione di canale. Le selezioni ηπ0 servono soltanto alla verifica dell'osservabile Σ. Rimangono le ipotesi concordate di durata costante e stabilità di trigger, prescale, tempo morto, fondo e risposta inclusiva. I conteggi locali vengono riutilizzati verificando identità ROOT, numero di entry e completezza del totale.

La verifica dei file grezzi e calibrati controlla che il contenuto sia trasferito alla stessa strip, applicando soltanto il trattamento dei valori negativi già previsto dalla calibrazione. Le energie cambiano leggermente fra run/stati: questa differenza rimane nei metadati di calibrazione e non entra nelle variabili del modello. La verifica certifica la corrispondenza nel software e nei file disponibili; non costituisce un controllo indipendente del cablaggio storico.

La ricostruzione avviene direttamente sulle 128 strip. Per i grafici in energia la calibrazione del bersaglio noto viene applicata **dopo** aver congelato la previsione. Non viene più eseguito il passaggio strip → griglia comune → strip nell'estrazione.

## Modelli e confronto equo

Il confronto include interpolazione, Ridge, Kernel Ridge, Extra Trees, MLP e CNN 1D. Tutti ricevono le informazioni degli stessi donatori e usano le stesse suddivisioni esterne. Il test non contribuisce né alle variabili né all'addestramento o alla scelta dei parametri.

Le 387 variabili iniziali sono i tre vettori da 128 valori — due donatori e loro interpolazione — più due distanze e posizione relativa. Le reti normalizzano ciascun vettore a forma unitaria e standardizzano usando soltanto il training. Apprendono una correzione alla forma interpolata; un'uscita normalizzata non negativa garantisce che l'integrale rimanga quello interpolato. Per le reti le etichette `direct` e `hybrid`, conservate nell'interfaccia comune, danno dunque la stessa normalizzazione per costruzione.

Per ciascuna rete si confrontano quattro configurazioni:

- MLP: larghezza 32 o 64; penalizzazione dei pesi 0 oppure 0,001.
- CNN: 8 o 16 canali; penalizzazione dei pesi 0 oppure 0,001; filtri di larghezza 5.
- Ogni configurazione combina tre inizializzazioni indipendenti, 120 epoche e ottimizzatore Adam con passo 0,003. Si salvano tutte le curve di apprendimento.
- La scelta minimizza l'errore spettrale relativo L1 sui tre fold interni. L1 è la somma degli scarti assoluti per strip, divisa per l'integrale vero. La L1 della forma applica prima la normalizzazione a integrale uno.

Questa griglia è un confronto locale delimitato: non dimostra che tutte le architetture o tutte le altre impostazioni possibili siano peggiori.

## Incertezze e beneficio della misura

Si generano **64 repliche allineate per periodo**, con gli stessi blocchi ricampionati per tutti gli stati e metodi. In ciascuna replica vengono ricalcolati i donatori effettivamente disponibili e riaddestrati i modelli con i parametri già scelti. Non si ripete la scelta dei parametri guardando i risultati esterni.

Si aggiungono residui di validazione completi, abbinati fra stati e metodi. Bersagli che condividono un blocco nascosto o un donatore nella replica condividono anche la sorgente del residuo. Questa è un'**ipotesi di dipendenza da verificare**, non una correlazione già misurata. Aggiungere l'intero residuo alla variazione del modello può contare due volte parte dell'errore di addestramento: le coperture osservate servono proprio a diagnosticare questo limite.

Repliche senza due donatori, con flussi non utilizzabili o estrazioni fallite rimangono nel denominatore richiesto. La covarianza dell'osservabile usa soltanto gli stessi indici di replica completi per tutti i punti valutabili dell'oracle; vengono pubblicati numero e motivi delle perdite. Non si generano repliche supplementari per nascondere i fallimenti.

Per ogni metodo si confrontano:

1. **Senza recupero:** escluse tutte le run mascherate, sia dagli eventi sia dalle esposizioni.
2. **Con recupero:** ripristinati gli eventi e sostituiti soltanto i flussi mascherati con le stime.
3. **Oracle:** stessi eventi del recupero, ma con i flussi calibrati noti.

L'incertezza condizionata statistica più ricostruzione è `sqrt(σ_stat,rec² + σ_flusso²)`. Il rapporto con l'errore statistico senza recupero misura il guadagno di precisione in questo modello di errore. Si riporta anche l'indicatore RMSE appaiato, che penalizza lo scostamento dall'oracle. Nessuno dei due include automaticamente tutte le altre sistematiche dell'esperimento.

I budget approvati restano: cambiamento della sola rappresentazione ≤0,05 σ_stat; bias medio ≤0,10 σ_stat considerando l'incertezza della sua stima; contributo aggiuntivo del flusso ≤0,30 σ_stat; copertura compatibile con 68% e 95%. Il denominatore è sempre l'errore statistico dell'oracle. La copertura condizionata calcolata sui punti correlati e lo scostamento su due periodi di sviluppo non bastano a certificare il bias medio o la copertura su nuovi periodi.

Per VIS le maschere realistiche riguardano soltanto BREM. Gli stimatori correnti di Σ dipendono dai flussi polarizzati: una variazione del solo BREM non cambia il valore centrale. Un'incertezza nulla in quel confronto non valida le correzioni di fondo che richiedono BREM.

## Risultati sugli spettri

La verifica nativa del campione controlla 498 spettri UV e 315 VIS: nessuna differenza fra contenuto grezzo, dopo il trattamento già previsto dei negativi, e contenuto calibrato nella stessa strip. La variazione massima degli estremi energetici fra spettri è 1,476 MeV in UV e 1,040 MeV in VIS.

La prova realistica usa gli stessi 55 spettri del confronto precedente: 8 POL1 e 47 BREM. La prova complementare a blocchi di tre usa **159 spettri**, 53 per stato: 32 run UV e 21 VIS. È un test più severo: la rimozione simultanea degli altri blocchi e le indisponibilità già presenti possono rendere la distanza effettiva dai donatori maggiore della sola lacuna di tre run.

| Metodo | L1 spettrale mediana, lacune realistiche | L1 forma mediana, lacune realistiche | L1 spettrale mediana, blocchi di tre | L1 forma mediana, blocchi di tre |
|---|---:|---:|---:|---:|
| Interpolazione | 19,52% | 15,19% | 12,40% | 10,53% |
| Extra Trees ibrido | 15,30% | 12,46% | 10,20% | 8,48% |
| Kernel Ridge ibrido | 15,09% | 12,63% | 10,12% | 8,56% |
| MLP ibrido | 18,83% | 15,03% | 12,37% | 10,59% |
| CNN 1D ibrido | 15,35% | 12,79% | 10,60% | 8,75% |

**Extra Trees e Kernel Ridge restano i riferimenti migliori; la CNN è competitiva ma non li supera chiaramente. L'MLP resta vicina all'interpolazione.** Non emerge un vincitore unico su tutte le metriche: Kernel Ridge ha una L1 spettrale mediana leggermente inferiore, Extra Trees una L1 della forma leggermente inferiore.

Per le otto POL1 realistiche, la L1 spettrale mediana passa dal 9,75% dell'interpolazione all'8,10% di Extra Trees, 8,17% di Kernel Ridge e 8,11% della CNN. L'MLP raggiunge 9,70%. Questi otto casi non bastano a stabilire una gerarchia definitiva fra metodi così vicini.

Le percentuali native **non vanno confrontate direttamente** con quelle della vecchia griglia energetica comune: la trasformazione precedente mescolava contenuti di strip vicine e smussava gli scarti. Cambia la rappresentazione su cui si misura L1; non è una prova che l'algoritmo sia peggiorato.

La grid search è utile per rendere equo il confronto, ma in questa griglia non risolve i limiti delle reti. Nelle lacune realistiche l'MLP seleziona sempre la configurazione di riferimento, mentre la L1 media della CNN cambia da 0,29663 a 0,29659. Nei blocchi di tre la CNN selezionata dal training passa da 0,28765 a 0,28771 sul test: il tuning non garantisce un miglioramento su ogni campione esterno. Questi confronti non sono usati per riscegliere la configurazione.

Nel test a blocchi di tre il 90° percentile della L1 spettrale resta circa 40% per tutti gli ibridi. L'integrale è comune all'interpolazione e conserva i suoi errori: una forma migliore non elimina una normalizzazione sbagliata. I casi peggiori restano nei risultati e nei grafici; non vengono rimossi dopo aver visto il test.

La coda estrema è rilevante e non va nascosta dalla mediana. Con Extra Trees ibrido:

| Run/stato nascosto | Donatori nello split | Errore relativo dell'integrale | L1 della forma |
|---|---|---:|---:|
| 2072 BREM | 2070, 2076 | +950,9% | 12,2% |
| 2074 BREM | 2070, 2076 | +536,2% | 14,2% |
| 2075 BREM | 2070, 2076 | +337,8% | 15,8% |
| 1508 POL2 | 1506, 1511 | +103,4% | 6,2% |
| 1508 POL1 | 1506, 1511 | +94,5% | 7,8% |

Sono **fallimenti della ricostruzione in questa geometria di test**, non una diagnosi automatica di run fisicamente difettose. Non sono nuove esclusioni. Dimostrano che, anche con una buona forma, la normalizzazione interpolata può fallire fortemente quando cambia il rapporto flusso/eventi fra le run. Il recupero generale richiede quindi anche un controllo delle discontinuità di normalizzazione; cambiare soltanto la rete non risolve questi casi.

## Risultati sulla misura e artefatti

Il confronto usa 10.487 eventi selezionati UV, di cui 1.862 nelle run mascherate, e 2.424 eventi VIS, di cui 495 nelle run mascherate. Per ciascuno stimatore sono valutabili 84 punti UV con recupero contro 83 senza recupero; in VIS sono 15 contro 14. Le griglie complete prevedono rispettivamente 120 e 30 punti: quelli non stimabili rimangono segnalati, senza sostituirli con zeri.

La tabella riporta Extra Trees ibrido. Gli altri metodi danno guadagni mediani quasi uguali; tutti condividono l'integrale interpolato. Il rapporto confronta l'errore statistico più ricostruzione con l'errore statistico senza recupero; valori inferiori a uno indicano maggiore precisione.

| Periodo / stimatore | Rapporto mediano degli errori | Riduzione mediana | Punti migliorati / confrontabili | Nuovi punti stimabili |
|---|---:|---:|---:|---:|
| UV / rapporti | 0,906 | 9,4% | 82 / 83 | 1 |
| UV / verosimiglianza | 0,905 | 9,5% | 81 / 83 | 1 |
| VIS / rapporti | 0,897 | 10,3% | 14 / 14 | 1 |
| VIS / verosimiglianza | 0,892 | 10,8% | 14 / 14 | 1 |

**Il recupero migliora la precisione tipica nel test locale, ma non ogni misura.** Nei peggiori punti UV della verosimiglianza l'errore aumenta di circa l'11,6%. L'indicatore RMSE appaiato, che include anche lo scostamento dall'oracle, conserva gli stessi conteggi di punti migliorati e mediane molto vicine. Questo risultato riguarda le maschere su run note; non certifica ancora il vantaggio delle run realmente mancanti.

Le 54 repliche complete su 64 per periodo arrivano anche al termine dell'estrazione: non si aggiungono fallimenti ai casi senza due donatori già registrati. In VIS, dopo aver verificato i flussi di ogni replica, si riutilizza il fit oracle perché le sole sostituzioni BREM non entrano nei due stimatori attuali. Il guadagno VIS deriva quindi dagli eventi recuperati; non misura la robustezza delle correzioni di fondo BREM.

La differenza dovuta alla **sola rappresentazione è esattamente zero** in entrambi i periodi, su tutti i punti valutabili: il budget di 0,05 σ_stat è rispettato. Per Extra Trees in UV, il massimo scostamento appaiato è 0,0493 σ_stat nello stimatore di verosimiglianza e 0,3465 σ_stat in quello a rapporti. Il massimo contributo stimato del flusso è rispettivamente 0,0190 e 0,1740 σ_stat; nessun punto osservato supera il budget diagnostico di 0,30 σ_stat. Questo non sostituisce la calibrazione indipendente delle incertezze.

### Causa dello scostamento nello stimatore a rapporti

Il punto UV con massa pπ0 fra 1,04 e 1,08 GeV ed energia del fascio fra 1,1 e 1,2 GeV attraversa la soglia di scelta della funzione di fit:

| Flussi utilizzati | p-value nominale | Funzione selezionata | Σ |
|---|---:|---|---:|
| Calibrati noti, oracle | 0,01001238 | Solo coseno | −0,3427543 |
| Extra Trees ricostruiti | 0,00998020 | Costante + coseno + seno | −0,2779799 |

La variazione del flusso POL1 aggregato è appena **0,0512%**, ma porta il p-value da sopra a sotto 0,01. Tutti i casi usano gli stessi nove intervalli azimutali; il calcolo è un fit lineare deterministico, quindi il salto non dipende da minimi locali dell'ottimizzatore. Mantenendo la sola funzione nominale, Extra Trees darebbe Σ = −0,3430045, con uno scostamento di appena −0,00134 σ_stat dall'oracle nominale.

Le 54 repliche Extra Trees si dividono in **26 fit nominali e 28 alternativi**, formando due gruppi distinti. La dispersione propagata include dunque l'instabilità della scelta del fit. Il confronto a funzione fissa è soltanto diagnostico: il codice dello stimatore e i risultati principali conservano la regola attuale. Prima dell'adozione occorre stabilire e validare una politica di fit coerente, senza sceglierla in base al miglior accordo di questo punto. I dettagli sono salvati in [ratio_branch_diagnostic.json](../../results/native-flux-recovery-20261019/ratio_branch_diagnostic.json).

Per Extra Trees, gli intervalli condizionati delle repliche UV contengono l'oracle in 64/84 e 84/84 punti dello stimatore a rapporti, ai livelli 68% e 95%; nello stimatore di verosimiglianza in 62/84 e 75/84 punti. Il secondo valore al 95% è quindi 89,3%. Sono frazioni su punti correlati e sugli stessi eventi, non prove indipendenti di copertura. Non vanno confuse con gli intervalli statistici complessivi della misura.

### Candidati reali e stato dei criteri di accettazione

Sono salvate **30 previsioni**, cinque metodi per sei stati mancanti in cinque run: **1382 BREM, 1409 BREM, 1442 POL1 e BREM, 1474 BREM, 1505 POL1**. Le quattro richieste **1388 BREM, 1416 BREM, 1425 BREM e 2071 BREM** restano fuori dall'intervallo di conteggi supportato dal campione di riferimento; non diventano nuove esclusioni di qualità. I grafici dei candidati mostrano le strip, poiché la calibrazione energetica dello stato mancante richiede una verifica separata.

| Criterio | Esito locale |
|---|---|
| Rappresentazione ≤0,05 σ_stat | Superato: differenza nulla. |
| Bias medio ≤0,10 σ_stat, con incertezza della media | Non validato: gli scostamenti appaiati non stimano un bias medio indipendente. |
| Incertezza aggiuntiva del flusso ≤0,30 σ_stat | Nessun superamento osservato; calibrazione dell'incertezza ancora da validare. |
| Copertura 68% / 95% | Diagnostica disponibile; certificazione indipendente ancora mancante. |
| Miglioramento della misura | Evidenza locale favorevole nella maggioranza dei punti; beneficio fisico complessivo non ancora certificato. |
| Adozione dei candidati reali | `not_adopted`: servono anche incertezze dei candidati e calibrazione energetica indipendente. |

Il seguito scientifico richiede una prova indipendente di bias e copertura, un controllo delle discontinuità del rapporto flusso/eventi e della scelta della funzione di fit, quindi il confronto finale sulle run realmente recuperabili. L'esecuzione locale e i grafici richiesti sono completati; questi requisiti delimitano l'uso fisico dei risultati.

## Copertura dei flussi: evidenza e precisione limitata

I residui accoppiati provengono da 33 run di validazione UV, in 30 blocchi, e 21 run VIS, in 21 blocchi. Delle 64 repliche richieste, **54 per periodo** ricostruiscono contemporaneamente tutti gli spettri mascherati. Le restanti non vengono sostituite per ottenere artificialmente un campione completo. Per singolo spettro le repliche disponibili variano fra 58 e 64 in UV e fra 55 e 64 in VIS.

La tabella mostra Extra Trees ibrido. Per la copertura marginale si calcola prima la frazione di strip coperte in ogni spettro, poi si media sugli spettri. Gli intervalli di confidenza vengono costruiti ricampionando gruppi di bersagli che condividono donatori o blocchi, assumendo indipendenti questi gruppi centrali. Questa approssimazione non comprende tutta la dipendenza dovuta al modello addestrato e al campione di residui comuni. Non si contano le 128 strip come 128 prove indipendenti.

| Campione | Spettri / gruppi | Copertura banda 68% | Copertura banda 95% | Intervallo di confidenza descrittivo sulla copertura 95% |
|---|---:|---:|---:|---:|
| UV POL1 | 8 / 8 | 73,5% | 95,2% | 93,7–96,9% |
| UV BREM | 26 / 22 | 71,1% | 94,6% | 92,3–96,6% |
| VIS BREM | 21 / 15 | 64,6% | 87,6% | 74,9–96,4% |

In VIS la copertura osservata della banda al 95% è inferiore al nominale, ma il campione piccolo produce un intervallo ampio che comprende ancora il 95%. Questo è compatibile con una copertura nominale nel modello di raggruppamento assunto; **non la dimostra**. Anche UV POL1 mostra una banda al 68% più larga del necessario in questa prova: l'intervallo descrittivo sulla sua copertura è circa 71,2–76,5%.

Per l'integrale, la copertura al 95% è 8/8 in UV POL1, 25/26 in UV BREM e 18/21 in VIS BREM. Una copertura osservata di 8/8 non dimostra copertura perfetta: il programma lascia non informativo l'intervallo bootstrap quando tutti gli esiti sono identici al bordo, evitando un falso intervallo esatto [100%, 100%].

Questi risultati motivano il mantenimento dei criteri di bias e copertura come **non ancora validati per l'adozione**, pur avendo ora una prima stima correlata e verificabile delle incertezze.

## File per la revisione

Le due cartelle sono separate: [lacune realistiche e misura](../../results/native-flux-recovery-20261019/) e [blocchi di tre run](../../results/native-flux-three-block-20261019/).

- [Spettri in energia: previsto contro misurato](../../results/native-flux-recovery-20261019/energy_overlays.pdf): una pagina per ciascuno dei 55 bersagli realistici, con rapporto previsto/misurato. Gli atlanti nativi nella sottocartella `block_native_realistic` mostrano anche forma normalizzata, residui e varianti dirette.
- [Confronto di tutti i modelli](../../results/native-flux-recovery-20261019/block_native_realistic/model_comparison.pdf) e [griglie complete](../../results/native-flux-recovery-20261019/block_native_realistic/grid_search.pdf).
- [Curve di apprendimento delle reti](../../results/native-flux-recovery-20261019/neural_learning.pdf), con tre inizializzazioni e confronto delle configurazioni.
- [Incertezze dei flussi](../../results/native-flux-recovery-20261019/flux_uncertainty.pdf): coperture, disponibilità delle repliche, correlazioni e bande sugli spettri.
- [Precisione e covarianza di Σ](../../results/native-flux-recovery-20261019/closure/recovery_precision.pdf) e [scostamenti dal riferimento](../../results/native-flux-recovery-20261019/closure/observable_closure.pdf).
- [Discontinuità del fit a rapporti](../../results/native-flux-recovery-20261019/ratio_branch_diagnostic.pdf): attraversamento della soglia e due gruppi di repliche.
- [Confronto a blocchi di tre](../../results/native-flux-three-block-20261019/block_3/model_comparison.pdf) e [159 confronti in energia](../../results/native-flux-three-block-20261019/energy_overlays.pdf), comprendenti POL2.
- [Candidati realmente mancanti](../../results/native-flux-recovery-20261019/missing_native_candidates.pdf): proposte separate, senza curva vera disponibile e senza adozione nella produzione.

I dati numerici sono disponibili in CSV, JSON e NPZ: parametri e curve di ogni prova, spettri misurati/previsti, indici delle repliche, covarianze, fallimenti e criteri di accettazione. `coverage_cluster_intervals.json` contiene gli intervalli descrittivi sulla copertura; `measurement_summary.json` riepiloga il confronto di precisione per metodo e stimatore. `input_integrity.json` registra gli hash degli input prima e dopo ogni studio.

## Riproduzione e controlli

Ambiente locale isolato `.venv-flux`, basato sul Python compatibile con ROOT. Versioni registrate: Python 3.14.6, PyTorch 2.14.1, NumPy 2.5.0, scikit-learn 1.9.0 e uproot 5.7.4. scikit-learn rimane per i modelli di riferimento; tutte le reti usano PyTorch.

```bash
MPLCONFIGDIR=/tmp/graal-mpl XDG_CACHE_HOME=/tmp/graal-cache \
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
.venv-flux/bin/python -m flux_studies.study_native_recovery \
  --output-dir results/native-flux-recovery-20261019-rerun --replicas 64

MPLCONFIGDIR=/tmp/graal-mpl XDG_CACHE_HOME=/tmp/graal-cache \
.venv-flux/bin/python -m flux_studies.native_diagnostics \
  results/native-flux-recovery-20261019-rerun

MPLCONFIGDIR=/tmp/graal-mpl XDG_CACHE_HOME=/tmp/graal-cache \
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
.venv-flux/bin/python results/native-flux-three-block-20261019/reproduce.py \
  --output-dir results/native-flux-three-block-20261019-rerun
```

Gli output devono avere nomi nuovi. Il file `execution.json` registra impostazioni, versioni e comando di ciascuno studio. I controlli comprendono separazione dei campioni, identità nativa, conservazione dell'integrale, riproducibilità delle reti, ricampionamento sincronizzato, conteggio dei fallimenti e rimozione coerente di eventi/esposizioni nello scenario senza recupero.

La suite completa ha superato **1.265 test**, con un avviso Matplotlib preesistente sulla legenda di un grafico estraneo a questa fase. Sono passati anche i due test aggiunti successivamente sugli intervalli di copertura e la verifica mirata dei 15 test dell'estrazione dopo l'aggiunta dei messaggi di avanzamento. La revisione indipendente ha portato a correggere il raggruppamento dei donatori nelle repliche, a rendere non vacui i test delle correlazioni e a distinguere esplicitamente precisione condizionata e beneficio fisico validato.

Nessuna campagna nuova sulla farm è stata avviata. Gli spettri ricostruiti rimangono separati dagli input di produzione.
