# Design: lookup strip→Eγ e integrazione dei flussi

**Data:** 2026-07-30
**Stato:** design approvato; implementazione non ancora iniziata

## Obiettivo

Costruire il blocco di normalizzazione energetica per l'estrazione degli
osservabili fisici del canale `γN → Nηπ0`.

Il blocco deve:

1. ricavare direttamente dai dati pre-analizzati la corrispondenza tra strip
   del tagger ed energia del fotone;
2. integrare gli istogrammi `POL1`, `POL2` e `BREM` di `data/flux/flux.root`
   nei bin di `Eγ`;
3. conservare il dettaglio per run;
4. produrre somme finali separate per `P_UV`, `P_VIS`, `D_UV` e `D_VIS`.

Non viene introdotta una calibrazione parametrica strip→energia. La relazione
è misurata come lookup dai dati.

## Input autorevoli

### Manifest run

`config/run_manifest.csv` è la sorgente autorevole per:

- numero di run;
- periodo;
- target `P` o `D`;
- fascio `UV` o `VIS`;
- gruppo finale.

Il manifest deve superare `scripts/build_run_manifest.py --validate` prima di
ogni estrazione.

### Dati pre-analizzati

Il lookup usa gli alberi inclusivi `h80`, prima della selezione `h85` e prima
del BDT. Servono soltanto:

- `RunNumber`;
- `Xstrip`;
- `beam`, da cui si legge `beam.E()` in GeV.

Usare `h80` evita che selezione del segnale o ricostruzione cinematica
determinino la mappa del tagger. Ogni file può contenere una o più run: il
raggruppamento usa sempre `RunNumber`, non il nome del file.

### Flussi

`data/flux/flux.root` contiene, per ogni run:

- `run<N>_POL1`;
- `run<N>_POL2`;
- `run<N>_BREM`.

Ogni oggetto deve essere un istogramma monodimensionale con 128 bin fisici,
uno per strip da 1 a 128. Underflow e overflow non entrano nelle somme e
devono essere riportati se non nulli.

Per decisione provvisoria di analisi, i contenuti sono considerati già
corretti e direttamente confrontabili tra stati. `BREM` viene sottratto
separatamente da ciascuna polarizzazione:

```text
F1_net = POL1 - BREM
F2_net = POL2 - BREM
Ftot_net = F1_net + F2_net
```

Vengono comunque conservate anche le tre somme originali. In questo modo la
convenzione può essere cambiata senza rileggere i file ROOT.

## Binning energetico

I bordi sono configurabili e identificati da un nome. P0 fornisce due preset
legacy:

### Sezione d'urto Ajaka

Quindici bin uniformi tra 0.95 e 1.50 GeV, come descritto in Ajaka et al.,
Phys. Rev. Lett. 100, 052003 (2008):

```text
edges = linspace(0.95, 1.50, 16)
```

### Asimmetria di fascio Ajaka

Quattro intervalli larghi:

```text
[1.10, 1.20, 1.30, 1.40, 1.50] GeV
```

La semantica è `[low, high)`; soltanto l'ultimo bin include il bordo destro.
Valori fuori intervallo vengono contati nel report, mai inseriti implicitamente
nel primo o ultimo bin.

## Costruzione del lookup

Per ogni coppia `(run, strip)` osservata in `h80`:

```text
E_lookup(run, strip) = median(beam.E())
```

Vengono inoltre calcolati:

- numero di eventi;
- minimo e massimo;
- MAD, `median(abs(E - median(E)))`;
- provenienza `observed`.

`Xstrip` deve essere finito, compreso tra 1 e 128 e compatibile con un intero.
Il valore viene convertito a intero soltanto dopo questo controllo.
`beam.E()` deve essere finito e positivo.

Nessun pooling tra run o periodi. Nessun riempimento silenzioso delle strip
vuote. Se una strip ha flusso non nullo ma manca dal lookup della run, output
resta disponibile per diagnosi ma integrazione della run è incompleta e CLI
termina con errore.

Questa scelta protegge da cambi di configurazione del tagger tra run. Un
fallback per periodo potrà essere aggiunto soltanto dopo aver visto il report
della farm e quantificato le strip mancanti.

## Controlli sul lookup

Per ogni run:

1. almeno una entry `h80`;
2. nessuna strip fuori dominio;
3. energia mediana finita e positiva;
4. ordinamento energetico coerente lungo le strip;
5. dispersione per strip riportata;
6. lista delle strip non osservate;
7. lista delle strip non osservate con flusso non nullo.

Direzione monotona viene inferita dalla correlazione tra strip ed energia,
perché il controllo non deve assumere a priori strip crescente o decrescente.
Inversioni locali vengono riportate con ampiezza in GeV.

Soglie numeriche di warning (`min_events`, MAD massima, tolleranza monotonia)
sono opzioni CLI e compaiono nei metadati dell'output. Non rendono una run
valida per decreto: errori strutturali e flusso non mappato restano fatali.

## Integrazione del flusso

Per ogni run, strip e schema di binning:

1. leggere `E_lookup(run, strip)`;
2. determinare unico bin energetico;
3. aggiungere intero contenuto della strip a `POL1`, `POL2` e `BREM`;
4. calcolare `F1_net`, `F2_net`, `Ftot_net`.

Niente assegnazione frazionaria delle strip sui bordi. Questa è coerente con
la strategia lookup. Sensibilità ai bordi verrà trattata successivamente come
sistematica, spostando i bordi rispetto alla risoluzione del tagger.

Flussi netti negativi vengono conservati per diagnosi ma marcano bin/run come
non valido per estrazione fisica.

## Aggregazione

Prima uscita mantiene granularità per run. Seconda uscita somma, per ciascun
bin, tutte le run con stesso:

- target;
- tipo di fascio;
- gruppo manifest;
- schema di binning.

UV e VIS non vengono mai sommati tra loro. Protone e deuterio non vengono mai
sommati tra loro.

Le somme di gruppo sono:

```text
F_group(bin, state) = Σ_run F_run(bin, state)
```

Non vengono usati conteggi medi. Questo vale anche per futura normalizzazione
delle sezioni d'urto, secondo assunzione corrente.

## Output

Output tabellari CSV, portabili dalla farm:

### `strip_energy_lookup.csv`

Una riga per `(run, strip)` osservata:

```text
run_number,source_period,target,beam_type,group,xstrip,event_count,
energy_median_gev,energy_mad_gev,energy_min_gev,energy_max_gev,provenance
```

### `flux_by_run_energy.csv`

Una riga per `(schema, run, bin)`:

```text
binning,run_number,source_period,target,beam_type,group,
energy_low_gev,energy_high_gev,pol1,brem,pol2,
pol1_net,pol2_net,total_net,status
```

Ordine colonne delle quantità di flusso mantiene visibili i tre istogrammi
originali; calcoli usano nomi, non posizione.

### `flux_by_group_energy.csv`

Una riga per `(schema, group, bin)`, con stesse quantità di flusso sommate.

### `strip_energy_flux_qa.json`

Contiene:

- versione schema;
- file e opzioni usate;
- preset energetici;
- numero run manifest, h80 e flusso;
- run mancanti o extra;
- strip vuote;
- inversioni monotone;
- dispersioni oltre soglia;
- underflow/overflow;
- flussi netti negativi;
- stato finale `valid` o `invalid`.

Scrittura atomica: file temporanei, poi sostituzione soltanto a elaborazione
completata. Output deterministico, ordinato numericamente per run, strip e bin.

## Interfaccia prevista

Nuovo comando:

```bash
python scripts/build_strip_energy_flux.py \
  --preanalysis-dir /farm/path/pre_analyzed \
  --manifest config/run_manifest.csv \
  --flux data/flux/flux.root \
  --output-dir results/strip_energy_flux
```

Preset predefiniti `ajaka_cross_section` e `ajaka_sigma` vengono prodotti
insieme. Eventuali bordi personalizzati richiedono nome e lista esplicita.

## Errori fatali

CLI termina non-zero per:

- manifest non valido;
- run manifest priva della tripla di istogrammi;
- tipo/dimensione/numero bin del flusso errato;
- run `h80` non presente nel manifest;
- mismatch `RunNumber`;
- branch obbligatorio assente;
- strip o energia non valida;
- strip con flusso non nullo e lookup assente;
- flusso netto negativo;
- collisione o output parziale non atomico.

Run presenti nel manifest ma senza file `h80` sono fatali per estrazione
completa, ma elencate nel QA prima dell'uscita.

## Organizzazione codice

Logica pura e testabile in nuovo modulo `00_common/strip_energy_flux.py`:

- validazione binning;
- statistiche lookup;
- assegnazione strip→bin;
- somme per run;
- somme per gruppo;
- modelli record e serializzazione.

I/O ROOT e CLI in `scripts/build_strip_energy_flux.py`. Il modulo comune non
deve dipendere da PyROOT; CLI adatta alberi e istogrammi ROOT ai record puri.

## Test

### Unit test

- mediana e MAD;
- conversione e rifiuto di `Xstrip`;
- binning sui bordi;
- direzione monotona crescente e decrescente;
- strip vuote con flusso nullo/non nullo;
- sottrazione `BREM`;
- flusso netto negativo;
- somma per gruppo senza mescolare P/D o UV/VIS;
- ordinamento deterministico.

### Integration test ROOT

Mini-file reali creati nel test:

- due run;
- piccolo `h80` con `RunNumber`, `Xstrip`, `beam`;
- `flux.root` con triplette `POL1/POL2/BREM`;
- manifest coerente.

Il test esegue CLI e verifica lookup, somme per run, somme per gruppo, QA e
codice di uscita.

### Verifica farm

Prima esecuzione serve anche come misura di fattibilità. Report da controllare:

- copertura delle 128 strip per run;
- distribuzione MAD;
- inversioni;
- numero run complete;
- copertura energetica UV e VIS;
- conteggi per gruppo e bin.

Se molte run hanno strip con flusso non nullo ma nessun evento h80, design
torna in revisione prima di introdurre interpolazione o fallback per periodo.

## Fuori scope

- accettanza MC;
- efficienza di selezione/ricostruzione;
- luminosità target;
- branching ratio;
- estrazione finale di σ;
- fit `cos(2φ)` per Σ;
- polarizzazione Compton `P(Eγ)`;
- sistematiche sui bordi;
- calibrazione parametrica strip→energia;
- pooling/fallback tra run.

Questo blocco produce normalizzazione energetica verificabile. Osservabili
fisici verranno costruiti sopra questi output.
