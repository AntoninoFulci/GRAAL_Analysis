# Flussi mancanti: lacune realistiche e chiusura sugli osservabili

Esecuzione del 19 ottobre 2026. **Completati l'inventario dei flussi mancanti,
le prove di ricostruzione su flussi conosciuti e il confronto sugli osservabili.**
Le stime dei flussi mancanti sono salvate separatamente e non sostituiscono
ancora i flussi usati nell'analisi fisica. Di seguito sono spiegati i termini
usati nel testo e le etichette inglesi presenti nei file e nei grafici.

## Come leggere la nomenclatura

### Dati, run e ricostruzioni

| Termine nel report o nei file | Significato in questo studio |
|---|---|
| **Run** | Una singola acquisizione, identificata da un numero, per esempio 1442. Qui si assume una durata di 15 minuti per tutte le run. |
| **Periodo; UV / VIS** | Gruppo di acquisizioni distinto nel registro, per esempio `1998_uv`. UV e VIS indicano rispettivamente laser ultravioletto e visibile. Il metodo cerca vicini nello stesso periodo e stato. |
| **Stato; POL1 / POL2 / BREM** | Categoria di acquisizione dentro una run: due stati di polarizzazione lineare e lo stato BREM, associato alla radiazione di frenamento. Ogni coppia run/stato ha il proprio spettro di flusso. |
| **Tripletto completo** | Per una run sono presenti tutti e tre gli spettri POL1, POL2 e BREM. Tre spettri non significano tre run indipendenti. |
| **h80; conteggio inclusivo** | `h80` è l'albero di eventi nei file di preanalisi. Il conteggio inclusivo conta tutte le sue entry per run/stato, senza selezionare un canale fisico. È distinto dal numero di eventi selezionati per estrarre un osservabile. |
| **Spettro; bin; integrale; forma** | Lo spettro distribuisce il flusso fra intervalli energetici, detti bin. L'integrale è la somma dei contenuti dei bin. La forma è lo spettro diviso per il suo integrale, così da confrontare la distribuzione indipendentemente dal flusso totale. |
| **Strip; griglia nativa / comune** | La strip è un canale del tagger, il sistema che permette di determinare l'energia del fotone incidente. La griglia nativa associa i bin alle strip con la calibrazione della run; la griglia comune usa gli stessi 128 intervalli energetici, fra 0,5 e 2 GeV, per confrontare e predire gli spettri delle diverse run. Il trasferimento tra griglie può modificare la forma. |
| **Flusso vero; truth; measured** | Il flusso calibrato noto, usato come riferimento nel test. «Vero» è un'abbreviazione: non significa che la misura sia priva di incertezza. |
| **Bersaglio; target** | La run/stato di cui vogliamo ricostruire il flusso, realmente mancante oppure nascosto per un test. Da non confondere con il bersaglio fisico dell'esperimento: nel registro `target=P` indica il bersaglio protonico. |
| **Donatore; donor; vicino** | Una run con flusso calibrato disponibile e accettato dai controlli, che fornisce uno spettro alla ricostruzione del bersaglio. Qui si usano un donatore precedente e uno successivo, nello stesso periodo/stato. Esempio: per 1442 i donatori possono essere 1440 e 1443, poiché 1441 è esclusa. |
| **Lacuna; gap; geometria della lacuna** | Una sequenza senza flussi utilizzabili. Nei file `gap` è la distanza complessiva fra i due donatori; la geometria specifica anche le due distanze dal bersaglio. Una coppia 30/15 minuti è diversa da 15/30, pur avendo entrambe `gap=45`. Sono tempi assunti dall'ordine delle run, non intervalli misurati. |
| **Maschera; masked; held-out** | Nascondere al modello dati che conosciamo, per poter confrontare la previsione con il riferimento. Qui si nasconde all'addestramento l'intera run; si valutano soltanto gli stati previsti dalla maschera. I file originali non vengono cancellati o modificati. |
| **Blocco di run** | Gruppo di run tenute insieme quando si assegnano i dati ad addestramento o verifica. «Blocchi da tre» significa tre run per gruppo, non tre donatori. Il numero di donatori resta due. |
| **Esposizione; strato run/strip** | L'esposizione contiene flussi e polarizzazioni necessari a normalizzare gli eventi di una coppia run/strip. Tale coppia è chiamata strato. Non indica qui un tempo di acquisizione misurato. |

### Modelli e campioni di confronto

| Termine | Significato in questo studio |
|---|---|
| **ML; machine learning** | Metodo che apprende dai dati una relazione fra informazioni disponibili e flusso da predire. |
| **Training** | Run usate per addestrare il modello. I donatori devono appartenere al campione consentito per quella specifica prova; non tutte le run di training sono donatori di ogni bersaglio. |
| **Validazione; validation** | Nel confronto esterno, campione separato usato per costruire bande empiriche d'errore. La «validazione interna» alla grid search è invece ricavata esclusivamente dal training e serve a scegliere i parametri del modello. |
| **Test; holdout di sviluppo** | Run escluse dall'addestramento e dalla scelta dei parametri, usate per misurare gli errori. Qui i periodi erano già stati esaminati e hanno informato le esclusioni: il test resta di sviluppo, non è una conferma indipendente su nuovi dati. |
| **Feature** | Variabile fornita al modello. Qui sono 387: 128 valori per ciascuno dei due donatori, 128 dell'interpolazione, due distanze e la posizione relativa del bersaglio fra i donatori. I valori di flusso sono normalizzati per il numero di eventi. |
| **Grid search; iperparametro; fold** | La grid search confronta una lista fissata di impostazioni del modello, dette iperparametri. Divide il training in sottocampioni, detti fold, addestra su alcuni e valuta sugli altri. Qui usa tre fold interni; `training-only` significa che non consulta il test esterno. |
| **Seed** | Numero che fissa le scelte pseudocasuali, così da poter riprodurre la stessa suddivisione dei dati e lo stesso esperimento. |
| **Ridge / Kernel Ridge / Extra Trees** | Tre famiglie di regressione: Ridge apprende una relazione lineare con una penalizzazione dei coefficienti; Kernel Ridge permette relazioni non lineari tramite somiglianze fra esempi; Extra Trees combina le previsioni di molti alberi decisionali randomizzati. |
| **Interpolazione; linear** | Combina i due spettri donatori con pesi determinati dalle distanze, dando più peso al vicino più prossimo, dopo averli divisi per i rispettivi conteggi di eventi; poi moltiplica per il conteggio del bersaglio. `linear` nei file indica questo riferimento, non il modello Ridge. |
| **Diretto / ibrido; direct / hybrid** | Nel metodo diretto il modello determina sia forma sia integrale. Nell'ibrido la forma viene dal modello, mentre l'integrale viene dall'interpolazione. L'ibrido conserva quindi anche gli eventuali errori dell'integrale interpolato. |
| **Benchmark; pilot** | Rispettivamente un confronto quantitativo fra metodi e uno studio preliminare. Nessuno dei due termini implica una validazione definitiva. |

### Candidati, supporto e uso nell'analisi

**Un flusso candidato è una stima da valutare, non un flusso già approvato per
l'analisi fisica.** Quando invece si parla di «modello candidato», si intende
un algoritmo preso in considerazione per la scelta finale, non un nuovo dato.
Nei file compaiono stati distinti perché i controlli avvengono in più passaggi:

| Etichetta | Significato e conseguenza |
|---|---|
| **`candidate`** nell'inventario iniziale | Stato mancante con conteggio h80 positivo, due donatori utilizzabili e run non esclusa. È sufficiente per tentare la previsione, ma non significa che tutti i controlli successivi siano superati. |
| **Supporto; support** | Insieme delle condizioni rappresentate nei dati disponibili. Qui si verifica che le distanze dai donatori siano già state provate nella validazione e che il conteggio del bersaglio rientri nell'intervallo osservato nel training. Non significa assistenza tecnica né prova di correttezza fisica. |
| **`experimental_candidate`** | Previsione che supera quei controlli di supporto: viene salvata fra gli spettri sperimentali separati. Può ancora mancare una validazione sufficiente per usarla negli osservabili finali. |
| **`unsupported_candidate`** | Tentativo di previsione fuori dalle condizioni verificate. Il motivo rimane nel report, ma lo spettro non entra nei file dei candidati utilizzabili. Questo non aggiunge automaticamente la run alla lista delle run anomale. |
| **`quality_excluded`** | Run esplicitamente esclusa dalle regole condivise di qualità o dalla decisione dell'utente. L'esclusione vale per tutti i suoi stati, per training, donatori ed estrazione degli osservabili. |
| **`missing_h80_count` / `no_two_sided_donors`** | Rispettivamente: manca un conteggio h80 positivo per il bersaglio, oppure manca almeno uno dei due donatori necessari. In queste condizioni non viene proposta una ricostruzione con questo metodo. |
| **Produzione; adozione; `not_adopted`** | La produzione è l'analisi che fornisce i risultati fisici da usare. L'adozione è l'inserimento di un flusso ricostruito in quell'analisi. `not_adopted` significa che tale inserimento non è avvenuto. |
| **Gate; `adoption_gate`** | Riepilogo dei requisiti e degli impedimenti all'adozione. Qui riguarda la validazione indipendente, le incertezze, la conversione alle strip e la tolleranza fisica accettabile. Non è una probabilità o un punteggio del modello. |

Esempio: 1388/BREM è inizialmente `candidate`, perché ha conteggi e donatori;
diventa `unsupported_candidate` perché i suoi conteggi sono fuori dall'intervallo
verificato. 1382/BREM supera anche questo controllo e diventa
`experimental_candidate`, ma resta `not_adopted` per l'analisi produttiva.

## Esclusioni concordate

La policy v2, cioè la seconda versione del file di regole condivise sulle
esclusioni, esclude interamente **1322, 1441, 1454, 1482, 1970, 1988, 2055,
2064**, da tutti gli stati, training, donatori, eventi ed esposizioni.

- 1322, 1482, 1970: evidenza originale sul rapporto flusso/evento rispetto alla
  mediana periodo/stato, fuori da [0,01; 100].
- 1441, 1454, 1988, 2055, 2064: esclusione esplicitamente richiesta dall'utente
  dopo gli errori BREM osservati nel benchmark precedente. Non si sostiene che
  soddisfino il criterio precedente. Evidenza, decisione e impronta del file
  tabellare CSV (l'hash, che identifica il suo contenuto) sono
  registrati separatamente nella [policy](../../config/run_quality_exclusions.json).

Impronta della policy, calcolata con l'algoritmo SHA256:
`c84c1a7e67018aed4f23002888bd6484617cccf9c9fc1d4339e7fcab096481b2`.
Restano **271 run, 813 spettri** con triplette complete e conteggi nei due h80
locali. Non è stata eseguita l'indagine fisica BREM, come richiesto.
Le esclusioni derivano da dati già ispezionati: nessun risultato di questa fase
viene presentato come conferma indipendente.

## Inventario reale

Il manifest è il registro che associa ogni run a periodo, bersaglio fisico e
tipo di fascio. Inventario su tutte le sue 1831 run P e sul calibrato locale:
**842 stati mancanti in 541 run**. Sono assenze nel file calibrato; non vengono
confuse con assenza di istogrammi grezzi o con istogrammi presenti ma difettosi.

Per 832 stati mancano i conteggi h80 nei due file locali usati qui. Per gli
altri **10 stati, in nove run**, esistono conteggi e due donatori puliti nello
stesso periodo/stato. Sono otto BREM e due POL1; la run 1442 manca di entrambi.
Distanze basate sull'ordine nel manifest e sull'ipotesi di 15 minuti/run.

| Run | Stato mancante | Conteggi h80 | Esito del controllo di supporto |
|---|---|---:|---|
| 1382 | BREM | 1954 | candidato sperimentale |
| 1388 | BREM | 330 | fuori dal range di conteggi del campione di training |
| 1409 | BREM | 1056 | candidato sperimentale |
| 1416 | BREM | 604 | fuori dal range di conteggi del campione di training |
| 1425 | BREM | 65 | fuori dal range di conteggi del campione di training |
| 1442 | POL1 | 130783 | candidato sperimentale |
| 1442 | BREM | 1003 | candidato sperimentale |
| 1474 | BREM | 1013 | candidato sperimentale |
| 1505 | POL1 | 56184 | candidato sperimentale |
| 2071 | BREM | 232 | fuori dal range di conteggi del campione di training |

Il controllo sul range dei conteggi è conservativo: indica assenza di verifica
in quel regime di statistica, non dimostra che quelle run siano fisicamente
anomale. Non sono nuove esclusioni nella policy degli osservabili.
Il controllo geometrico richiede una coppia di distanze sinistra/destra già
rappresentata nella validazione, non soltanto lo stesso intervallo totale.

## Validazione con maschere realistiche

Seed 142; intere run nascoste al training, compresi tutti i loro stati. Si
valutano soltanto gli stati che riproducono le lacune reali. I vicini esterni
rimangono nel training; le lacune artificiali non si fondono accidentalmente.
Una run esclusa adiacente all'assenza allarga la finestra nascosta anche se non
è un bersaglio da ricostruire. Per esempio 1442 ha distanze 30/15 minuti perché
1441 è esclusa: il test riproduce entrambe le distanze.

Sono valutati **55 spettri: 34 UV, 21 VIS; 8 POL1 e 47 BREM**. Nessun POL2 è
mancante nelle nove run locali: questo disegno non fornisce una nuova prova
specifica su POL2. Le maschere realistiche sono replicate sul campione noto
per aumentare il numero di confronti; non sono 55 nuove run realmente mancanti.

Stesse feature e grid search training-only del benchmark precedente. Ridge
rimane nei plot come riferimento; confronto principale fra interpolazione,
Extra Trees ibrido e Kernel Ridge ibrido. Tutti gli ibridi conservano l'integrale
interpolato. La validazione separata calibra soltanto bande empiriche esplorative.
Sono intervalli costruiti dagli errori osservati nel campione di validazione;
non hanno ancora una garanzia di copertura, cioè di contenere il riferimento
con la frequenza nominale indicata, per esempio 68% o 95%.

Le colonne seguenti misurano aspetti diversi dell'errore:

- **L1 spettrale relativa:** somma degli scarti assoluti fra previsione e
  riferimento, bin per bin, divisa per l'integrale del riferimento. Risente di
  forma e normalizzazione; gli scarti di segno opposto non si cancellano.
  Un valore del 7% non significa che ogni bin abbia un errore del 7%.
- **Errore integrale assoluto relativo:** prima si calcola
  `(integrale stimato / integrale vero) − 1`, poi se ne prende il valore
  assoluto. Misura soltanto l'errore sul flusso totale.
- **L1 della forma:** somma degli scarti assoluti dopo aver normalizzato
  separatamente entrambi gli spettri a integrale uno. Misura la sola forma.
- **Mediana; p90; n:** la mediana divide a metà gli errori del campione; p90 è
  il 90° percentile, sotto cui cade circa il 90% degli errori. `n` è il numero
  di spettri confrontati. La «coda» degli errori indica i casi peggiori, che
  possono essere poco visibili nella mediana.
- **Residuo; residual:** differenza con segno fra previsione e riferimento.
  Nei grafici il residuo di ciascun bin viene diviso per l'integrale vero;
  un residuo positivo indica una sovrastima.

| Metodo | L1 spettrale mediana | L1 p90 | Errore integrale assoluto mediano | L1 forma mediana |
|---|---:|---:|---:|---:|
| Interpolazione | 14,27% | 33,77% | 4,70% | 11,02% |
| Extra Trees ibrido | 11,51% | 33,41% | 4,70% | 8,95% |
| Kernel Ridge ibrido | 11,65% | 33,38% | 4,70% | 9,10% |

| Stato | n | Interpolazione L1 mediana | Extra Trees ibrido | Kernel Ridge ibrido |
|---|---:|---:|---:|---:|
| POL1 | 8 | 6,90% | 5,73% | 5,77% |
| BREM | 47 | 14,75% | 12,32% | 12,19% |

L1 = somma degli scarti assoluti bin per bin / integrale vero. Questi valori
non vanno confrontati direttamente con le mediane globali del pilot precedente:
qui BREM costituisce 47/55 del campione. Non è un peggioramento dimostrato del
modello. Il miglioramento mediano non elimina la coda degli errori.

## Chiusura sugli osservabili

La **chiusura**, o *closure test*, consiste nel ripetere l'estrazione di un
osservabile su dati di cui conosciamo i flussi, sostituendone alcuni con le
ricostruzioni e confrontando i risultati. Qui l'osservabile è **Σ (Sigma)**,
l'asimmetria rispetto alla polarizzazione lineare del fascio; **ΔΣ** è la
differenza fra le due estrazioni indicate nella tabella.

Input `results/uv/reco/reco_eta_pi0_bdt.root` e corrispondente VIS; quadrivettori
raw, cioè ricostruiti prima dell'eventuale fit cinematico, e campione eta-pi0
selezionato BDT (*Boosted Decision Trees*, un classificatore ad alberi usato
per selezionare gli eventi, distinto dal modello che ricostruisce i flussi).
Il campione ML resta inclusivo: il canale
specifico entra soltanto nella prova sugli osservabili. Riusati il selettore e
l'estrattore effettivi. Un **estimatore** è il procedimento che ricava Σ dai
dati: **ratio** usa rapporti di distribuzioni normalizzate, mentre
**likelihood** adatta un modello probabilistico ai dati massimizzandone la
verosimiglianza. Si usano 12 bin in **phi (φ)**, l'angolo azimutale, e le griglie
energetiche standard dei profili registrate nel file JSON di risultati.
Il **binning** è la suddivisione in intervalli; qui è fisso, senza scegliere
automaticamente quello preferito per ogni punto (*best-binning*).

Per ciascun periodo, le predizioni sostituiscono insieme soltanto gli stati
mascherati; tutti gli altri flussi restano misurati. Stessi eventi, stessa
selezione, stessi run/strip e stesso binning per ogni scenario. Gli strati senza
flusso valido sono selezionati una sola volta prima del confronto; nessun modello
può rimuovere silenziosamente strati o maschere difficili.

Il **roundtrip**, letteralmente «andata e ritorno», trasferisce il flusso vero
dalla griglia nativa alla griglia comune e poi di nuovo alle strip. Non usa ML:
misura l'effetto della sola discretizzazione, cioè della rappresentazione dello
spettro mediante bin diversi. Un **punto stimabile** è una combinazione di
intervalli fisici per cui l'adattamento del modello ai dati, detto *fit*,
produce un risultato convergente; un punto non stimabile non equivale a Σ=0.

Cinque scenari: flussi nativi veri; flussi veri trasferiti alla griglia comune e
riportati alle strip (controllo roundtrip); interpolazione; Extra Trees ibrido;
Kernel Ridge ibrido. Gli assi del bersaglio noto entrano soltanto nel confronto
finale, dopo la predizione. Questo separa discretizzazione e ricostruzione.

- UV: 10.487 eventi selezionati; 1.862 nelle run mascherate. Per ciascun
  estimatore 84 punti confrontabili su 120 previsti; 36 non stimabili.
- VIS: 2.424 eventi selezionati; 495 nelle run mascherate. Per ciascun
  estimatore 15 punti confrontabili su 30 previsti; 15 non stimabili.
- Gli insiemi di punti stimabili coincidono fra tutti e cinque gli scenari.

Per UV, massimi sui punti confrontabili:

| Confronto | Estimatore | max assoluto ΔΣ | max assoluto ΔΣ / errore statistico del riferimento |
|---|---|---:|---:|
| Roundtrip − nativo | ratio | 0,06480 | 0,34666 |
| Roundtrip − nativo | likelihood | 0,00313 | 0,02341 |
| Extra Trees ibrido − roundtrip | ratio | 0,00044 | 0,00215 |
| Extra Trees ibrido − roundtrip | likelihood | 0,00303 | 0,03333 |
| Extra Trees ibrido − nativo | ratio | 0,06476 | 0,34648 |
| Extra Trees ibrido − nativo | likelihood | 0,00435 | 0,05112 |

I due massimi di ciascuna riga possono appartenere a punti diversi. Il rapporto
con l'errore statistico è una **misura di sensibilità**, non una significatività:
nessuna ipotesi di indipendenza fra i due risultati sugli stessi eventi.
Un **bootstrap appaiato** ripeterebbe il confronto usando gli stessi
ricampionamenti casuali degli eventi per entrambi gli scenari, per stimare
l'incertezza della differenza mantenendo le correlazioni. La **covarianza**
descrive come le variazioni di quantità diverse si muovono insieme, per esempio
fra bin energetici o stati. Qui non è stato eseguito tale bootstrap né validata
la covarianza dei flussi.

Il cambio di griglia merita attenzione: per il ratio arriva a circa 0,35 errori
statistici, molto più del contributo aggiuntivo del modello in questo test.
Non si può dichiarare risolto il passaggio operativo dagli spettri energetici
comuni ai flussi per strip.

Per VIS le maschere riguardano soltanto BREM. Le Σ centrali di questi estimatori
non dipendono da BREM, quindi tutte le differenze sono nulle **per costruzione**:
non è una validazione di BREM, delle correzioni di fondo o delle sue incertezze.

## Candidati e stato operativo

Pubblicati spettri sperimentali per **sei stati in cinque run**: 1382/BREM,
1409/BREM, 1442/POL1, 1442/BREM, 1474/BREM e 1505/POL1. Tre metodi per stato,
18 righe complessive. Per la run 1442 entrambi gli stati mancanti sono coperti.
Le quattro predizioni fuori supporto non compaiono negli array o nei plot dei
candidati; restano motivate nell'inventario e nel report di supporto.

I candidati sono su griglia energetica comune, senza errori calibrati, e non
vengono caricati dall'estrazione produttiva. `adoption_gate.json` resta
`not_adopted`: conferma indipendente assente, covarianza/copertura non validate,
tolleranza fisica non definita e assi delle strip degli stati mancanti non
stabiliti in questo studio. Nessun asse viene copiato silenziosamente da un
altro stato. I ROOT originali e gli output di produzione restano invariati.

Lavoro residuo prima dell'adozione: risolvere e validare il trasferimento agli
assi delle strip, calibrare e propagare le incertezze correlate, confermare su
nuovi dati e fissare la tolleranza sugli osservabili. Per estendere alle altre
832 assenze servono conteggi inclusivi h80 dei rispettivi periodi.

## Artefatti e prove

Gli **artefatti** sono i file prodotti dallo studio. CSV indica tabelle di testo;
JSON dati e metadati strutturati; NPZ insiemi compressi di array numerici NumPy;
ROOT il formato usato per eventi e istogrammi dell'analisi. Un **audit** è il
registro verificabile di input, scelte ed esclusioni. «Righe allineate» significa
che la riga numero i del CSV descrive lo spettro numero i nell'array associato.

Output: [realistic-flux-closure-20261019](../../results/realistic-flux-closure-20261019/).

- `gap_inventory.json`, `missing_states.csv`, `gap_inventory.png`: mappa globale.
- `realistic_design.json`: maschere, finestre complete, ruoli e casi non coperti.
- `block_realistic/`: 55 pagine di confronto con la verità, diagnostica, griglie,
  CSV, array NPZ e audit dei fit/donatori.
- `closure/observable_closure.json`, `.csv`, `.pdf`: confronti, denominatori,
  proiezioni per stato e limiti della prova.
- `candidate_predictions.csv` e `candidate_spectra.npz`: righe allineate;
  `missing_candidates.pdf`: sei pagine, una per stato mancante supportato.
- `candidate_support.json`, `candidate_fits.json`, `candidate_exclusions.json`,
  `adoption_gate.json`, `input_integrity.json`: provenienza e stato operativo.

Comando:

```bash
MPLCONFIGDIR=/tmp/graal-mpl XDG_CACHE_HOME=/tmp/graal-cache \
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
python3 -u -m flux_studies.study_realistic_gaps \
  --calibrated-flux data/00_external/flux_calibrated.root \
  --h80 test_data/pre_analyzed/pre_analisi_1998_uv.root \
  --h80 test_data/pre_analyzed/pre_analisi_1999_vis.root \
  --reco-uv results/uv/reco/reco_eta_pi0_bdt.root \
  --reco-vis results/vis/reco/reco_eta_pi0_bdt.root \
  --output-dir results/realistic-flux-closure-20261019
```

**Verifica completa: 1232 test passati**, un warning preesistente di legenda
vuota, 161,70 secondi. Regression test per policy esplicita, isolamento dei
bersagli, distanza reale dai donatori, maschere mancanti, supporto dei candidati,
proiezione e identità degli scenari. Corretto anche il conflitto fra nomi dei
test qualità, così le due suite vengono effettivamente raccolte.
Revisione indipendente senza rilievi materiali residui. Hash prima/dopo identici;
verificata l'assenza di tutte le otto run da donatori, bersagli ed esposizioni;
indici, dimensioni NPZ e PDF verificati, plot ispezionati visivamente.
