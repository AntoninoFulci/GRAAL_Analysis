# Piano 06 — confronto pairing e BDT+pairing senza 6C

Data: 13 ottobre 2026. **Software e confronto diagnostico locale UV/VIS eseguiti.**
Non è una misura finale di miglioramento: efficienza di segnale, fondo indipendente
per entrambe le selezioni e copertura frequentista restano da stabilire.

## Verifica iniziale e riuso

Graphify interrogato con vocaboli presenti nel grafo:
`pairing gate comparison covariance asymmetry reconstruction`. Il grafo individua
`run_reconstruction`, `reconstruct_event`, `best_pairing` e il test gate aperto.
Verifica sul codice e sugli artefatti: baseline 00 già completa, piano 06 non
completo. Riusata `results/baseline-no-fit-20261013/`, senza nuova ricostruzione
né nuovo algoritmo di pairing; riusati stimatori Stage 07 e bootstrap del piano 01.

I ROOT hanno identici input e codice di ricostruzione (size/SHA256), stesso
universo inclusivo run/stato e stessa selezione salvo gate. Tagli già approvati:
χ² < 10, risoluzione relativa 0.08, missing mass entro ±0.06 GeV, almeno quattro
fotoni con uso dei primi quattro, esattamente un protone, `do_fit=false`, nessun CL.
Soglie BDT registrate: UV 0.27593; VIS 0.236533.

## File e comportamento

- `07_observable_extraction/core/gate_comparison.py`: contratti, contenimento
  multinsieme delle cinematiche, griglia completa, covarianza delle differenze.
- `07_observable_extraction/compare_gate.py`: CLI dedicata, esposizioni inclusive,
  cutflow, ratio/likelihood, bootstrap, ROOT/JSON/NPZ e PDF.
- `07_observable_extraction/core/ratio_fit.py`: correzione di un errore emerso
  nelle repliche reali. Un fit con Σ corretto fuori [-1,1] rende quel bin non
  stimabile; non interrompe gli altri bin e non viene forzato al limite fisico.
- `07_observable_extraction/tests/test_gate_comparison.py`: contratti, duplicati,
  covarianza incrociata, fallimenti, griglia vuota, gate aperto, toy selettivo,
  ROOT e preservazione degli output precedenti.
- Aggiornati solo questo rapporto e il piano 06; indice generale e moduli già
  modificati dagli altri agenti lasciati al rispettivo lavoro.

## Metodo e decisioni

Esposizioni definite dall'universo **prima del gate**, letto dalla provenienza.
I run a resa zero restano nell'universo se il flusso è valido. Stesse esposizioni,
polarizzazioni, bin di massa/energia, φ e correzione finite-bin per entrambi i
campioni. Fondo identicamente **non corretto**, indicato anche nelle figure.

Per ogni profilo: 64 repliche appaiate per run, stratificate per periodo, seed
1208. Ogni draw ricampiona entrambi i campioni e moltiplica i flussi con la stessa
molteplicità di run. Ratio e likelihood vengono ricalcolati. Si conservano tutti
i draw; nessuna replica fallita viene eliminata o ridisegnata.

Convenzione: ΔΣ = Σ_BDT − Σ_pairing. Con `C_AB = Cov(pairing, BDT)`:

`C_delta = C_BDT + C_pairing − C_AB − C_AB.T`.

La covarianza è disponibile solo per punti stimabili in **tutte** le 64 repliche.
Gli altri restano nella griglia e nelle repliche, con errore assente, mai zero.
La matrice riporta chiavi ordinate, blocco incrociato, rango e stima della
precisione Monte Carlo. Non è sommata alle incertezze pubblicate del piano 01.

Decisioni esplicite:

1. File dedicati nel checkout condiviso, nessun cambio branch o reset. Calcolo
   lungo da snapshot `source_snapshot_v2`, perché i prerequisiti ancora non
   committati e gli altri agenti rendono HEAD da solo insufficiente. Hash del
   codice verificati prima/dopo ogni studio; rischio residuo: integrazione delle
   successive modifiche concorrenti da verificare separatamente.
2. Riutilizzati tagli approvati nel prerequisito 00; nessuna nuova scelta fisica.
3. Baseline priva di source-entry ID: contenimento **esatto delle cinematiche**,
   indipendente dall'ordine e con molteplicità dei duplicati. Non equivale a
   identità certificata dell'evento. Bootstrap per run, nessun accoppiamento
   evento-per-evento. Per quest'ultimo serviranno source-file/hash + entry
   persistiti in futura ricostruzione.
4. Nessun controllo indipendente certificato per entrambe le selezioni: fondo
   lasciato non corretto su entrambe, efficienza non inventata. La retention
   dei dati sotto è una sopravvivenza al gate, non efficienza di segnale.
5. Fit fuori dominio registrato come bin non stimabile, coerentemente con il
   contratto `SigmaPoint`. Questo limita la disponibilità della covarianza nei
   bin sparsi; non corregge bias o copertura statistica.

## Risultati numerici

Conteggi dopo selezione energia, stato POL1/POL2 ed esposizioni valide:

| Profilo | Pairing ricostruiti | BDT ricostruiti | Pairing selezionati | BDT selezionati | Retention dati |
|---|---:|---:|---:|---:|---:|
| UV | 15.164 | 12.261 | 14.443 | 11.674 | 80.828% |
| VIS | 6.219 | 2.706 | 6.160 | 2.682 | 43.539% |

Contenimento verificato per tutti i 12.261 eventi BDT UV e 2.706 VIS; nessuna
impronta cinematica duplicata ambigua nei subset di questa campagna.

| Profilo | Punti griglia (ratio + likelihood) | Comuni | Solo pairing | Nessuno stimabile | Con covarianza Δ |
|---|---:|---:|---:|---:|---:|
| UV | 240 | 184 | 14 | 42 | 160 |
| VIS | 60 | 30 | 4 | 26 | 28 |

UV: 92 punti comuni per stimatore; covarianza per 77 ratio e 83 likelihood.
VIS: 15 comuni per stimatore; covarianza per 14 e 14. I due punti VIS senza
covarianza sono `p_pi0:E0:M5`: ratio non stimabile in 40/64 repliche,
likelihood in 26/64. Le ragioni non vengono convertite in una barra nulla.

Intervalli osservati di ΔΣ, **non significatività né test globale**:

| Profilo | Ratio | Likelihood |
|---|---|---|
| UV | [-0.2201, +0.4896] | [-0.1934, +0.4454] |
| VIS | [-0.2248, +0.0364] | [-0.1731, +0.0493] |

Universo UV: 170 run esposti, 9.180 run/strip, numero effettivo di run 144.72.
VIS: 109 run, 2.289 run/strip, numero effettivo 101.46. Rango di `C_delta`: UV
63 su 160, VIS 28 su 28. **Non invertire la matrice UV per test globale**: 64
repliche non consentono rango superiore a 63. Errore Monte Carlo relativo
mediano sulle diagonali della covarianza: circa 17.3% UV, 18.0% VIS.

Run esclusi interamente per flusso incompleto: UV 1382, 1388, 1409, 1416,
1425, 1442, 1474, 1505; VIS 2071. UV: altri 510 run/strip fuori dominio di
polarizzazione. Eventi senza esposizione valida: UV 719 pairing / 586 BDT;
VIS 59 / 24. Due eventi BREM pairing e uno BDT UV non entrano in Σ.

Run BDT a zero eventi conservati: 7 UV e 6 VIS. Quattro di quelli UV sono
vuoti anche nel pairing. Elenco completo, cutflow run/periodo/energia/stato,
flussi, conteggi per φ e diagnostica dei fit sono nei JSON e nei ROOT.

Fra i punti comuni ratio UV, fallback armonico in 5 fit pairing e 6 BDT;
nessuno VIS. Nessun punto comune centrale con |Σ| > 0.95. Le repliche sparse
restano problematiche, come mostra la covarianza mancante. Disponibile un solo
periodo per profilo (`1998_uv`, `1999_vis`): nessuna prova di stabilità fra
periodi distinti dello stesso profilo.

## Artefatti e riproduzione

- [Figure UV](../../results/gate-comparison-20261013/uv/comparison.pdf), 8 pagine.
- [Figure VIS](../../results/gate-comparison-20261013/vis/comparison.pdf), 2 pagine.
- [ROOT UV](../../results/gate-comparison-20261013/uv/comparison.root) e
  [ROOT VIS](../../results/gate-comparison-20261013/vis/comparison.root).
- Nelle stesse directory: `comparison.json` e `paired_replicas.npz` con array,
  chiavi e draw; ROOT contiene TTree `comparison`, matrici TH2 e TNamed
  `comparison_metadata` equivalente al JSON.
- `results/gate-comparison-20261013/source_snapshot_v2/` conserva il codice
  effettivamente eseguito, comprensivo dei prerequisiti non committati.

Esempio per riprodurre su **nuova** directory, mantenendo PYTHONPATH necessario
al PyROOT locale; sostituire `uv` con `vis` per il secondo profilo:

```bash
MPLCONFIGDIR=/tmp/graal-gate-mpl \
PYTHONPATH="$PWD/results/gate-comparison-20261013/source_snapshot_v2:$PYTHONPATH" \
python3 -m observable_extraction.compare_gate \
  --pairing results/baseline-no-fit-20261013/uv/reco/reco_eta_pi0_chi2.root \
  --bdt results/baseline-no-fit-20261013/uv/reco/reco_eta_pi0_bdt.root \
  --flux-file results/baseline-no-fit-20261013/common/flux_calibrated.root \
  --run-manifest config/run_manifest.csv --profile uv \
  --output-dir results/gate-comparison-repeat/uv --replicas 64 --seed 1208
```

Destinazione già esistente rifiutata. Scrittura in staging e pubblicazione
atomica; campagne precedenti preservate. Nessun 6C eseguito.

## Prove e review

Suite iniziale del piano: 41 passati. Suite mirata finale: **91 passati**,
inclusi contratti, pairing, ricostruzione senza fitter, gate aperto, Stage 1,
diagnostica, sistematici e ratio. Un warning Matplotlib innocuo nel test della
griglia completamente vuota (legenda priva di artisti).

Gate aperto: uguali eventi/risultati nella ricostruzione esistente; prova nuova
con entrambi gli stimatori e bootstrap effettivo a due run produce ΔΣ e
covarianza Δ nulle. Toy selettivo con accettanza dipendente da φ ma identica
per stato recupera Σ=0.35 dopo correzione finite-bin. Questo è closure
deterministica, **non misura della copertura frequentista**.

Review indipendente: due rilievi materiali, entrambi riprodotti con test rossi
e corretti: eccezione su Σ fuori dominio; perdita del rapporto senza bin comuni.
Test gate chiuso verifica scrittura ROOT/JSON/PDF e rifiuto di sovrascrittura.
Nessun altro rilievo materiale. Il reviewer ha escluso dal giudizio inferenza
finale, efficienza/fondo indipendenti e identità source-entry: limiti mantenuti
espliciti, nessuna conclusione finale derivata. Artefatti verificati dopo review.

ROOT riaperti: numero righe, metadata e ogni elemento della matrice Δ coincidono
con JSON; NPZ UV `(64,368)`, VIS `(64,60)`. Tutte le 10 pagine PDF renderizzate
e controllate visivamente: legende, assi e marcatori di covarianza assente leggibili.

Suite globale durante lavoro concorrente: **885 passati, 6 falliti**. Fallimenti
fuori dai file del confronto: quattro test di conferma launcher hanno mock
incompatibili con `energy_binnings`; due test CLI BDT hanno mock incompatibili
con `energy_range_gev`. Modifiche parallele nei relativi moduli/test confermate;
nessuna correzione applicata al lavoro degli altri agenti. Log preservati in
`results/gate-comparison-20261013/validation/`.

## Limiti ancora aperti del piano

Non disponibili qui: efficienza da MC indipendente certificato, fondo indipendente
per entrambi i percorsi, copertura statistica, source-entry ID persistenti e
cutflow pre-ricostruzione suddiviso anche in energia. Il cutflow originario offre
run/stato; quello dopo ricostruzione offre anche energia. Il confronto è una
diagnostica del gate sui dati locali, non replica di una pubblicazione e non
dimostrazione di maggiore precisione o minore bias. Inferenza finale sospesa.
