# Geometria GRAAL in GEANT4

Prima configurazione convertita: **GRAAL_26, cilindri vecchi, camere piane nuove,
dischi Catania, bersaglio di deuterio lungo 6,12 cm**. È la configurazione
presente nell'immagine, scelta dall'utente per il primo porting.

La conversione usa la geometria inizializzata dal vero GEANT3 su trima.
Non ricopia a mano le dimensioni dell'apparato. Il riferimento immutabile è
`reference/geometry.g3`; il manifest identifica sorgenti, card, driver e librerie.

La prima verifica geometrica usa **GEANT4 11.4.3 installato con Spack sul Mac**:
98.685 interrogazioni, tutte le 858 identità fisiche occupate, zero differenze
di mezzo o percorso, nessun overlap rilevato sopra **0,001 mm**. Il GDML viene
riaperto in un secondo processo GEANT4 e ricontrollato, incluse densità, A, Z e
frazioni dei 16 materiali effettivamente utilizzati.

Questi controlli non validano trasporto, physics list, risposta, trigger,
digitizzazione o accettanza. Le definizioni efficaci dei materiali storici
sono conservate; la loro sostituzione con isotopi e composti fisici sarà una
scelta esplicita della fase successiva.

## Risultati da aprire

- [Vista 3D interattiva offline](../../results/geant4-migration-audit-20261023/geometria-geant4-verificata.html): rotazione, zoom, gruppi selezionabili e identificazione delle copie.
- [Anteprima](../../results/geant4-migration-audit-20261023/geometria-geant4.png).
- [GDML verificato](../../results/geant4-migration-audit-20261023/conversion-spack-certified/geometry.gdml).
- [Rapporto](../../docs/reports/2026-10-23-geant4-geometry.md) e [piano esecutivo](../../docs/superpowers/plans/2026-10-23-geant3-to-geant4.md).

Gli artefatti grandi sono sotto `results/`, ignorato da Git. L'HTML include
Plotly e non richiede rete, Docker, Qt o OpenGL. Le mesh visuali sono ottenute
da `G4VSolid::GetPolyhedron()`; la navigazione usa i solidi nativi, non le mesh.

## Build con Spack

Eseguire dalla radice del repository, usando il comando Spack della propria
installazione. Su questo Mac si trova in `/Users/tonyf/Software/spack/bin/spack`.
Per conversione e controlli numerici basta anche la variante senza Qt.
L'ambiente locale seleziona invece la variante grafica senza ambiguità fra
le due installazioni.

```bash
geant4_prefix=$(/Users/tonyf/Software/spack/bin/spack \
  -e 03_mc_simulation/geant4/spack-macos-qt location -i geant4)
cmake -S 03_mc_simulation/geant4 -B build/graal-geant4 \
  -DGeant4_DIR="$geant4_prefix/lib/cmake/Geant4" \
  -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=ON
cmake --build build/graal-geant4 --parallel 4
```

Sono necessari C++17, CMake e GEANT4 con GDML/Xerces. Il codice è stato
verificato con 11.4.3. Nessun dataset di fisica viene utilizzato dalla prova
geometrica. La variante originale senza Qt resta disponibile; quella grafica
riusa Qt6 ARM installato con Homebrew.

## Aprire la geometria nel viewer nativo GEANT4

Dalla radice del repository:

```bash
bash 03_mc_simulation/geant4/view_native.sh
```

Il comando seleziona GEANT4 11.4.3 `+qt` tramite l'ambiente locale, compila
l'esempio ufficiale **G01/load_gdml** e apre il GDML certificato in una finestra
Qt con viewer **OpenGLStoredQt**. Avviarlo da Terminale sul Mac con sessione
grafica attiva. Si può passare un altro percorso GDML come primo argomento;
la macro dei colori è specifica del profilo GRAAL_26 esportato qui.

Trascinare nella vista per ruotare; usare strumenti della finestra per zoom
e traslazione. BGO blu, bersaglio giallo, cilindri verde acqua, camere piane
viola, TOF arancione, calorimetro forward rosso, dischi Catania rosa. Aria e
supporti BGO partono nascosti soltanto nella visualizzazione.

Nel campo comandi di GEANT4:

```text
# Struttura interna in wireframe
/vis/viewer/set/style wireframe
# Superfici e taglio lungo un piano passante per l'asse del fascio
/vis/viewer/set/style surface
/vis/viewer/addCutawayPlane 0 0 0 cm 1 0 0
# Rimuovere il taglio
/vis/viewer/clearCutawayPlanes
# Ingrandimento assoluto; 1 ripristina lo zoom iniziale del viewer
/vis/viewer/zoomTo 3
# Vista lungo l'asse z
/vis/viewer/set/viewpointThetaPhi 0 0 deg
# Esportare la vista corrente; GEANT4 aggiunge un suffisso numerico
/vis/ogl/export geometria.png
```

Le macro cambiano solo l'aspetto. Il GDML originale non viene riscritto.
L'adattamento della copia G01 generata sotto `build/` disabilita il recupero
dello schema XML dalla rete e il controllo overlap automatico a tolleranza
zero. Il parser continua a leggere solidi e materiali dal file.
La copia fisica del world viene ripristinata dall'auxiliary GEANT3, come nel
verificatore numerico.

## Verificare gli overlap direttamente da GEANT4

Nel campo comandi della finestra:

```text
/control/execute check-overlaps.mac
```

La macro esegue **10.000 campioni di superficie per collocazione**, ricorsione
completa e tolleranza di segnalazione **0,001 mm**, come nella certificazione.
Il risultato atteso è `OK!` per i volumi controllati, senza avvisi
`Overlap is detected`. Durante la scansione la finestra può restare occupata.
La tolleranza filtra le segnalazioni: non cambia dimensioni o navigazione.

L'ispezione visiva e gli overlap non provano da soli equivalenza con GEANT3.
Per mezzo, percorso delle copie e materiali, ripetere anche il verificatore
numerico della sezione seguente. Nessuno di questi controlli valida la fisica
degli eventi. G01 inizializza una physics list di esempio per avviare GEANT4,
ma il lanciatore non richiede eventi.
All'apertura possono comparire warning `mat017`: riguardano gli Z efficaci
non interi dei materiali GEANT3 conservati intenzionalmente, non overlap.

## Riprodurre l'installazione grafica Spack

L'ambiente [spack-macos-qt/spack.yaml](spack-macos-qt/spack.yaml) usa Qt6
6.11.2 già presente in `/opt/homebrew/opt/qtbase`; il lock registra la
concretizzazione di questo Mac. Nessuna configurazione globale Spack è
modificata.
Una piccola ricetta locale eredita quella ufficiale e imposta
`CMAKE_FIND_FRAMEWORK=FIRST` su Darwin con Qt: evita che la presenza di XQuartz
faccia collegare GEANT4 al suo `libGL` invece del framework Apple.

```bash
/Users/tonyf/Software/spack/bin/spack \
  -e 03_mc_simulation/geant4/spack-macos-qt install -j 6 --fail-fast
```

Su Darwin serve **`+qt ~opengl`**: la variante separata `+opengl` della ricetta
è riservata ad altre piattaforme, mentre Qt include il supporto GL necessario.
Un aggiornamento maggiore di Qt tramite Homebrew può richiedere aggiornamento
della dichiarazione esterna, nuova concretizzazione e ricompilazione GEANT4.

## Conversione e verifica

Una conversione senza confronto produce GDML, mesh e inventario; non assegna
da sola uno stato di validazione. La directory di output deve essere nuova:

```bash
build/graal-geant4/graal_geometry \
  03_mc_simulation/geant4/reference/geometry.g3 \
  results/geant4-new-conversion
```

Per ripetere la verifica completa usando il riferimento sintetico GEANT3 già
prodotto in questa sessione:

```bash
python3 03_mc_simulation/geant4/tests/verify_native.py \
  --executable "$PWD/build/graal-geant4/graal_geometry" \
  --reference 03_mc_simulation/geant4/reference/geometry.g3 \
  --navigation results/geant4-migration-audit-20261023/navigation-complete.g3 \
  --output results/geant4-new-verification

GRAAL_GEOMETRY_EXE="$PWD/build/graal-geant4/graal_geometry" \
  python3 -m unittest discover -s 03_mc_simulation/geant4/tests -v
```

Il verificatore rifiuta campioni vuoti o privi di copertura dell'inventario.
Confronta separatamente identità, mezzi, materiali e riapertura GDML. Le prove
negative controllano parametri mancanti, rotazioni mancanti, prerequisiti delle
sottrazioni e rifiuto della sovrascrittura degli output.

Per rigenerare vista e anteprima, usando Python con Plotly e Matplotlib:

```bash
python3 03_mc_simulation/geant4/view_geometry.py \
  results/geant4-new-verification/scene.json \
  results/geant4-new-view.html --preview results/geant4-new-preview.png
```

## Rigenerare il riferimento GEANT3 su trima

Immagine fissata, piattaforma `linux/386`:

```text
afulci/ubuntu77@sha256:cb810e84914ae1a440663c391b26058c3bb13fff1b41760da6bbc4d1c31a3ca6
```

L'archivio sorgenti della sessione si trova in
`results/geant4-migration-audit-20261023/legacy-sources.tar.gz`. La sua radice
contiene `software/` e `data/`, estratti da `/home/gmandaglio/graal` nell'immagine.
Per ricostruire il riferimento servono i sorgenti/include LAGGEN, `pilot.h`,
`check_pilot.h`, `GRAAL_machine.h`, `GRAAL_period.h` e la card generica.

I comandi seguenti vanno eseguiti su trima, dopo aver trasferito questa area
del progetto e l'archivio autorizzato. Scegliere sempre directory nuove:

```bash
mkdir -p results/geant4-reproduce/source
tar xzf results/geant4-migration-audit-20261023/legacy-sources.tar.gz \
  -C results/geant4-reproduce/source
python3 03_mc_simulation/geant4/legacy/prepare_legacy.py \
  --source results/geant4-reproduce/source \
  --output results/geant4-reproduce/reference-build
python3 03_mc_simulation/geant4/legacy/make_points.py \
  03_mc_simulation/geant4/reference/geometry.g3 \
  results/geant4-reproduce/reference-build/points.txt

docker run --rm --platform linux/386 --network none --read-only \
  --tmpfs /tmp:rw,exec,size=256m --cpus 1 --memory 1g \
  --mount "type=bind,src=$PWD/results/geant4-reproduce/reference-build,dst=/work" \
  --entrypoint /bin/sh \
  afulci/ubuntu77@sha256:cb810e84914ae1a440663c391b26058c3bb13fff1b41760da6bbc4d1c31a3ca6 \
  /work/run_in_image.sh > results/geant4-reproduce/reference.log 2>&1
```

Controllare `GEOMETRY_REFERENCE_COMPLETE` nel log e confrontare l'hash di
`geometry.g3` con il manifest. `navigation.g3` contiene soltanto interrogazioni
sintetiche del navigatore; nessun evento sperimentale o simulato.

Il driver imposta esplicitamente `TARG 2 2` e `PDEC 0 0 0` e chiama solo
`GINIT/GZINIT`, materiali, mezzi e geometria. Non esegue `LAGDATA`, che aprirebbe
gli output della simulazione, né generatore, trasporto o i 300000 eventi della
card. Le routine geometriche originali e la libreria GEANT3 restano quelle
congelate. In UGEOM viene escluso solo l'output grafico successivo a GGCLOS.

## Rappresentazione delle sovrapposizioni

L'utente ha scelto di conservare il comportamento del navigatore GEANT3.
Le regole sono specifiche di questo primo profilo, con prerequisiti verificati:

- `TROU` è completamente nascosto dalle camere piane: le due dichiarazioni
  rimangono nel riferimento, senza creare due ulteriori regioni occupate.
- `TROM` viene limitato alle parti non occupate dalle pareti TOF.
- `TROC` viene limitato alle parti non occupate dai moduli del calorimetro e
  dalle piastre di ferro.
- La finestra posteriore `FEN3` ha precedenza sull'involucro `ENVM`.
- I trapezi BGO arrotondati vengono rappresentati da `G4GenericTrap`, che
  conserva gli otto vertici senza forzare la planarità delle facce.

Le parti disconnesse usano `G4MultiUnion`, le altre differenze
`G4SubtractionSolid`. Le dimensioni originali non vengono traslate per
eliminare warning. La tolleranza di 1 µm appartiene al controllo degli overlap;
non modifica il navigatore o le dimensioni. Contatti residui sotto questa
tolleranza restano parte della precisione numerica della prima conversione.

`EffectiveGdmlWriter.hh` conserva elementi efficaci con A/Z espliciti: export
standard tramite isotopi naturali cambierebbe, per esempio, il bersaglio da
A=2,01 a circa 1,008. Il verificatore protegge questa proprietà dopo riapertura.
Gli auxiliary GDML conservano nome, mezzo, materiale e copia del world GEANT3.

La simulazione degli eventi e il contratto di output GRAAL sono le fasi 2 e 3
del piano; non sono implementati da questa applicazione di sola geometria.
