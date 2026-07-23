# 05 — Ricostruzione

`05_reconstruction/` trasforma i quattro fotoni e il barione di rinculo selezionati nella fase 2 (`h85`) in eventi ηπ⁰ o 2π⁰ ricostruiti.

Sono presenti tre entrypoint:

| Entrypoint                    | Canale       | Gate BDT |
| ----------------------------- | ------------ | -------- |
| `reconstruct_eta_pi0_chi2.py` | γp → p η π⁰  | no       |
| `reconstruct_eta_pi0_bdt.py`  | γp → p η π⁰  | sì       |
| `reconstruct_2pi0.py`         | γp → p π⁰ π⁰ | no       |

## Struttura

Tutti gli script usano:

`reco_core.run_reconstruction(cfg, channel, gate)`

divisa in:

* **`reco_core.py`**: gestione ROOT, selezione eventi, applicazione del gate e scrittura dell'output.
* **`reco_physics.py`**: logica fisica (combinazioni fotoni, chi², assegnazione η/π⁰), indipendente da ROOT e basata su array NumPy.

Questa separazione permette di mantenere la stessa catena di ricostruzione e confrontare direttamente i risultati con e senza BDT.

## Confronto chi² vs BDT

`reconstruct_eta_pi0_chi2.py` e `reconstruct_eta_pi0_bdt.py` differiscono solo per il gate passato a `run_reconstruction`:

* `None` nel caso chi²;
* `Stage1Gate` nel caso BDT.

Tutto il resto della ricostruzione è identico, quindi ogni differenza nei risultati è attribuibile esclusivamente al gate.

## Selezione iniziale degli eventi

Prima della combinatoria chi² e del gate vengono richiesti:

* almeno 4 fotoni ricostruiti;
* esattamente 1 protone.

Gli eventi con un numero diverso di protoni vengono scartati:

```python
if chain.protons.size() != 1:
    continue
```

Non viene creato un protone fittizio, perché altererebbe la massa mancante e renderebbe diverso il campione iniziale tra il run chi² e quello BDT.

## Canale 2π⁰

Non esiste un `reconstruct_2pi0_bdt.py` perché il modello BDT stage-1 è addestrato per distinguere ηπ⁰ dal fondo, e il canale 2π⁰ è uno dei fondi usati nell'addestramento.

Applicare il gate BDT al campione 2π⁰ non avrebbe quindi significato fisico.

## Fit cinematico

Dopo la ricostruzione chi² (e il gate BDT per il canale ηπ⁰), gli eventi vengono sottoposti al fit cinematico 6C. La selezione finale usa la confidence level del fit invece della finestra sulla massa mancante.
