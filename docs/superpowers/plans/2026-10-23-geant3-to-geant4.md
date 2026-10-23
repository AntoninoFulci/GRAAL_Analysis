# Migrazione della geometria GRAAL da GEANT3 a GEANT4

> **Per l'esecuzione:** procedere in questa sessione per milestone, con `superpowers:executing-plans`. Verificare ogni risultato prima di passare alla fase successiva.

**Obiettivo:** riprodurre in GEANT4 la geometria presente in `afulci/ubuntu77:v2.8`, renderla ispezionabile e verificarne la corrispondenza con GEANT3; successivamente introdurre simulazione, risposta e output GRAAL.

**Architettura:** eseguire su trima soltanto l'inizializzazione geometrica GEANT3, registrando materiali, mezzi, solidi, trasformazioni e posizionamenti effettivi. Convertire questo snapshot in solidi nativi GEANT4, con gestione esplicita dei vuoti e delle sovrapposizioni storiche. Il riferimento resta il codice inizializzato, non una seconda tabella di dimensioni ricopiata a mano.

**Tecnologie:** GEANT3/g77 nell'immagine immutabile `linux/386`; applicazione C++/CMake GEANT4 nativa su trima; esportazione geometria e viste recuperabili sul Mac senza Docker.

**Specifica:** richieste dell'utente del 23 ottobre 2026 e decisioni riportate sotto. Questo documento comprende specifica, inventario iniziale e piano esecutivo.

## Decisioni confermate

- Ordine: **1)** geometria completa visualizzabile e verificata; **2)** simulazione degli eventi e risposta dei rivelatori; **3)** output compatibile con l'analisi GRAAL.
- Prima configurazione: quella attuale dell'immagine, anche se non rappresenta ancora il periodo di dati da analizzare. Non sostituirla con un profilo protonico o una geometria aggiornata.
- Sono autorizzati recupero dei soli sorgenti/configurazioni nel workspace e prove su trima. Nessun dato sperimentale deve essere trasferito per questa attività.
- Le modifiche successive a periodo, bersaglio o apparato saranno concordate separatamente.

## Vincoli globali

- GEANT3 di riferimento: `afulci/ubuntu77@sha256:cb810e84914ae1a440663c391b26058c3bb13fff1b41760da6bbc4d1c31a3ca6`.
- Image ID verificato: `sha256:0090b49d8e70bb85858e68a3e8f59e41c1b3d6a746153770d2dee4d2b75b0002`; piattaforma `linux/386`.
- Prove del vecchio ambiente su **trima**, host `trimax`, architettura `x86_64`. Non tentare di risolvere la compatibilità del Docker sul Mac.
- Primo profilo: `GRAAL_26`, `GRAAL_OLD_CYL`, camere `GRAAL_NEW_PLAN`, disco Catania presente, BC448 disabilitato. Verificare le macro preprocessate: il solo nome `laggen_oc` non dimostra come fu compilato.
- Card geometrica di partenza: `data/inp_laggen/laggen.dat`, `TARG 2 2`, `PDEC 0. 0. 0.`: deuterio, lunghezza **6,12 cm**, spostamento nullo. Non eseguire i 300000 eventi indicati dalla card per estrarre la geometria.
- Conservare coordinate in cm, angoli in gradi e densità in g/cm³ nel riferimento; conversioni GEANT4 esplicite. Conservare semilunghezze, intervalli angolari e convenzioni delle rotazioni.
- ID materiale, ID mezzo di tracking e ID canale sono distinti. Il mezzo 16 del calorimetro usa materiale 14, non argon 16; mezzi 17–23 condividono materiale 18.
- Non modificare immagine, binari storici o risultati precedenti. Ogni build/prova usa directory nuova e registra comando, versioni, hash, stato e log.
- Non ripristinare file GEANT3 cancellati nel workspace, né sovrascrivere modifiche estranee già presenti.
- Geometria equivalente non significa risposta fisica equivalente: niente accettanza scientifica, trigger o compatibilità di output dichiarati sulla sola base di questa fase.

## Evidenze dell'ispezione iniziale

Verificate direttamente su trima il 23 ottobre 2026: Docker 29.9.0, immagine già presente, CMake 3.22.1, g++ 11.4.0. `geant4-config` non è nel PATH e non sono state trovate installazioni nei percorsi `/opt/geant4` e `/usr/local/geant4`; durante questa prima ispezione l'ambiente GEANT4 non era ancora individuato. Successivamente è stata trovata e usata per i test finali l'installazione Spack 11.4.3 del Mac, senza modificarla.

Sorgenti recuperati con autorizzazione dell'utente: `results/geant4-migration-audit-20261023/legacy-sources.tar.gz`, 129 file, SHA256 `e4973d4f6efa592c51295342c2718004fd677776905280bc567397a2d9106033`. Sono sorgenti, include e card; nessun dato sperimentale. L'archivio è un artefatto locale ignorato da Git.

Radice nell'immagine: `/home/gmandaglio/graal`. Percorsi seguenti relativi a `software/prog/laggen/`, salvo indicazione diversa.

| Sorgente | Responsabilità / vincolo osservato |
|---|---|
| `src/uginit.F` | Ordine: `GINIT`, `LAGDATA`, `GZINIT`, `LAGMAT`, `GPART`, `LAGTMP`, `UGEOM`, poi fisica e generatore. L'estrattore si arresta prima di questi ultimi. |
| `src/ugeom.F` | World `LAGR`, BOX con semilati 200, 200, 370 cm; costruzione dei sottorivelatori e `GGCLOS`. |
| `src/lagmat.F`, `src/lagtmp.F` | Materiali, miscele e mapping dei mezzi; sensibilità e limiti di tracking non vanno confusi con la composizione. |
| `src/lagcri.F`, `lagtrp.F`, `lagcxyz.F`, `lagcang.F` | BGO: 15 corone × 32 cristalli = **480**; parametri `TRAP` per posizionamento via `GSPOSP`, rotazioni da `GSROTM`, supporti `NID1/NID2`. |
| `src/lagecvr.F` | Volumi d'aria `ARI*` che eliminano carbonio; includerli nel confronto del materiale attraversato. |
| `src/lagbers.F`, `lagdata.F`, `include/lagtarg.inc` | Bersaglio, finestre, rivestimenti e traslazione Z; valori dipendenti dalla card. |
| `src/lagvrtx.F` | Scintillatori DEDX, camere cilindriche, gas, strutture; rami vecchi/nuovi distinti. |
| `src/lagplch.F`, `include/lagvert.inc` | Camere piane, telai PGON, piani sensibili `MANY`, foro centrale. Per il ramo attuale ZP1=94,4 cm e ZP2=134,4 cm. |
| `src/lagwall.F` | Due pareti TOF, ciascuna con 26 barre, foro centrale d'aria. |
| `src/lagcalo.F` | Calorimetro forward: 16 moduli, piombo, mylar, ferro e foro d'aria. |
| `src/lagctdisk.F` | Dischi Catania e assorbitori; inclusi nel profilo attuale. |
| `pilot.h`, `../include/GRAAL_period.h` | Selezione effettiva della geometria, da archiviare dopo preprocessing. |
| `src/gustep.F` | Il codice hit usa `ISVOL` e `NUMBER(NLEVEL)`: preservare identità e percorso delle copie per le fasi successive. |

### Punti da trattare esplicitamente

1. **Solidi per copia:** `GSPOSP` può cambiare dimensioni a parità di nome. Non collassare i 480 cristalli in un unico solido con parametri comuni.
2. **Angoli:** TUBS/CONS GEANT3 codificano estremi iniziale/finale; GEANT4 richiede inizio/ampiezza. PGON richiede verifica della convenzione sui raggi.
3. **Sovrapposizioni:** esistono sia posizionamenti `MANY` sia volumi d'aria posti tra i fratelli per creare fori. Sostituire `MANY` con normali placement non basta: identificare precedenza del navigatore e costruire gerarchie o sottrazioni equivalenti.
4. **Materiali storici:** aria descritta con A/Z efficaci e alcune miscele composte tramite valori medi. Conservare definizioni originali nel riferimento e dichiarare qualsiasi rappresentazione GEANT4 non identica; non correggere composizioni silenziosamente.
5. **Binari preesistenti:** gli oggetti `.o` e i nomi dei binari non provano la coerenza con gli header. Per il riferimento usare inizializzazione ricompilata pulita con il profilo autorizzato.

## Struttura prevista

Nuova area autonoma `03_mc_simulation/geant4/`, senza dipendere dai wrapper GEANT3 cancellati:

- `README.md`: build, visualizzazione, contratto e limiti della prima fase.
- `CMakeLists.txt`, `src/`: costruzione nativa GEANT4, verifica e export; separare il caricamento del riferimento dalla geometria quando migliora la leggibilità.
- `legacy/`: driver di sola inizializzazione, ricetta di estrazione e provenienza. Il codice storico resta separato dagli adattamenti.
- `reference/`: snapshot geometrico deterministico e manifest con digest, macro, card e hash delle dipendenze.
- `tests/`: controlli di completezza, trasformazioni, navigazione e materiale attraversato.

Output pesanti, mesh, screenshot, build e log in `results/geant4-*` o in directory dedicate su trima; non versionare librerie o dataset GEANT4.

## Fase 1 — Geometria completa

### Task 1: Congelare il riferimento inizializzato

- [x] Verificare accesso trima, architettura, digest, sorgenti, macro e card.
- [x] Recuperare sorgenti/configurazioni dopo autorizzazione; registrarne hash.
- [x] Preparare driver GEANT3 che inizializzi solo materiali, mezzi e geometria con profilo confermato, senza `GPHYSI` e senza generazione eventi.
- [x] Registrare le chiamate effettive `GSMATE/GSMIXT/GSTMED/GSVOLU/GSROTM/GSPOS/GSPOSP` e le eventuali divisioni, delegando comunque alle routine GEANT3 originali.
- [x] Eseguire build pulita su trima; salvare macro preprocessate, compilatore, card, sorgenti utilizzati e snapshot numerico.
- [x] Controllare 480 copie BGO, world, bersaglio D da 6,12 cm e tutti i sottorivelatori attivi. Registrare anche volumi definiti ma non posizionati.
- [x] Preparare campioni di punti globali, per primitiva/copia e prossimi alle superfici interrogando il navigatore GEANT3, con ID mezzo e percorso delle copie. Includere fori, bordi e regioni di sovrapposizione.

**Risultato verificabile:** manifest riproducibile e snapshot completo. Arrestare su routine non registrate, ID mancanti, macro incoerenti o inizializzazione incompleta; un exit code zero non basta.

### Task 2: Predisporre GEANT4 e costruire la prima geometria

- [x] Individuare GEANT4 installato o compilare una release stabile fissata per versione e hash in prefisso dedicato su trima. Registrare dipendenze, opzioni e comandi ripetibili.
- [x] Valutare il convertitore ufficiale G3toG4 sullo snapshot: usarlo solo se copre solidi e semantica dei posizionamenti senza alterazioni. Se richiede una seconda ricostruzione delle stesse informazioni, usare direttamente solidi nativi GEANT4.
- [x] Caricare il solo formato di riferimento effettivamente necessario. Rifiutare esplicitamente forme, parametri, materiali o trasformazioni sconosciuti.
- [x] Costruire BOX, TUBE/TUBS, TRAP, CONS e PGON effettivamente presenti, preservando nome storico, copy number e mapping mezzo→materiale.
- [x] Verificare le trasformazioni tramite punti interni, esterni e prossimi alle superfici in ciascun sistema locale; confrontare col navigatore GEANT3, inclusi tutti i cristalli nei due emisferi.
- [x] Gestire separatamente solido, logical volume e physical placement quando i parametri dipendono dalla copia.

**Risultato verificabile:** geometria costruita interamente, inventario confrontabile e fallimenti espliciti per input incompleti. Nessuna risposta fisica abilitata.

### Task 3: Risolvere fori e sovrapposizioni senza cambiare l'apparato

- [x] Localizzare sovrapposizioni e uscita dei figli dalle madri con controlli GEANT4 e confronto con GEANT3.
- [x] Per ogni foro o regione `MANY`, identificare materiale e identità effettivamente restituiti da GEANT3 sui due lati e all'interno.
- [x] Tradurre la regione in gerarchia o operazione booleana GEANT4 equivalente, documentando il mapping degli ID. Non aggiungere spazi artificiali o spostare componenti per far sparire i warning.
- [x] Distinguere difetti di conversione da ambiguità già presenti nel riferimento. Chiedere all'utente prima di correggere dimensioni o composizioni storiche.
- [x] Confrontare punti interni/esterni e campioni prossimi alle superfici di bersaglio, BGO/supporti, camere, TOF e calorimetro. Richiedere copertura di ogni identità fisica occupata e corrispondenza dei mezzi. Le scansioni continue del budget di materiale precedono il trasporto nella fase 2.

**Risultato verificabile:** nessuna sovrapposizione materiale irrisolta sopra la tolleranza numerica dichiarata; differenze rispetto a GEANT3 localizzate e motivate. Un'immagine plausibile o il solo controllo stocastico degli overlap non dimostrano equivalenza.

### Task 4: Validazione e consegna visuale

- [x] Aggiungere test di regressione per inventario, copie e parametri; testare che omissioni e rotazioni errate vengano rilevate.
- [x] Confrontare navigazione su griglia deterministica e raggi mirati. Trattare separatamente i punti esattamente su una superficie; riportare tolleranze numeriche e precisione REAL*4 del riferimento.
- [x] Verificare estensione del world, posizione/dimensioni bersaglio, 480 BGO, entrambe le camere piane, cilindri, TOF, calorimetro e dischi Catania.
- [x] Esportare geometria riapribile, anteprima globale/centrale e vista interattiva ruotabile con preset centrale e forward. Rendere identificabili sottorivelatore, materiale e copy number; verificare dopo riapertura anche A, Z, densità e frazioni.
- [x] Rendere disponibile sul Mac una vista ispezionabile senza il vecchio Docker; verificare che corrisponda alla stessa geometria GEANT4 testata.
- [x] Scrivere rapporto con conteggi, tolleranze, massimo scarto, esempi dei confronti e limiti residui. Separare equivalenza geometrica da rappresentazione dei materiali e validazione della fisica.

**Criterio di completamento della fase 1:** tutti i componenti attivi presenti, output visualizzabile, test geometrici campionati passati entro le tolleranze dichiarate, differenze materiali/semantiche risolte oppure chiaramente dichiarate come blocchi alla validazione. In caso di blocco, consegnare il risultato parziale senza chiamarlo geometria validata.

## Fase 2 — Simulazione degli eventi e risposta

Da dettagliare dopo la fase 1, con nuova scelta dei campioni fisici di confronto; non si ricavano automaticamente dalla card geometrica.

- [ ] Eseguire scansioni continue di navigazione e budget di materiale lungo tracce prima di validare il trasporto.
- [ ] Concordare particelle, energie, vertici e processo iniziale; separare generatori di prova dal generatore scientifico.
- [ ] Collegare sensitive detector agli ID storici, conservando identità evento, verità e hit anche per eventi che non passano trigger/selezione.
- [ ] Scegliere e registrare physics list, produzione di secondari e limiti per regione. I CUTS GEANT3 in energia non sono production cut GEANT4 in lunghezza: serve una scelta esplicita e una verifica di convergenza.
- [ ] Verificare prima particelle singole, depositi energetici e tempi, poi risposta del BGO, scintillatori, camere e forward; confrontare statisticamente con GEANT3. Non attendersi uguaglianza evento per evento tra motori diversi.
- [ ] Portare digitizzazione, soglie, risoluzioni, inefficienze e trigger dalla catena LAGDIG verificata, evitando di confonderli con gli hit del trasporto.

**Criterio:** risposta verificata con campioni e tolleranze concordati; dipendenze da parametri fisici documentate. Nessun valore di efficienza scientifica dichiarato da soli test tecnici.

## Fase 3 — Output compatibile con l'analisi GRAAL

- [ ] Definire il confine richiesto: `.hit` per LAGDIG, `.dig` per PREAN oppure ROOT direttamente consumabile dalla pipeline corrente. Scegliere dopo aver ispezionato i contratti reali, senza imporre ora una riscrittura dell'analisi.
- [ ] Fissare schema, unità, convenzioni angolari, run/event ID, ID di canale, eventi vuoti e associazione truth→hit→ricostruzione.
- [ ] Provare un campione piccolo nella stessa catena di selezione/ricostruzione usata per i dati; verificare lettura, conteggi e identità degli eventi.
- [ ] Introdurre il backend GEANT4 nella pipeline solo dopo verifica del contratto; conservare GEANT3 come riferimento riproducibile.

**Criterio:** campione GEANT4 attraversa l'analisi senza adattamenti manuali ai file e senza perdite silenziose di eventi o significato delle variabili.

## Casi critici da coprire nei test

| Caso | Prova richiesta | Task |
|---|---|---|
| Stesso nome, forma diversa per copia | Tutte le corone BGO e parametri delle copie coincidono con lo snapshot; mutazione rilevata. | 2, 4 |
| Rotazione invertita o intervallo phi sbagliato | Assi locali e punti interni/esterni nei due emisferi e sul bordo tra NID1/NID2. | 2, 4 |
| Foro d'aria o `MANY` trattato come overlap ordinario | Raggi dentro/fuori foro e attraverso piani sensibili; stesso materiale e stessi attraversamenti di GEANT3. | 1, 3, 4 |
| ID mezzo scambiato per ID materiale | Controllo del mapping su CASC, gas camere e dischi, oltre a densità e composizione. | 1, 2, 4 |
| Snapshot incompleto o profilo diverso | Il caricamento rifiuta riferimenti mancanti; il manifest identifica card, macro e digest esatti. | 1, 2, 4 |

## Fonti tecniche

Documentazione consultata tramite Context7, con riscontro nei sorgenti dell'immagine:

- [GEANT4, esempio ufficiale G3toG4/clGeometry](https://github.com/Geant4/geant4/blob/master/examples/extended/g3tog4/clGeometry/README.md): conversione di geometrie GEANT3 tramite call list e dipendenza opzionale G3toG4; non costituisce promessa di conversione completa dell'applicazione.
- [GEANT4, build dell'esempio](https://github.com/Geant4/geant4/blob/master/examples/extended/g3tog4/clGeometry/CMakeLists.txt): componenti opzionali, modalità batch e visualizzazione.
- [Docker create](https://docs.docker.com/reference/cli/docker/container/create/), [Docker cp](https://docs.docker.com/reference/cli/docker/container/cp/), [Docker inspect](https://docs.docker.com/reference/cli/docker/image/inspect/): identità immutabile e ispezione del filesystem.

## Stato di esecuzione

Prima fase completata con i controlli campionati descritti nel [rapporto](../../reports/2026-10-23-geant4-geometry.md): GEANT3 su trima, GEANT4 Spack 11.4.3 sul Mac, 98.685 interrogazioni e 858 identità fisiche coperte, zero differenze di mezzo/percorso occupato, zero overlap rilevati sopra 1 µm. Riapertura GDML passata con verifica di densità, A, Z e frazioni dei 16 materiali usati. Otto test mirati passati e Ruff pulito.

Decisione confermata durante l'esecuzione: riprodurre il comportamento effettivo GEANT3 nei fori, non modificarlo per rendere i fori vuoti. Gli adattamenti geometrici e la rappresentazione degli otto vertici BGO sono documentati nel rapporto e nel manifest.

Precisazione del confine della fase 1: verifica discreta completa dell'inventario e delle regioni occupate, con campioni a 2 µm dalle superfici e controllo overlap a 1 µm. Le scansioni continue del budget di materiale sono state collocate prima del trasporto nella fase 2; non sono dichiarate eseguite. Rischio residuo: differenze sotto la risoluzione campionata o tra campioni possono richiedere ulteriori controlli prima della simulazione fisica.

Fasi 2 e 3 ancora da eseguire. Nessuna physics list, digitizzazione, accettanza o compatibilità di output GRAAL viene dichiarata validata da questa prima consegna.

## Estensione autorizzata: viewer nativo sul Mac

L'utente ha richiesto l'installazione del supporto grafico e istruzioni per
ispezionare la geometria direttamente in GEANT4.

1. Concretizzare un ambiente Spack locale con GEANT4 11.4.3 `+qt ~opengl`,
   riusando Qt6 ARM 6.11.2 già installato con Homebrew. La variante `+opengl`
   separata è vietata dalla ricetta Spack su Darwin; Qt abilita il viewer GL.
2. Installare nel nuovo prefisso, conservando la build senza Qt.
3. Riutilizzare G01 installato, adattando solo la copia generata per la build:
   lettura GDML offline e nessuna scansione overlap automatica a tolleranza zero.
   Macro visuali del profilo certificato e controllo esplicito a 0,001 mm.
4. Verificare driver Qt, caricamento del GDML, rendering OpenGL nativo e
   macro overlap; documentare avvio e comandi di ispezione.

Decisione: usare la dipendenza Qt già disponibile riduce la compilazione a
GEANT4. Qt rimane gestito da Homebrew: un suo aggiornamento maggiore può
richiedere nuova concretizzazione e ricompilazione di questa variante.

Diagnosi durante l'installazione: il default Spack `CMAKE_FIND_FRAMEWORK=LAST`
selezionava `/opt/X11/lib/libGL.1.dylib`. La prova `otool -L` ha rilevato il
collegamento indesiderato. Una ricetta locale ereditata imposta `FIRST`, senza
modificare quella builtin. Il nuovo CMakeCache seleziona OpenGL.framework
dall'SDK Apple; il controllo del collegamento verrà ripetuto a fine build.

Estensione completata: variante finale `dd37u4w`, controllo `otool` passato,
renderer OpenGLStoredQt avviato e PNG ispezionati, 857 collocazioni figlie
controllate dalla macro GEANT4 senza overlap sopra 1 µm. Nuova certificazione
di 98.685 punti e 16 materiali passata, otto test passati. Lanciatore provato;
finestra nativa lasciata aperta. Rimosso solo il prefisso Qt sperimentale
collegato a XQuartz. Guida aggiornata con avvio e controlli interattivi.
