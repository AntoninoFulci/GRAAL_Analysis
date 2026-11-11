# Digitizzazione diagnostica BGO/barrel

La prima conversione funzionale di LAGDIG è disponibile come modalità **`legacy09_diagnostic`**: hit ROOT → ADC BGO e ADC/TDC barrel. Riproduce il calcolo storico su input espliciti. **Non è una risposta calibrata, una ricostruzione h70 o una misura di efficienza.**

## Confine implementato

`geant4/legacy_response.py` seleziona esplicitamente run storica1321 o1324, indipendente dal contatore `run` di GEANT4. Legge `data09.base`, conserva hash/fonti e controlla le sei famiglie di calibrazione. Le calibrazioni dei dati sono ispezionate, non applicate: la modalità simulazione originale bypassa guadagni, piedistalli, linearità BGO e CBAR.

`src/LegacyDigitization.hh` porta BGOD/DEDX/ATDEDX in C++17 con aritmetica REAL binary32 e Gaussiane iniettate. Il trasporto originale resta float64. L'adattatore somma i depositi BGO per cristallo in MeV float64, converte in GeV e restringe una volta all'input REAL di BGOD: non riproduce l'accumulazione REAL per step di GUSTEP. BGO: soglia sui conteggi arrotondati, saturazione inclusiva 2048, totale analogico distinto da somma dei canali sopravvissuti. Barrel: smearing energetico per hit compattato, somma per barra, soglia energetica, primo tempo propagato, smearing temporale e conversione TDC diretta. Nessun quenching o coefficiente di risposta aggiunto.

Il ramo ATDEDX09 è conservato: con i coefficienti data09 l'attenuazione vale 1. Sostituirlo con l'esponenziale07/08 sarebbe un cambiamento fisico. Il reader rifiuta X1>1: richiederebbe un'ulteriore correzione CONSTAN non necessaria ai coefficienti archiviati. Canale barrel 33 e overflow della memoria legacy non vengono emulati.

## Adattamento degli step e limiti

L'adattatore usa depositi positivi, coordinata **globale post-step** e tempo post-step. Gli step barrel mantengono l'ordine originale: si uniscono soltanto all'ultimo record della stessa barra quando la distanza z dall'ancora iniziale è strettamente minore di 1 cm. Posizione media non pesata per energia; tempo del primo step, limitato a 1 µs. I legami record→righe sorgente restano nell'output.

Questa è una convenzione diagnostica dichiarata. L'esclusione del meccanismo 22 di GEANT3 non ha una corrispondenza GEANT4 qualificata; non viene indovinata. Differenze di trasporto, suddivisione degli step, ordine delle tracce e compressione HBOOK impediscono di estendere la parità aritmetica a equivalenza completa GEANT3→GEANT4.

Tutti gli eventi completati restano nel ledger, anche senza hit. Un evento con oltre 100 record barrel conserva i record e lo stato `unsupported_barrel_record_overflow`, senza produrre digit barrel validi. Input abortiti/parziali o strutturalmente incoerenti vengono rifiutati; restano nell'output grezzo del trasporto. Trigger completo indisponibile, non rappresentato come decisione negativa. Pesi e truth restano accessibili tramite riferimento immutabile all'input, senza moltiplicare i depositi per pesi statistici.

## Output e uso

Il launcher produce configurazione e risposta ROOT compressa; la provenienza è conservata in ROOT. Log tecnici separati non contengono dump degli eventi. `response.root` contiene:

| TTree | Contenuto |
| --- | --- |
| `response_events` | Identità originale, run storica distinta, ledger, stato, totali BGO, molteplicità, disponibilità trigger |
| `bgo_digits` | Cristallo e ADC |
| `barrel_digits` | Barra, ADC, TDC, energia e tempo diagnostici |
| `barrel_records` | Input compattati del kernel |
| `barrel_step_links` | Relazione esatta con le righe degli step originali |
| `gaussian_draws` | Sequenza effettiva delle Gaussiane per riproducibilità |

Metadati incorporano configurazione, schema/modello, convenzioni, seed, fonti e limiti. Il generatore diagnostico è distinto da RAND e dal flusso casuale completo LAGDIG. SHA-256 del launcher identifica input, configurazione, codice presente ed eseguibile; il solo nativo usa MD5 per rilevare cambiamenti durante la lettura. Hash del codice presente non prova da solo la corrispondenza con un eseguibile precompilato.

Build autonomo del digitizzatore, con ROOT installato (nessun trasporto GEANT4 richiesto):

```sh
cmake -S 03_mc_simulation/geant4 \
  -B results_test/nuova-campagna/build \
  -DGRAAL_RESPONSE_ONLY=ON -DROOT_DIR=/percorso/root/cmake
cmake --build results_test/nuova-campagna/build --target graal_digitize
```

Poi, dalla root del progetto con package locale disponibile:

```sh
python -m mc_simulation.geant4.digitize \
  --mode legacy09_diagnostic \
  --input /percorso/transport.root \
  --historical-run 1321 \
  --output results_test/nuova-campagna/risposta1321 \
  --executable /percorso/build/graal_digitize \
  --seed 20261109
```

Il parent dell'output deve esistere; la directory finale deve essere nuova. La risposta si trova in `digits/response.root`. Il contratto richiede rami stringa nativi `std::string`; encoding TLeafC estranei al trasporto vengono rifiutati. Gli input scientifici e gli output storici non vengono modificati. Il target nativo richiede ROOT Core/RIO/Tree/TreePlayer; l'opzione `GRAAL_RESPONSE_ONLY` esclude le dipendenze del trasporto.

## Verifica e prossimo confine

Confronto su **423 casi** con BGOD/DEDX/ATDEDX originali compilati in ambiente controllato GRAAL_09: conteggi, consumo delle Gaussiane e bit REAL delle quantità confrontate coincidono. Comprende vicini delle soglie e dei semicanali, saturazione, tempi limite, contributi negativi, ordine dei canali e tutti i 32 coefficienti di attenuazione. Fixture indipendenti verificano anche il compattamento; sanitizer controlla accessi/conversioni. Questo certifica il confine numerico testato, non la risposta sperimentale.

Verifica finale del confine interessato: **197 test passati, nessun fallimento o skip**, includendo trasporto, ROOT, nove canali di replay truth, condizioni per periodo, reader legacy e nuova digitizzazione. Due esecuzioni sullo stesso pilot da80 eventi, configurate per1321 e1324 con seed uguale: tutti80 eventi conservati,204 digit BGO,59 barrel,153 record compattati,853 legami agli step,138 Gaussiane e zero overflow. Le tabelle coincidono salvo la run storica dichiarata, perché i coefficienti MC data09 sono comuni. Ogni `response.root` occupa circa28,7kB, senza duplicare gli hit grezzi. Le fixture separate verificano anche eventi senza hit e overflow.

Evidenza locale e dettaglio dei test d'integrazione: `results_test/geant4-digitization-20261109/`. Audit scientifici conservati in `reports/mapping.md`, `lagdig.md`, `controls.md`; stato e limiti di migrazione in [geant4-migration](geant4-migration).

Il responsabile ha scelto di mantenere la geometria convertita corrente come riferimento del nuovo modello e aumentare la statistica del pilot. Si prosegue quindi con forward/camere e ricostruzione senza richiedere prima una nuova geometria. Per qualificare le efficienze restano da valutare le differenze rispetto al periodo storico, la risposta/trigger e i controlli, e da applicare gli stessi PID/tagli/BDT. I sorgenti `libclusC` sono stati forniti; configurazioni PREAN e provenienza h70 restano da qualificare. Le successive [camere centrali, associazioni forward e trigger](geant4-reconstruction) sono ora collegate e verificate per diagnostica. Entrambe le run1321/1324 hanno già contribuito alle condizioni target/fascio:1324 non valida indipendentemente l'intero setup.

## Pilot esteso sulla geometria corrente

Il 9 novembre, su richiesta del responsabile, il pilot è stato esteso da80 a800 eventi mantenendo geometria, condizioni1998_uv, particelle/direzioni, energia200MeV e seed20261109. Cento eventi per ciascuna delle otto combinazioni γ/p/π± × centrale/forward. Risultato:800 eventi e primarie,1.588.661 step sensibili,268.591 step a deposito nullo;2.056 digit BGO,578 barrel,zero aborti e zero overflow. I sei eventi senza energia totale depositata restano nell'output; possiedono comunque righe di step sensibili. Identità degli eventi e hash di geometria/condizioni sono verificati anche dal coordinatore.

Il ROOT grezzo occupa232.177.163 byte ed è conservato per lo sviluppo delle risposte successive; la risposta ROOT occupa93.410 byte. Gli80 eventi precedenti sono il sottoinsieme iniziale di10 per gruppo del nuovo trasporto: il confronto non riguarda campioni indipendenti. Non sono state cambiate sorgenti di produzione né rieseguita l'intera suite197-test già superata: sono stati verificati i confini specifici del pilot. Evidenze locali: `results_test/geant4-pilot800-20261109/reports/pilot.md`, `validation.root`, `coordinator-check.root`. Build, geometria generata e cache temporanee eliminate dopo il completamento dei job.
