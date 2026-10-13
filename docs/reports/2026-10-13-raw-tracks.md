# Tracce strane: audit tecnico e persistenza

Data: 13 ottobre 2026. Piano 11. Audit e persistenza implementati; definizione
fisica e taglio restano sospesi. L'utente ha confermato di completare audit e
persistenza e bloccare il taglio fino alla definizione. Un eventuale taglio
successivo dovrà essere opzionale, disattivato per default, per un confronto
con la baseline; questa consegna non misura miglioramenti di Σ.

## Stato iniziale e decisioni

Graphify interrogato sul grafo esistente con vocabolario
`preanalysis track selector reconstruction branch output`: proprietari individuati
in `PreAnalysis`, selettore h85 e adattatore ROOT della ricostruzione. Verifica
sui sorgenti correnti: `Nparf_strange` era collegato in `PreAnalysis.h` ma non
attivato dal wrapper; nessuno dei tre candidati era scritto in h80. Il selettore
già copia tutti i branch: nessuna sua modifica necessaria.

- Persistenza autorizzata dall'utente anche prima del dizionario fisico, limitata
  alla copia dei valori raw. Nessuna equivalenza fra contatore, tipo e indice.
- Metadati aggiunti nel proprietario dello schema h80 e nel livello IO della
  ricostruzione. Nessuna modifica al modello BDT o al modello fisico dell'evento.
- Checkout condiviso mantenuto; modifiche preesistenti degli altri agenti
  conservate, nessun commit cumulativo o ripristino. Patch sulla ricostruzione
  confrontata anche con copia del file prima dell'intervento.
- Nessuna nuova opzione CLI che fingerebbe di applicare una definizione ancora
  ignota. Provenienza ricostruzione: `raw_track_metadata.cut =
  "disabled_pending_definition"`.

## Dizionario tecnico verificato

Fonte: schema ROOT locale h70, `PreAnalysis.h`, comportamento di `PreAnalysis.C`.
Queste sono evidenze tecniche, non una definizione fisica ufficiale.

| Campo | Tipo raw / cardinalità | Persistenza h80, h85, reco | Significato accertato |
|---|---|---|---|
| `Nass_3` | `Int_t`, scalare | `Int_t` | Dimensione di `Itipo_track` |
| `Itipo_track` | `Int_t[Nass_3]`, buffer 291 | `vector<int>` | Codici centrali originali; codice usa 11 per neutri, 13/14 nel percorso carico |
| `Nparf_strange` | `UChar_t`, scalare | `UChar_t` | Valore originale; definizione delle «tracce strane» non confermata |
| `Nparf` | `Int_t`, scalare | `Int_t` | Dimensione di `Index_trf` |
| `Index_trf` | `UChar_t[Nparf]`, buffer 90 | `vector<unsigned char>` | Valore indice raw originale, senza conversione in output |
| `N_traf` | `Int_t`, scalare | `Int_t` | Dimensione di `Iass_trf` |
| `Iass_trf` | `UChar_t[N_traf]`, buffer 90 | `vector<unsigned char>` | Codice associazione; codice distingue 1 da altri valori per neutro/carico |
| `RawSourceFile` | aggiunto | `string` | Nome file raw come aperto; conservare cwd per nomi relativi |
| `RawSourceEntry` | aggiunto | `Long64_t` | Entry h70 locale al file, zero-based |

Chiave evento: `(RawSourceFile, RawSourceEntry, RunNumber)`. Chiave di una traccia:
aggiungere nome array e posizione raw zero-based. Posizioni nei vettori di
fotoni/protoni selezionati o nel pairing non sono gli indici raw. Nessun riordino
dei vettori diagnostici; Snapshot può riordinare gli eventi, la chiave resta valida.

Conversione per il lookup storico: indice positivo → `Index_trf - 1`; zero →
primo elemento di `Iass_trf`. Questa seconda regola resta comportamento legacy,
non interpretazione approvata della sentinella. Lookup fuori limite interrompe
la preanalisi con errore; non diventa scarto silenzioso o codice inventato.
Valori sconosciuti vengono conservati quando il processamento è sicuro.

## Inventario e campione

Unico raw nel repository locale: `test_data/raw/1998_uv/run1321.root`, h70,
585.613 eventi, 284.770.796 byte, UUID `340b4e60-d71b-11eb-90db-ec01a8c0beef`.
SHA-256: `38f506a40e498be3082b16b4cec7477e62201f5caf7520ac132ed542e8444b78`.
`N_TIPO_TRACK` assente. Nessun raw VIS locale disponibile.

Ispezione limitata alle prime 10.000 entry:

- `Nparf_strange`: valori 0–5; 2.849 eventi nonzero. Distribuzione:
  0: 7.151, 1: 1.836, 2: 639, 3: 290, 4: 72, 5: 12.
- `Nparf_strange > Nparf` in 1.581 eventi: non assumere che il primo sia un
  sottoinsieme contato dal secondo.
- `Itipo_track`: codici osservati 2–30; `Nass_3` massimo 33.
- `Index_trf`: 1–7; zero sentinelle nulle osservate, zero indici positivi oltre
  `N_traf`. `Iass_trf`: 1–7; `Nparf` massimo 6, `N_traf` massimo 7.
- Zero conteggi fuori capacità o divergenze fra conteggi e lunghezze.

Gli h80 esistenti UV/VIS (90.279.078 / 94.402.268 entry) e gli h85 locali
UV/VIS (5.341.787 / 3.207.538 entry) non contengono il gruppo diagnostico.
Ispezionato solo schema, senza scorrere le campagne. L'assenza resta esplicita;
per ottenere valori serve rigenerazione dai raw, non un riempimento con zeri.

Inventari riproducibili, UUID, tipi, count-leaf, distribuzioni e comandi:
`results/2026-10-13-tracce-strane/audit/{raw,legacy,roundtrip}.json`.
I file legacy grandi hanno identità percorso/dimensione/mtime/UUID, senza hash
completo; raw e prodotti piccoli del round-trip includono SHA-256.

```bash
python3 scripts/audit_raw_tracks.py test_data/raw/1998_uv/run1321.root \
  --entries 10000 --sha256 --output results/nuovo-audit/raw.json
```

Il comando rifiuta di sovrascrivere un JSON esistente. Un altro raw/periodo può
essere aggiunto come argomento, senza inferirne lo schema da UV.

## Verifiche

Comando:

```bash
python3 -m pytest tests/test_raw_track_metadata.py tests/test_event_selector.py \
  tests/test_stage1_contracts.py 05_reconstruction/tests -vv
```

**103 test passati**, log in `results/2026-10-13-tracce-strane/verification.log`.
Anche i 79 test `tests/test_wiki.py tests/test_wiki_sync.py` passano; `git diff --check`
non segnala problemi.
Test nuovi verificati prima in fallimento, poi in successo. Copertura:

- h70→h80 con confronto dei valori originali, h85→reco e BDT a buffer multipli;
- cambio file nel TChain e reset corretto dell'entry locale;
- zero, limiti inclusivi 291/90, overflow, indici 1-based e sentinelle;
- codici non standard e byte 255 preservati, array vuoti, lunghezze discordanti;
- legacy senza valori fittizi; gruppi parziali, misti e tipi errati rifiutati
  prima di creare output.

Round-trip persistente:

```bash
python3 -m pytest tests/test_raw_track_metadata.py -k raw_h70 -vv -s \
  --basetemp results/2026-10-13-tracce-strane/roundtrip
```

**Per ripetere usare una nuova directory `--basetemp`: pytest cancella quella
indicata.** Artefatti correnti da conservare in `roundtrip/test_raw_h70_round_trip0/`.
Due copie delle prime 512 entry originali verificano il cambio file, non sono
campioni fisici indipendenti: 1.024 entry h80, 66 h85, 8 reco. Ricostruzione solo
diagnostica con χ² < 1000, missing-mass disattivata e nessun 6C/BDT; questi numeri
non rappresentano resa o miglioramento fisico. Log: `roundtrip.log`.

Review indipendente: trovato controllo insufficiente dei tipi downstream,
che poteva troncare float in interi. Corretto con validazione leaf/type/shape,
tipi vettore/string e test di regressione fallito→passato. Nessun altro rilievo
sostanziale segnalato. Revisione Git osservata alla verifica:
`f568c6b5fdeef1d12fc241aecb2cea810e6bb574`, checkout con modifiche concorrenti.

## File e limiti residui

- `01_pre_analysis/PreAnalysis.C`, `RawTrackContract.h`: attivazione, controlli,
  persistenza raw e identità sorgente.
- `00_common/io/raw_tracks.py`, `05_reconstruction/runtime/reco_core.py`:
  contratto downstream, snapshot indipendenti per il buffering, output e provenienza.
- `scripts/audit_raw_tracks.py`, `tests/test_raw_track_metadata.py`: audit e prove.
- Wiki preanalisi, piano 11 e questa relazione: dizionario tecnico e stato.

Restano definizione fisica, sentinelle ufficiali, validazione raw di altri periodi
e rigenerazione delle campagne. Nessun confronto finale con taglio eseguito.
Domanda pronta per Giuseppe, non inviata:

> Con «tracce strane» intendi `Nparf_strange`, codici di `Itipo_track` o
> classificazione `Index_trf/Iass_trf`? Quale nome raw h70, codici, indice,
> sentinelle e periodi? Esiste `N_TIPO_TRACK` in altro schema? Puoi indicare
> run/evento esempio?
