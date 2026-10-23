# Prima conversione della geometria GRAAL in GEANT4

La geometria dell'immagine `afulci/ubuntu77:v2.8` è stata convertita e sottoposta
alla prima validazione geometrica con **GEANT4 11.4.3 installato con Spack sul
Mac**. Il riferimento GEANT3 è stato costruito ed eseguito nativamente su trima.
Sono disponibili [vista 3D offline](../../results/geant4-migration-audit-20261023/geometria-geant4-verificata.html),
[anteprima](../../results/geant4-migration-audit-20261023/geometria-geant4.png) e
[GDML verificato](../../results/geant4-migration-audit-20261023/conversion-spack-certified/geometry.gdml).

## Configurazione e risultato

Configurazione iniziale confermata dall'utente: `GRAAL_26`, cilindri vecchi,
camere piane nuove, dischi Catania, BC448 disabilitato, deuterio da **6,12 cm**,
densità **0,162 g/cm³**, spostamento del bersaglio nullo. È una riproduzione del
profilo dell'immagine; l'associazione a un periodo di dati fisici resta futura.

| Controllo | Esito |
|---|---|
| Forme GEANT3 dichiarate | 78 definizioni; BOX, TUBE, TUBS, TRAP, CONS, PGON |
| Posizionamenti sorgente | 724 record; 480 copie BGO |
| Istanziazioni fisiche GEANT4 | 858, considerando le copie delle madri |
| Copertura delle interrogazioni | Tutte le 858 identità fisiche occupate, inclusi tutti i 480 BGO e gli strati sottili |
| Interrogazioni GEANT3/GEANT4 | **98.685**: globali, per primitiva/copia e prossime alle superfici |
| Differenze di mezzo | **0** |
| Differenze di percorso occupato/copy number | **0** |
| Overlap rilevati sopra 0,001 mm | **0**, con 10.000 campioni di superficie per placement |
| Riapertura GDML in secondo processo GEANT4 | Passata; stesse 98.685 interrogazioni e 858 identità |
| Materiali riaperti | **16**; densità, A, Z e frazioni corrispondenti al riferimento entro tolleranza relativa 10⁻¹⁰ |
| Test strutturali e negativi | **8 passati** |
| Ruff sulla nuova area Python | Passato |

Sei interrogazioni sono appena fuori dal world. Entrambi i motori restituiscono
mezzo zero. GEANT3 conserva in GCVOLU un vecchio hint del world; questo non è
un percorso di volume localizzato e viene escluso dal confronto dei percorsi.

## Come è stata ottenuta la geometria

Il driver GEANT3 inizializza ZEBRA, materiali, mezzi e geometria. Non genera
eventi, non invoca GPHYSI e non esegue digitizzazione o analisi. Le chiamate
applicative vengono registrate da wrapper che delegano alle routine originali;
la libreria GEANT3 resta immutata. Le dichiarazioni senza parametri vengono
risolte con i parametri effettivi di ciascun GSPOSP.

GEANT4 costruisce i solidi nativi da questo snapshot. La matrice GSROTM viene
convertita da assi locali a trasformazioni nel sistema della madre; i parametri
angolari iniziale/finale diventano iniziale/ampiezza dove richiesto. Materiale,
mezzo e identità della copia restano distinti. Le mesh della vista sono esportate
direttamente dai solidi GEANT4, non ricostruite separatamente in Python.

Il convertitore ufficiale G3toG4 è stato valutato: il README nella release
11.4.3 richiede informazioni aggiuntive per MANY e limita un volume MANY a un
solo posizionamento. Il riferimento usa due copie sia di PLN1 sia di PLN2.
L'importazione nativa delle sei forme presenti evita una dipendenza da una
conversione automatica non equivalente su questi casi.

## Decisioni necessarie per preservare GEANT3

La prima costruzione geometrica grezza produceva 58 differenze di percorso
su 55.713 punti, delle quali 52 anche di mezzo. Erano tutte nei fori delle
camere piane e del forward. Sono state rilevate anche sovrapposizioni tra la
finestra posteriore del bersaglio e il suo involucro.

L'utente ha scelto esplicitamente **«Riproduci comportamento GEANT3»**, invece
di rendere i fori realmente vuoti. Le interrogazioni mirate hanno determinato
le precedenze utilizzate:

| Regione | Rappresentazione GEANT4 equivalente al comportamento osservato |
|---|---|
| TROU nelle camere piane | Nessuna regione fisica aggiuntiva: le due dichiarazioni sono completamente nascoste dalle camere, inclusi i piani sensibili. Restano nello snapshot originale. |
| TROM nelle pareti TOF | Differenza rispetto agli involucri WAL1/WAL2, rappresentata da intervalli cilindrici disgiunti in G4MultiUnion. |
| TROC nel calorimetro | G4SubtractionSolid rispetto ai moduli CASC e alle piastre di ferro. |
| ENVM e finestra posteriore FEN3 | Precedenza alla finestra; involucro suddiviso in intervalli anulari disgiunti in G4MultiUnion. |

La validazione controlla i prerequisiti di queste regole: conteggi e forma dei
parametri, trasformazioni, copertura trasversale dei cutter e inclusione delle
regioni nascoste. Un profilo modificato incompatibile fallisce esplicitamente,
invece di applicare una sottrazione basata su assunzioni non più vere.

Le dimensioni arrotondate dei BGO producono facce laterali leggermente non
piane; G4Trap rifiutava il primo solido con scarto di circa **0,54 µm**.
G4GenericTrap conserva gli otto vertici dichiarati senza ritoccare dimensioni.
Le interrogazioni comprendono punti interni ed esterni alle superfici con
offset di **2 µm**. Non viene dichiarata un'equivalenza sotto questa risoluzione.

## Correzione dell'export dei materiali

La riapertura del primo GDML ha rivelato un problema che il solo controllo
visivo non avrebbe trovato: il writer standard serializza gli isotopi naturali
autogenerati, facendo diventare il bersaglio A=2,01 un materiale con A≈1,008.
L'ottimizzazione per materiali monoisotopici poteva inoltre sostituire masse
atomiche dichiarate con valori NIST.

Il writer dedicato serializza esplicitamente gli elementi efficaci A/Z e le
frazioni, definendo gli elementi prima dei materiali. Una seconda applicazione
GEANT4 rilegge il file e ne controlla le proprietà reali. Il test ha prima
riprodotto la corruzione, poi verificato la correzione su tutti i 16 materiali
utilizzati. Il GDML conserva anche gli auxiliary per volume, mezzo, materiale e
copia del world, dato che il setup GDML descrive direttamente il world logico.

GEANT4 segnala quattro warning `mat017` per gli Z efficaci non interi di aria,
gas e Stesalit: sono definizioni del modello storico conservate intenzionalmente.
Questi warning non sono stati soppressi né trasformati in materiali diversi.

## Provenienza e riproduzione

- Immagine immutabile: `afulci/ubuntu77@sha256:cb810e84914ae1a440663c391b26058c3bb13fff1b41760da6bbc4d1c31a3ca6`, piattaforma `linux/386`.
- Riferimento geometrico: [geometry.g3](../../03_mc_simulation/geant4/reference/geometry.g3), SHA256 `5591dd6bf6d7782bc40b4b9a482e8ccec0a7c0759cc4e0a4f4b6ffd61edb450b`.
- [Manifest](../../03_mc_simulation/geant4/reference/manifest.json): 59 input originali con hash, driver/wrapper/generatore dei punti, compilatore e sei librerie CERN, binari e artefatti finali.
- Spack: `geant4@11.4.3`, hash `oobiuvctfdg4emuyqpnhr5p7z4l565cr`, macOS arm64, AppleClang 21.0.0, GDML/Xerces abilitato.
- [Comandi di build, confronto e rigenerazione](../../03_mc_simulation/geant4/README.md).
- Risultato numerico: `results/geant4-migration-audit-20261023/conversion-spack-certified/comparison.json`.
- Log completo: `results/geant4-migration-audit-20261023/conversion-spack-certified.log`.

Le prove grezze e quelle fallite sono conservate in directory distinte; gli
output precedenti non sono stati sovrascritti. Una revisione indipendente ha
individuato i problemi di riapertura materiali, copertura e prerequisiti dei
cutter, tutti affrontati con controlli mirati. Il codice e i risultati della
pipeline di analisi preesistente non sono stati ripristinati o sostituiti.

## Limiti e prossime fasi

Questa è una verifica geometrica campionata del primo profilo, non una prova
matematica di equivalenza su ogni punto. La tolleranza degli overlap è 1 µm;
i contatti numerici inferiori, dovuti anche a REAL*4, non sono stati eliminati
spostando le superfici. Controlli continui di navigazione e budget di materiale
lungo tracce saranno eseguiti prima di validare il trasporto.

Le definizioni efficaci A/Z e le densità sono preservate, ma questo non valida
il modello isotopico, i valori di lunghezza di radiazione o i processi fisici
GEANT4. In particolare, prima della simulazione fisica bisogna definire il
bersaglio isotopico e i composti reali, fissare physics list e cut, e verificarne
l'effetto con campioni appropriati. Non è ancora stata prodotta un'accettanza.

La fase 2 del piano copre generazione, trasporto, sensitive detector,
digitizzazione e risposta. La fase 3 definirà il confine di compatibilità
con LAGDIG/PREAN o con i file ROOT dell'analisi GRAAL. Non è stato scelto
silenziosamente un nuovo schema di output.

## Viewer nativo GEANT4 Qt sul Mac

Su richiesta dell'utente è stata installata una seconda variante Spack
**GEANT4 11.4.3 `+qt ~opengl`**, hash `dd37u4w`, conservando la precedente
`~qt` (`oobiuvc`). Qt6 ARM 6.11.2 viene riutilizzato da Homebrew tramite una
dichiarazione esterna nell'ambiente locale
`03_mc_simulation/geant4/spack-macos-qt`; nessuna configurazione globale
Spack è stata cambiata.

La prima compilazione Qt selezionava il libGL XQuartz a causa del default
Spack `CMAKE_FIND_FRAMEWORK=LAST`. La ricetta locale eredita quella builtin
e imposta `FIRST` su Darwin con Qt. Verificato con `otool -L`: la variante
finale collega OpenGL.framework Apple e non contiene dipendenze `/opt/X11`.
La variante intermedia sperimentale `t4nanaf` è stata rimossa.

Il lanciatore `03_mc_simulation/geant4/view_native.sh` compila e avvia
l'esempio ufficiale G01 dalla nuova installazione. La sola copia generata
sotto `build/` viene adattata per lettura offline, assenza di controllo
overlap implicito a tolleranza zero e ripristino della copia fisica world
dall'auxiliary storico. Il lanciatore passa soltanto il file GDML di ingresso:
non viene eseguito il ramo di esportazione standard G01. Colori, visibilità
e sezioni non modificano il modello geometrico.

Prove completate con la variante finale:

- Finestra Qt e renderer **OpenGLStoredQt** avviati effettivamente sul Mac.
- Due PNG esportati dal renderer nativo e ispezionati visivamente:
  [apparato completo](../../results/geant4-migration-audit-20261023/native-qt-smoke/full_0000.png)
  e [taglio](../../results/geant4-migration-audit-20261023/native-qt-smoke/cutaway_0000.png).
- Macro `/geometry/test/run placed`: **857 collocazioni figlie** controllate,
  ricorsione completa, 10.000 punti di superficie per collocazione,
  tolleranza 0,001 mm, tutte `OK!`, nessun `Overlap is detected`.
- Nuova certificazione numerica: **98.685 interrogazioni**, **858 identità
  fisiche** incluso il world, zero differenze di mezzo e percorso, zero
  overlap sopra 1 µm; roundtrip e 16 materiali passati.
- Otto test del modulo passati; comando di lancio finale provato e finestra
  lasciata aperta. Revisione indipendente dell'estensione senza problemi
  sostanziali.

Evidenze: `results/geant4-migration-audit-20261023/spack-qt-native-install.log`,
`native-qt-smoke/viewer.log`, `native-viewer-launcher.log`,
`qt-native-unit-tests.log` e `conversion-qt-native-certified/comparison.json`.
I warning `mat017` dei quattro elementi con Z efficace non intero sono
coerenti con le definizioni GEANT3 conservate. L'inizializzazione FTFP_BERT
dell'esempio G01 non costituisce una validazione della simulazione fisica;
nessun evento è stato richiesto.

Avvio, comandi per wireframe/tagli e controllo overlap sono nella
[guida del modulo](../../03_mc_simulation/geant4/README.md).
