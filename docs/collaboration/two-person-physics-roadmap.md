# Roadmap fisica a due persone

## Scopo e confine

Questa roadmap rende eseguibile il passaggio dall'attuale bundle di run per
osservabili al benchmark P0 sul canale protone `γ p → p η π⁰`. Non implementa
ancora una sezione d'urto o `Σ`, non autorizza l'uso di `results/reco/` legacy
per la normalizzazione e non inventa input sperimentali mancanti.

Esistono esattamente due ownership primarie. Le directory e gli artefatti
elencati per una persona non possono essere modificati dall'altra senza una
revisione congiunta del cambiamento di interfaccia. I file upstream condivisi
(manifest, bundle osservabili, registro canali, schema reco e bin comuni) non
hanno un terzo proprietario: richiedono entrambi i revisori.

## Gate 0 — bundle osservabili congelato

**Input.** La stessa pubblicazione valida di `results/observable_runs/`:
`run_manifest_observables.csv`, `run_quality.csv`, lookup e flussi filtrati,
`flux_by_group_energy.csv` e `observable_run_qa.json`; il manifest autorevole
`config/run_manifest.csv`; inventario `ARTIFACTS.json`.

**Output.** Un `results/observable_runs/HANDOFF.json` versionato che contiene
`schema_version`, `producer_commit`, `manifest_path`, `manifest_sha256`, i
percorsi e SHA-256 dei sei file del bundle, `observable_run_qa_path`,
`observable_run_qa_sha256`, `observable_run_qa_valid`, binning dichiarato e
timestamp UTC. Non sostituisce il QA sorgente.

**Validation — interface to implement.**

```text
python 00_common/validate_observable_handoff.py \
  --handoff results/observable_runs/HANDOFF.json \
  --require-qa-valid
```

**Rejection.** Rifiutare se manca un file, un hash non coincide,
`observable_run_qa.valid` non è `true`, il manifest non è quello curato, o il
manifest/lookup/flussi filtrati contengono run `review`/`bad`.
`run_quality.csv` conserva invece tutte le run, comprese quelle escluse,
per tracciabilità diagnostica. Nessun lavoro fisico procede su un mix di
pubblicazioni.

## Primary ownership: Person 1 — normalizzazione e sezioni d'urto

La [guida operativa della Persona 1](../physics/normalization.md) distingue
comandi disponibili, decisioni da congelare e sequenza N1–N7. Le 2.372 run
good del bundle comprendono tutti i gruppi: il sottoinsieme protone per P0
conta 1.579 run (`P_UV=1256`, `P_VIS=323`).

**Area esclusiva.**

```text
07_physics_normalization/
07_physics_normalization/tests/
config/physics/normalization_v1.json
results/physics/normalization/
docs/physics/normalization.md
```

### N1 — congelare Gate 0 e schema di accettanza

- **Input:** `HANDOFF.json` valido, definizione canale `pηπ0`, bordi Ajaka e
  configurazione `normalization_v1.json` proposta.
- **Output:** schema CSV v1 con chiavi `analysis_version`, `channel`,
  `target`, `beam_group`, `Egamma_low`, `Egamma_high`, `cos_theta_low`,
  `cos_theta_high`, `observable`, `selection_id`; denominatori
  `n_generated`, `n_thrown_in_bin`, `n_reconstructed_selected`; campi
  `acceptance`, `acceptance_stat_uncertainty`, `validity_mask` e hash degli
  input/configurazione.
- **Validation — interface to implement:**

  ```text
  python 07_physics_normalization/validate_acceptance_schema.py \
    --handoff results/observable_runs/HANDOFF.json \
    --config config/physics/normalization_v1.json
  ```

- **Rejection:** rifiutare chiavi non univoche, denominatori negativi,
  selezioni senza identificatore, bin incompatibili con il handoff, o una
  configurazione senza hash.

### N2 — rigenerare ricostruzione con metadati

- **Input:** MC e dati LH2, modello BDT fissato, configurazione di ricostruzione
  e il bundle Gate 0.
- **Output:** ricostruzione nuova con `RunNumber`, `Polarization` e `Xstrip`
  propagati; inventario di provenienza e controllo che la selezione usa solo
  le run good del handoff.
- **Validation — interface to implement:**

  ```text
  python 07_physics_normalization/validate_metadata_reco.py \
    --handoff results/observable_runs/HANDOFF.json --require-run-metadata
  ```

- **Rejection:** rifiutare un output che eredita `results/reco/` legacy, perde
  uno dei tre campi, o include una run non-good nella misura normalizzata.

### N3 — efficienza MC e accettanza

- **Input:** eventi generati con pesi dichiarati, output ricostruito N2,
  selezione identica ai dati e schema N1.
- **Output:** conteggi generated/thrown/reconstructed per chiave, efficienza
  e incertezza statistica; maschera per bin a denominatore nullo o qualità
  insufficiente.
- **Validation — interface to implement:**

  ```text
  python 07_physics_normalization/build_acceptance.py \
    --config config/physics/normalization_v1.json --check-closure
  ```

- **Rejection:** rifiutare accettanza fuori `[0,1]`, conteggi incoerenti,
  bin non mascherati con zero generatori, o closure MC fallita.

### N4 — yield good-only

- **Input:** dati ricostruiti N2, `run_manifest_observables.csv`, qualità fit e
  schema di bin N1.
- **Output:** yield selezionati per chiave, run-list e hash del manifest;
  separazione esplicita di segnale, fondo e incertezza statistica.
- **Validation — interface to implement:**

  ```text
  python 07_physics_normalization/extract_yields.py \
    --handoff results/observable_runs/HANDOFF.json --good-runs-only
  ```

- **Rejection:** rifiutare una yield senza run-list o hash, una run review/bad,
  o un fit/sideband QA non valido.

### N5 — fattori di normalizzazione

- **Input:** yield N4, accettanza N3, flusso good-only, numero bersagli,
  branching ratio e relative incertezze documentate.
- **Output:** luminosità/fattori v1 per bin con unità, fonti, correlazioni e
  hash; nessun valore implicito di dead time, live time o tagging efficiency.
- **Validation — interface to implement:**

  ```text
  python 07_physics_normalization/validate_normalization_inputs.py \
    --config config/physics/normalization_v1.json --require-sources
  ```

- **Rejection:** rifiutare unità o sorgenti assenti, fattori non finiti, input
  sperimentali sostituiti da assunzioni non approvate, o flussi da un bundle
  diverso.

### N6 — sezioni d'urto e closure Ajaka

- **Input:** yield N4, accettanza N3, fattori N5 e bin `ajaka_cross_section`.
- **Output:** sezioni d'urto totali/differenziali, confronti pubblicabili con
  Ajaka e tabella di residuali/compatibilità.
- **Validation — interface to implement:**

  ```text
  python 07_physics_normalization/compare_ajaka.py \
    --results results/physics/normalization --observable cross_section
  ```

- **Rejection:** rifiutare bin fuori definizione, normalizzazione non
  riproducibile, o closure oltre le soglie pre-registrate senza una spiegazione
  sistematica approvata.

### N7 — propagazione incertezze e provenienza

- **Input:** output N3–N6, correlazioni dei fattori N5, commit e hash di ogni
  input.
- **Output:** componenti statistiche/sistematiche e matrice di covarianza;
  release di accettanza con QA e inventario.
- **Validation — interface to implement:**

  ```text
  python 07_physics_normalization/validate_normalization_release.py \
    --results results/physics/normalization --check-provenance
  ```

- **Rejection:** rifiutare incertezze senza sorgente, covarianza non
  simmetrica/semidefinita positiva entro tolleranza, o artefatti privi di hash.

## Primary ownership: Person 2 — polarizzazione e asimmetria del fascio

**Area esclusiva.**

```text
08_polarization/
08_polarization/tests/
config/physics/polarization_v1.json
results/physics/polarization/
docs/physics/polarization.md
```

### S1 — mappa autorevole degli stati di polarizzazione

- **Input:** descrizione sperimentale firmata per `Polarization`, istogrammi
  `POL1/POL2/BREM`, manifest curato e Gate 0.
- **Output:** mappa versione v1 stato→orientazione (`parallel`/`perpendicular`)
  per run/periodo, convenzione di segno, lacune e hash della fonte.
- **Validation — interface to implement:**

  ```text
  python 08_polarization/validate_state_mapping.py \
    --config config/physics/polarization_v1.json --handoff results/observable_runs/HANDOFF.json
  ```

- **Rejection:** rifiutare una mappa dedotta da nomi file, stati ambigui,
  copertura parziale non mascherata o fonte priva di approvazione sperimentale.

### S2 — ingresso Compton `P(Egamma)`

- **Input:** curva/parametri Compton autorevoli per periodo, incertezza e
  binning energia Gate 0.
- **Output:** `P(Egamma)` e covarianza/interpolazione dichiarata per bin, con
  unità, range valido e hash della sorgente.
- **Validation — interface to implement:**

  ```text
  python 08_polarization/validate_compton_polarization.py \
    --config config/physics/polarization_v1.json
  ```

- **Rejection:** rifiutare estrapolazione oltre la sorgente, valori non fisici,
  incertezze mancanti o combinazione di periodi incompatibili.

### S3 — definizione periodica di `phi`

- **Input:** quattro-vettori ricostruiti, assi di reazione/decadimento,
  convenzione S1 e casi sintetici con angoli noti.
- **Output:** definizione `phi` periodica su `[0, π)`, implementazione testata,
  gestione di piani degeneri e documentazione del verso degli assi.
- **Validation — interface to implement:**

  ```text
  python 08_polarization/test_phi_periodicity.py \
    --config config/physics/polarization_v1.json
  ```

- **Rejection:** rifiutare discontinuità a `0/π`, piani degeneri non marcati o
  casi sintetici che cambiano segno sotto una trasformazione equivalente.

### S4 — fit `cos(2phi)` consapevole dell'accettanza

- **Input:** `phi` S3, stati S1, `P(Egamma)` S2, accettanza v1 di Person 1 e
  yield per bin.
- **Output:** modello di likelihood/fit con pesi o risposta di accettanza,
  parametri `Σ`, diagnostica per bin e specifica delle correlazioni.
- **Validation — interface to implement:**

  ```text
  python 08_polarization/fit_sigma.py \
    --acceptance results/physics/normalization/acceptance_v1.csv \
    --config config/physics/polarization_v1.json
  ```

- **Rejection:** rifiutare fit senza accettanza valida, bin con copertura
  angolare insufficiente, mancata convergenza o QA dei residui fallito.

### S5 — closure a asimmetria iniettata e convenzione di segno

- **Input:** campioni MC/sintetici con `Σ` iniettata, catena S3–S4 e mappa S1.
- **Output:** recupero della `Σ` iniettata, bias e pull, test di inversione
  parallel/perpendicular e registrazione della convenzione finale.
- **Validation — interface to implement:**

  ```text
  python 08_polarization/closure_injected_sigma.py \
    --config config/physics/polarization_v1.json --require-sign-check
  ```

- **Rejection:** rifiutare bias o pull fuori soglia predefinita, segno non
  invertito nel test controllato, o una closure che omette l'accettanza.

### S6 — release `Σ`, covarianza e sistematiche

- **Input:** fit validi S4–S5, `P(Egamma)` S2, accettanza handoff e variazioni
  sistematiche registrate.
- **Output:** tabella `Σ`, covarianza NPZ, QA fit, componenti sistematiche e
  hash di config/input per ogni bin.
- **Validation — interface to implement:**

  ```text
  python 08_polarization/validate_sigma_release.py \
    --results results/physics/polarization --check-covariance --check-qa
  ```

- **Rejection:** rifiutare una covarianza di dimensione/ordine non dichiarato,
  QA non valido, sorgenti sistematiche non tracciate o hash mancanti.

### S7 — binning P1/P2

- **Input:** release S6, binning P0 congelato, definizioni P1 di massa `Mpη`
  e P2 in `Egamma`, `cosθ` e coppie invarianti.
- **Output:** mapping dai bin elementari ai deliverable P1/P2, maschere di
  copertura e controllo di compatibilità con P0.
- **Validation — interface to implement:**

  ```text
  python 08_polarization/validate_publication_binning.py \
    --results results/physics/polarization --papers P1 P2
  ```

- **Rejection:** rifiutare bin non riconducibili al fit, aggregazioni che
  perdono covarianza, o risultati P1/P2 rilasciati prima del gate P0.

## Handoff condivisi e release P0

### Handoff Person 1 → Person 2

I due filename sono l'interfaccia condivisa v1; devono essere pubblicati
insieme, con gli hash nel rispettivo QA e in `ARTIFACTS.json`:

```text
results/physics/normalization/acceptance_v1.csv
results/physics/normalization/acceptance_qa.json
```

`acceptance_v1.csv` usa le chiavi e i denominatori N1, più accettanza,
incertezza statistica, `validity_mask`, `input_sha256` e `config_sha256`.
`acceptance_qa.json` registra schema, commit, SHA-256 dell'intero CSV, bundle
Gate 0, controlli di conteggio, closure e decisione `valid`. Person 2 rifiuta
il handoff se i bin fit non hanno una riga valida o un hash non coincide.

### Handoff Person 2 → P0/P1/P2

I tre filename sono l'interfaccia condivisa v1; sono pubblicati insieme e
con hash incrociati nel QA:

```text
results/physics/polarization/sigma_v1.csv
results/physics/polarization/sigma_covariance.npz
results/physics/polarization/polarization_qa.json
```

`sigma_v1.csv` contiene `analysis_version`, chiavi di bin,
`sigma`, `stat_uncertainty`, componenti sistematiche, `validity_mask`,
`fit_id`, `input_sha256` e `config_sha256`. `sigma_covariance.npz` contiene
`covariance`, `bin_keys`, `stat_covariance`, `systematic_covariance` e
`schema_version`; l'ordine di `bin_keys` è quello della tabella. Il QA riporta
mappa stati, fonte `P(Egamma)`, hash accettanza, convergenza/GOF, closure
iniettata, test di segno e `valid`. Il consumatore rifiuta mismatch di ordine,
dimensione, hash o QA.

### Cambiamenti di interfaccia e gate finale

Entrambi i revisori devono approvare prima di modificare manifest o policy
good/review/bad, registro canali, schema di ricostruzione, bordi bin comuni,
`HANDOFF.json`, CSV/NPZ/QA di handoff, definizione `phi`, policy QA o target
Make/documentazione pubblica. Un commit di una sola persona non rende valido
un cambiamento condiviso.

**P0 release gate. Input:** Gate 0 valido, accettanza/yield/normalizzazione
Person 1, mappa stati/`P(Egamma)`/fit Person 2, validazioni fondi e tutte le
closure. **Output:** un benchmark P0 con sezioni d'urto e `Σ` tracciabili.
**Validation — interface to implement:**

```text
python 00_common/validate_p0_release.py \
  --normalization results/physics/normalization \
  --polarization results/physics/polarization --require-two-reviewers
```

**Rejection:** rifiutare P0 se qualunque QA è invalido, se non esistono due
approvazioni alle interfacce, se una closure/fondo/sistematica resta aperta o
se gli hash non portano allo stesso Gate 0.

## Esplicitamente differito

D2/neutron work is deferred fino a quando P0 sul protone e i contratti di
polarizzazione non superano il release gate; richiede inoltre Fermi motion e
tag neutrone quasi-free separati.

eta-prime work is deferred fino a P0, ai contratti di polarizzazione e a una
feasibility-count approvata; richiede topologie di ricostruzione η' nuove.
