# Conservare e aggiornare l'ambiente Docker GEANT3

Questo documento registra le modifiche da consegnare all'utente per un suo
successivo aggiornamento dell'immagine. **L'immagine originale è immutata:**
finora sorgenti modificati, binari e risultati sono stati scritti in directory
esterne montate nei container. Non è stata creata né pubblicata una nuova
immagine. Un `docker commit` dei container di prova non conserverebbe i file
nei bind mount: occorre conservare esplicitamente il pacchetto descritto qui.

Il pacchetto è in
[`resources/geant3/docker-upgrade/`](../../resources/geant3/docker-upgrade/).
Il suo `manifest.json` distingue stato del congelamento dei sorgenti e stato
della validazione fisica. Lo stato è `frozen_sources_pending_native_campaign`:
le impronte definitive e la copia `snapshot/` conservano i sorgenti al termine
delle correzioni locali; la nuova campagna nativa non è stata eseguita. Un pacchetto congelato conserva
un risultato riproducibile;
non significa automaticamente che il trasporto sia validato.

## Ambiente di partenza

| Elemento | Identità |
|---|---|
| Immagine base | `afulci/ubuntu77@sha256:cb810e84914ae1a440663c391b26058c3bb13fff1b41760da6bbc4d1c31a3ca6` |
| Tag originariamente ispezionato | `afulci/ubuntu77:v2.8` |
| Image ID locale osservato | `sha256:0090b49d8e70bb85858e68a3e8f59e41c1b3d6a746153770d2dee4d2b75b0002` |
| Piattaforma | `linux/386`, eseguita su OrbStack |
| Context utilizzato | `orbstack` |
| Compilatore | GNU g77 3.4.6 |
| Progetto storico nell'immagine | `/home/gmandaglio/graal` |
| Librerie CERN | `/home/gmandaglio/graal/2004` |
| Programmi storici | `/home/gmandaglio/graal/software/prog` |

Il digest, non il tag mobile, identifica il punto di ripristino. Il build usa
`-B/usr/lib/i386-linux-gnu/` per trovare gli oggetti di avvio richiesti al link.
Le opzioni del compilatore e le librerie CERN restano quelle registrate nei log
del build, salvo modifiche esplicitamente elencate nel manifest finale.

## Inventario delle modifiche

I percorsi della prima tabella sono relativi a
`/home/gmandaglio/graal/software/prog/laggen`. Le patch riutilizzabili, applicate in quest’ordine, sono
[`signal.patch`](../../resources/geant3/signal.patch) e
[`energy_window.patch`](../../resources/geant3/energy_window.patch).

| Sorgente | Modifica conservata | Motivo e natura |
|---|---|---|
| `src/blockdata.F` | Registra il nuovo canale 38 e una forza unitaria convenzionale. | Nuova funzionalità; il valore non è una sezione d'urto fisica. |
| `src/channeldef.F` | Definisce eta, pi0 e protone per gamma p→eta pi0 p. | Nuovo canale separato; le definizioni preesistenti restano disponibili. |
| `src/totalsect.F` | Aggiunge il nome del canale 38. | Identificazione del nuovo canale. |
| `src/ev_nuc.F` | Collega il canale 38 a GENBOD e scarta proposte secondo `WT`, accettando eventi con peso1; controlla il limite del peso. | Correzione necessaria alla generazione non pesata: `KGENEV=1` restituisce ancora un peso. Il modello di sola fase-spazio è una scelta fisica. |
| `src/lagdata.F` | Inizializza separatamente il generatore CERN RNDM e aggiunge `TARG x 4` per12cm. | Seed riproducibile; lunghezza12cm scelta provvisoria esplicita. |
| `src/gukine.F` | Scrive la verità completa delle madri prima delle perdite; per il canale 38 genera decadimenti isotropi prompt gg e inserisce quattro fotoni più il protone come primari; conserva la verità delle figlie. | Denominatore completo e percorso di decadimento esplicito; nessuna dichiarazione automatica di correttezza del trasporto. |
| `src/laggen.F` | Sposta l'output legacy nel lavoro isolato; apre le verità madri/figlie e scrive terminatori di chiusura. | Elimina il percorso di output condiviso e consente di distinguere output completo e interrotto. |
| `src/uginit.F` | Verifica `ETDK 1` per il segnale e imposta i decadimenti gg forzati. | Convenzione del campione; branching fisici applicati separatamente nell'analisi. |
| `pilot.h` | Seleziona ntuple, batch, stampa opzioni e cilindri vecchi, disattivando opzioni di altri canali e Condor. | Pilot locale dedicato; geometria cilindrica provvisoria, non correzione universale dell'apparato. |

`energy_window.patch` estende `src/lagdata.F` con la card facoltativa `EWIN`
e il COMMON `SIGNAL_ENERGY`; estende `src/montecarlo.F` con l’estrazione uniforme
dell’energia nell’intervallo richiesto, limitata al canale 38. In assenza di
`EWIN` conserva l’energia fissa. Il launcher espone `--energy-range LOW HIGH`
e verifica che ogni energia generata appartenga all’intervallo. Questo è un
campionamento MC dichiarato per coprire i bin, non lo spettro misurato dei dati;
la risposta va normalizzata con il denominatore generato di ciascun bin.

Le modifiche seguenti sono applicate dalle ricette shell, non tutte compaiono
in `signal.patch`. Per ricostruire il cambiamento completo conservare anche le
ricette, la card, il mapping e il launcher Python.

| Programma/file | Modifica della ricetta | Motivo e natura |
|---|---|---|
| Tutti: copia locale `GRAAL_period.h` | Disabilita26, abilita21 nelle copie private dei tre programmi. | Associazione iniziale ai dati protonici2002_uv1; non altera l'header globale dell'immagine. |
| LAGGEN `src/gsking.F` e `Makefile.signal` | Copia e ricompila il sorgente CERN GSKING invariato; lo aggiunge agli oggetti del programma. | Dipendenza di build esplicita. **Non è una correzione dimostrata del trasporto**: il precedente successo attribuito a GSKING è stato smentito. |
| LAGDIG `pilot.h` | Abilita BGO, elimina `OFFSET` e opzioni omega; seleziona cilindri vecchi. | Trigger dichiarato e rimozione di opzioni non appartenenti al pilot. L'abilitazione BGO-only è provvisoria. |
| LAGDIG `src/opennt_out.F` | Allarga `IDRUN` a16bit e `IDEVT` a24bit. | Conserva identità complete e consente il collegamento agli eventi generati. |
| LAGDIG `src/init_random.F` | Legge `GRAAL_DIG_SEED`, inizializza CERN RDMIN e g77 SRAND. | Riproducibilità; elimina il seed dipendente dall'orologio. |
| PREAN `pilot.h` | Seleziona cilindri vecchi coerenti con LAGGEN/LAGDIG. | Coerenza del profilo provvisorio. |
| PREAN `src/readevents.F` | Limita a `LDATA` gli override di cablaggio barrel e trigger dipendenti dal run. | Impedisce che correzioni dei dati decodificati siano applicate ai dati simulati. |
| Makefile dei tre programmi | Elimina oggetti archiviati e dipendenze obsolete; crea `Makefile.signal`; evita i comandi PREAN che ripristinano il vecchio Makefile durante il link. | Build fresco controllabile, senza dipendere dagli oggetti presenti nell'immagine. |
| Base runtime privata `data21.base` | Porta `THLENGTH` da6 a12cm. | Coerenza con il bersaglio scelto nella card; il database originale resta immutato. |
| `transport_probe.F` e build LAGGEN | Compila un piccolo eseguibile che chiama GTGAMA dalla libreria CERN storica, con fotoni sopra e sotto cutoff. | Controllo della corretta esecuzione della libreria sul runtime corrente; nessuna sostituzione del GTGAMA di produzione. |
| `run_signal_chain.sh` | Esegue il probe prima degli eventi e si ferma se fallisce; usa base21 e `calib_3700.cal`, verifica macro, seed, completamento e registra hash dei binari/dipendenze. | Contratto di esecuzione per il profilo iniziale e arresto preventivo su runtime non affidabile. |
| `03_mc_simulation/geant3_signal.py` | Genera card; congela le risorse in `resource_snapshot`; isola il container; valida identità, energie, masse, decadimenti, geometria e conteggi. | Controlli dell'intera catena. Conserva stato non validato quando la sola terminazione non basta. |
| `03_mc_simulation/tests/test_geant3_signal.py` | Regressioni su verità incompleta/incoerente, selezione di profilo e mount dello snapshot. | Protezione contro errori già osservati; non test di accettanza fisica. |

## Correzioni software e ipotesi fisiche

Le identità degli eventi, il denominatore completo, la verifica dei terminatori,
i seed espliciti, il gating `LDATA` e la copia immutabile delle risorse sono
correzioni o controlli del software. Non vanno rimossi per ottenere un conteggio
di eventi più favorevole. Lo snapshot risolve un problema effettivamente
osservato: modificare una shell ancora in lettura da un bind mount ha fatto
fallire una replica dopo l'elaborazione fisica.

Il modello uniforme nello spazio delle fasi, i decadimenti prompt forzati gg,
il bersaglio LH2 da 12cm, la scelta di cilindri vecchi e il trigger solo BGO
appartengono al contratto fisico provvisorio. La densità0.071g/cm³ deriva dal
sorgente storico; l'assegnazione uniforme del bersaglio ai periodi è autorizzata
dall'utente. Le frazioni di branching non devono comparire sia nell'efficienza
sia nella normalizzazione: si applicano una volta nella sezione d'urto.

Il mapping documentato comprende sette periodi:
1998_uv→09, 1999_uv→10, 2000_uv1→14, 2000_fuv→15, 2000_uv2→17,
2002_uv1→21 e2002_uv2→22. L'implementazione iniziale è2002_uv1/run3629.
2001_uv/base18 resta indisponibile nel dominio di flusso corrente.
Periodo26/run4300 appartiene al deuterio e non è una configurazione protonica.

## Diagnosi del runtime e modifiche non adottate

La stessa combinazione di binari proton21, card e seed produce **999/1000**
eventi PREAN su `trima` x86_64 nativo, contro **117/1000** su OrbStack.
L’evidenza nativa è conservata in
`results/cross-section-signal-acceptance-20261021/native-original-1000`.
La selezione corrente produce727 eventi h85 e11 ricostruiti: il campione è
insufficiente per una matrice di risposta con otto bin azimutali. Il controllo
su colonne vuote deve restare attivo; non si riempiono le colonne inventando
efficienze o riusando un singolo numero medio.

Un probe minimo riproduce il difetto su OrbStack chiamando l’oggetto storico
GTGAMA: un fotone da100MeV, con cutoff0.01MeV, processi disabilitati e passo
richiesto nullo, viene assorbito a distanza zero. Il sorgente GTGAMA
ricompilato supera il probe. Anche una sostituzione diagnostica a lunghezza
invariata dell’istruzione `OR AX,0xc00` con `MOV AH,0xc` e NOP lo fa superare.
Questa evidenza localizza una dipendenza dal percorso di esecuzione x87 emulato;
non autorizza a interpretare successi sensibili al layout come correzioni
fisiche del generatore.

**Né il GTGAMA ricompilato né la modifica delle istruzioni sono adottati nella
produzione.** Non copiarli nel futuro aggiornamento dell’immagine. Il probe
conservato deve linkare la libreria storica realmente usata; una versione
sostitutiva del solo probe nasconderebbe il problema. Il probe verifica sia
il fotone sopra soglia che deve sopravvivere, sia quello sotto soglia che deve
fermarsi. Un particolare g77 è stato verificato: `STOP 1` può restituire
exit code0. Il sorgente conservato usa quindi `CALL EXIT(1)`/`CALL EXIT(2)`;
la shell richiede anche il marcatore `TRANSPORT PROBE PASS`. Il probe locale
aggiornato fallisce correttamente su OrbStack con exit code1 prima degli eventi. Il superamento è necessario, ma non basta a certificare
l’intera
risposta del rivelatore.

Il build dei programmi può avvenire nell’ambiente isolato di OrbStack;
l’esecuzione fisica in quell’ambiente deve ora arrestarsi sul probe se il
difetto persiste. Per la produzione usare un runtime nativo verificato,
conservando identità dei binari, architettura, probe e log. Il comando nativo già eseguito è registrato sotto.
Il nuovo probe ed EWIN
non sono ancora verificati su trima al momento di questo congelamento.
Non si presume autorizzato un trasferimento o un lancio remoto aggiuntivo.

## Esecuzione nativa storica e campagna preparata

Comando già usato su trima per il campione originale1000-eventi, riportato
come evidenza. Non è una richiesta di rieseguirlo nelle directory esistenti,
né il launcher della nuova campagna; i nuovi sorgenti non sono ancora stati
trasferiti e validati sul nodo nativo.

```sh
docker run --rm --platform linux/386 --network none --read-only \
  --cpus 2 --memory 2g --pids-limit 256 --tmpfs /tmp:rw,size=256m \
  --env GRAAL_DIG_SEED=231025 \
  -v /data/graal/GRAAL_Analysis/results/cross-section-native-validation-20261021/build:/build:ro \
  -v /data/graal/GRAAL_Analysis/results/cross-section-native-validation-20261021/original-1000:/work \
  -v /data/graal/GRAAL_Analysis/results/cross-section-native-validation-20261021/original-1000/resource_snapshot:/resources:ro \
  --entrypoint /bin/sh \
  afulci/ubuntu77@sha256:cb810e84914ae1a440663c391b26058c3bb13fff1b41760da6bbc4d1c31a3ca6 \
  /resources/run_signal_chain.sh
```

Il piano locale conservato in
`results/cross-section-signal-acceptance-20261021/native-campaign-inputs/plan.json`
prevede 100 eventi di smoke test (seed310027), poi 99900 eventi (seed310031),
con energia uniforme0.95–1.4875GeV. L’intervallo0.95–1.1GeV serve a controllare
le migrazioni sotto il dominio d’analisi1.1–1.5GeV. Il piano è preparato,
con autorizzazione estesa ancora in attesa al momento del congelamento;
non è un conteggio di eventi prodotti. Il launcher registra `energy_gev=null`
e `energy_range_gev` quando viene richiesto l’intervallo, evitando di attribuire
al campione una singola energia fittizia.

La libreria storica e il probe fanno parte del contratto di esecuzione. Il
probe è incluso tra gli eseguibili con hash nel build e nel launcher.
Tredici test mirati sono passati dopo il controllo del fallimento del probe;
la suite Stage03 completa conta94 test passati e Ruff non segnala problemi.
Gli hash dei tre binari originali/nativi coincidono. Nessun container della
simulazione resta attivo.
Questi numeri sono lo stato software al congelamento, non una validazione
della nuova campagna nativa.

## Ricostruzione locale del pacchetto congelato

I comandi seguenti sono istruzioni per una replica successiva; questo runbook
non li esegue. Usare un checkout corrispondente alle impronte del manifest,
con ambiente Python del progetto già disponibile. Scegliere una directory
nuova: i build rifiutano di sovrascrivere directory dei programmi già esistenti.

Prima controllare che il manifest non sia ancora draft e che gli SHA256 del
payload coincidano con quelli registrati. Il suo campo `files` associa
`source_path`, `snapshot_path`, dimensione e SHA256. Per usare il launcher del
checkout verificare anche che il suo `source_path` corrisponda alla stessa
impronta. Se il checkout è avanzato, usare la revisione archiviata o il suo
worktree senza ripristinare file sopra il lavoro corrente.

```sh
repo_dir="$PWD"
upgrade_run="$repo_dir/results/geant3-upgrade-rebuild-20261021"
mkdir "$upgrade_run"
cp -R resources/geant3/docker-upgrade/snapshot/resources/geant3 \
  "$upgrade_run/resources"
mkdir "$upgrade_run/output"
docker --context orbstack run --rm --platform linux/386 \
  --network none --read-only --tmpfs /tmp:rw,exec,size=512m \
  --mount "type=bind,src=$upgrade_run/resources,dst=/resources,readonly" \
  --mount "type=bind,src=$upgrade_run/output,dst=/work" \
  --entrypoint /bin/sh \
  afulci/ubuntu77@sha256:cb810e84914ae1a440663c391b26058c3bb13fff1b41760da6bbc4d1c31a3ca6 \
  /resources/build_all_signal.sh > "$upgrade_run/build.log" 2>&1
```

Questo ricompila programmi esterni, senza creare una nuova immagine. Conservare
`build.log`, `output/build-binaries.sha256`, le tre directory dei programmi,
i loro header/pilot e il pacchetto sorgente. Non confrontare solo gli hash dei
binari: temporary filename e metadati possono cambiare senza modificare il
codice macchina; i risultati fisici e la provenienza restano necessari.

Il comando seguente illustra il launcher locale e registra comando, seed e
dipendenze. Su OrbStack con il difetto osservato deve **fermarsi sul probe**;
non è il comando per aggirare il controllo o lanciare automaticamente su trima:

```sh
.venv-flux/bin/python -m mc_simulation.geant3_signal \
  --build-dir "$upgrade_run/output/build" \
  --output-dir "$upgrade_run/pilot-1000" \
  --events 1000 --energy 1.2 --seed 231021 --timeout 600
```

`run.json` e il report scientifico prevalgono su un semplice exit code0.
In particolare, un risultato `detector_chain_complete_unvalidated` non è una
misura di efficienza. Il launcher copia risorse in ogni output e usa quella
copia per evitare cambiamenti durante l'esecuzione.

## Validazione prima di sostituire l'ambiente

La replica deve verificare tre livelli distinti:

1. **Build e provenienza:** digest base, piattaforma, compilatore, assenza di
   oggetti stantii, hash sorgenti e dipendenze, stesso profilo nei tre log,
   probe GTGAMA superato sul runtime effettivo di esecuzione.
2. **Generazione e catena:** verità completa con run/eventi univoci, quadrimpulso
   conservato, fotoni con massa nulla ed energia positiva, momenti angolari
   compatibili con isotropia, corrispondenza generati→hit→digitizzati→PREAN.
   Le perdite reali devono rimanere nel denominatore.
3. **Risposta fisica e analisi:** sciami ed energia depositata plausibili,
   stabilità rispetto a replica e seed indipendenti, selezione corrente BDT/no-fit,
   copertura cinematica e confronto con dati/riferimento con le incertezze
   esplicitamente disponibili. L'assenza di un crash non sostituisce questo livello.

Test software mirati nel checkout corrispondente:

```sh
.venv-flux/bin/python -m pytest 03_mc_simulation/tests/test_geant3_signal.py -q
.venv-flux/bin/python -m ruff check \
  03_mc_simulation/geant3_signal.py \
  03_mc_simulation/tests/test_geant3_signal.py
```

Lo stato fisico al congelamento è registrato nel manifest e
nel [report del segnale](../reports/2026-10-21-signal-acceptance.md), senza
trasformare automaticamente un test diagnostico in accettanza valida.

## Aggiornamento futuro dell'immagine da parte dell'utente

Conservare il payload completo del manifest in un contesto di build ristretto.
Un futuro Dockerfile deve partire dal digest sopra e copiare esplicitamente
patch, ricette, mapping e provenienza con `COPY`; può poi eseguire il build in
una directory nuova. È preferibile conservare i programmi aggiornati in un
percorso dedicato, per esempio `/opt/graal-signal/`, mantenendo i programmi
storici originali disponibili. Registrare nel nuovo artefatto l'impronta del
manifest e lo stato della validazione fisica. Eventuali binari precompilati
vanno legati allo stesso manifest e ai relativi log, non scelti dal nome.

Il launcher corrente importa il digest da `03_mc_simulation/geant3.py` e monta
binari esterni in `/build`: pubblicare una nuova immagine non lo fa passare
automaticamente a quella nuova. L'adozione successiva richiede una modifica
esplicita del riferimento immagine e del contratto dei binari, con nuova
verifica. Qui non sono stati eseguiti `docker build`, `docker commit`, `docker tag`
né `docker push` per produrre o pubblicare l'aggiornamento.

## Rollback

L'immagine di partenza è già il punto di rollback perché non è stata mutata.
Per riprodurre lo stato precedente usare il vecchio digest, il suo pacchetto
sorgenti e il suo set coerente di binari/header/base. Non mischiare binari del
nuovo profilo con file di calibrazione o pilot del precedente. Conservare gli
output delle prove fallite come evidenza e cambiare directory per la nuova
prova; non sovrascriverli per ottenere un log apparentemente pulito.

Dopo un eventuale aggiornamento dell'utente, ritornare al digest originale e
al manifest precedente nel launcher. La sola inversione di un tag mobile non
è una registrazione riproducibile del rollback.

## Fonti Docker verificate

Documentazione consultata con Context7 (`/docker/docs`):
[bind mount](https://docs.docker.com/engine/storage/bind-mounts/),
[tmpfs](https://docs.docker.com/engine/storage/tmpfs/),
[rete none](https://docs.docker.com/engine/network/drivers/none/),
[container commit](https://docs.docker.com/reference/cli/docker/container/commit/),
[build cache e COPY](https://docs.docker.com/build/cache/optimize/).
