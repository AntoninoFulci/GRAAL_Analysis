# Ambiente storico GRAAL / GEANT3

**Stato aggiornato:** canale dedicato38, γp→ηπ⁰p, con decadimenti
isotropi prompt in quattro fotoni primari, verità delle madri e dei fotoni,
e build isolati LAGGEN/LAGDIG/PREAN. Il profilo iniziale usa
**2002_uv1/run3629/base21/cilindri vecchi**; il
[mapping JSON](proton_periods_provisional.json) include le altre sei basi.
Il test pulito1000-eventi completa la catena ma conserva solo117 eventi al
trigger BGO: il trasporto non è ancora validato, e non esiste un'accettanza
fisica utilizzabile. Cilindri vecchi, trigger solo BGO e bersaglio12cm restano
ipotesi provvisorie. Il precedente periodo26/deuterio è solo diagnostico.
Le risorse di ogni esecuzione sono copiate e bloccate contro modifiche
concorrenti. Vedere il [report aggiornato](../../docs/reports/2026-10-21-signal-acceptance.md);
i paragrafi seguenti conservano le verifiche storiche.

Risorsa indicata dall'utente il 21 ottobre 2026: repository Docker Hub
[`afulci/ubuntu77`](https://hub.docker.com/r/afulci/ubuntu77), usato con
OrbStack su macOS. `tagname` nel comando comunicato era un segnaposto:
l'API pubblica elenca `v1`, `v2.3`, `v2.6`, `v2.8`.

## Immagine identificata

- Tag candidato: `afulci/ubuntu77:v2.8`, aggiornato il 16 luglio 2026.
- Riferimento immutabile:
  `afulci/ubuntu77@sha256:cb810e84914ae1a440663c391b26058c3bb13fff1b41760da6bbc4d1c31a3ca6`.
- Piattaforma: `linux/386`; dimensione compressa dichiarata: 1.521.225.164 byte.
- Selezione: versione più recente pubblicata, scaricata e ispezionata;
  non ancora versione validata della simulazione per questa analisi.

L'immagine risiede nello storage Docker/OrbStack. Questa directory conserva
identità e istruzioni; i layer binari non sono duplicati nel repository Git.
Un `docker push` pubblica un'immagine, mentre il recupero usa `docker pull`.

```sh
docker --context orbstack pull --platform linux/386 \
  afulci/ubuntu77@sha256:cb810e84914ae1a440663c391b26058c3bb13fff1b41760da6bbc4d1c31a3ca6
```

Ispezione temporanea, senza montare directory del Mac né abilitare la rete:

```sh
docker --context orbstack run --rm --platform linux/386 \
  --network none --read-only --entrypoint /bin/sh \
  afulci/ubuntu77@sha256:cb810e84914ae1a440663c391b26058c3bb13fff1b41760da6bbc4d1c31a3ca6 \
  -c 'uname -m; command -v g77; command -v gfortran'
```

Questo è un controllo dell'ambiente, non il comando di simulazione. Percorsi
dei sorgenti, steering card, geometria, trigger, seed, generatore e output
devono essere identificati prima di definire il lancio fisico. Montaggi
scrivibili, directory di lavoro e risorse di calcolo dipendono da quel contratto.

## Verifiche del 21 ottobre 2026

- Context Docker attivo: `orbstack`.
- Copia preesistente: `v2.3`, digest
  `sha256:6006af6aa6dbdcf121a32a16cf97c6e58546a6bfdc694c020e5ce5c28e773586`.
- Avvio di `v2.3` riuscito sul Mac con host arm64; container riporta `i686`.
  `g77 --version` restituisce GNU Fortran 3.4.6.
- In `v2.3`, `/g77` è vuota; ricerca per nomi GEANT/LAGGEN/GRAAL/CERN non
  trova componenti. Questa verifica non descrive il contenuto di `v2.8`.
- Recupero di `v2.8` completato; digest locale coincide con Docker Hub.
  Image ID: `sha256:0090b49d8e70bb85858e68a3e8f59e41c1b3d6a746153770d2dee4d2b75b0002`.
- Container `v2.8` avviato con successo su OrbStack, piattaforma `linux/386`,
  senza rete e filesystem read-only. Inventario conferma GEANT3 e progetto
  GRAAL completo di sorgenti e binari LAGGEN/LAGDIG. Prova tecnica di due
  eventi π⁰ completata successivamente, descritta sotto; nessuna closure
  del segnale o ricompilazione eseguita.

## Inventario e punti d'integrazione verificati in v2.8

Radice progetto nell'immagine: `/home/gmandaglio/graal`.

| Percorso relativo | Contenuto verificato |
|---|---|
| `2004/lib/libgeant321.a`, `2004/lib/libgeant.a` | Librerie GEANT3 |
| `2004/src/geant321/` | Sorgenti CERN/GEANT3 |
| `software/prog/laggen/` | Sorgenti, binari `laggen_nc`/`laggen_oc`, script e README |
| `software/prog/lagdig/` | Digitizzazione, binari `lagdig_nc`/`lagdig_oc` |
| `data/inp_laggen/` | Steering card di vari canali e configurazioni |
| `data/base/`, `data/calib_*` | Basi e calibrazioni da associare ai periodi |
| `data/out_evgen/`, `data/out_laggen/`, `data/out_lagdig/`, `data/out_prean/` | Directory di output dei passaggi storici |

Evidenze che impediscono un lancio fisico indiscriminato:

- `software/prog/laggen/src/lagdata.F:301–305` assegna `THLENGTH` a **11.1,
  6.12 o 3 cm**, secondo secondo parametro di `TARG` (`<=1`, `=2`, `>=3`).
  Questi valori sono codice effettivo, oltre ai commenti alle righe 109–111.
- `software/prog/laggen/src/lagmat.F:50` usa H₂ con densità **0.071 g/cm³**.
  `lagbers.F` usa `THLENGTH/2` per il volume e `vertex.F` per i vertici.
  Non è ancora noto quale configurazione corrisponda ai nostri run. Differenza
  11.1 cm nel codice / 12 cm nel paper da risolvere, senza mediare i valori.
- Card generica `data/inp_laggen/laggen.dat` contiene **`TARG 2 2`**:
  deuterio, lunghezza 6.12 cm. Non è card pronta per γp→pηπ⁰.
- `lagdata.F` definisce polarizzazione **1 orizzontale, 2 verticale**;
  contratto attuale della pipeline associa POL1 a verticale e POL2 a
  orizzontale. La conversione richiede mapping esplicito verificato.
- README LAGGEN richiede compilazione con `./comp`, che seleziona macro
  per geometria del cilindro e opzione Condor. Non ricompilare con un `make`
  generico assumendo equivalenza dei binari.
- Wrapper `laggen_run`/`lagdig_run` invocano `qsub`: non sono launcher locali
  OrbStack pronti all'uso. Il sorgente `laggen.F` scrive inoltre un file fisso
  `data/out_evgen/outev.dat`: esecuzioni parallele devono avere output isolati.
- `/setmeall.sh` contiene percorsi e modifiche d'ambiente storiche; è stato
  letto, non eseguito. Preparare ambiente minimo esplicito dopo aver tracciato
  dipendenze e output, senza usare il profilo del Mac come directory di lavoro.

Fonti tecniche: [API pubblica dei tag](https://hub.docker.com/v2/repositories/afulci/ubuntu77/tags?page_size=100),
[Docker image pull](https://docs.docker.com/reference/cli/docker/image/pull/),
[Docker image inspect](https://docs.docker.com/reference/cli/docker/image/inspect/).
Documentazione Docker verificata tramite Context7.

Disegno dell'analisi: [estrazione sezioni d'urto](../../docs/superpowers/specs/2026-10-21-cross-section-extraction-design.md).

## Launcher locale e prova completata

```sh
python3 -m mc_simulation.geant3 run \
  --card resources/geant3/smoke_pi0.dat --geometry old \
  --output-dir results/geant3-smoke-new --timeout 90
```

Launcher vincola digest, piattaforma, memoria e CPU; container senza rete,
filesystem read-only, card read-only, output nuovi e isolati. `CERN_ROOT`
vale `/home/gmandaglio/graal/2004`: contiene `lib/flukaaf.dat` richiesto da
FLUKA. Non viene eseguito `/setmeall.sh`.

Prova del 21 ottobre in `results/cross-section-geant3-smoke-fixed-20261021`:
**2 eventi γp→pπ⁰**, geometria `old`, card di prova H₂ da 3 cm, Eγ=1.2 GeV.
`outev.dat` contiene due record e terminatore `-1`; log riporta due eventi
GG, zero eventi errati, chiusura HBOOK e `Time of CPU Used`.
`run.json` conserva card, comando e hash degli output. Questi parametri
servono alla prova tecnica, non descrivono il bersaglio dei dati.

La prima prova, in `results/cross-section-geant3-smoke-20261021`, si fermava
per `FLUKAAF.DAT` assente dal percorso: exit code 0 e header `.hit` di 48 byte
non dimostravano completamento. Il suo vecchio `status=hits_written` è un
falso positivo, conservato come evidenza diagnostica. Launcher corretto
richiede anche terminazione normale nel log e terminatore del generato.

**Canale pηπ⁰ assente nella versione corrente, confermato dall’utente.** Nomi delle
card non bastano: canale 19 è ridefinito come η′ in questa versione. Il file
generato ASCII non fornisce un'identità evento direttamente affidabile;
l'ntuple hit h50 contiene IDRUN/IDEVT, ma può omettere eventi. Restano da
collegare generato completo, digitizzazione e ricostruzione corrente.
Non usare i due eventi π⁰ per calcolare efficienza del segnale.


## Chiarimento sul generatore e integrazione pηπ⁰

Utente conferma: il canale non era definito; LAGGEN usa sezioni d'urto
sperimentali totali/differenziali e particelle richieste, con GENBOD per
la cinematica. Non occorre cercare una presunta card del segnale già pronta.
Questo chiarimento definisce il lavoro come estensione del generatore corrente.

Traccia verificata nei sorgenti dell'immagine fissata dal digest:

| Sorgente sotto `software/prog/laggen/src/` | Responsabilità verificata |
|---|---|
| `gen_init.F:73–98` | Legge `channel.mat`: 64 canali, 50 nodi, 19 valori angolari per nodo in `XSECT`. |
| `channeldef.F` | Definisce particelle, molteplicità e decadimenti per canale. |
| `blockdata.F:13`, `totalsect.F` | Registro dei canali e sezioni totali; verifica canali e costruisce pesi dello spettro. |
| `channelex.F` | Seleziona canali con probabilità proporzionali alle sezioni totali. |
| `montecarlo.F:75–109` | Con `BEAM 0`, energia fissata da `ETAG`; altrimenti campiona spettro convoluto con probabilità di interazione. |
| `ev_nuc.F:146–150` | Un solo canale selezionato evita il sorteggio fra canali. |
| `ev_nuc.F:270–284` | Lista esplicita di canali instradata a GENBOD; altri a generatori angolari. |
| `gen_evt_3body.F` | Angolo della prima particella da distribuzione differenziale, altre variabili da spazio delle fasi. Non è un modello generale delle correlazioni a tre corpi. |
| `ev_nuc.F:1067–1093` | Output ASCII con formati e molteplicità scelti mediante liste di canali; non aggiunge ID evento. |

Due dettagli impediscono di aggiungere soltanto una riga a `channeldef.F`:

- Nel sorgente corrente, canale 54 compare già nel ramo GENBOD; successivo
  `ELSEIF(JCH.EQ.54)` verso `GEN_EVT_3BODY` risulta quindi irraggiungibile.
  Non assumere attiva quella distribuzione differenziale dai soli commenti.
- `GEN_EVT_3BODY` dichiara `XMX(50), FMX(50)` ma il ciclo parte da indice 0;
  la routine non può essere adottata senza correggere e verificare i limiti.

Percorso di implementazione ora identificato:

1. Registrare un canale dedicato γp→ηπ⁰p senza ridefinire canali storici;
   aggiornare registro, definizione, instradamento multibody e copia delle
   particelle finali verso GEANT3. Gestire esplicitamente i due decadimenti.
2. Prova tecnica iniziale a energia fissa, con spazio delle fasi dichiarato,
   conservazione del quadrimpulso, soglia e masse controllate. Verificare
   convenzione `KGENEV=1`/`WT` della GENBOD effettivamente linkata: il ponte
   risposta attuale accetta eventi non pesati, non pesi trattati come conteggi.
3. Scrivere verità completa con IDRUN/IDEVT, energia, particelle e quadrimpulsi
   dopo assegnazione del vertice, prima delle perdite del rivelatore. L'ASCII
   attuale viene scritto dentro EV_NUC, prima di `CALL VERTEX` in GUKINE:
   il vertice di quel record non va assunto corrispondente all'evento corrente.
4. Integrare distribuzioni sperimentali/modelli di produzione e variazioni
   alternative; controllare dipendenza dell'accettanza da masse e angoli
   correlati. Sole proiezioni differenziali non determinano distribuzione
   multidimensionale completa.
5. Collegare hit, digitizzazione, ricostruzione e selezione corrente tramite
   identità; denominatore include ogni evento generato nel campione definito.

Le sezioni d'urto del generatore definiscono il campionamento. La sezione
misurata rimane normalizzata con flusso, bersaglio, BR ed efficienza; non con
la sezione totale impostata nel generatore. Ajaka può fornire un modello di
forma, ma tale uso va dichiarato e variato: confronto con Ajaka non sarebbe
indipendente rispetto a quell'input di accettanza. Nessuna tabella Ajaka è
stata aggiunta o spacciata per già disponibile.

Questa verifica aggiorna il contratto di integrazione; non modifica ancora
binario/container e non dichiara generati eventi pηπ⁰.


## Catena completa LAGGEN → LAGDIG → PREAN

Chiarimento aggiuntivo dell'utente, confermato nei sorgenti: LAGGEN/GEANT3
produce le interazioni e gli hit; LAGDIG simula la digitalizzazione; PREAN
elabora l'output digitalizzato e lo porta nella struttura di analisi usata
per i dati reali. Il numeratore della risposta deve attraversare tutta questa
catena, poi conversione HBOOK/ROOT, selezione e ricostruzione corrente.

```text
verità completa + identità evento
            │
LAGGEN / GEANT3 → .hit → LAGDIG → .dig → PREAN (LSIMUL) → .pol
                                                            │
                    conversione e pipeline dati corrente ←──┘
                                  │
                    selezione / pairing / BDT → numeratore
```

Evidenze nel sorgente sotto `software/prog/`:

- `lagdig/src/opennt_in.F` legge `.hit` da `OUT_LAGGEN`.
- `lagdig/src/eventloop.F` applica `TAG`, digitalizzazione BGO, parete,
  barrel, camere e shower; applica poi `TRIG`. Scrive solo eventi accettati.
  `NBTAG`, `NBEV`, `NGEV` distinguono perdite di tagging, trigger e accettati.
- `lagdig/src/lagwrev.F` descrive output come canali ADC/TDC;
  `opennt_out.F` scrive `.dig` in `OUT_LAGDIG`, conservando IDRUN/IDEVT e
  blocco di verità `EVENT_CH`, oltre alle quantità digitalizzate.
- `prean/src/openntuple_in.F`, ramo `LSIMUL`, legge precisamente `.dig`
  da `OUT_LAGDIG`; il ramo dati legge invece output del decoder.
- `prean/src/openntuple_out.F` scrive ntuple `.pol` in `OUT_PREAN_SIM`,
  con blocchi di analisi e informazioni MC aggiuntive. Struttura destinata
  alla stessa analisi non implica identità di ogni branch fra MC e dati:
  schema effettivo dopo conversione va confrontato.

Contratto dell'efficienza: denominatore = tutti gli eventi generati del
campione, prima delle perdite; numeratore = eventi ricostruiti/selezionati
dopo GEANT3, LAGDIG e PREAN. Perdita a qualunque passaggio resta perdita,
non scompare dal denominatore. Salvare conteggi per passaggio e hash di
binari, macro di compilazione, basi/calibrazioni e steering dei tre programmi.
La simulazione delle condizioni di tagging va confrontata con la definizione
del flusso assoluto adottato, evitando di correggere due volte lo stesso effetto.

Identità e configurazione richiedono verifiche specifiche:

- LAGDIG dichiara IDRUN a 8 bit e IDEVT a 23 bit; PREAN amplia i campi, ma
  non può recuperare eventuale informazione già persa a monte.
- Macro `OFFSET` in LAGDIG può aggiungere `ISTART` a IDEVT. Registrare la
  trasformazione; usare identità globale con campagna/shard e mappa esplicita.
- PREAN contiene correzioni dipendenti da IDRUN (`SWAP_ADC_23_24` per
  3778–4407, assegnazione ITRIG=1 per IDRUN<=666). Non sostituire run con
  numeri arbitrari per comodità di matching senza verificare questi rami.
- I blocchi verità presenti in `.dig`/`.pol` descrivono i sopravvissuti:
  non sostituiscono il registro completo del generato.

Questa sessione ha verificato i collegamenti nel codice e aggiornato il
contratto; prova end-to-end LAGDIG/PREAN non ancora eseguita. La precedente
prova di due eventi resta limitata a LAGGEN/GEANT3.

## Canale segnale implementato: build isolato e pilot (21 ottobre 2026)

`signal.patch` aggiunge **canale38, γp→ηπ⁰p** senza ridefinire quelli storici.
GENBOD usa spazio delle fasi dichiarato; `KGENEV=1` non basta a rendere gli eventi
non pesati, quindi il nuovo ramo applica rejection sampling sul `WT` e conserva
unit weight. Eta e pi0 sono forzati a2γ. Le BR fisiche restano esterne
all'efficienza. `TARG 1 4` seleziona esplicitamente H₂12cm; la base isolata di
LAGDIG/PREAN viene adeguata alla stessa lunghezza provvisoria.

`build_all_signal.sh` esegue i tre build dal sorgente nell'immagine fissata:
usa `/resources` read-only per questa directory e `/work` come directory nuova
scrivibile. Nessun qsub, Condor o profilo shell. I build ricompilano gli oggetti
con g77 e `-B/usr/lib/i386-linux-gnu/`, necessario per trovare gli startup object.
L'output è `/work/build/{laggen,lagdig,prean}`. Per esempio, sostituire soltanto
`/PERCORSO/ASSOLUTO/OUTPUT_NUOVO` con una directory di risultati vuota:

```sh
docker --context orbstack run --rm --platform linux/386 \
  --network none --read-only --cpus 2 --memory 2g \
  --tmpfs /tmp:rw,size=256m \
  --mount type=bind,src="$PWD/resources/geant3",dst=/resources,readonly \
  --mount type=bind,src=/PERCORSO/ASSOLUTO/OUTPUT_NUOVO,dst=/work \
  --entrypoint /bin/sh \
  afulci/ubuntu77@sha256:cb810e84914ae1a440663c391b26058c3bb13fff1b41760da6bbc4d1c31a3ca6 \
  /resources/build_all_signal.sh
```

Il build ricompila anche **GSKING** dal sorgente CERN presente nell'immagine:
la versione linkata dall'archivio, nei test controllati, produceva solo depositi
del protone e un ciclo di decadimenti pi0 all'evento653. Un build con quel sorgente e strumentazione diagnostica ha ripristinato gli
sciami e completato1000 eventi:996 sopravvissuti al trigger BGO. Il replay
senza strumentazione riproduce il difetto: la ricompilazione di GSKING da sola
**non è una correzione validata**. Il build rimane diagnostico fino alla
risoluzione della dipendenza dalla strumentazione.

LAGDIG conserva ora IDRUN16/IDEVT24bit senza OFFSET; abilita esplicitamente
`GRAAL_T_BGO`. PREAN viene ricompilato con le stesse camere; le correzioni di
cablaggio dipendenti dal run sono applicate solo a LDATA. I seed di GEANT,
GENBOD/CERN RNDM e digitizer/g77 RAND sono registrati separatamente.

```sh
python3 -m mc_simulation.geant3_signal \
  --build-dir results/cross-section-signal-acceptance-20261021/build \
  --output-dir results/cross-section-signal-pilot-new \
  --events 10000 --energy 1.2 --seed 310027
```

Il launcher richiede output nuovo e produce verità completa, `.hit`, `.dig`,
`.pol`, log, hash e `run.json`. Valida conservazione quadrimpulso, masse, vertici,
identità e conteggi. Non assegna un'accettanza prima di conversione e selezioni.

**Limite del pilot:** usa periodo26/run4300 e camere nuove, condizioni tecniche
prese dall'immagine. Il manifest dati assegna4300 a deuterio2002_d3: questo pilot
con bersaglio H₂ non può essere attribuito ai periodi di dati sul protone. Per
produzione fisica vanno associati periodo, calibrazioni e camere dei run H₂.
Dettagli, risultati e prove non valide conservate:
[report segnale](../../docs/reports/2026-10-21-signal-acceptance.md).
