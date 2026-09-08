# Current Status

**Aggiornato:** 9 settembre 2026
**Stato sintetico:** QA della produzione farm ricevuta e database run per
osservabili curato; la normalizzazione fisica finale resta fuori ambito.
**Snapshot del codice precedente a questa pagina:** `1ed73e1`

## Dove stiamo andando

Obiettivo finale: estrarre osservabili fisici pubblicabili per il canale
fotoproduzione

```text
γ p → p η π⁰
```

Il lavoro completato finora non costituisce ancora estrazione finale di
sezioni d'urto o asimmetrie. Abbiamo costruito e verificato infrastruttura
necessaria per associare ogni evento a run, stato di polarizzazione, strip del
tagger ed energia del fotone, quindi normalizzare conteggi selezionati usando
flussi coerenti con bin energetici della pubblicazione.

In altre parole: gli artefatti della farm sono stati ricevuti e una policy
fail-closed ha pubblicato il sottoinsieme usabile per osservabili; mancano
ancora le correzioni e gli ingredienti fisici della normalizzazione finale.

## Metadati portati lungo tutta la catena

Pre-analisi e ricostruzione ora conservano:

- `RunNumber`, necessario per collegare evento a periodo sperimentale e flusso;
- `Polarization`, necessario per separare stati del fascio;
- `Xstrip`, strip del tagger compresa tra 1 e 128.

`Xstrip` era ramo mancante nella pre-analisi. Ora viene letto dai dati grezzi,
scritto nell'albero inclusivo `h80` e propagato fino agli output di
ricostruzione insieme a `RunNumber` e `Polarization`. Questo evita di dover
ricostruire informazione da nomi file nelle fasi finali.

## Manifest delle run

È stato aggiunto un processo riproducibile per costruire e validare inventario
delle run. Prima viene generato un manifest dai nomi di directory e file;
successivamente classificazione viene curata usando tabella sperimentale dei
periodi.

Manifest autorevole corrente:

```text
config/run_manifest.csv
```

Contiene 2711 run, divise senza mescolare target o tipo di laser:

| Gruppo | Target | Laser | Run |
|---|---|---:|---:|
| `P_UV` | protone | UV | 1426 |
| `P_VIS` | protone | VIS | 405 |
| `D_UV` | deuterio | UV | 538 |
| `D_VIS` | deuterio | VIS | 342 |

Il file `data/run_manifest.generated.csv` resta inventario di supporto. Non è
autorità per classificazione fisica. Periodo, target e fascio del manifest
curato possono essere corretti manualmente quando arrivano informazioni
migliori.

Separazione UV/VIS viene mantenuta perché picco di polarizzazione atteso cade
in regioni energetiche diverse: circa 1.5 GeV per UV e circa 1.1 GeV per VIS.
Separazione protone/deuterio viene mantenuta per evitare aggregazioni fisiche
incompatibili.

## Flussi disponibili

Input locale:

```text
data/flux/flux.root
```

Per ogni run contiene istogrammi con strip 1…128 su asse X e conteggi su asse
Y:

- `run<N>_POL1`;
- `run<N>_POL2`;
- `run<N>_BREM`.

`BREM` viene trattato come fondo. Assunzione provvisoria approvata per questa
fase: conteggi medi sono considerati corretti sia per flussi sia per futura
normalizzazione delle sezioni d'urto. Nessuna correzione aggiuntiva di live
time, dead time o tagging efficiency viene applicata ora.

Convenzione numerica corrente:

```text
pol1_net = POL1 - BREM
pol2_net = POL2 - BREM
total_net = POL1 + POL2 - 2 × BREM
```

Questa convenzione è esplicitamente provvisoria. Quando arriveranno
normalizzazioni più precise, dovranno cambiare formule, test, QA e
documentazione insieme.

## Scelta strip→Eγ

Manca calibrazione parametrica strip→energia per periodo/run. Abbiamo scelto
di non inventarla e di non usare una conversione globale.

Per ogni coppia `(RunNumber, Xstrip)`, energia viene ricavata direttamente
dagli alberi inclusivi `h80`:

```text
Eγ(run, strip) = mediana di beam.E() per eventi di quella run e strip
```

Vengono salvati anche numero eventi, MAD, minimo e massimo. Calcolo è esatto:
nessun campionamento, pooling tra run, interpolazione, extrapolazione o
fallback per strip vuote. Eventi vengono temporaneamente spooled in SQLite,
così memoria resta limitata mentre statistica rimane esatta.

Ogni strip viene assegnata interamente al bin di `Eγ` contenente energia
mediana. Flusso dell'istogramma corrispondente viene quindi sommato nel bin.
Questa strategia realizza idea iniziale: binning degli eventi in energia,
lettura delle `Xstrip` corrispondenti e integrazione diretta dei flussi sulle
stesse strip, senza introdurre calibrazione separata.

## Binning e aggregazione

Due schemi Ajaka vengono prodotti di default:

- `ajaka_cross_section`: 15 bin uniformi tra 0.95 e 1.50 GeV;
- `ajaka_sigma`: bordi 1.10, 1.20, 1.30, 1.40 e 1.50 GeV.

Si possono aggiungere schemi custom da CLI. Dopo integrazione per singola run,
flussi vengono aggregati soltanto tra periodi con stesso target e stesso tipo
di fascio: `P_UV`, `P_VIS`, `D_UV`, `D_VIS`.

## Artefatti prodotti

Comando farm produce directory portabile con quattro file:

- `strip_energy_lookup.csv`: lookup e diagnostica per `(run, strip)`;
- `flux_by_run_energy.csv`: flussi integrati per run e bin energetico;
- `flux_by_group_energy.csv`: somme per gruppo fisico e bin energetico;
- `strip_energy_flux_qa.json`: inventario input, warning, errori, soglie e
  controlli di conservazione.

Pubblicazione directory è atomica. Un rerun fallito non distrugge output buono
precedente; QA del fallimento viene scritto in directory sibling separata.

Controlli implementati includono:

- triplette ROOT richieste esattamente `POL1/POL2/BREM`;
- 128 bin e asse strip valido;
- valori finiti;
- run mancanti o inattese;
- strip senza lookup;
- direzione strip→energia e inversioni;
- statistica bassa o MAD elevata;
- flussi netti negativi;
- underflow/overflow;
- conservazione dei conteggi per run e per gruppo.

Run di flusso extra non richieste producono warning, non invalidano subset
autorevole del manifest. Errori strutturali delle run richieste restano
fatali.

## Database run per osservabili: accettazione produzione

Il bundle trasferito `results/strip_energy_flux/` è stato curato senza
rieseguire ROOT né leggere `h80`:

```bash
python scripts/build_observable_run_database.py \
  --manifest config/run_manifest.csv \
  --strip-energy-dir results/strip_energy_flux \
  --output-dir results/observable_runs
```

La pubblicazione atomica contiene sei output: `run_quality.csv`, il manifest
good-only `run_manifest_observables.csv`, lookup e flusso per run filtrati,
flusso per gruppo rigenerato e `observable_run_qa.json`. Quest'ultimo registra
schema/policy v1, percorsi, hash degli input e hash di tutti i CSV prodotti.
L'accettazione ha terminato con exit 0 e QA `valid: true`: su 2711 run,
`good=2372`, `review=152`, `bad=187`; le good sono `P_UV=1256`, `P_VIS=323`,
`D_UV=531`, `D_VIS=262`.

La classificazione usa precedenza `bad > review > good`. In particolare, una
somma BREM `ajaka_cross_section` con rapporto alla mediana del periodo
maggiore o uguale a `100.0` è bad; una baseline con meno di cinque run o
mediana non positiva è review. Le ragioni e i parametri effettivi sono
archiviati riga per riga in `run_quality.csv` e nel QA.

Il manifest completo continua a servire studi di cut e cinematica. Per una
normalizzazione è obbligatorio usare soltanto
`run_manifest_observables.csv` e i CSV della medesima pubblicazione valida;
le run review/bad non entrano negli osservabili, ma restano tracciabili nel
manifest completo e in `run_quality.csv`.

## Verifiche locali completate

Ultimo controllo prima del push:

```text
353 passed
```

Inoltre:

- compilazione moduli Python completata senza errori;
- manifest validato: 2711 run;
- CLI principale e generatore benchmark verificati;
- benchmark sintetico da 200 mila e 1 milione di eventi conferma memoria
  sostanzialmente indipendente dal numero totale di eventi;
- branch `main` sincronizzato con `origin/main` al commit `1ed73e1` prima
  dell'aggiunta di questa pagina.

## Cosa manca

La curation della produzione è completata. Restano attività dipendenti da
informazioni sperimentali non ancora disponibili:

1. esaminare le run review/bad e confermare fisicamente la policy BREM;
2. verificare convenzione fisica esatta di `POL1` e `POL2` prima di estrarre
   `Σ`;
3. sostituire assunzioni provvisorie sui conteggi quando arriveranno dead time,
   live time, tagging efficiency o scala corretta di `BREM`;
4. collegare flussi validati ai yield selezionati, efficienze MC e branching
   ratio per estrarre sezioni d'urto e osservabili finali.

Quindi risposta breve a «siamo arrivati agli osservabili?» è: no. Abbiamo
completato infrastruttura di metadati e normalizzazione necessaria per
arrivarci senza mescolare periodi incompatibili o inventare calibrazioni.

## Prossimo comando sulla farm

```bash
git pull origin main

python scripts/build_run_manifest.py \
  --validate config/run_manifest.csv

python scripts/build_strip_energy_flux.py \
  --preanalysis-dir data/pre_analyzed \
  --manifest config/run_manifest.csv \
  --flux data/flux/flux.root \
  --output-dir results/strip_energy_flux

python scripts/build_observable_run_database.py \
  --manifest config/run_manifest.csv \
  --strip-energy-dir results/strip_energy_flux \
  --output-dir results/observable_runs
```

Per exit 0 o analisi completata con exit 1, riportare tutta
`results/strip_energy_flux/`. Se stderr stampa `Failure QA:`, riportare anche
directory sibling indicata.

## Dove approfondire

- [Pipeline](pipeline): ordine operativo e comando farm;
- [Formati dati](data-formats): colonne, unità e schema QA;
- [Manutenzione strip-energy flux](strip-energy-flux-maintenance): assunzioni,
  policy di errore e punti esatti da cambiare;
- [Design strip-energy flux](strip-energy-flux-design): contratto scientifico;
- [Implementation plan](strip-energy-flux-implementation-plan): storia tecnica
  e verifiche dell'implementazione.
