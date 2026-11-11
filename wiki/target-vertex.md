# Targhetta dai vertici di due carichi centrali

`python -m plots.target_vertex` ricostruisce il vertice direttamente dagli **h70 grezzi**, senza BDT o selezione di un canale esclusivo. Il calcolo riprende il ramo centrale–centrale (`IWHERE=1`) di [vertex2.F](https://github.com/AntoninoFulci/GRAAL_Analysis/blob/main/docs/reference/fortran/pimdeu_2apr2009/src/vertex2.F), conservato intatto. È una diagnostica geometrica indipendente: non modifica la ricostruzione ηπ⁰, i tagli di periodo o i contratti di produzione.

## Produzione corrente: fit locali dei bordi su tutte le run

Aggiornamento del 6 novembre 2026, autorizzato dopo la prova `2000_uv2`: **2.711 run elaborate, 22 periodi coperti, 2.416 run incluse nelle medie**. Il modello locale dei bordi sostituisce il fit uniforme globale per i nuovi prodotti. Risultato: **20 periodi con lunghezze compatibili**, due senza run validi (`2001_d`, `2005_d1`). Le 295 esclusioni restano nel CSV con motivo; nessuna lunghezza viene inventata per completare la configurazione.

Percorsi correnti, uguali nel checkout locale e in `/data/graal/GRAAL_Analysis` su `trima`:

- `config/support/target_conditions_current/` è un collegamento relativo a `target_conditions_2026-11-06_edges/`: database `target_runs.csv`, medie `target_periods.csv`, condizioni `geant4_candidates.json`, hash `publication.json`.
- `results/2026-11-06-target-edges-final/products/`: **22 PNG per periodo**, archivio unico `run_plots.npz`, metadati e checksum. Tutti i **98.190.010 vertici selezionati**, DCA e identificatori sorgente conservati identici all'archivio iniziale.
- `results/2026-11-06-target-edges-final/campaign.log` e `exit_code`: aggregazione conclusa con codice 0. Fit completi nel log `results_test/2026-11-06-target-edges-production/refit.log`; trasferimento e verifica nella stessa directory.

`target_edges.py` trova separatamente in ogni run le transizioni del componente longitudinale continuo, inizializzato al 15% del picco sopra fondo. Ogni bordo usa gradino con densità interna esponenziale, smussamento Gaussiano e fondo costante; nessuna lunghezza nominale imposta. Semifinestra nominale 1,6 cm, limitata al 40% della distanza iniziale fra bordi per evitare sovrapposizione nelle celle corte. Il modello esiste solo nelle finestre dei bordi: zona centrale non modellata resta `null`/NaN, senza plateau artificiale. Il profilo locale medio mantiene la normalizzazione rispetto all'intero istogramma del run.

Selezione invariata: esattamente due carichi eleggibili e DCA ≤4 mm. La mappa XY viene ricalcolata usando i nuovi bordi z. Ogni run valido pesa uno nelle medie di lunghezza/centro; ogni mappa XY viene normalizzata prima della media. Per contribuire al periodo servono fit nominale valido, XY non vuoto, almeno una verifica DCA valida (2 o 3 mm) e almeno una verifica con **semifinestra effettiva diversa** (richieste 1,2 e 2,0 cm). Uno spostamento di lunghezza superiore a 0,5 cm nelle verifiche riuscite segnala instabilità; un'escursione fra run oltre 0,5 cm blocca una geometria unica. Nessun periodo finale supera quest'ultimo controllo.

Run 1860 e 4750 mantengono stime nominali nel CSV, ma sono escluse con `edge_robustness_unavailable`: manca una verifica DCA riuscita; per 4750 falliscono anche le finestre alternative. Altri fallimenti restano distinti (statistica, riconoscimento bordi, parametri ai limiti, ricostruzione). Profili con due picchi stretti e poco segnale interno possono fallire il riconoscimento della cella: questo non prova da solo materiale o stato hardware.

| Esempio | Run incluse | Lunghezza media | Dispersione fra run |
| --- | ---: | ---: | ---: |
| 1998_uv | 148 | 6,213 cm | 0,026 cm |
| 2000_uv2 | 102 | 11,149 cm | 0,047 cm |
| 2005_d2 | 117 | 6,104 cm | 0,034 cm |

Fra i periodi validi, celle corte circa 6,04–6,34 cm e lunghe 11,15–11,18 cm. Il bootstrap (32 repliche) è condizionale alle finestre/semi iniziali e non rappresenta l'incertezza sistematica totale. Il diametro fisico resta non misurato; **50 mm è solo riferimento storico esplicito**. XY resta profilo osservato delle interazioni, utilizzabile come approssimazione del fascio, senza deconvoluzione di accettanza/risoluzione. Materiale deriva dal catalogo, non dai vertici. Dal 6 novembre il [launcher GEANT4 consuma le condizioni per periodo](03-monte-carlo-simulation#monte-carlo-per-acquisition-period): geometria derivata, profilo XY e vertici salvati, con ipotesi meccaniche/materiali dichiarate. Nessuna modifica ai prodotti dei fit; validazione di produzione resta distinta.

Verifica: **45 test superati**, confronto SHA-256 di ogni array di eventi con l'originale, ricalcolo indipendente di tutte le mappe XY e delle medie a uguale peso, checksum di prodotti/configurazioni e copie server. Evidenza `results_test/2026-11-06-target-edges-production/validation.json`, `tests-reviewed.log`, `remote-publication.json`. Snapshot `source/` conserva codice dei fit, `source-final/` quello dell'aggregazione. Due correzioni successive (finestre effettivamente diverse e conservazione della provenienza su aggregazioni ripetute) sono verificate dai test: il controllo indipendente conferma che non cambiano nessuna delle 2.711 decisioni di inclusione; non si riscrivono i prodotti per aggiornarne artificialmente la provenienza.

Per nuovi fit: `06_calibration/target_refit.py ARCHIVIO --catalog config/support/run_manifest.csv --output NUOVA_DIRECTORY --work DIRECTORY_SHARD --workers 8 --bootstrap 32`. Per aggiornare solo aggregazione/policy: sottocomando `aggregate ARCHIVIO --catalog ... --output NUOVA_DIRECTORY`. Entrambi conservano gli input e richiedono una nuova destinazione; `target_publish.py` pubblica dopo verifica. Il calcolo completato ha riusato i vertici archiviati, senza rileggere gli h70 o rifare la geometria delle tracce.

Le sezioni di pilot e campagna iniziale sotto sono **evidenza storica**, non le condizioni correnti. Dopo pulizia autorizzata, il riferimento iniziale integro è in `results/2026-11-06-target-edges-final/history/initial-production/`. La prima aggregazione dei bordi conserva solo metadati e array di periodo in `history/first-edge-aggregation/`: tutti i suoi array di run erano identici byte per byte a quelli correnti. Pilot, sorgenti e verifiche precedenti sono raccolti in `results_test/2026-11-06-target-edges-production/history/`. `tidy-report.json` registra hash e spostamenti; nessun percorso storico è una configurazione attiva. I lock `.target*.lock` e `.products.lock` inattivi sono stati eliminati: verranno ricreati solo se riparte una pubblicazione.

## Selezione e geometria

Per ogni evento si leggono `Iass_3`, `Itipo_track`, `Nb_traces_cyl` e le sei coordinate `X/Y/Z_trace_int/ext`. `Iass_3` contiene righe `[BGO, barrel, cilindro]`, con indici Fortran a partire da **1**, zero per associazione assente. Sono candidati carichi centrali con associazione positiva a **barrel e cilindro**. BGO, energia, tagger, identificazione protone/pione e altri rivelatori non sono richiesti. Tracce viste solo nelle camere non entrano in questo campione; questa scelta limita l'accettanza e deve restare esplicita nei confronti.

Le associazioni ripetute allo stesso cilindro contano come una traccia, conservando la prima riga eleggibile. Si usano tutte le coppie con cilindri e barrel distinti. Con più di due carichi, uno stesso evento produce più vertici: gli istogrammi contano **coppie**, non eventi indipendenti. Non si sceglie la coppia più vicina al centro della targhetta.

Ogni traccia è una retta infinita attraverso i punti delle due camere. Si calcolano i due punti di minima distanza e il loro punto medio: nessun vincolo al fascio, alla cella o ai segmenti fra camere. Coordinate in **cm**, riferimento nativo h70, nessuna traslazione di allineamento. La distanza minima (`dca_cm`) e `sin2`, seno al quadrato dell'angolo fra rette, restano disponibili per studi di qualità. Non sono incertezze del vertice.

Il calcolo usa doppia precisione e `|u×v|²` per il determinante equivalente a `CHI*PSI-OMEGA²`. Rette di lunghezza nulla, coordinate non finite, sentinella `−1000` e `sin² ≤ 10⁻¹⁰` producono vertici indefiniti, salvati come NaN con stato esplicito. La soglia angolare è una protezione numerica, non una selezione basata sulla risoluzione. Geometrie quasi parallele sopra soglia possono comunque dare grandi code. Indici e dimensioni incoerenti interrompono l'analisi senza pubblicare output parziale.

## Esecuzione

Dalla radice del checkout, con ambiente Python del progetto:

```bash
TASK_ROOT="$PWD/results_test/target-vertex-study"
mkdir -p "$TASK_ROOT/tmp" "$TASK_ROOT/mpl"
export PYTHONDONTWRITEBYTECODE=1
export TMPDIR="$TASK_ROOT/tmp"
export MPLCONFIGDIR="$TASK_ROOT/mpl"
python -B -m plots.target_vertex data_test/raw_data/1998_uv \
  --output "$TASK_ROOT/runs"
```

Si possono passare più file o directory; una directory espande i suoi `*.root` senza ricorsione. `--max-entries N` limita la lettura ai primi N eventi **per file** e registra l'intervallo effettivo; in assenza del parametro legge tutto. `--step-size` regola gli eventi per blocco. Input duplicati vengono rifiutati. La directory finale deve essere nuova: nessuna sovrascrittura implicita.

La separazione avviene usando `Idrun`, non il nome del file. Il tree `vertices` in `vertices.root` conserva tutte le coppie tentate, stato, molteplicità, indici delle associazioni e delle camere **1-based**, codici `Itipo_track`, numero evento, indice del file e entry locale **0-based**. `summary.json` mappa i file originali con percorso, dimensione, mtime, UUID ROOT e intervallo letto; registra versioni software, hash dei moduli, selezione, codici di stato e conteggi per run. È uno schema diagnostico; non sostituisce la provenienza di ricostruzione di produzione.

Per ogni run:

- `run_<id>.png`: vista 3D, confronto con DCA ≤ 1 cm, profilo z e densità XY/XZ/YZ.
- `run_<id>_dca.png`: distanza fra rette, con confronto al sottoinsieme di eventi con esattamente due carichi candidati.

`--view-cm X Y Z` controlla le semiampiezze delle viste (default 5, 5, 15 cm). `--display-dca-cm` controlla solo il confronto visivo. **Nessun taglio su posizione o DCA nei dati salvati.** I plot 3D mostrano fino a 20.000 punti per pannello, campionati con seed fisso; densità e profili usano tutte le coppie valide. Il conteggio fuori dal box è dichiarato. Ciascuna proiezione 2D limita solo i suoi due assi; il profilo z non taglia x o y. La distribuzione DCA mostra 0–10 cm e dichiara quanti punti stanno sopra il limite.

## Evidenza locale del 6 novembre 2026

Analisi completa dei due h70 in `data_test/raw_data/1998_uv`, richiesta dall'utente:

| Run | Eventi letti | Eventi con coppie | Coppie valide | Mediana x | Mediana y | Mediana z |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1321 | 585.613 | 47.743 | 63.534 | +0,500 cm | +0,070 cm | −0,014 cm |
| 1324 | 648.006 | 50.267 | 65.960 | +0,498 cm | +0,068 cm | −0,016 cm |

Le immagini mostrano nuclei allungati simili, con estensione longitudinale approssimativa da −3 a +3 cm: **compatibili visivamente con la famiglia di targhette di circa 6 cm**, senza assegnazione automatica. Le [varianti storiche](legacy-fortran-map#geometria-materiali-e-varianti-target) includono 6,12 cm. Le mediane sono descrittive delle coppie, non un fit di allineamento. Fondo, risoluzione, accettanza e possibili interazioni secondarie non sono corretti; la geometria da sola non distingue idrogeno da deuterio.

Output e log conservati in `results_test/2026-11-06-target-edges-production/history/2026-11-06-target-vertex/` per revisione scientifica della prima diagnostica. Non sono validazione di produzione o identificazione certificata della targhetta. Restano aperti confronto fra periodi, modellazione dei bordi con risoluzione/fondo, stabilità rispetto a DCA e molteplicità, confronto con geometrie e registri run. Vedere [stato scientifico](status).

## Pilot locale: database per run e taglio a 4 mm

Il responsabile ha precisato il 6 novembre: accettare vertici con **distanza minima fra rette ≤ 4 mm**, senza interpretare questo valore come incertezza sulle coordinate. Prima di qualsiasi esecuzione sul server, eseguire un piccolo test locale sui run 1321 e 1324. Questo pilot è implementato in `06_calibration/target_database.py`; precede la campagna server autorizzata descritta sotto. Nessuna geometria GEANT4 è stata modificata.

L'estrazione riusa i vertici già salvati. Il campione di riferimento richiede **esattamente due carichi centrali eleggibili**, stato valido e DCA ≤ 0,4 cm: così ogni evento contribuisce una volta. È distinto dalla diagnostica iniziale con tutte le coppie. Nessun taglio x/y nella stima longitudinale. Il modello è una cella uniforme lungo z, convoluta con una Gaussiana, più fondo costante; integra le probabilità nei bin di 0,1 cm fra −15 e +15 cm. Lunghezza, centro, smussamento efficace e frazione di fondo sono liberi. Sono provate inizializzazioni a 3, 6,12 e 11,1 cm, senza fissare la lunghezza a una variante storica. I parametri ai limiti vengono segnalati; meno di 200 eventi nel fit o meno di 12 bin occupati non producono una lunghezza.

L'errore statistico usa 32 bootstrap multinomiali degli eventi nel fit, condizionati alla selezione e al modello. Lo smussamento efficace **non** è una calibrazione della risoluzione. Devianza e devianza/gradi di libertà sono riportate; il flag per rapporto >2 è un controllo descrittivo, non un test calibrato di bontà del modello. Le forme osservate non sono perfettamente uniformi: accettanza, fondo e modello restano limiti delle lunghezze approssimate. Sono salvate anche variazioni del taglio DCA a 2 e 8 mm; la loro escursione non è un'incertezza sistematica completa.

| Run | Eventi con DCA ≤ 4 mm, due carichi | Lunghezza stimata | Errore statistico condizionale | Centro z del fit | Centro XY osservato | Larghezze XY del nucleo |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| 1321 | 27.438 | 6,123 cm | 0,020 cm | +0,139 cm | (+0,517; +0,072) cm | (0,481; 0,281) cm |
| 1324 | 29.261 | 6,136 cm | 0,021 cm | +0,141 cm | (+0,514; +0,072) cm | (0,471; 0,284) cm |

Il profilo XY usa gli eventi fra i bordi z del fit. Il centro è la mediana; le larghezze sono `(q84−q16)/2` per asse, equivalenti circa a σ per una Gaussiana. Il diametro di contenimento osservato `2·q95(r)` attorno alla mediana è circa **2,01 e 2,00 cm**: descrive la regione illuminata, **non il diametro fisico della cella**. Le mappe XY hanno bin di 1 mm nel riferimento h70; il file per il consumo futuro usa bordi in mm e conteggi, senza spostare il fascio all'origine. Fuori-range e taglio z sono contabilizzati. Nessuna deconvoluzione di risoluzione o correzione di accettanza.

Il diametro fisico resta `NULL` nel database. `docs/reference/fortran/prog/laggen/include/lagtarg.inc` contiene `TRADIUS=2.5 cm`: il riferimento storico **D=5 cm** compare separatamente nella proposta GEANT4 come ipotesi dichiarata, non come misura dei run. Anche il centro trasverso della cella resta sconosciuto: il centro dello spot non viene sostituito al centro della cella. La proposta GEANT4 contiene lunghezza e centro z in mm, stato del fit e profilo XY osservato come approssimazione del fascio; lunghezze ai limiti o fit falliti non sono esportati come configurazioni valide. Materiale P/D, quando disponibile, viene dal catalogo run, non dai vertici.

Esecuzione dal checkout con dipendenze del progetto disponibili (anche prima di reinstallare i nuovi moduli):

```bash
TASK_ROOT="$PWD/results_test/target-database-local"
mkdir -p "$TASK_ROOT/tmp" "$TASK_ROOT/mpl" "$TASK_ROOT/cache"
export PYTHONDONTWRITEBYTECODE=1
export TMPDIR="$TASK_ROOT/tmp"
export MPLCONFIGDIR="$TASK_ROOT/mpl"
export XDG_CACHE_HOME="$TASK_ROOT/cache"
python -B 06_calibration/target_database.py \
  results_test/2026-11-06-target-edges-production/history/2026-11-06-target-vertex/runs \
  --catalog config/support/run_manifest.csv \
  --output "$TASK_ROOT/pilot" --bootstrap 32
```

Il primo pilot è conservato in `results_test/2026-11-06-target-edges-production/history/2026-11-06-target-database/local/`: CSV, JSON, mappe XY e figure iniziali costituiscono il riferimento del test locale. Il file SQLite ridondante è stato rimosso su richiesta esplicita del responsabile, dopo aver verificato che il payload completo fosse conservato nel JSON. Il formato corrente è descritto sotto; non produce SQLite.

## CSV e profili medi per periodo

Piano concordato il 6 novembre: ricostruire run per run sul server, mantenere un **database CSV completo**, aggregare per periodo e usare una configurazione GEANT4 per periodo omogeneo. Conservare i dati dei plot dei singoli run in un archivio numerico, mentre le figure PNG automatiche mostrano il periodo. Il codice implementa formato, aggregazione e orchestrazione server con ripresa/merge. La campagna server del 6 novembre è descritta sotto; il collegamento effettivo a GEANT4 resta un passo successivo.

Il comando `06_calibration/target_database.py` richiede `--catalog`: i periodi vengono da `source_period`, non sono dedotti dal nome dei file. Il catalogo è validato; run non catalogati o input cambiati durante il lavoro interrompono la pubblicazione. Directory di uscita nuova, senza sovrascrittura.

- **`target_runs.csv`**: database principale, una riga per run, con periodo/materiale/beam dal catalogo, conteggi, tagli, lunghezza/centro/bordi e diagnostiche del fit, centro/larghezze XY, diametro di contenimento dello spot, sorgenti e riferimento ai dati del plot. Diametro fisico non misurato resta vuoto, riferimento storico 5 cm separato.
- **`target_periods.csv`**: una riga per periodo, con medie, dispersione fra run, conteggi di copertura, run inclusi/esclusi/mancanti e stato della compatibilità geometrica.
- **`run_plots.npz`**: archivio unico per tutti i run e periodi. Conserva tutti gli xyz selezionati, senza riduzione statistica, DCA e identità dell'evento sorgente, istogrammi z/XY e curve dei fit. Contiene anche mappe medie per periodo e metadati incorporati: basta questo file per rigenerare una figura di run. Solo array NumPy, leggibili con `allow_pickle=False`; nessun oggetto pickle.
- **`metadata.json`**: provenienza, hash, tagli, versioni, definizioni, parametri e diagnostiche. Integra i CSV; non è un secondo database numerico degli istogrammi.
- **`geant4_candidates.json`**: proposta **per periodo**, con lunghezza/centro z in mm e chiavi del profilo XY nell'NPZ. Le approssimazioni storiche per diametro e profilo del fascio restano esplicite; nessun consumo automatico o modifica della geometria congelata.
- **`period_<periodo>_target_spot.png`**: figura 3D + profilo z + mappa XY richiesta. Le PNG per run si rigenerano su richiesta dall'archivio.

Per la media ogni run valido ha **uguale peso**. La lunghezza e il centro z sono medie aritmetiche dei fit; si registra la deviazione standard fra run. L'errore statistico condizionale sulla media è `sqrt(sum(error_i²))/N`, quando disponibile per tutti i run, e non include sistematiche comuni. Il profilo z medio è la media dei profili normalizzati e delle rispettive curve; non viene presentato come un nuovo fit ai dati mescolati.

Per XY si normalizza ogni istogramma del run e poi si fa la media delle probabilità, mantenendo il riferimento detector comune. Non si ricentra il fascio e non si fa la media delle sole σ: la mappa finale conserva spostamenti e allargamenti fra run. Centro e covarianza derivano da questa miscela, assumendo densità uniforme dentro ciascun bin; le larghezze 68% provengono dalle marginali. Il diametro di contenimento di periodo usa distanze dai centri dei bin rispetto al centro medio: è approssimato dalla griglia, sempre distinto dal diametro della cella. Le finestre XY dei singoli run sono normalizzate separatamente; code fuori finestra rimangono contate nei metadati del run. Questa scelta di pesi non sostituisce la policy di flusso/esposizione e non rappresenta una media pesata per luminosità.

Fit falliti/ai limiti o mappe XY vuote vengono esclusi dalle medie e restano nel CSV dei run con motivazione. Un modello con scarso accordo di forma resta riconoscibile in `poor_shape_runs`, senza promozione a calibrazione certificata. Differenze di lunghezza `max−min > 0,5 cm` segnalano un periodo eterogeneo: la media descrittiva resta nel CSV, ma non viene esportata come singola lunghezza GEANT4. La soglia è un controllo pratico, non un test fisico calibrato. Materiali o beam label misti bloccano anch'essi la proposta geometrica; occorrerà distinguere sottoperiodi, non simulare una cella intermedia inesistente. Senza run validi, lunghezza e proposta di campionamento del fascio restano indisponibili.

Risultato locale del formato corrente: **1998_uv, 2 run elaborati su 179 nel catalogo**, copertura parziale. Lunghezza media **6,129 cm**, dispersione fra i due run **0,0095 cm**; centro XY della miscela circa **(+0,520; +0,068) cm**. Questi numeri non sono ancora la media dell'intero periodo acquisito. Prodotti in `results_test/2026-11-06-target-edges-production/history/2026-11-06-target-periods/final/`.

Per rigenerare un plot di run in una nuova directory, senza riaprire dati grezzi o rilanciare fit:

```bash
python -B 06_calibration/target_database.py plot-run \
  results_test/2026-11-06-target-edges-production/history/2026-11-06-target-periods/final/run_plots.npz \
  --run 1321 --output "$TASK_ROOT/view-run1321"
```

L'archivio usa chiavi `run_1321_xyz_cm`, `run_1321_z_edges_cm`, `run_1321_z_counts`, `run_1321_z_expected_counts`, `run_1321_xy_counts` e relativi bordi in cm; `metadata_json` contiene definizioni e identificazione. Per GEANT4 le chiavi `period_1998_uv_x_edges_mm`, `period_1998_uv_y_edges_mm` e `period_1998_uv_xy_probability` definiscono il profilo medio 2D; la somma delle probabilità è uno quando disponibile. Si sceglie il bin dalla probabilità e si campiona uniformemente al suo interno. Gli xyz archiviati dei run restano in cm. I punti 3D di periodo sono soltanto un campione visivo, con la stessa numerosità per ciascun run incluso; tutti i punti originali restano nell'NPZ.


## Campagna server del 6 novembre 2026

Autorizzata dal responsabile dopo il pilot: **2.711 run del catalogo, 22 periodi**, inclusi P e D, stessa selezione geometrica. Avviata su `trima` in sessione tmux `target_conditions_20261106`, 24 processi e un thread numerico per processo. **Completata** il 6 novembre alle 13:39:56 Europe/Rome; trasferimento locale completato alle 13:40:32, entrambi con exit code 0.

Il responsabile richiede di saltare run con camere spente/inutilizzabili. `target_batch.py` isola ogni run: branch mancanti, input assenti/illeggibili, identità incoerente, assenza di tracce, assenza di vertici validi o selezionati diventano righe con `reconstruction_status` e `reconstruction_note`, warning nel log e nessun peso nella media. `no_chamber_tracks` indica assenza osservata di tracce, senza attribuirla con certezza allo stato hardware. Statistica insufficiente, fit ai limiti e scarso accordo di forma restano segnalati. Errori di scrittura, checksum o provenienza interrompono invece la pubblicazione per evitare prodotti incompleti.

Ogni run produce uno shard atomico con record, eventuale traceback e dati numerici. Ripresa consentita solo con stesso catalogo, codice, versioni, tagli e identità del file raw (percorso/dimensione/mtime; UUID ROOT conservato quando leggibile). Lock di campagna e di run impediscono scritture concorrenti; prenotazioni vuote e staging interrotti vengono recuperati sotto lock. Il merge verifica gli hash degli shard e produce un solo NPZ, CSV e PNG per periodo. Snapshot del codice e runtime isolato in `results_test/2026-11-06-target-edges-production/history/2026-11-06-target-batch/` sul server restano necessari finché il job è attivo; nessuna installazione condivisa modificata.

Benchmark remoto completo: run 1321/1324, circa 10,7/10,5 secondi con due processi; coordinate, DCA e indici degli eventi identici al pilot locale. Differenze sulle lunghezze inferiori a 1e-6 cm, compatibili con differenze di versione SciPy. Rendering 3D verificato dopo isolamento del conflitto Matplotlib sistema/utente. Test locali: **33 passati**, inclusi prosecuzione dopo run inutilizzabile, ripresa, identità errata, input non accessibile e pubblicazione con checksum. Evidenza locale conservata in `results_test/2026-11-06-target-edges-production/history/2026-11-06-target-batch/tests-final.log` e `benchmark-validation.json`.

Monitoraggio dall'esterno:

```bash
ssh trima 'tail -f /data/graal/GRAAL_Analysis/results/2026-11-06-target-edges-final/history/initial-production/campaign.log'
ssh -t trima 'tmux attach -t target_conditions_20261106'
```

Il launcher `scripts/run_target_campaign.sh` mantiene log tramite `tee`, registra `exit_code` e, soltanto dopo merge verificato, pubblica sul server:

- `results/2026-11-06-target-edges-final/history/target_conditions_2026-11-06/`: `target_runs.csv`, `target_periods.csv`, `geant4_candidates.json`, `publication.json` con hash di origine/destinazione.
- `results/2026-11-06-target-edges-final/history/initial-production/products/`: unico `run_plots.npz`, PNG dei periodi, metadati e checksum; CSV originali conservati come evidenza della pubblicazione.

Percorsi del profilo nei CSV/JSON di supporto sono relativi alla directory della configurazione. `target_publish.py` rifiuta checksum incoerenti e copertura incompleta. Copertura completa significa tutti i run tentati, non tutti ricostruibili; esclusioni e periodi eterogenei restano espliciti.

Sessione tmux locale `target_conditions_fetch_20261106` attende `exit_code=0`, scarica prodotti e log, verifica tutti gli SHA-256 e pubblica nelle stesse posizioni relative del checkout locale. Log locale: `results_test/2026-11-06-target-edges-production/history/2026-11-06-target-batch/fetch.log`. Script specifico conservato come evidenza del trasferimento; eventuale fallimento resta in `fetch_exit_code`. File finali locali disponibili; 30 checksum di prodotti/configurazioni riverificati dopo il trasferimento. Dopo trasferimento verificato si possono rimuovere runtime/caches temporanei e shard numerici ridondanti, conservando provenienza, warning e prodotti finali.


Risultato completo: **2.711 run tentati, 22/22 periodi con copertura completa**, 22 PNG e archivio unico NPZ di 3.197.497.011 byte. Stati di ricostruzione: 2.538 completati, 171 senza tracce delle camere, un run senza vertici selezionati (2804), un errore di identità (1509). Tutti gli esclusi restano nei CSV e nei log. Fit: 2.527 approssimati, 180 con statistica insufficiente, quattro ai limiti. Geometria di periodo: **nove compatibili, undici eterogenei, due senza run validi** (`2001_d`, `2005_d1`). Le medie descrittive dei periodi eterogenei non diventano automaticamente una singola geometria GEANT4; resta da distinguere cambi reali di cella e run anomali. Evidenza conclusiva: `results_test/2026-11-06-target-edges-production/history/2026-11-06-target-batch/completion-validation.json`.


## Prova locale dei bordi: `2000_uv2`

Il 6 novembre il responsabile ha segnalato che il profilo di `2000_uv2` mostra bordi più lontani dei 9,649 cm stimati dal modello uniforme, autorizzando una prova con fit separati delle transizioni. La diagnostica usa soltanto NPZ archiviato, senza modificare database/configurazioni di produzione. Tutti i 102 run hanno vecchie stime fra 9,40 e 9,99 cm; 98/102 presentano scarso accordo del modello globale. Il precedente flag di eterogeneità deriva dalla soglia sull'escursione, non dimostra un cambio di cella.

Prototipo riproducibile in `results_test/2026-11-06-target-edges-production/history/2026-11-06-target-edges/edge_pilot.py` e `run_pilot.py`. Per ciascun bordo si usa un gradino con densità interna localmente esponenziale, convoluto analiticamente con una Gaussiana, più fondo costante. Posizione, smussamento efficace, pendenza interna e frazione locale di fondo sono liberi; integrazione numerica nei bin. I punti al 15% dell'altezza del profilo medio smussato inizializzano le finestre, senza fissare i bordi del fit. Riferimento: DCA ≤4 mm, semifinestra 1,6 cm. Controlli: DCA 2/3/4 mm e semifinestre 1,2/1,6/2,0 cm; **918 coppie di fit valide**, nessun parametro al limite. L'NPZ non contiene vertici con DCA >4 mm, quindi quel controllo richiederebbe sorgenti diverse.

| Quantità | Nuova stima diagnostica |
| --- | ---: |
| Bordo sinistro medio | −5,2544 cm |
| Bordo destro medio | +5,8941 cm |
| Lunghezza media | 11,1484 cm |
| Centro z medio | +0,3198 cm |
| Dispersione delle lunghezze fra run | 0,0474 cm |
| Min/max delle nove medie metodologiche | 11,1415–11,1540 cm |

Le medie in cinque blocchi consecutivi di run vanno da 11,1426 a 11,1597 cm; variazione lineare descrittiva sull'intero intervallo circa 0,0183 cm. Non emerge un salto macroscopico di lunghezza nel periodo. Non è stato eseguito un test di significatività del punto di cambio né un fit simultaneo con bordi condivisi: le stime di periodo sono medie aritmetiche dei bordi dei run. La media risulta plausibile dopo aver corretto il modello; la famiglia storica da 11,1 cm (`lagdata.F`) è un confronto esterno, mai un vincolo imposto al fit.

Verifica indipendente con eventi sintetici: lunghezze vere 6,12/11,6/12 cm, smussamento 1,5 mm, fondo e, nei casi lunghi, accettanza parabolica. Scarti ricostruiti −0,0015/−0,0275/−0,0202 cm. Integrali a 12 e 64 nodi concordano entro 1e-9 sul caso di controllo. Le devianze locali mediane/ndf sono 1,18 e 1,21; non sono direttamente confrontabili tramite likelihood ratio con il vecchio fit su tutti i bin. Dispersione fra run, intervallo delle varianti e smussamento non costituiscono un'incertezza totale calibrata.

Figure: `period_2000_uv2_edge_comparison.png`, `period_2000_uv2_edge_stability.png`, `period_2000_uv2_edge_robustness.png`. Dati: `edge_runs.csv`, `edge_scenarios.csv`, `edge_comparison.npz`, dettagli di tutti i fit e `summary.json`; controlli in `closure.json` e `validation.json`. Conservati come evidenza della prova autorizzata. I bordi stimati sono posizioni dei gradini prima dello smussamento, non gli ultimi vertici delle code. Questa verifica era aperta al termine del pilot; la produzione corrente descritta sopra estende il metodo a tutti i periodi.
