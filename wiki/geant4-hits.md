# Hit di trasporto GEANT4

Dal **10 novembre 2026**, il launcher usa il formato compatto descritto sotto. La modalità diagnostica completa, introdotta il 9 novembre, resta disponibile con `--storage full`. Il trasporto non applica soglie, quenching, risoluzioni, trigger, PID o BDT. Questi file sono input per lo sviluppo della risposta, non eventi sperimentali ricostruiti né efficienze fisiche.

## Formato compatto predefinito: schema hit 3

`run.py smoke` e `run.py replay` usano **`--storage compact`** per impostazione predefinita. Per conservare ogni campo diagnostico usare `--storage full`. L'eseguibile nativo `graal_g4` accetta lo stesso argomento finale; senza argomento mantiene schema 2 per compatibilità con chiamanti esistenti. Entrambe le modalità usano ROOT/ZSTD livello 5, identiche condizioni, fisica, seed e politica di completamento atomico.

Dal 11 novembre 2026, replay ROOT tramite launcher usa `--threads auto`: un job,
tutte le CPU disponibili. `--threads N` seleziona MT esplicito; `--threads serial`
mantiene flusso casuale storico. Eventi, primarie e step sono scritti in ordine di
origine anche quando trasportati fuori ordine. Gli indici degli step sensibili e
i contatori callback/reset passivi vengono ricomposti globalmente: nessun reset
artificiale del contesto cilindrico al cambio evento o thread. Provenienza distingue
MT da seriale; numero thread e motore casuale sono registrati. Dettagli e limiti in
[Monte Carlo](03-monte-carlo-simulation#exclusive-truth-replay).

- **BGO:** nessuna riga per singolo step; `bgo_hits` conserva somme float64 per cristallo e primo tempo di deposito positivo, nello stesso ordine di accumulo del trasporto completo.
- **Altri rivelatori:** tutti gli step sensibili restano presenti, anche quelli senza deposito. Si conservano posizione globale pre/post, carica, deposito, tempi, percorso, identità traccia/parent/step e flag di stato/attraversamento. Direzioni, coordinate locali, energie cinetiche, lunghezza dello step, deposito non ionizzante, PDG/peso della singola traccia e stringhe di processo/materiale per step non sono necessari alla risposta corrente e non vengono scritti. Inventario dei materiali e primarie restano completi.
- **Contabilità:** `events`, `primaries`, `vertices`, condizioni, input, pesi primari e stati RNG restano invariati. `events.hit_steps` e `summary.detector_steps` contano sempre tutti gli step sensibili originali. `storage_events` contiene `run,event,stored_steps,bgo_steps` per ogni evento, anche vuoto o abortito; i due contatori sommano a `hit_steps`. `summary.stored_detector_steps` conta le righe realmente scritte.
- **Identità:** `detector_steps.source_step_entry` è l'indice sensibile originale, sparso, non il numero di riga ROOT compatta. Tutti i collegamenti downstream usano tale indice. Il contesto cilindrico dichiara `source_index=original_sensitive_step`; resta valida l'identità `callback_index = source_step_entry + passive_epoch`, anche tra eventi/run. Nessuno stato delle camere viene azzerato dalla compattazione.

`summary` dichiara `hit_schema_version=3`, `storage_mode=compact`, `hit_policy=compact_response_inputs_v1`. L'oggetto JSON ROOT `storage_metadata` richiede `schema_version=1`, `mode=compact`, `bgo=sum_per_crystal_float64`, `source_index=original_sensitive_step`, `response_scope=current_response_no_step_quenching`. I reader nativi verificano metadati, tipi, contatori, intervalli/ordine degli indici, somme BGO, inventario e validità dei campi conservati. I consumer Python del denominatore verificano metadati e ledger al proprio confine, senza caricare gli step.

La compattazione conserva gli input dei modelli di risposta **attualmente implementati**, prima di digitizzazione/PID/selezione. Non conserva quanto necessario a qualsiasi modello futuro: nuovi studi di quenching per step, traiettorie o pesi secondari richiedono modalità completa o un nuovo trasporto. Nessuna conversione distruttiva dei risultati storici.

Misura sullo stesso pilot di 128 reazioni: **370.319.390 → 11.823.704 byte**, fattore **31,32**. Dei 2.604.842 step originali restano 171.585 righe non-BGO; eventi, primarie, somme BGO, contesto cilindrico e ogni campo conservato coincidono esattamente. Estrapolazione del solo trasporto: **1,85 GB per 20.000 eventi**, **46,19 GB per 500.000**. Non è un limite universale né include generatori, ricostruzione e file temporanei. Evidenza e limiti: `results_test/geant4-compact-20261110/reports/handoff.md`.

## Contratto e identità

`graal_geometry` esporta `geant3_sensitive` dal campo ISVOL del mezzo nel `geometry.g3` originale. `DetectorHits.hh` interpreta i casi 1–14 di `laggen/src/gustep.F`; i codici passivi storici sono 200, 210, …, 340 (anche 0 indica assenza di sensibilità). Metadati mancanti o sconosciuti fanno fallire il trasporto batch. **Rigenerare i vecchi GDML con il convertitore corrente**; non modificare gli snapshot o i risultati archiviati. La visualizzazione rimane utilizzabile anche con vecchi GDML.

L'identità primaria di un volume è il percorso completo, per esempio `/LAGR:1/NID1:1/BGO:1`. Il percorso usa nomi GEANT3 e numeri di copia di ogni antenato, non nomi interni o indirizzi di memoria GEANT4. La coppia `(run,event)` identifica l'evento nel singolo output: `run` è l'indice GEANT4 di `/run/beamOn`, **non una run sperimentale**. Un merge deve aggiungere l'identità della campagna/file; tracce e parent sono locali all'evento.

| Rivelatore | Volumi nel modello corrente | Numero legacy | Significato |
| --- | ---: | --- | --- |
| BGO | 480 | copia 1–480 | Cristallo; indici polare/azimutale legacy: `(n-1)//32+1`, `(n-1)%32+1` |
| Barrel DEDX | 32 | copia − 100 → 1–32 | Barra |
| TOF orizzontale / verticale | 26 + 26 | copia 1–26 per piano | Barra; `CES1` e `CEL1` condividono numerazione orizzontale |
| Shower CASC | 16 | copia 1–16 | Modulo del modello omogeneizzato |
| Camere cilindriche | 2 superfici + 4 volumi gas | copia conservata | Superficie/gas, **non filo o strip** |
| Camere planari | 2 + 2 piani | copia 1 o 2 per camera | Piano, **non canale elettronico** |
| Dischi Catania | 2 | copie 2000 e 2003 | Disco non segmentato, **non strip** |

Totale: **592 percorsi sensibili**, 13 famiglie presenti. Il codice legacy 14 identifica BC448 (otto settori nella sorgente), assente nello snapshot corrente. Canali scintillatori duplicati tra percorsi distinti, numeri fuori intervallo o inventari BGO/barrel/TOF/shower incompleti vengono rifiutati. Ripetizioni del numero di copia nei gas sono legittime e distinte dal percorso.

L'assemblaggio dei rivelatori resta quello congelato **GRAAL_26, cilindriche OLD e planari NEW**. Le condizioni per periodo modificano target e campionamento del vertice; non certificano automaticamente la configurazione strumentale completa del 1998 o degli altri periodi.

## Output ROOT completo (`--storage full`, schema hit 2)

Il trasporto batch produce **un solo `transport.root`**, compresso **ZSTD livello 5**. I campi continui restano `double` (64 bit), gli identificativi `int32` e i contatori di step/tentativi `uint64`. Non vengono più prodotti CSV o file di testo per eventi, hit, vertici o metadati di trasporto.

| Oggetto nel ROOT | Contenuto |
| --- | --- |
| TTree `channels` | Inventario completo, anche volumi mai colpiti: percorso, famiglia, ISVOL, nome, copia, numero legacy, tipo di identificativo, mezzo/materiale GEANT3 e materiale effettivo GEANT4 |
| TTree `detector_steps` | Ogni step sensibile, **anche con deposito zero**, senza filtri di carica o processo |
| TTree `primaries` | PDG, pesi del vertice/particella, posizione, tempo, impulso ed energia cinetica effettivamente forniti al trasporto |
| TTree `events` | Ledger con somme, `aborted` e `hit_steps`; include eventi senza hit e abortiti |
| TTree `bgo_hits` | Somme per cristallo e primo tempo di deposito positivo |
| TTree `vertices` | Vertici campionati dalle condizioni per periodo e tentativi XY; vuoto per GPS senza condizioni |
| `summary`, `materials` | Metadati JSON dentro oggetti ROOT `TObjString`, non file JSON separati |
| `input_macro`, `conditions`, `random_state_run_N` | Macro GPS, condizioni e stato completo del generatore casuale incorporati nel ROOT |
| `input_source`, `input_md5` | Origine e controllo di stabilità dell'input nativo; il launcher conserva la provenienza SHA-256 degli input truth |

Il riepilogo dichiara `hit_schema_version=2`, `output_format=ROOT_TTree`, `compression=ZSTD_5`. La versione degli hit è indipendente dallo schema 2 / `pairing_missing_mass` della ricostruzione. `channels` si unisce agli step tramite `path`. I vecchi output CSV restano evidenza storica e non vengono riscritti.

Il file nasce come **`transport.partial.root`**. Solo scrittura/flush/chiusura verificati lo promuovono a `transport.root`. Abort o errori mantengono il nome parziale; con un errore di storage il file parziale può non essere recuperabile. Consumare solo il nome finale. La ripetibilità si confronta sui valori degli alberi, non sui byte del file ROOT, che contiene UUID/timestamp.

`root_output.py` legge piccoli alberi e metadati tramite uproot; per grandi campioni usare lettura a blocchi. ROOT ≥6.30 (Core/RIO/Tree) è ora dipendenza della build C++; CMake usa `ROOT_DIR`, `CMAKE_PREFIX_PATH` oppure `root-config` disponibile sul PATH. Gli input legacy/GDML/HEPEvt e i log di compilazione restano nei propri formati: questa modifica riguarda l'output del trasporto, non una riscrittura degli originali o dell'intero bridge truth.

Ogni step conserva track/parent/PDG, carica, numero di step e peso pre-step; deposito totale e non ionizzante; lunghezza; materiale; tempi globali, energie cinetiche, direzioni e coordinate pre/post. Posizioni in **mm**, tempi in **ns**, energie e componenti dell'impulso in **MeV** (c=1), carica in unità di e. Le coordinate locali di **entrambi** gli estremi usano il riferimento del volume pre-step, anche in uscita. `pre_dir_*`/`post_dir_*` sono versori globali. `pre_status`, `post_status` e `track_status` conservano gli enum GEANT4 della versione registrata; i flag boundary distinguono attraversamenti geometrici. Il processo è quello che limita lo step, non una decomposizione del deposito per processo; è conservato anche il processo creatore della traccia.

Nessuna divisione per lunghezza: depositi a lunghezza zero restano espliciti. Questi input consentono studi di risposta non lineare entro la granularità di step/tagli di produzione scelti; restano necessari studi di convergenza e modelli di quenching. Il primo tempo BGO non equivale al TDC sperimentale.

Eventi abortiti mantengono primarie, step già scritti e ledger parziale; l'eseguibile termina con errore e non scrive un riepilogo di successo. Un arresto del processo o un errore I/O può lasciare file incompleti: solo output conclusi e verificati sono campioni completi. I pesi registrati non includono normalizzazione a flusso, esposizione o sezione d'urto.

## Uso e prova del 9 novembre

`run.py smoke` e `replay` producono automaticamente i nuovi file. Esempio con macro esplicita e destinazione nuova:

```sh
python -B 03_mc_simulation/geant4/run.py smoke \
  --period 1998_uv --seed 20261109 \
  --macro percorso/pilot.mac \
  --work-dir results_test/nuovo-pilot-hit
```

Pilot locale: 10 eventi per combinazione di γ, protoni, π⁺ e π⁻ a energia cinetica 200 MeV con direzioni `(1,0,0)` e `(0.15,0.1,1)`, normalizzate dal GPS. Vertici dal profilo pubblicato `1998_uv`: **80 eventi, zero abortiti, 155.097 step**. Presenti tutte le 13 famiglie, inclusi i dischi. Scarto massimo fra somma BGO degli step e ledger evento: **2,45 × 10⁻¹² MeV**. CSV degli step: **86.464.630 byte**, circa 1,08 MB/evento nel formato storico. Il nuovo ROOT completo occupa circa **22,7 MB**, contro **86,5 MB** del solo CSV degli step e **20,1 MB** del suo gzip. ROOT non è più piccolo del gzip in questo pilot: fornisce accesso diretto, tipi espliciti e lettura per colonne. Tutti i campi delle sei tabelle comuni, inclusi 155.097 step e ogni bit dei double letti dal CSV, coincidono. Non è una stima universale per eventi fisici multibody.

Evidenza della raccolta originale: `results_test/geant4-hits-20261109/`; migrazione ROOT e confronto completo: `results_test/geant4-root-20261109/`, con audit input, log, confronto precedente/nuovo, inventario, validazione quantitativa e pilot conservato. Test coprono attraversamenti a deposito zero, evento senza hit, identificativi, somme/tempi BGO, ripetibilità, metadati invalidi, duplicazioni e aborti reali GEANT4.

## Lavoro fisico ancora aperto

Sei famiglie di calibrazione leggibili per **179/179 run `1998_uv`**. Run1321 e run1324 disponibili come candidati per tuning e verifica della risposta; entrambe hanno già contribuito alle condizioni target/fascio. Purezza, trigger, stabilità e precedenti usi per tuning della risposta restano da qualificare. La separazione per run non garantisce indipendenza dell'intero setup. Il reader legacy mantiene un vecchio campo sulla lunghezza target non collegato alla pubblicazione: per questo pilot fanno fede `period.json`, `conditions.dat` e relativi hash del launcher.

Disponibile il primo confine di [digitizzazione diagnostica BGO/barrel legacy09](geant4-digitization), con mappatura elettronica verificata e confronto numerico con Fortran. Restano digitizzazione degli altri detector, risposta calibrata, ricostruzione, trigger, tagli/BDT, contabilità pesata delle efficienze e validazione sui dati. Profilo XY osservato e media a ugual peso per run non dimostrano rappresentatività rispetto all'esposizione. Vedere [requisiti di validazione](geant4-validation).
