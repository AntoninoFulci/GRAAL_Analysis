# Tracking forward NEW_PLAN da misure di camera

**Stato del 9 novembre 2026:** il percorso diagnostico `selected26_newplan_diagnostic` esegue la catena completa **trasporto ROOT → ingressi carichi nei piani → fili digitali → tracce delle due camere → ROOT**. Il riferimento resta la geometria corrente **GRAAL_26 + GRAAL_NEW_PLAN + GRAAL_OLD_CYL**. NEW_PLAN non implica NEW_CYL e non modifica le condizioni storiche dei dati.

I sorgenti originali del tracking **centrale e forward sono stati recuperati** nell'archivio PREAN. Il port corrente riguarda il percorso forward; non dipende dalla libreria di clustering BGO `libclusC`. La condizione prevista per sostituire un tracker originale non recuperabile con tecniche CMS non si è verificata: **nessun sorgente o componente CMS è stato importato**. Il recupero degli algoritmi non identifica automaticamente il programma che produsse gli h70 storici.

## Confine implementato

La configurazione delle camere proviene esplicitamente da `data26.base`, separata dalla risposta [BGO/barrel legacy09](geant4-digitization). I campi originali, le unità e gli hash sono registrati nel file ROOT di configurazione.

| Parametro | selected26 |
| --- | --- |
| Semilarghezze XP1 / XP2 | 48 / 57.6 cm |
| Centri ZP1 / ZP2 | 94.4 / 134.4 cm |
| Fili NF1 / NF2 | 320 / 384 |
| Passo dei fili | 0.3 cm |
| Angolo di lettura ANG(5) | −45° |
| Efficienze configurate U/V/X/Y | 1 / 1 / 1 / 1 |

L'adattatore seleziona gli step con `charge_e != 0 && pre_boundary == 1`, inclusi secondari carichi e ingressi con deposito nullo. Usa le coordinate **globali** pre-step, converte mm→cm e arrotonda a REAL una sola volta. Conserva l'ordine originale degli ingressi in ciascuna vista. L'angolo di lettura −45° non viene sostituito dalla rotazione fisica +45° della prima camera.

`NewPlan.hh` porta PLCH/LAGROTA/LAGLWH, poi ANAPLN_CLUSTERS/ANAPLN4/TRANSFO. La ricostruzione riceve esclusivamente quattro liste ordinate di fili interi e la geometria: gli ID truth, le direzioni generate, i raggruppamenti per particella e le posizioni vere non entrano nell'associazione delle tracce. Restano originali l'aritmetica binary32, il trattamento degli interi negativi, il clustering dipendente dall'ordine, la scelta dei candidati per residuo e il vincolo di non riutilizzare valori di coordinate trasformate. Sono conservate l'inferenza geometrica di una sola vista mancante, CL/CLTOT e le correzioni di separazione ±0.5 cm.

Gli output sono due punti ricostruiti alle Z nominali delle camere e le loro associazioni ai fili. Non sono una misura di momento, carica o covarianza. Le coordinate vere degli ingressi restano una provenienza separata, non endpoint ricostruiti.

## Output scientifici e stati

Il launcher `03_mc_simulation/geant4/newplan.py` scrive **solo ROOT per configurazione, dati scientifici e provenienza**:

- `newplan_config.root`: selezione, costanti e riferimenti agli originali;
- `tracking/tracking.root`: alberi `tracking_events`, `plane_crossings`, `plane_digits`, `crossing_digit_links`, `planar_tracks`, `track_wire_links`;
- `tracking/provenance.root`: hash di input, configurazione, eseguibile e sorgenti correnti.

Log e report testuali sono evidenza tecnica. Non vengono creati CSV, JSON o NPZ sostitutivi dei dati scientifici. Step completi, primarie e truth rimangono nel ROOT di trasporto immutabile referenziato; non sono duplicati come stime ricostruite.

Ogni evento di input resta presente, anche senza ingressi o tracce. Oltre a conteggi grezzi/ridotti, candidati e CLTOT, gli alberi conservano i collegamenti ingresso→filo e traccia→fili. Una vista inferita non riceve collegamenti fittizi. Sono espliciti gli eventi fuori dominio: più di 20 ingressi/fili in una vista, prodotto delle molteplicità ridotte oltre 256, indirizzi invalidi, overflow superiore X/Y non definito nel sorgente, aritmetica non finita e collisioni di coordinate che lascerebbero output Fortran non inizializzati. Non producono tracce valide.

Il clamp superiore U/V è riprodotto per diagnostica, compresa la deduplicazione originale precedente al clamp; per scelta di dominio questi eventi sono comunque esclusi dalla pubblicazione di tracce valide. L'adattatore controlla schema e tipi ROOT, inventario dei quattro piani, identità/ordine/conteggi degli eventi, bilancio energetico e stabilità degli hash prima della pubblicazione. Non sovrascrive output esistenti. Il controllo delle Z osservate negli slab dimostra compatibilità per gli ingressi presenti, non certifica tutta la geometria né i piani senza ingressi.

Esecuzione offline, con un eseguibile costruito dal target ROOT-only `graal_newplan`:

```sh
python3 -m mc_simulation.geant4.newplan \
  --mode selected26_newplan_diagnostic \
  --input INPUT_TRANSPORT.root \
  --output results_test/newplan-check/output \
  --executable BUILD_DIR/graal_newplan
```

## Verifiche del 9 novembre 2026

**94 test del confine interessato superati, zero saltati**: 41 di regressione della digitizzazione esistente, 7 della configurazione selected26, 41 della pipeline NEW_PLAN e 5 gruppi indipendenti kernel/oracolo. Altri **51 test della risposta legacy** sono passati in una verifica separata: totale distinto 145 test fra le due esecuzioni 94+51. Non è una nuova esecuzione dell'intera suite 197 precedente né un nuovo trasporto Geant4.

L'oracolo compila sorgenti Fortran originali non modificati e include COMMON originali; non esegue binari archiviati. Confronta fili, ordine/numero dei draw, molteplicità, CL/CLTOT e bit degli endpoint REAL nei casi definiti. Include tutte le viste mancanti, ordine/duplicati, limiti di canale, overflow, una/più tracce e correzioni geometriche. Fixture indipendenti con AddressSanitizer e UndefinedBehaviorSanitizer sono passate.

È stato recuperato anche SORTZV generico CERNLIB, con ordinamento non stabile dei punteggi uguali. Il port C++ e l'oracolo coincidono con quella sorgente fissata; ciò **non identifica l'oggetto CERNLIB storicamente collegato**. Sorgente e licenza sono conservati solo come fixture di test in `geant4/tests/reference/cernlib/`, senza collegamento alla produzione. I casi di collisione con conteggio/output non coerente nel Fortran sono segnalati, non trasformati in golden validi.

Il pilot offline ha letto il ROOT già conservato di 800 eventi, senza rilanciare il trasporto:

| Quantità | Risultato osservato |
| --- | ---: |
| Eventi conservati | 800 |
| Step sensibili letti | 1,588,661 |
| Ingressi carichi U / V / X / Y | 327 / 317 / 328 / 330 |
| Ingressi carichi totali | 1,302 |
| Fili digitali | 1,281 |
| Tracce | 305 |
| Eventi con / senza tracce | 298 / 502 |
| Eventi fuori dominio del kernel | 0 |
| Collegamenti traccia→filo | 1,229 |

Sono presenti 304 tracce CL0 e una CL2. La distribuzione CLTOT è `0:776, 1:9, 2:7, 3:1, 9:6, -1:1`; i sei eventi ambigui CLTOT9 restano conservati. I conteggi sono popolazioni diagnostiche, **non efficienze o accettanze**. Tutti gli 800 stati del kernel sono zero. Il controllo indipendente del coordinatore ha verificato hash di input, configurazione, eseguibile, output e tutti i sorgenti; corrispondenza esatta degli 800 ledger; campi degli ingressi contro gli step originali; destinazioni, intervalli, ordine e conteggi dei collegamenti ed endpoint. Lo script conservato è `reports/verify_pilot.py`; `reports/pilot-verification.root` registra il controllo eseguito, compreso l'hash del binario allora presente. La build temporanea è stata rimossa: ripetere il controllo richiede ricostruire l'eseguibile e verificarne l'hash rispetto alla provenienza. Una ricompilazione non garantisce identità binaria e non sostituisce automaticamente l'evidenza dell'esecuzione originale.

Evidenza locale mantenuta: `results_test/geant4-tracking-20261109/reports/{legacy-tracking,newplan-measurements,kernels,adapter,review}.md`, `adapter-integration-final.log` e `pilot/selected26/`. Il trasporto originale rimane in `results_test/geant4-pilot800-20261109/transport/events/transport.root`. Build e fixture riproducibili sono stati eliminati dopo i controlli, come registrato in `cleanup.log`; ROOT del pilot e report restano evidenza diagnostica datata.

## Lavoro scientifico ancora aperto

La successiva [catena centrale e forward](geant4-reconstruction) collega ora `CYCH_OLD`, fili/strip/ADC e ricostruzione cilindrica. Il trasporto registra il contesto compatto dei reset passivi necessario per riprodurre lo stato del gas GUSTEP. Il pilot centrale conserva 800 eventi e produce 293 tracce; NEW_PLAN e OLD_CYL restano scelte distinte.

WALL_DEV/SHOW_DEV, associazioni forward `ANA_WAL`, core centrale `FIND_TRACK_CBB` e trigger diagnostico sono ora portati e verificati separatamente. Il sorgente dell'automa cellulare BGO è stato fornito in `docs/reference/fortran/lib_cluster_c`; le configurazioni PREAN saranno consegnate successivamente. Restano il completamento BGO configurato, il contratto h70/tagger/PID e la selezione comune ai dati. Stati non definiti nei sorgenti originali restano espliciti.

Le efficienze unità sono costanti del modello MC selezionato, non misure di efficienza delle camere. Calibrazione, controlli indipendenti sui dati, risoluzioni, differenze GRAAL_26/GRAAL_09, sistematici, denominatori pesati e migrazioni restano da validare. Questi risultati non costituiscono ricostruzione completa h70 né efficienza fisica certificata. Sequenza corrente nella [migrazione GEANT4](geant4-migration) e nello [stato scientifico](status).
