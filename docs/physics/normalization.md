# Persona 1 — guida operativa alla normalizzazione

Questa guida prepara il lavoro su normalizzazione, accettanza e sezioni
d'urto del canale protone `γ p → p η π⁰` per il benchmark P0. Attua sul piano
documentale la [roadmap a due persone](../collaboration/two-person-physics-roadmap.md):
non introduce codice fisico, configurazioni approvate o nuovi risultati.
La Persona 2 mantiene polarizzazione e asimmetria `Σ`; D2/neutrone e η′
restano differiti fino al gate congiunto P0.

## Punto di partenza verificabile

Lo snapshot esaminato il 10 settembre 2026 parte dal commit `a0f1a30`.
Il [piano di handoff del 9 settembre](../superpowers/plans/2026-09-09-two-person-ai-handoff.md)
descrive il confezionamento del progetto; le sue checkbox storiche non sono
un registro aggiornato dell'esecuzione N1–N7.

| Oggetto | Stato nello snapshot | Conseguenza operativa |
| --- | --- | --- |
| `config/run_manifest.csv` | Manifest curato: 2.711 run | È l'autorità per metadati e gruppi. |
| `results/observable_runs/` | Sei file, QA `valid: true`, 2.372 run good | È il bundle di partenza; verificarne gli hash prima dell'uso. |
| Sottoinsieme protone good | `P_UV=1256`, `P_VIS=323`: 1.579 run | È la popolazione candidata per P0, da mantenere distinta per gruppo. |
| Sottoinsieme deuterio good | `D_UV=531`, `D_VIS=262`: 793 run | Rimane pubblicato, ma fuori dal lavoro P0 sul protone. |
| `results/observable_runs/HANDOFF.json` e relativo validatore | Assenti | Gate 0 non è ancora congelato. |
| `07_physics_normalization/` e `config/physics/normalization_v1.json` | Assenti | Le interfacce N1–N7 sono da implementare. |
| `results/physics/normalization/` | Nessuna release pubblicata | Accettanza, yield e sezioni d'urto non sono ancora disponibili. |
| `results/reco/` | ROOT legacy, anteriori alla propagazione dei metadati | Utilizzabili per riprodurre plot legacy; vietati per normalizzazione run-flux. |

Le 2.372 run good non sono tutte run di protone né garantiscono una yield
utilizzabile in ogni bin. I conteggi provengono da
`observable_run_qa.json`: su 2.711 run, 152 sono review e 187 bad.
Il QA sorgente `results/strip_energy_flux/strip_energy_flux_qa.json` conserva
`valid: false` come stato diagnostico; è distinto dal QA valido del bundle
curato, come stabilisce la [politica artefatti](../artifact-policy.md).

## Letture, Graphify e comandi disponibili

Prima di modificare il progetto leggere [AGENTS.md](../../AGENTS.md),
[politica artefatti](../artifact-policy.md), [inventario](../../ARTIFACTS.json)
e [roadmap](../collaboration/two-person-physics-roadmap.md).
Il [Graphify report](../../graphify-out/GRAPH_REPORT.md) aiuta a trovare le
dipendenze; il codice e i QA citati restano le fonti da verificare.

Per un clone nuovo seguire [Clone e ambiente](../../README.md#clone-e-ambiente):
recuperare gli oggetti con `git lfs pull`, creare un ambiente nuovo usando
l'interprete compatibile con PyROOT e installare con `make setup`.
Non ricreare né sovrascrivere un ambiente già presente. Con l'ambiente
attivato, questi comandi sono disponibili oggi dalla radice del repository:

```bash
make graph-query QUERY="How does the observable-run handoff reach normalization?"
make graph-query QUERY="Reconstruction metadata RunNumber Polarization Xstrip Stage1Gate"
make validate-manifest
make verify
```

`make verify` comprende sintassi, manifest, suite senza ROOT e confronto
con l'inventario salvato: non rigenera input o risultati. Per controllare la
disponibilità di PyROOT usare `python -c 'import ROOT'`; solo se riesce,
eseguire `make test` per la suite completa. In alternativa all'attivazione,
passare ai target Make `PYTHON=.venv/bin/python`.

Graphify è `graphifyy==0.9.7`, installato da `requirements-graphify.txt` e
invocato tramite il Python selezionato. Le interrogazioni conducono a:

| Nodo o relazione da seguire | Fonte da leggere | Implicazione per Persona 1 |
| --- | --- | --- |
| `ObservableRunError`, `classify_run_quality()` | [observable_runs.py](../../00_common/observable_runs.py), [builder del database](../../scripts/build_observable_run_database.py) | Riutilizzare le regole di selezione e i controlli sugli artefatti. |
| Gate 0, Acceptance Handoff | [Roadmap](../collaboration/two-person-physics-roadmap.md) | Congelare input e interfaccia prima del calcolo fisico. |
| `run_reconstruction()`, `Stage1Gate`, test metadati | [reco_core.py](../../05_reconstruction/reco_core.py), [stage1_gate.py](../../05_reconstruction/stage1_gate.py), [test reco](../../05_reconstruction/tests/test_reco_physics.py) | Verificare la propagazione e fissare modello, soglia e selezione. |
| `MCChannel`, `ChannelYield`, `Hypothesis` | [channels.py](../../00_common/channels.py), [MC e pesi](../../wiki/03-mc-simulation.md) | Distinguere pesi di training, conteggi generati e accettanza della misura. |

La centralità di un nodo è un aiuto alla navigazione, non un'approvazione
scientifica. In particolare `00_common/cross_sections.py` descrive pesi dei
fondi: non è l'estrattore della sezione d'urto misurata del segnale
`eta_pi0`, che nel registry non ha una `sigma_ref_ub` assegnata.

## Gate 0 — cosa verificare e cosa congelare

Usare insieme i sei file della medesima pubblicazione:

| File in `results/observable_runs/` | Uso |
| --- | --- |
| `run_manifest_observables.csv` | Run good ammesse, con metadati curati. |
| `run_quality.csv` | Diagnostica di tutte le 2.711 run, incluse review/bad. |
| `strip_energy_lookup.csv` | Lookup `(run, strip)` filtrato sulle good. |
| `flux_by_run_energy.csv` | Flussi delle good per run e bin. |
| `flux_by_group_energy.csv` | Aggregazione coerente dei flussi filtrati. |
| `observable_run_qa.json` | Validità, policy, conteggi e hash di input e CSV. |

La presenza di review/bad in `run_quality.csv` è prevista. Il rifiuto riguarda
la loro presenza negli input filtrati o la loro inclusione in eventi, yield
e flussi usati per normalizzare. Non eliminare le righe diagnostiche.

Prima di proporre il congelamento:

1. Far passare `make verify`, compreso il controllo dei payload LFS reali e
   dei SHA-256. Non usare `make artifact-inventory` per far scomparire un
   mismatch: prima identificarne la causa.
2. Controllare `observable_run_qa.valid=true`, l'hash del manifest curato e
   gli hash dei cinque CSV. Conservare il collegamento alla pubblicazione
   sorgente; non ricombinare file prodotti da esecuzioni diverse.
3. Registrare commit produttore, binning energetico e timestamp UTC secondo
   il contratto Gate 0. Il futuro `HANDOFF.json` deve fissare percorsi e
   SHA-256 dei sei file, manifest e QA, senza sostituire il QA sorgente.
4. Ottenere la revisione di entrambe le persone sul contratto condiviso e
   implementarne il validatore. Il QA attuale da solo non certifica Gate 0.

Lo SHA-256 corrente di `data/flux/flux.root` si legge e si verifica in
`ARTIFACTS.json`; non va fissato nel CSV del manifest. Il flusso compatto è
un input upstream, mentre la normalizzazione deve consumare i flussi
good-only della pubblicazione accettata.

Se gli input elaborati non coprono tutte le run good di un gruppo, fissare
la run-list di esposizione dalla copertura della produzione, prima della
selezione degli eventi, e ricavare il flusso dalla stessa lista e dagli
stessi bin di `flux_by_run_energy.csv`. Una run good interamente elaborata
con zero eventi selezionati mantiene il proprio flusso: non costruire la
luminosità dalla lista delle sole run con yield positiva. La somma completa
del gruppo non è il denominatore di una produzione parziale non documentata.
Qualsiasi esclusione ulteriore deve propagarsi a provenienza e QA.

## Decisioni necessarie prima di N1

Persona 1 prepara le proposte; Persona 2 revisiona ciò che influenza
l'accettanza ricevuta e il gate P0. Queste decisioni non sono già risolte
dalla presenza delle colonne nel roadmap:

| Decisione da congelare | Evidenza richiesta |
| --- | --- |
| Identità di analisi e selezione | `analysis_version`, nome fisico leggibile `γ p → p η π⁰`, chiave serializzata del registry `eta_pi0`, target, `selection_id`, modello BDT, soglia, tagli e configurazione del fit con hash. `pηπ0` non è una chiave serializzata alternativa. |
| Gruppi sperimentali | Mapping esplicito fra `target`, `beam_type`, `group` dei CSV attuali e `beam_group` dello schema futuro; mantenere separati UV/VIS fino a una combinazione validata. |
| Binning comune | Nome, bordi, unità, convenzione degli estremi; variabile angolare, sistema di riferimento, assi e range d'integrazione dichiarati. |
| Denominatori MC | Significato distinto di `n_generated`, `n_thrown_in_bin`, `n_reconstructed_selected`; pesi, fase generata, migrazioni e metodo d'incertezza. |
| Accettanza utile a `Σ` | Interfaccia condivisa approvata: tabella comune, risposta azimutale separata e QA nella stessa release immutabile. Una tabella integrata in `phi` non è sufficiente per S4. |
| QA e closure | Soglie preregistrate per popolazione dei bin, fit/fondo, closure MC e confronto Ajaka; regole per maschere e sistematiche. |

I bin energetici già disponibili sono `ajaka_cross_section` (15 bin
uniformi fra 0.95 e 1.50 GeV) e `ajaka_sigma` (bordi 1.10, 1.20, 1.30,
1.40, 1.50 GeV). La funzione attuale
`graal_common.strip_energy_flux.energy_bin_index` usa intervalli chiusi a
sinistra e aperti a destra, includendo l'ultimo estremo superiore nell'ultimo
bin. Riutilizzare la definizione verificata nei CSV; non arrotondare o
reinventare i bordi. I bin angolari di N1 restano da concordare.

## Sequenza di lavoro N1–N7

Gate 0 precede il lavoro fisico. N1 congela il contratto condiviso, N2 produce
la ricostruzione valida e N3 produce l'accettanza. Dopo QA N3 valido, la
consegna immutabile dell'accettanza abilita S4 senza attendere N7. S4 consuma
la ricostruzione dati N2 metadata-bearing e la risposta N3; Persona 2 costruisce
da esse i conteggi azimutali. N4 non alimenta S4 ed è riservato alle sezioni
d'urto. Da quel punto N4–N7 e S4–S6 possono avanzare in parallelo; N7 chiude la
release finale di normalizzazione e sistematiche. La tabella descrive attività
future, non risultati conseguiti.

| Fase | Ingressi e lavoro della Persona 1 | Evidenza da consegnare e condizione di rifiuto |
| --- | --- | --- |
| **N1 — schema** | Gate 0 valido, canale, bin e proposta `normalization_v1.json`; congelare chiavi, denominatori, contratto azimutale e hash secondo l'interfaccia condivisa approvata. | Schema e configurazione revisionati; rifiutare duplicati, denominatori negativi, selezioni senza ID, bin incompatibili, hash assenti o l'assenza della risposta `phi` separata. |
| **N2 — ricostruzione** | Dati LH2 e MC appropriati, modello fissato, configurazione e Gate 0; produrre nuovi output in un percorso dedicato. | Provenienza e controllo di `RunNumber`, `Polarization`, `Xstrip`; rifiutare legacy, metadati mancanti o run non-good nella misura. La rappresentazione dei metadati MC richiede una convenzione esplicita. |
| **N3 — accettanza** | Generato, eventi thrown nel bin e ricostruito N2 con la stessa selezione dei dati; dichiarare pesi, migrazioni e risposta. | Conteggi, accettanza, risposta azimutale concordata, incertezze, maschere e closure MC; con QA valido pubblicare l'handoff immutabile per S4. Rifiutare valori fuori `[0,1]`, conteggi incoerenti, denominatore nullo non mascherato, hash mancanti o closure fallita. |
| **N4 — yield per sezioni d'urto** | Dati N2, run-list good-only, bin N1 e metodo di estrazione con QA del fondo. | Segnale, fondo e incertezza statistica per chiave, run-list e hash destinati a N5–N7; rifiutare review/bad, provenienza mancante o fit/sideband QA invalido. N4 non è un input di S4. |
| **N5 — fattori** | Yield, accettanza, flusso coerente, quantità di bersaglio e branching ratio con fonti. | Fattori/luminosità, unità, incertezze e correlazioni; rifiutare valori non finiti, sorgenti mancanti, assunzioni non approvate o flussi estranei al Gate 0. |
| **N6 — sezioni d'urto** | N3–N5 e bin `ajaka_cross_section`; produrre totali/differenziali e confronto al riferimento. | Tabella dei risultati, residuali e compatibilità Ajaka; rifiutare bin errati, normalizzazione non riproducibile o scarti oltre soglia senza spiegazione sistematica approvata. |
| **N7 — release finale** | N3–N6, variazioni sistematiche, correlazioni e provenienza completa. | Release finale di normalizzazione, componenti d'incertezza e covarianza, con riferimento per hash all'handoff N3 consumato da Persona 2; rifiutare sorgenti/hash mancanti o covarianza non simmetrica/semidefinita positiva entro tolleranza dichiarata. N7 non muta né sostituisce l'handoff N3. |

Il modello di perdita fotoni del training è documentato come
[approssimazione non calibrata](../../wiki/03-mc-simulation.md#il-modello-di-perdita-fotoni).
Non certifica da solo l'efficienza assoluta dell'apparato, del trigger o
dei periodi. N3 richiede una risposta detector validata e una closure
documentata; il rapporto di sopravvivenza usato nel training non basta.
La closure su campioni sintetici e la calibrazione sperimentale indipendente
sono evidenze distinte.

Per N5 raccogliere fonti e incertezze della densità areale dei bersagli,
dei decadimenti osservati e dei fattori di flusso applicabili. Dichiarare
se i branching ratio sono già inclusi nel campione generato o nei fattori,
evitandone l'applicazione doppia. Il trattamento attuale
`total_net = POL1 + POL2 - 2 × BREM` è provvisorio: non introdurre valori
impliciti per dead time, live time, tagging efficiency o scala BREM.
La convenzione fisica degli stati rimane responsabilità della Persona 2.

### Comandi futuri — interface to implement

Questi comandi sono il contratto del roadmap. I relativi script e la
configurazione non esistono nello snapshot di partenza; non eseguirli come
check già disponibili. Non creare artefatti vuoti per simularne il passaggio.

```text
python 00_common/validate_observable_handoff.py \
  --handoff results/observable_runs/HANDOFF.json --require-qa-valid

python 07_physics_normalization/validate_acceptance_schema.py \
  --handoff results/observable_runs/HANDOFF.json \
  --config config/physics/normalization_v1.json

python 07_physics_normalization/validate_metadata_reco.py \
  --handoff results/observable_runs/HANDOFF.json --require-run-metadata

python 07_physics_normalization/build_acceptance.py \
  --config config/physics/normalization_v1.json --check-closure

python 07_physics_normalization/extract_yields.py \
  --handoff results/observable_runs/HANDOFF.json --good-runs-only

python 07_physics_normalization/validate_normalization_inputs.py \
  --config config/physics/normalization_v1.json --require-sources

python 07_physics_normalization/compare_ajaka.py \
  --results results/physics/normalization --observable cross_section

python 07_physics_normalization/validate_normalization_release.py \
  --results results/physics/normalization --check-provenance
```

## Consegna dell'accettanza alla Persona 2

### Ordine, versione e immutabilità

La prima consegna a Persona 2 avviene dopo N1, N2 e N3, soltanto quando il QA
N3 è valido e il contratto azimutale ha ricevuto la revisione congiunta. N7
non è un prerequisito: produce una release finale distinta, che riferisce
per hash l'handoff N3 già consumato da S4–S6.

L'interfaccia condivisa approvata è una directory identificata da un
`acceptance_release_id` univoco e immutabile:

```text
results/physics/normalization/handoffs/<acceptance_release_id>/acceptance_v1.csv
results/physics/normalization/handoffs/<acceptance_release_id>/acceptance_phi_response_v1.csv
results/physics/normalization/handoffs/<acceptance_release_id>/acceptance_qa.json
```

I tre file sono una sola pubblicazione atomica. Dopo la consegna non vengono
sovrascritti. Una correzione, una nuova selezione, un nuovo modello, un diverso
Gate 0 o una diversa decisione sul `phi` produce un nuovo
`acceptance_release_id`, una nuova directory e nuovi hash; Persona 2 deve
rivalidare e registrare esplicitamente quale release consuma. Non esistono file
"preliminari" e "finali" con lo stesso path e contenuto mutabile.

### Tabella comune e risposta azimutale approvata

Il CSV v1 deve portare le chiavi concordate nel roadmap:
`analysis_version`, `channel`, `target`, `beam_group`, `Egamma_low`,
`Egamma_high`, `cos_theta_low`, `cos_theta_high`, `observable`,
`selection_id`. Contiene inoltre `n_generated`, `n_thrown_in_bin`,
`n_reconstructed_selected`, `acceptance`, `acceptance_stat_uncertainty`,
`validity_mask`, `input_sha256` e `config_sha256`.

`acceptance_v1.csv` resta la tabella delle chiavi comuni e dell'accettanza
integrata in `phi`; da sola non è un input sufficiente per S4. L'interfaccia
richiede `acceptance_phi_response_v1.csv` come risposta sparsa
true→reconstructed.
Ogni riga riusa le chiavi comuni e un identificatore univoco della relativa
riga di `acceptance_v1.csv`, quindi dichiara:

- bordi `phi_true_low`, `phi_true_high`, `phi_reco_low`, `phi_reco_high` in
  radianti, intervalli chiusi a sinistra e aperti a destra e periodicità
  `[0, π)`;
- sistema di riferimento, assi, verso/orientamento e trattamento dei piani
  degeneri, identici alla definizione S3 approvata;
- `selection_id`, modello, soglia, tagli e hash della configurazione;
- denominatori true, conteggi ricostruiti, convenzione dei pesi, migrazioni,
  risposta, incertezza statistica e relativa procedura;
- maschera di validità con motivazione per celle o bin nulli/insufficienti;
- commit produttore e hash di Gate 0, MC, ricostruzione N2, configurazione e
  tabella comune.

`acceptance_qa.json` registra schema e `acceptance_release_id`, commit
produttore, SHA-256 di entrambi i CSV, collegamento e hash di Gate 0, controlli
dei conteggi, closure e decisione `valid`. I tre file devono essere
inventariati con hash in `ARTIFACTS.json`. L'inventario registra anche l'hash
del QA; non richiedere al QA di contenere l'hash dei propri byte. La forma
precisa delle referenze/hash degli input deve essere approvata insieme allo
schema, senza dichiarare qui approvato un JSON v1.

Persona 2 verifica gli hash, il QA, il contratto azimutale e la presenza di
copertura valida per ogni bin necessario al fit. Costruisce i conteggi
azimutali direttamente dalla ricostruzione dati N2 metadata-bearing collegata
per hash al QA e applica la risposta N3; non consuma le yield N4. Un bin
mascherato rimane escluso. N7 può incorporare o riferire l'handoff soltanto
con i suoi hash originali; qualsiasi sostituzione richiede una nuova release
di accettanza e la rivalidazione degli output dipendenti.

La pubblicazione futura di `results/physics/` richiede anche una modifica
revisionata delle allowlist Git e dell'inventario: oggi questa directory è
ignorata e non è fra gli artefatti ammessi dal builder. Non forzare `git add`
per aggirare il contratto di pubblicazione e non includere i grandi corpora
MC o raw detector.

## Registro di avanzamento e revisione

Per ogni consegna N1–N7 registrare nella relativa PR: fase, commit sorgente,
percorsi e hash degli input, configurazione/selezione, comando esatto,
esito e log della verifica, percorso e hash del QA prodotto, limiti ancora
aperti e revisori. Separare evidenza di manutenzione, closure sintetica e
validazione scientifica. Una checkbox completata o un test software passato
non sostituiscono l'approvazione sperimentale.

La Persona 1 modifica la propria area: `07_physics_normalization/`, i suoi
test, `config/physics/normalization_v1.json`,
`results/physics/normalization/` e questa guida. Modifiche upstream a
`00_common/`, schema reco, manifest, policy QA, bin comuni, handoff,
target Make e documentazione pubblica richiedono entrambi i revisori prima
del merge. La revisione di un agente non equivale alla firma di un owner.

Per la prima implementazione preparare Gate 0 e N1 con le decisioni della
tabella precedente; raccogliere in parallelo gli input sperimentali N2/N5.
Non dichiarare completate N2–N7 in assenza delle rispettive produzioni e QA.
La release P0 richiede anche la consegna `Σ` della Persona 2, validazioni
dei fondi, closure e sistematiche: tutti gli hash devono ricondurre allo
stesso Gate 0 e devono essere presenti entrambe le approvazioni.

Dopo modifiche strutturali o documentali, aggiornare Graphify con
`make graph-update` e completare l'estrazione semantica tramite Gemini o
host-agent quando richiesta. Pubblicare solo i file portabili elencati nella
politica artefatti. Rigenerare poi con `make artifact-inventory`, esaminare
il diff e lanciare `make verify`; eseguire `make test` se PyROOT è disponibile.
Non confondere il refresh del grafo con una nuova pubblicazione fisica.

Lavorare in un worktree e branch separati, conservando input, cache e
modifiche altrui. Per questa consegna il push richiede conferma esplicita
dell'utente; dopo la conferma aprire una pull request verso `main` e
sottoporre la documentazione condivisa a entrambi gli owner prima del merge.
