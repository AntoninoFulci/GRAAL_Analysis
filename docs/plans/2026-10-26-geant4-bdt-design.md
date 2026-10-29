# Geant4 e BDT: decisione scientifica e architettura

Creato il 26 ottobre, aggiornato il 27 ottobre 2026 con le indicazioni del responsabile. Stato: requisiti scientifici chiariti, implementazione e validazione aperte. Piano collegato: [esecuzione](2026-10-26-geant4-bdt-execution.md); decisioni e riscontri: [requisiti e benchmark](../../wiki/geant4-validation.md).

## Obiettivo

Usare Geant4 per determinare le efficienze necessarie alla stima delle sezioni d'urto e il fondo residuo nei canali analizzati. Benchmark obbligatori: dE/dx contro energia BGO centrale e dE/dx contro TOF forward, con discriminazione pioni/protoni. Obiettivo esplorativo separato: discriminazione γ/neutrone nel BGO tramite osservabili di tempo e cluster, senza promessa di separazione. Il BDT è parte della selezione da validare, non il fine esclusivo della simulazione.

ROOT rimane utile per generazione, file e analisi. Il responsabile conferma GENBOD e richiede di conservarne i pesi; usare sezioni d'urto sperimentali totali/differenziali disponibili, incluse le tabelle in `laggen`, oppure modelli esterni documentati dove necessario. La physics list governa il trasporto e non sostituisce questi input di produzione. Il percorso ROOT corrente è unweighted tramite accept–reject: serve un contratto distinto per nuovi campioni GENBOD pesati, senza riscrivere i campioni esistenti.

## Stato verificato e limiti

- Il replay dei quadrivettori veri funziona per nove canali; sono disponibili depositi BGO per cristallo e provenienza dell'evento originale. I 214 test passati e il piccolo replay del 26 ottobre certificano il percorso software, non il rivelatore.
- Il responsabile conferma geometria/materiali ricavati dal Fortran come base, con quattro opzioni target: LH₂/LD₂ × cella nominale 6/12 cm e densità nominale del materiale puro liquido. Lo snapshot conserva 6.12 cm e 0.162 g/cm³: non sovrascriverlo per costruire i nuovi profili. Mappa run/configurazione e convenzione lunghezza attiva/nominale restano da registrare.
- `FTFP_BERT_HP_EMZ` e le composizioni runtime attuali sono una base diagnostica da confrontare con dati e alternative, non una precisione già dimostrata.
- Il percorso veloce usa `generators/smearing.h` e `04_bdt_training/photon_loss.py`: perdite Bernoulli indipendenti, dipendenti da energia e angolo, con selezione di esattamente quattro fotoni. Non descrive esplicitamente merging/splitting dei cluster o correlazioni delle perdite dovute a shower e trigger.
- `dataset/mc_samples.py` legge i rami già smeared, non i nuovi `_true`, nonostante una docstring usi “true photons”. I nuovi rami non hanno cambiato automaticamente il training.
- Le 26 feature includono quantità del protone e missing mass. Un buon calorimetro fotonico, da solo, non rende realistico il BDT.
- `Stage1Rows` e `grouped_split.py` offrono già identità d'origine e split 60/20/20. Il percorso legacy senza identità resta 80/20 di sviluppo; non è la base del nuovo confronto finale.
- La soglia corrente massimizza F1 sulla validation. Quel criterio non certifica la precisione o l'assenza di bias dell'asimmetria.
- Il cohort ridotto in `data_test/sample/` risulta assente dalla documentazione locale. Nessun piano presume di avere già un campione di controllo certificato; non si sostituisce con i file completi senza dichiararlo.

## Alternative e scelta proposta

| Scelta | Vantaggio | Limite | Ruolo proposto |
| --- | --- | --- | --- |
| Continuare soltanto con il MC veloce | Costi bassi, iterazioni e regressioni rapide | Risposta semplificata; incertezze di dominio restano | Riferimento corrente, non soluzione definitiva |
| Passare subito a G4 | Depositi e interazioni più dettagliati | Target, risposta, PID e trigger non validati: rischio di imparare nuovi artefatti | Da escludere nello stato attuale |
| MC veloce e G4 sullo stesso truth, confronto controllato | Isola il contributo del detector e misura il beneficio | Richiede calibrazione, controlli indipendenti e tempo di calcolo | **Percorso raccomandato** |
| MC veloce ricalibrato con dati e G4 | Può ridurre i costi dopo la validazione | Non riproduce automaticamente correlazioni; serve verifica separata | Opzione successiva, se i numeri la giustificano |

Manteniamo il BDT attuale come riferimento operativo. Dopo validazione del rivelatore, confrontiamo BDT allenato sul veloce e BDT allenato su G4, valutando soprattutto la dipendenza di efficienze e fondo dal modello. Un modello misto è un esperimento distinto: mescolare campioni con pesi arbitrari può nascondere differenze di dominio. G4 può fornire efficienze anche per una selezione con il BDT attuale; il suo uso non richiede automaticamente un retraining.

## Architettura minima

1. **Truth comune:** GENBOD, canali e finestre cinematiche espliciti, pesi di generazione e densità di proposta conservati, identità della sorgente e dell'entry. Distribuzione fisica da tabelle/modelli dichiarati; beam vero, vertice, profilo e stato sperimentale separati dai valori misurati.
2. **Due risposte:** percorso veloce esistente oppure Geant4 con profilo detector dichiarato. G4 riceve solo particelle non smeared. Il modello Bernoulli `photon_loss` non si applica agli eventi già ricostruiti da G4.
3. **Depositi → lettura detector → ricostruzione:** risposta calibrata per canale, soglie, rumore, inefficienze e trigger; riusare clustering originale in `prean` e ricostruzione/PID senza accesso al truth. Il truth resta disponibile per etichette e diagnosi separate. La preanalisi ROOT corrente consuma già cluster: non è il sostituto dimostrato dell'algoritmo originale.
4. **Confine comune degli eventi osservati:** quattro-vettori ricostruiti e informazioni necessarie alla selezione. Stessi tagli di periodo e stesse 26 feature per i due percorsi. Beam/tagger misurato riceve la propria risoluzione una sola volta.
5. **Training e verifica:** split persistente per origine, weighting condiviso, modello/soglia congelati prima del test finale. Verifica sia del classificatore sia dell'estrazione dell'osservabile.

Le risposte parametrizzate dopo i depositi sono legittime: G4 non elimina elettronica, calibrazione e risoluzione. Per il quenching delle cariche, conservare energia/lunghezza/materiale a livello di step oppure calcolare durante stepping l'energia visibile con modello/parametri versionati; la somma dei depositi per cristallo non permette di ricostruire una risposta non lineare dipendente da dE/dx. Eventuale informazione fisica usata dal modello di scintillazione resta interna alla risposta e non diventa PID vero per la ricostruzione. Il trasporto ottico completo è condizionato a una discrepanza misurata e a proprietà affidabili; un tuning parametrico non deve contare due volte fluttuazioni già simulate.

## Invarianti

- Conservare snapshot/manifest storici, geometria diagnostica e output scientifici. Un profilo di idrogeno è un nuovo input documentato, mai un cambio silenzioso del deuterio o la sola sostituzione del simbolo chimico.
- `origin_id = SHA256_del_ROOT_truth_originale:entry`; copie veloce/G4, repliche di risposta e profili UV/VIS dello stesso evento condividono origine e split. Hash del file ricostruito e seed di risposta non diventano identità del genitore. Una rigenerazione equivalente richiede una mappa di parentela, non un nuovo split indipendente.
- Mantenere conteggi e somme dei pesi di tutti gli eventi generati nel dominio dichiarato. Per campioni pesati `ε=Σ(w I_pass)/Σw`; salvare anche risposta truth→reco e incertezze. Zero hit, trigger fallito e selezione fallita restano nel bookkeeping; aborti/incompletezze invalidano la campagna. Per un export parziale il denominatore è il sottoinsieme effettivamente scelto, non l'intero ROOT sorgente.
- Mantenere pesi di beam, prior di training, rapporti di branching e normalizzazione per canale nei proprietari attuali. Una maggiore statistica simulata non assegna più probabilità fisica al canale. Nessuna sezione d'urto del segnale viene inventata.
- Dataset di training e stima di accettanza hanno scopi diversi. Un prior di classe o la normalizzazione dei pesi del training non è una misura di flusso, sezione d'urto o esposizione.
- UV/VIS, centrale/forward e regione energetica restano domini espliciti. Non generare un canale sotto soglia; non proiettare i nove smoke test a 1.5–1.6 GeV sull'intera copertura VIS.
- Provenienza di ricostruzione schema 2, `pairing_missing_mass`, 26 feature e relativo ordine, convenzioni ratio/likelihood e divisori di bin finito restano invariati.
- La ricostruzione non usa parentela dei fotoni, PID vero o protone vero per facilitare selezione o clustering. Queste informazioni servono solo alle verifiche MC.
- Target LD₂ e generazione nucleare sono scelte distinte: per una reazione su D dichiarare canale coerente/incoerente/quasi-libero, spettatore e trattamento nucleare. Un cambio del materiale non rende valido il truth γp come campione fisico γD.

## Esperimento per decidere sul BDT

Congelare stessa selezione, feature, ipotesi, pesi e split. Nella prima comparazione usare iperparametri già fissati; tuning successivo identico per budget e confinato a train/validation.

| Training | Test veloce indipendente | Test G4 indipendente | Dati di controllo indipendenti |
| --- | --- | --- | --- |
| Veloce | Riferimento interno | Trasferimento del modello corrente | Score, feature, stabilità dei tagli |
| G4 | Trasferimento inverso | Prestazione interna del candidato | Confronto determinante per credibilità detector |

Gli eventi di test sono origini mai usate nel training, in nessuna variante. I controlli dati vengono separati per run da quelli usati per calibrare/tarare il detector. Nessuna “efficienza di segnale sui dati” viene dedotta da retention o ROC su etichette inesistenti; purezza e fondi dei controlli richiedono il proprio metodo e incertezza.

Misurare efficienza di segnale e contaminazione per canale a pari efficienza e a working point fissati, ROC pesata, dipendenza da energia/angoli/molteplicità, topologia del protone, sculpting delle masse, dipendenza azimutale e stabilità rispetto ai nuisance di detector/generatore/pesi. La risoluzione delle feature deve essere sostenuta da quella dei candidati ricostruiti, non solo da un buon score.

Per l'asimmetria eseguire closure con modulazione nota, caso nullo e valori non nulli ammissibili, usando convenzioni e flussi/polarizzazioni dell'analisi. Registrare bias, pull, copertura e incertezza MC. G4 nominale confrontato solo con sé stesso non valida i dati: includere nuisance indipendenti e controlli reali. Questi pseudoesperimenti non riattivano lo stage 09 e non assumono un nuovo modello teorico del segnale.

**Prodotti principali:** efficienze pesate, matrici di risposta/migrazione e stime del fondo residuo con covarianze, per successiva estrazione di sezioni d'urto. Validare chiusura di yield/sezione d'urto con luminosità e densità areale del target dichiarate, branching una sola volta e dipendenza dalla distribuzione generata. Il valore di sezione d'urto esterno usato per generare il segnale non vincola il risultato estratto. `ratio_fit.py` e `conditional_likelihood.py` restano gli stimatori attuali dell'asimmetria: verificarne accettanza comune, differenze tra stati/run e migrazioni. Una loro nuova correzione richiede progetto statistico separato; non è la stessa operazione dell'efficienza per una sezione d'urto assoluta.

## Condizioni per avanzare

| Gate | Condizione osservabile | Se manca |
| --- | --- | --- |
| G0: input | Configurazioni detector/periodo, target, calibrazioni e controlli con fonti e hash; domini coperti dichiarati | Resta diagnostica; si proseguono contratti e inventario |
| G1: risposta | Conservazione/contabilità, hit e lettura per sottosistema; riproduzione delle bande dE/dx–E BGO e dE/dx–TOF con PID π/p, trigger e clustering `prean`; convergenza di cut/modelli | Nessuna efficienza o stima di fondo dichiarata validata |
| G2: contratto | Feature e selezione equivalenti a parità di evento osservato; denominatori integri, nessun doppio smearing/loss, zero origini condivise tra split | Correggere adapter e provenienza |
| G3: BDT | Comparazione incrociata, budget uguale, test finale intatto, supporto statistico nei domini usati, nessun peggioramento non spiegato dei controlli | Mantenere riferimento; iterare su train/validation |
| G4: fisica | Efficienze/risposta e fondo con precisione richiesta, closure di yield/sezione d'urto e controllo della dipendenza da forma/normalizzazione; asimmetria come verifica complementare | Nessuna promozione scientifica |
| G5: operazione | Riproducibilità dichiarata, benchmark, quota di calcolo, artefatti e rollback pronti | Niente campagna estesa |

Le tolleranze fisiche non si ricavano dai 214 test né si scelgono dopo aver visto il candidato. Prima del test fissare bin, precisione relativa delle efficienze, incertezza del fondo e budget sistematico della sezione d'urto, includendo detector/generatore/MC, luminosità e target. La precedente proposta `0.2 σ_stat` per l'asimmetria non è stata approvata e non sostituisce questi requisiti. Se manca una precisione obiettivo, il gate resta aperto; pochi MC non dimostrano equivalenza. Lo studio γ/n ha criteri separati di contaminazione a efficienza fissata e può concludere con separazione insufficiente.

## Risorse e ordine

Prima misurare tempo/evento, memoria, spazio/evento e frazione che supera trigger/selezione, per canale e dominio. Per efficienza non pesata, la stima preliminare `N_gen ≈ (1−ε)/(ε r²)` indica quanta generazione serve per errore relativo `r`; non basta per eventi pesati, correlati, bin con zero successi o stima del bias. Usare `N_eff=(Σw)²/Σw²` solo come diagnostica dei pesi e intervalli/bootstrap raggruppati appropriati per il disegno effettivo.

Un pilot limitato parte da segnale e π⁰π⁰ nei domini aperti; aggiungere i canali con fotoni persi/cluster sovrapposti. I nove canali neutri su p sono il primo catalogo, non una prova di completezza del fondo. Prima di dichiarare fondo totale, valutare contributi omessi plausibili: cariche malidentificate, neutroni, processi nucleari/finestre e accidentali se pertinenti ai dati. Per ciascuno registrare inclusione, esclusione motivata o limite/incertezza da controllo. Senza questo audit il risultato riguarda soltanto il fondo dei processi inclusi. Nessun numero fisso “un milione per canale” precede benchmark e precisione richiesta.

Server di produzione designato dal responsabile: **trima**, senza vincolo di budget imposto; benchmark breve confermato prima di scegliere la statistica. Rilevare ambiente e risorse al momento dell'esecuzione. MacOS resta sviluppo/diagnostica; validare Windows se dovrà essere usato. Prima scalare processi seriali su partizioni disgiunte, con seed e origini espliciti; introdurre multithreading solo dopo test dedicati di lettura HEPEvt, scoring e RNG. Non promettere uguaglianza bitwise tra piattaforme/versioni/configurazioni diverse.

## Fonti

Contratti locali: [stage 03](../../wiki/03-monte-carlo-simulation.md), [stage 04](../../wiki/04-bdt-training.md), [selezione](../../wiki/02-event-selection.md), [dati e provenienza](../../wiki/data-and-artifacts.md). Codice proprietario e modifiche proposte sono elencati nel piano.

Documentazione Geant4 consultata tramite Context7 il 26 ottobre 2026: [`G4VSensitiveDetector`](https://github.com/Geant4/geant4/blob/master/source/digits_hits/detector/include/G4VSensitiveDetector.hh), [`GammaRayTelDigitizer`](https://github.com/Geant4/geant4/blob/master/examples/advanced/gammaray_telescope/src/GammaRayTelDigitizer.cc), [`CexmcEnergyDepositDigitizer`](https://github.com/Geant4/geant4/blob/master/examples/advanced/ChargeExchangeMC/src/CexmcEnergyDepositDigitizer.cc), [salvataggio RNG nell'esempio LXe](https://github.com/Geant4/geant4/blob/master/examples/extended/optical/LXe/README.md). Questi esempi documentano la separazione trasporto/hit/digitizzazione e la gestione dello stato RNG; non forniscono calibrazioni GRAAL. I link `master` non fissano una release: verificare le API contro Geant4 11.4.x installato quando si implementa.
