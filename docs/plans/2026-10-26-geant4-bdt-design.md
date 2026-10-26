# Geant4 e BDT: decisione scientifica e architettura

Data: 26 ottobre 2026. Stato: proposta di lavoro; nessun cambio della produzione autorizzato da questo documento. Piano collegato: [esecuzione](2026-10-26-geant4-bdt-execution.md).

## Obiettivo

Usare Geant4 per descrivere il rivelatore abbastanza bene da sostenere training, selezione e studi di efficienza del BDT, con una decisione basata sui dati e sull'osservabile finale. Assunzione proposta: priorità all'accordo MC–dati e al controllo del bias sull'asimmetria, prima del solo miglioramento della separazione segnale/fondo. La priorità resta correggibile durante il brainstorming.

Il confronto riguarda due modelli di risposta del rivelatore. ROOT rimane utile per generazione, file e analisi anche dopo l'adozione di Geant4. Il generatore esclusivo di spazio delle fasi non viene sostituito automaticamente da una physics list: anche la distribuzione cinematica generata deve essere verificata e variata negli studi sistematici.

## Stato verificato e limiti

- Il replay dei quadrivettori veri funziona per nove canali; sono disponibili depositi BGO per cristallo e provenienza dell'evento originale. I 214 test passati e il piccolo replay del 26 ottobre certificano il percorso software, non il rivelatore.
- `config/run_manifest.csv` classifica run di interesse come `P_UV` e `P_VIS`; `00_common/physics/beam_profiles.py` dichiara target `P`. La geometria congelata GRAAL_26 contiene deuterio. Conoscere il target dell'analisi non fornisce automaticamente dimensioni, finestre, densità, materiali e configurazione del periodo.
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

Manteniamo il BDT attuale come riferimento operativo. Dopo validazione del rivelatore, confrontiamo BDT allenato sul veloce e BDT allenato su G4. Un modello misto è un esperimento distinto, non la scelta automatica: mescolare campioni con pesi arbitrari può nascondere differenze di dominio.

## Architettura minima

1. **Truth comune:** generatori ROOT attuali, canali e finestre cinematiche espliciti, identità della sorgente e dell'entry. Beam vero, vertice, profilo e stato sperimentale separati dai valori misurati.
2. **Due risposte:** percorso veloce esistente oppure Geant4 con profilo detector dichiarato. G4 riceve solo particelle non smeared. Il modello Bernoulli `photon_loss` non si applica agli eventi già ricostruiti da G4.
3. **Depositi → lettura detector → ricostruzione:** risposta calibrata per canale, soglie, rumore, inefficienze e trigger; clustering e ricostruzione del protone senza accesso al truth. Il truth resta disponibile per etichette e diagnosi separate.
4. **Confine comune degli eventi osservati:** quattro-vettori ricostruiti e informazioni necessarie alla selezione. Stessi tagli di periodo e stesse 26 feature per i due percorsi. Beam/tagger misurato riceve la propria risoluzione una sola volta.
5. **Training e verifica:** split persistente per origine, weighting condiviso, modello/soglia congelati prima del test finale. Verifica sia del classificatore sia dell'estrazione dell'osservabile.

Le risposte parametrizzate dopo i depositi sono legittime: G4 non elimina elettronica, calibrazione e risoluzione. Partiamo da una risposta calibrata sui depositi. Il trasporto ottico completo è un'estensione condizionata a una discrepanza misurata e alla disponibilità di proprietà ottiche/superfici affidabili; non è requisito per dichiarare utile G4. Un tuning parametrico non deve contare due volte fluttuazioni già simulate.

## Invarianti

- Conservare snapshot/manifest storici, geometria diagnostica e output scientifici. Un profilo di idrogeno è un nuovo input documentato, mai un cambio silenzioso del deuterio o la sola sostituzione del simbolo chimico.
- `origin_id = SHA256_del_ROOT_truth_originale:entry`; copie veloce/G4, repliche di risposta e profili UV/VIS dello stesso evento condividono origine e split. Hash del file ricostruito e seed di risposta non diventano identità del genitore. Una rigenerazione equivalente richiede una mappa di parentela, non un nuovo split indipendente.
- Mantenere il denominatore di tutti gli eventi generati nel dominio dichiarato. Zero hit, trigger fallito e selezione fallita restano nel bookkeeping; aborti/incompletezze invalidano la campagna, non sono inefficienza fisica. Per un export parziale il denominatore è il sottoinsieme effettivamente scelto, non l'intero ROOT sorgente.
- Mantenere pesi di beam, prior di training, rapporti di branching e normalizzazione per canale nei proprietari attuali. Una maggiore statistica simulata non assegna più probabilità fisica al canale. Nessuna sezione d'urto del segnale viene inventata.
- Dataset di training e stima di accettanza hanno scopi diversi. Un prior di classe o la normalizzazione dei pesi del training non è una misura di flusso, sezione d'urto o esposizione.
- UV/VIS, centrale/forward e regione energetica restano domini espliciti. Non generare un canale sotto soglia; non proiettare i nove smoke test a 1.5–1.6 GeV sull'intera copertura VIS.
- Provenienza di ricostruzione schema 2, `pairing_missing_mass`, 26 feature e relativo ordine, convenzioni ratio/likelihood e divisori di bin finito restano invariati.
- La ricostruzione non usa parentela dei fotoni, PID vero o protone vero per facilitare selezione o clustering. Queste informazioni servono solo alle verifiche MC.

## Esperimento per decidere sul BDT

Congelare stessa selezione, feature, ipotesi, pesi e split. Nella prima comparazione usare iperparametri già fissati; tuning successivo identico per budget e confinato a train/validation.

| Training | Test veloce indipendente | Test G4 indipendente | Dati di controllo indipendenti |
| --- | --- | --- | --- |
| Veloce | Riferimento interno | Trasferimento del modello corrente | Score, feature, stabilità dei tagli |
| G4 | Trasferimento inverso | Prestazione interna del candidato | Confronto determinante per credibilità detector |

Gli eventi di test sono origini mai usate nel training, in nessuna variante. I controlli dati vengono separati per run da quelli usati per calibrare/tarare il detector. Nessuna “efficienza di segnale sui dati” viene dedotta da retention o ROC su etichette inesistenti; purezza e fondi dei controlli richiedono il proprio metodo e incertezza.

Misurare efficienza di segnale e contaminazione per canale a pari efficienza e a working point fissati, ROC pesata, dipendenza da energia/angoli/molteplicità, topologia del protone, sculpting delle masse, dipendenza azimutale e stabilità rispetto ai nuisance di detector/generatore/pesi. La risoluzione delle feature deve essere sostenuta da quella dei candidati ricostruiti, non solo da un buon score.

Per l'asimmetria eseguire closure con modulazione nota, caso nullo e valori non nulli ammissibili, usando convenzioni e flussi/polarizzazioni dell'analisi. Registrare bias, pull, copertura e incertezza MC. G4 nominale confrontato solo con sé stesso non valida i dati: includere nuisance indipendenti e controlli reali. Questi pseudoesperimenti non riattivano lo stage 09 e non assumono un nuovo modello teorico del segnale.

**Confine dell'accettanza, scelta proposta:** questo piano produce mappe diagnostiche di efficienza/risposta e verifica gli stimatori attuali invariati. `ratio_fit.py` e `conditional_likelihood.py` non consumano oggi una mappa di efficienza. La closure deve distinguere accettanza comune ai due stati, differenze tra stati/run e migrazioni cinematiche: la cancellazione di una risposta comune non garantisce cancellazione negli altri casi. Nessuna divisione automatica dei dati per efficienza e nessuna nuova correzione dell'asimmetria. Se il bias richiede una correzione, si apre un progetto distinto con derivazione, contratto statistico, covarianze e validazione; il relativo gate scientifico resta aperto nel frattempo.

## Condizioni per avanzare

| Gate | Condizione osservabile | Se manca |
| --- | --- | --- |
| G0: input | Configurazioni detector/periodo, target, calibrazioni e controlli con fonti e hash; domini coperti dichiarati | Resta diagnostica; si proseguono contratti e inventario |
| G1: risposta | Conservazione/contabilità, hit e lettura per sottosistema, ricostruzione/PID/trigger confrontati con controlli; convergenza di cut/modelli | Nessun training G4 candidato alla produzione |
| G2: contratto | Feature e selezione equivalenti a parità di evento osservato; denominatori integri, nessun doppio smearing/loss, zero origini condivise tra split | Correggere adapter e provenienza |
| G3: BDT | Comparazione incrociata, budget uguale, test finale intatto, supporto statistico nei domini usati, nessun peggioramento non spiegato dei controlli | Mantenere riferimento; iterare su train/validation |
| G4: fisica | Bias/copertura e stabilità dell'osservabile entro budget preregistrato, incertezze detector/generatore/MC incluse | Nessuna promozione scientifica |
| G5: operazione | Riproducibilità dichiarata, benchmark, quota di calcolo, artefatti e rollback pronti | Niente campagna estesa |

Le tolleranze fisiche non si ricavano dai 214 test né si scelgono dopo aver visto il candidato. Prima di aprire il test, fissare un budget per bin e dominio. Proposta da approvare scientificamente: contributo del bias detector/BDT non oltre 0.2 volte l'incertezza statistica obiettivo, verificato con limite superiore che includa l'incertezza del test. Se manca un'incertezza obiettivo credibile, G4 resta aperto; una differenza non significativa con pochi MC non dimostra equivalenza. Fissare anche precisione delle efficienze e copertura attesa con intervalli, prima della campagna.

## Risorse e ordine

Prima misurare tempo/evento, memoria, spazio/evento e frazione che supera trigger/selezione, per canale e dominio. Per efficienza non pesata, la stima preliminare `N_gen ≈ (1−ε)/(ε r²)` indica quanta generazione serve per errore relativo `r`; non basta per eventi pesati, correlati, bin con zero successi o stima del bias. Usare `N_eff=(Σw)²/Σw²` solo come diagnostica dei pesi e intervalli/bootstrap raggruppati appropriati per il disegno effettivo.

Un pilot limitato parte da segnale e π⁰π⁰ nei domini aperti; aggiungere i canali con fotoni persi/cluster sovrapposti per provare le differenze più rilevanti. Il confronto finale include tutti i canali cinematicamente accessibili e quelli assenti sono dichiarati. Nessun numero fisso “un milione per canale” precede questa misura.

MacOS resta sviluppo/diagnostica. Scegliere ambiente di produzione dopo il benchmark e prova Linux; validare Windows se dovrà essere usato. Prima scalare processi seriali su partizioni disgiunte, con seed e origini espliciti; introdurre multithreading solo dopo test dedicati di lettura HEPEvt, scoring e RNG. Non promettere uguaglianza bitwise tra piattaforme/versioni/configurazioni diverse.

## Fonti

Contratti locali: [stage 03](../../wiki/03-monte-carlo-simulation.md), [stage 04](../../wiki/04-bdt-training.md), [selezione](../../wiki/02-event-selection.md), [dati e provenienza](../../wiki/data-and-artifacts.md). Codice proprietario e modifiche proposte sono elencati nel piano.

Documentazione Geant4 consultata tramite Context7 il 26 ottobre 2026: [`G4VSensitiveDetector`](https://github.com/Geant4/geant4/blob/master/source/digits_hits/detector/include/G4VSensitiveDetector.hh), [`GammaRayTelDigitizer`](https://github.com/Geant4/geant4/blob/master/examples/advanced/gammaray_telescope/src/GammaRayTelDigitizer.cc), [`CexmcEnergyDepositDigitizer`](https://github.com/Geant4/geant4/blob/master/examples/advanced/ChargeExchangeMC/src/CexmcEnergyDepositDigitizer.cc), [salvataggio RNG nell'esempio LXe](https://github.com/Geant4/geant4/blob/master/examples/extended/optical/LXe/README.md). Questi esempi documentano la separazione trasporto/hit/digitizzazione e la gestione dello stato RNG; non forniscono calibrazioni GRAAL. I link `master` non fissano una release: verificare le API contro Geant4 11.4.x installato quando si implementa.
