# Current Status

**Aggiornato:** 1 settembre 2026
**Stato sintetico:** infrastruttura strip→energia e integrazione flussi pronta;
validazione sui dati completi della farm ancora da eseguire.
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

In altre parole: catena software locale pronta; prossimo passaggio reale è
produrre artefatti sulla farm e controllarne QA prima di usarli nella fisica.

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

Parte locale implementabile è completata. Restano attività dipendenti dai dati
completi o da informazioni sperimentali non ancora disponibili:

1. eseguire pre-analisi completa sulla farm con ramo `Xstrip` aggiornato;
2. eseguire estrazione strip-energy flux su tutti file `h80`;
3. riportare intera directory `results/strip_energy_flux/`;
4. leggere `strip_energy_flux_qa.json` e risolvere eventuali errori o warning;
5. verificare convenzione fisica esatta di `POL1` e `POL2` prima di estrarre
   `Σ`;
6. sostituire assunzioni provvisorie sui conteggi quando arriveranno dead time,
   live time, tagging efficiency o scala corretta di `BREM`;
7. collegare flussi validati ai yield selezionati, efficienze MC e branching
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
