# Strip-energy flux: manutenzione e correzioni

**Stato:** implemented; farm production validation pending
**Ambito:** lookup run/strip→Eγ, integrazione `POL1/POL2/BREM`, QA e output farm

Questa pagina è il punto di partenza per correggere la normalizzazione quando
arrivano nuove informazioni sperimentali. Il contratto scientifico è in
[Design strip-energy flux](strip-energy-flux-design), gli schemi serializzati
sono in [Formati dati](data-formats), e la storia di implementazione è in
[Implementation plan](strip-energy-flux-implementation-plan).

## Assunzioni scientifiche provvisorie

Le voci di questa sezione sono **PROVVISORIE, non risultati di fisica**. Devono
essere riesaminate prima di usare gli output per osservabili pubblicabili.

1. `BREM` è direttamente confrontabile con ciascuno stato polarizzato e viene
   sottratto una sola volta da `POL1` e una sola volta da `POL2`:
   `pol1_net = pol1 - brem`, `pol2_net = pol2 - brem`,
   `total_net = pol1 + pol2 - 2*brem`. La scala di `BREM` è quindi
   provvisoriamente unitaria.
2. I conteggi degli istogrammi di flusso sono trattati come già corretti quanto
   basta per l'uso di normalizzazione corrente. Non viene applicata qui alcuna
   correzione di dead time, tagging efficiency o live time.
3. Non esiste una calibrazione parametrica strip→energia. Il lookup deriva
   direttamente dagli alberi inclusivi `h80`, usando la mediana di `beam.E()`
   per ogni `(RunNumber, Xstrip)`.
4. Non si fa pooling tra run o periodi, né interpolazione, extrapolazione o
   fallback per strip vuote.
5. L'intero contenuto di una strip viene assegnato a un solo bin energetico,
   determinato dall'energia mediana; non esiste assegnazione frazionaria.
6. Target `P`/`D` e fasci `UV`/`VIS` non vengono mai mescolati. L'aggregazione
   usa soltanto il `group` autorevole del manifest.
7. Le classificazioni del manifest sono curate manualmente a partire dalla
   tabella dei periodi fornita dall'utente; il nome della directory da solo non
   è una nuova autorità per riclassificarle.
8. I preset Ajaka sono provvisoriamente:
   `ajaka_cross_section` = 15 bin uniformi da 0.95 a 1.50 GeV, quindi 16
   bordi; `ajaka_sigma` = bordi
   `[1.10, 1.20, 1.30, 1.40, 1.50]` GeV.

Il significato fisico preciso e l'orientazione di `POL1` rispetto a `POL2`
non sono documentati in modo autorevole nel repository. Non inferirli dai
nomi: ottenere la convenzione sperimentale prima dell'estrazione di `Σ`.
I due preset Ajaka vengono sempre prodotti di default; ogni opzione ripetuta
`--binning NAME:EDGE,EDGE,...` **aggiunge** uno schema custom e non sostituisce
i preset.

## Input autorevoli

- `config/run_manifest.csv`: unica autorità per run, periodo, target, fascio e
  gruppo; deve passare `scripts/build_run_manifest.py --validate`.
- alberi inclusivi `h80` sotto `--preanalysis-dir`: autorità osservata per
  `RunNumber`, `Xstrip` e `beam.E()`; i nomi file non sostituiscono il ramo run
  e gli `h85` selezionati non sono ammessi per il lookup.
- `--flux data/flux/flux.root`: autorità raw per le triplette ROOT
  `POL1/POL2/BREM` delle run richieste.
- preset in `00_common/strip_energy_flux.py` e opzioni CLI ripetute
  `--binning`: autorità versionata dei bordi usati in una pubblicazione.

Percorsi, soglie, bordi e digest devono essere archiviati con gli output. Il
locale `data/run_manifest.generated.csv`, quando presente, è inventario di
supporto e non sostituisce il manifest curato.

## Flusso dati completo

```text
config/run_manifest.csv ──validate_manifest──────────────┐
                                                         │
inclusive h80 ROOT ──iter_h80_samples────────────────────┤
                    file/entry validation                │
                    bounded batches → temporary SQLite   │
                    exact median/MAD → lookup records    │
                                                         ├─ run/bin flux
data/flux/flux.root ──read_flux_histograms───────────────┤
                       strict requested triplets         │
                       warning-only unrequested keys     │
                                                         ├─ group/bin flux
named energy binnings ──whole-strip assignment───────────┤
                                                         │
run/group raw sums ──check_flux_conservation─────────────┤
                                                         │
all diagnostics ──build_qa_payload───────────────────────┘
             → sibling staging → atomic directory publication
```

Il database SQLite è temporaneo, univoco per invocazione e rimosso anche
quando la lettura fallisce. Contiene ogni evento validato, mentre la memoria
Python conserva batch di inserimento limitati e al massimo
`manifest-runs × 128` record lookup. Mediana e MAD sono statistiche d'ordine
esatte: nessun campionamento, istogramma approssimato o fit.

### Responsabilità dei moduli

- `00_common/strip_energy_flux.py` contiene record immutabili, validazione
  semantica, preset/bordi, riferimento lookup puro, lookup SQLite esatto,
  integrazione per run, aggregazione per gruppo, invarianti di conservazione e
  serializzazione deterministica. Non dipende da PyROOT.
- `scripts/build_strip_energy_flux.py` possiede gli adapter ROOT, lo streaming
  `h80`, la selezione stretta delle triplette richieste, lo spool temporaneo,
  l'orchestrazione QA, gli exit code e la pubblicazione atomica/sibling.
- `00_common/run_manifest.py` e `config/run_manifest.csv` definiscono e
  validano la classificazione autorevole run→periodo/target/fascio/gruppo.
- `00_common/tests/test_strip_energy_flux.py` protegge la logica pura,
  l'esattezza e il limite di memoria; `test_build_strip_energy_flux.py`
  esercita ROOT reali e il vero `main()` subprocess.
- `wiki/strip-energy-flux-design.md`, questa pagina, `pipeline.md` e
  `data-formats.md` sono rispettivamente contratto scientifico, handoff di
  manutenzione, procedura farm e contratto serializzato.

## Artefatti e schema QA

Una pubblicazione completa contiene sempre:

- `strip_energy_lookup.csv`: una riga per `(run, strip)` osservata;
- `flux_by_run_energy.csv`: una riga per `(binning, run, energy-bin)`;
- `flux_by_group_energy.csv`: una riga per
  `(binning, target, beam_type, group, energy-bin)`;
- `strip_energy_flux_qa.json`: schema QA v1.

Le colonne complete, le unità e la semantica dei bordi sono definite in
[Formati dati — lookup e flussi integrati](data-formats#lookup-stripeγ-e-flussi-integrati).
Il QA v1 contiene i blocchi `inputs`, `thresholds`, `binnings`, conteggi
manifest/h80/flusso/lookup, diagnostica `h80` e `flux`, discrepanze di run,
strip vuote o non mappate, inversioni, warning MAD/statistica,
underflow/overflow, esclusioni fuori range, flussi netti negativi,
`conservation`, `errors` e `valid`. `conservation` riporta tolleranze,
numero di controlli e fallimenti dettagliati: per ogni run/schema/stato
verifica `included + out_of_range = physical_total`; per ogni
gruppo/bin/stato verifica la somma raw delle run contribuenti. Un fallimento è
un errore strutturale fatale. Qualunque aggiunta incompatibile richiede un nuovo
`schema_version`, aggiornamento dei test e della pagina `data-formats`.

## Matrice warning/fatale

| Condizione | QA | Pubblicazione | Exit |
|---|---|---|---|
| MAD sopra soglia o conteggio sotto soglia | warning in `mad_warnings` / `low_stat_warnings` | quattro artefatti, `valid` invariato | 0 se nessun altro errore |
| strip non osservata con flusso tutto zero | diagnostica in `empty_strips` | quattro artefatti | 0 se nessun altro errore |
| energia lookup fuori dai bordi di uno schema | warning in `out_of_range`, flusso raw escluso contabilizzato | quattro artefatti | 0 se nessun altro errore |
| underflow/overflow ROOT non nullo | warning, mai sommato | quattro artefatti | 0 se nessun altro errore |
| run di flusso extra completa o malformata | warning in `extra_flux_runs` / `malformed_flux_triplets` | quattro artefatti | 0 se nessun altro errore |
| run manifest senza h80, o run h80 extra | errore in QA completo | quattro artefatti diagnostici | 1 |
| strip senza lookup ma con flusso non nullo | errore e dettaglio `nonzero_unmapped_strips` | quattro artefatti diagnostici | 1 |
| inversione oltre tolleranza o direzione indeterminata | errore e `monotonic_inversions` | quattro artefatti diagnostici | 1 |
| flusso netto negativo | riga run/gruppo conservata con `status=invalid`, dettaglio in `negative_net_errors` | quattro artefatti diagnostici | 1 |
| mismatch strutturale di conservazione raw run o gruppo | dettaglio in `conservation.failures` ed errore | quattro artefatti diagnostici | 1 |
| manifest invalido; h80/branch/entry invalida; run richiesta senza tripla esatta; oggetto/asse/contenuto flusso invalido; opzione semantica invalida | QA minimo se scrivibile | nessuna pubblicazione completa | 1 |
| sintassi CLI o flag obbligatorio mancante | nessun QA | nessun artefatto | 2 |

La strictness del flusso vale per ogni run richiesta: esattamente una chiave
canonica `run<N>_POL1`, `run<N>_POL2`, `run<N>_BREM`; ciascun oggetto deve
essere un `TH1` monodimensionale con 128 bin, bordi 0…128 e contenuti finiti.
Le run non richieste non possono invalidare un subset autorevole del manifest.

## Pubblicazione atomica e fallimenti

La CLI costruisce i quattro artefatti in una staging sibling univoca. Solo
dopo il completamento sposta l'eventuale output precedente in un backup
univoco, pubblica la staging con rename e poi rimuove il backup in best effort.
Se il rename della staging fallisce, ripristina il backup.

Un errore prima della pubblicazione segue questa policy:

- se `--output-dir` non esiste ed è una destinazione sicura, il QA minimo può
  essere pubblicato nella destinazione richiesta;
- se `--output-dir` esiste, non viene modificato, anche se contiene una
  precedente analisi valida; il QA minimo va in
  `<output-dir>.failure.<token>/strip_energy_flux_qa.json`;
- stderr stampa `Failure QA: <percorso-assoluto>`; riportare anche quella
  sibling dalla farm;
- gli errori `argparse` con exit 2 avvengono prima di questa policy e non
  producono QA.

Un'analisi completata ma `valid: false` è invece una pubblicazione completa:
conserva tutte le righe diagnostiche e può sostituire atomicamente l'output
precedente. Non usarla per estrazione fisica.

## Comando farm e directory da riportare

Prima validare il manifest:

```bash
python scripts/build_run_manifest.py --validate config/run_manifest.csv
```

Comando esatto:

```bash
python scripts/build_strip_energy_flux.py \
  --preanalysis-dir data/pre_analyzed \
  --manifest config/run_manifest.csv \
  --flux data/flux/flux.root \
  --output-dir results/strip_energy_flux
```

Riportare integralmente `results/strip_energy_flux/` per exit 0 o per
un'analisi completata con exit 1. Per un fallimento anticipato su una
destinazione già esistente, riportare inoltre la directory assoluta stampata
dopo `Failure QA:`.

## Benchmark bounded-memory del 2026-07-30

Piattaforma: macOS 26.5.2 arm64, Python 3.14.6, ROOT 6.38.04, SQLite 3.53.3.
Il generatore riproducibile è
`scripts/benchmark_strip_energy_flux.py`.
Entrambi i dataset hanno quattro file ROOT, quattro run, tutte le 128 strip;
ogni file contiene più run e ogni run attraversa tutti i file. I due comandi
misurati sono stati:

```bash
python scripts/benchmark_strip_energy_flux.py \
  /private/tmp/graal-strip-bench.fVeRPu/events-200k 50000
/usr/bin/time -l python scripts/build_strip_energy_flux.py \
  --preanalysis-dir /private/tmp/graal-strip-bench.fVeRPu/events-200k/pre \
  --manifest /private/tmp/graal-strip-bench.fVeRPu/events-200k/manifest.csv \
  --flux /private/tmp/graal-strip-bench.fVeRPu/events-200k/flux.root \
  --output-dir /private/tmp/graal-strip-bench.fVeRPu/events-200k/output

python scripts/benchmark_strip_energy_flux.py \
  /private/tmp/graal-strip-bench.fVeRPu/events-1m 250000
/usr/bin/time -l python scripts/build_strip_energy_flux.py \
  --preanalysis-dir /private/tmp/graal-strip-bench.fVeRPu/events-1m/pre \
  --manifest /private/tmp/graal-strip-bench.fVeRPu/events-1m/manifest.csv \
  --flux /private/tmp/graal-strip-bench.fVeRPu/events-1m/flux.root \
  --output-dir /private/tmp/graal-strip-bench.fVeRPu/events-1m/output
```

| Eventi h80 | Record lookup | Tempo reale | Peak RSS |
|---:|---:|---:|---:|
| 200,000 | 512 | 2.88 s | 398,786,560 B (380.31 MiB) |
| 1,000,000 | 512 | 12.60 s | 399,310,848 B (380.81 MiB) |

Con 5× eventi, il peak RSS è aumentato di 524,288 B (0.13%), mentre il tempo
è cresciuto 4.38×. Questo supporta il limite rispetto al conteggio totale
degli eventi; non è una misura della farm reale. I dati sono sintetici e
molto comprimibili, il filesystem/cache erano locali, il processo PyROOT ha
un baseline RSS elevato, non sono state simulate tutte le distribuzioni o
concorrenze della produzione. Ripetere quindi la misura sulla farm e
archiviare hardware, versioni, input inventory e `/usr/bin/time` completo.

## Guida alle correzioni future

La tabella indica il minimo punto di modifica. Prima di cambiare una
convenzione, aggiungere un test che fallisce con il comportamento corrente.

| Correzione | Codice/config da modificare | Test e documenti da aggiornare | Output da rigenerare |
|---|---|---|---|
| Scala o trattamento diverso di `BREM` | `00_common/strip_energy_flux.py`: `integrate_run_flux`, `aggregate_group_flux`, eventualmente nuovi campi record; `scripts/build_strip_energy_flux.py`: QA/opzioni | test `test_flux_integration_sums_whole_strips_and_subtracts_brem_twice`, test negativi e aggregazione in `test_strip_energy_flux.py`, CLI diagnostica in `test_build_strip_energy_flux.py`; design, `data-formats`, questa pagina | `flux_by_run_energy.csv`, `flux_by_group_energy.csv`, QA; ripubblicare la cartella completa |
| Dead time, live time o tagging efficiency | introdurre un record/funzione pura di correzione prima di `integrate_run_flux`; aggiungere input con provenienza in CLI e `build_qa_payload` | unit test per fattori, missing/zero/nonfinite, test ROOT/CLI e conservazione raw; design, schema QA, pipeline, questa pagina | entrambi i CSV di flusso e QA; lookup può restare identico ma la cartella va ripubblicata |
| Normalizzazione di luminosità corretta | creare uno strato downstream esplicito o nuovi record versionati; non ridefinire silenziosamente `total_net`; usare `aggregate_group_flux` solo come somma raw/net | nuovi test di unità, fattori target e conservazione run→gruppo; design, `data-formats`, pipeline e documentazione dell'osservabile | nuovi artefatti normalizzati più entrambi i CSV di flusso/QA se cambia la convenzione di base |
| Calibrazione strip→energia | `iter_h80_samples`, `build_strip_energy_lookup_on_disk`, `StripEnergyRecord.provenance` o nuovo modulo/calibration input; mantenere controllo run/strip | test di calibrazione e propagazione, exactness/QA, fixture CLI; design, `data-formats`, pipeline, questa pagina | tutti e quattro gli artefatti e ogni output fisico derivato |
| Fallback per strip vuote | `run()` nei blocchi `empty_strips`/`nonzero_unmapped_strips`, `integrate_run_flux`, provenienza lookup e QA | sostituire/estendere `test_nonzero_flux_without_lookup_is_fatal` e test CLI relativo; test che P/D, UV/VIS e run non vengano poolati per errore; design e schema | tutti e quattro gli artefatti e output fisici derivati |
| Nuovi bin energetici | `AJAKA_CROSS_SECTION`, `AJAKA_SIGMA`, `EnergyBinning` oppure `--binning`/`parse_custom_binnings` | test preset/bordi e test CLI custom binning; design, `data-formats`, pipeline se diventa preset | CSV run/gruppo e QA; lookup invariato, ma ripubblicare la cartella completa |
| Correzioni del manifest | `config/run_manifest.csv`; se cambia l'inferenza per nuovi scan, anche `classify_period`/`scan_runs` in `00_common/run_manifest.py` | `00_common/tests/test_run_manifest.py`, validator, conteggi e hash di provenienza in questa pagina; verificare manualmente la tabella periodo utente | tutti e quattro gli artefatti e ogni aggregato/risultato downstream |
| Convenzione di polarizzazione | `01_pre_analysis/PreAnalysis.C` per la provenienza del ramo evento; `_FLUX_SUFFIXES`, `read_flux_histograms`, `StripFlux` e `integrate_run_flux` per gli stati di flusso. `06_plots/fig7_compton_polarization.py` è solo riferimento al trasferimento Compton, non un estrattore di `Σ` | test triplette ROOT, integrazione, ordine colonne/QA, `06_plots/tests/test_fig7_compton_polarization.py`; design, `data-formats`, questa pagina | CSV di flusso, QA e osservabili di asimmetria; lookup solo se la nuova convenzione lo richiede |
| Accettanza ed efficienza finali | **nessun modulo finale esiste**. Creare uno strato physics versionato downstream. `04_bdt_training/photon_loss.py` e `build_background_features.py` descrivono solo l'accettanza/perdita usata nel training BDT, non l'accettanza finale | nuovi test MC/data, binning run/gruppo, incertezze e closure; nuova pagina di formato/lineage | nuovi artefatti di accettanza e tutti gli osservabili fisici downstream |
| Luminosità target | **nessuna config/implementazione/test esiste**. Creare input autorevole con unità, densità, lunghezza, live time e provenienza, più modulo puro downstream | test dimensionali, zero/missing/nonfinite, separazione P/D e propagazione errori; design e formato nuovi | nuovi artefatti di luminosità e sezione d'urto |
| Branching ratio | `00_common/channels.py` e `00_common/cross_sections.py` contengono registry/pesi di fondo per MC/BDT, **non** la normalizzazione finale. Creare config versionata con fonte e incertezza | `00_common/tests/test_channels.py`, `test_cross_sections.py` solo se cambia il registry; aggiungere test specifici dell'estrattore fisico | sezione d'urto e prodotti derivati, non il lookup |
| Estrazione finale `σ`/`Σ` | **nessun estrattore esiste**. Creare moduli/config/test dedicati downstream per yield corretti, luminosità, accettanza, branching ratio e fit azimutale `cos(2φ)` | closure su pseudo-dati, unità, propagazione incertezze, covariance, convenzione segni/polarizzazione; nuova documentazione di schema | nuovi output physics; rigenerare da lookup/flussi validati dopo ogni migrazione upstream |

## Migrazione, compatibilità e rerun

1. Aprire un cambiamento con test RED che esprima la nuova informazione
   scientifica; aggiornare design e assunzioni prima del codice.
2. Decidere esplicitamente la compatibilità. Campi QA v1 additivi, come
   `conservation`, richiedono consumer tolleranti a chiavi sconosciute e
   aggiornamento della lista documentata. Rimozione/rinomina/cambio semantico
   di chiavi o colonne richiede un nuovo `schema_version` o nuovi nomi file.
3. Aggiornare nello stesso commit codice puro, CLI/config, test unit/ROOT,
   `data-formats`, pipeline e questa pagina. Non cambiare una costante fisica
   senza provenienza e unità.
4. Validare manifest e input, eseguire test focused/full, help, diff-check e
   benchmark rappresentativo. Sulla farm salvare commit, versioni, comando,
   digest manifest e inventario ROOT.
5. Eseguire sempre un rerun completo: la cartella è una pubblicazione atomica,
   non un dataset append-only. Non mescolare CSV vecchi e nuovi. Un successo o
   una QA completa non valida sostituisce l'intera destinazione; un fallimento
   anticipato preserva la destinazione e crea una sibling diagnostica.
6. Confrontare conteggi/schema/digest e rieseguire tutti gli output downstream
   elencati nella tabella. Conservare la versione precedente finché il nuovo
   QA è `valid: true` e la validazione fisica è firmata.

Aspettativa corrente: ordinamento e schemi CSV restano deterministici; il
lookup puro rimane disponibile come riferimento, mentre la farm usa solo il
percorso SQLite bounded. Nessun fallback/pooling può comparire come modifica
compatibile silenziosa: cambia la provenienza scientifica e richiede versione,
QA e rerun completi.

## Decisioni cambiate durante le revisioni

- La prima implementazione teneva tutti gli eventi `h80` e liste per strip in
  RAM. La revisione finale l'ha sostituita con spool SQLite e order statistics
  esatte perché il peak della farm non deve crescere col corpus totale.
- Il QA minimo di un errore runtime sostituiva atomicamente anche un output
  valido. Ora usa una sibling unica quando la destinazione esiste, perché un
  rerun fallito non è una nuova pubblicazione scientifica.
- Le run di flusso extra complete o incomplete erano promosse a errori dalla
  CLI, nonostante il reader le trattasse come diagnostica. Ora sono
  warning-only e non entrano nei CSV; la strictness resta sulle sole run
  richieste.
- Errori semantici `Xstrip`/energia erano validati dopo aver perso file ed
  entry. Ora la validazione avviene durante lo streaming per rendere il QA
  azionabile.
- La conservazione era soltanto conseguenza implicita dei loop. Ora è
  ricontrollata indipendentemente a livello run e gruppo e un mismatch è
  strutturale/fatale.
- Revisioni precedenti avevano già reso backup/staging univoci, mantenuto le
  righe negative come diagnostica `status=invalid`, classificato
  underflow/overflow come warning e riservato exit 2 agli errori `argparse`.
  Queste scelte restano perché preservano dati diagnostici senza confondere un
  errore d'uso con una QA scientifica.

## Checklist prima dell'uso fisico

- [ ] Confermare per iscritto le otto assunzioni provvisorie sopra, oppure
  implementare e revisionare le correzioni.
- [ ] Validare il manifest e ottenere esattamente 2711 run con i conteggi di
  gruppo riportati nella sezione Provenienza.
- [ ] Conservare hash e copia del manifest, inventario degli input ROOT,
  comando completo, versione Python/ROOT e commit Git.
- [ ] Eseguire la CLI su h80 inclusivi, non h85 selezionati.
- [ ] Richiedere exit 0 e `valid: true`; non trattare exit 1 come risultato
  fisico anche quando i CSV diagnostici esistono.
- [ ] Ispezionare run mancanti/extra, triplette extra, strip vuote,
  `nonzero_unmapped_strips`, inversioni, MAD e bassa statistica.
- [ ] Verificare underflow/overflow e flusso escluso fuori range per ciascun
  binning.
- [ ] Verificare che `negative_net_errors` sia vuoto.
- [ ] Controllare conservazione raw: flusso incluso più escluso deve spiegare
  le 128 strip fisiche; somme di gruppo devono uguagliare le run contribuenti.
- [ ] Ripetere il benchmark peak RSS/tempo sulla farm con un inventario
  rappresentativo; confrontarlo con il baseline sintetico e spiegare ogni
  crescita con il numero totale di eventi.
- [ ] Confrontare copertura energetica e lookup per P/D e UV/VIS senza
  mescolare gruppi.
- [ ] Archiviare insieme i quattro artefatti; se c'è stato un fallimento,
  archiviare anche la sibling QA indicata su stderr.
- [ ] Rigenerare tutti gli osservabili downstream dopo qualunque modifica a
  manifest, lookup, correzione flusso, binning o convenzione.

## Provenienza corrente

`config/run_manifest.csv` è il manifest curato autorevole, introdotto nel
commit `36921a4`. Contiene 2711 righe run, 22 periodi e quattro gruppi:
`D_UV=538`, `D_VIS=342`, `P_UV=1426`, `P_VIS=405`.
La classificazione manuale deriva esclusivamente dalla mappa a 22 periodi
fornita dall'utente; il repository non contiene una provenienza esterna più
specifica e non bisogna inventarla.

| Periodo | Target | Fascio | Gruppo | Run |
|---|---:|---:|---:|---:|
| `1998_uv` | P | UV | P_UV | 179 |
| `1999_d1` | D | VIS | D_VIS | 69 |
| `1999_d2` | D | VIS | D_VIS | 97 |
| `1999_uv` | P | UV | P_UV | 339 |
| `1999_vis` | P | VIS | P_VIS | 110 |
| `2000_fuv` | P | UV | P_UV | 147 |
| `2000_uv1` | P | UV | P_UV | 204 |
| `2000_uv2` | P | UV | P_UV | 102 |
| `2000_vis` | P | VIS | P_VIS | 129 |
| `2001_d` | D | VIS | D_VIS | 111 |
| `2001_uv` | P | UV | P_UV | 137 |
| `2002_d1` | D | UV | D_UV | 137 |
| `2002_d2` | D | VIS | D_VIS | 65 |
| `2002_d3` | D | UV | D_UV | 98 |
| `2002_uv1` | P | UV | P_UV | 128 |
| `2002_uv2` | P | UV | P_UV | 190 |
| `2002_vis1` | P | VIS | P_VIS | 94 |
| `2002_vis2` | P | VIS | P_VIS | 25 |
| `2003_vis` | P | VIS | P_VIS | 47 |
| `2005_d1` | D | UV | D_UV | 23 |
| `2005_d2` | D | UV | D_UV | 151 |
| `2006_d` | D | UV | D_UV | 129 |

Digest riproducibili:

```bash
shasum -a 256 config/run_manifest.csv data/run_manifest.generated.csv
```

Risultato corrente:

```text
64a2096602e0db2a7de2b5a2c4b64c94df3e2719c3f8510b69b44018033d3160  config/run_manifest.csv
6cdd8c2dde0fb5dbfb8e179908184bc60b0dc740832229432945261ea578ea35  data/run_manifest.generated.csv
```

`data/run_manifest.generated.csv` è un inventario locale ignorato da Git,
presente durante questa revisione ma non garantito in un clone. Ha le stesse
2711 combinazioni
run/periodo/target/file. Contiene 1831 classificazioni automatiche e 880 righe
senza fascio/gruppo; il manifest curato conserva l'inventario ma applica a
tutte le righe la mappa utente, colmando quelle 880 assegnazioni. Dopo
qualsiasi modifica rieseguire il validator, ricontare tabella/gruppi e
aggiornare entrambi i digest qui senza attribuire fonti non presenti.

- Implementazione strip-energy flux: commit range `529cad8..HEAD`; la fix wave
  finale è il commit contenente questa pagina e segue il baseline `5179a2a`.
- Decisioni, verifiche e istruzioni correnti sono consolidate in questa pagina,
  nel design, nel piano di implementazione e in `Current-Status.md`; la cronologia
  Git conserva il dettaglio delle modifiche.

## Non-obiettivi ancora aperti

Questa pipeline non produce ancora osservabili fisici completi. Restano fuori:

- accettanza geometrica e da Monte Carlo;
- efficienza di selezione e ricostruzione;
- correzioni di dead time/tagging/live time;
- luminosità target;
- branching ratio;
- normalizzazione finale della sezione d'urto;
- fit di `Σ` con `cos(2φ)`;
- trasferimento della polarizzazione e sua calibrazione;
- sistematiche su polarizzazione, bordi, calibrazione, efficienze e modello.

Qualunque risultato che dipenda da questi elementi deve dichiararli mancanti
o implementarli in uno strato versionato e verificato prima dell'uso fisico.
