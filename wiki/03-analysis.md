# 03 — Analisi

`03_analysis/` è dove i quattro fotoni e il barione di rinculo selezionati
dalla fase 2 (`h85`) diventano un η e un π⁰ ricostruiti. La cartella espone
tre entrypoint eseguibili sopra un nucleo condiviso:

| Entrypoint | Canale | Gate BDT |
|---|---|---|
| `reconstruct_eta_pi0_chi2.py` | γp → p η π⁰ | no |
| `reconstruct_eta_pi0_bdt.py` | γp → p η π⁰ | sì (stage-1) |
| `reconstruct_2pi0.py` | γp → p π⁰ π⁰ | no — vedi sotto |

## Il nucleo condiviso

Tutti e tre gli entrypoint chiamano la stessa funzione,
`reco_core.run_reconstruction(cfg, channel, gate)`, divisa in due moduli con
responsabilità nettamente separate:

- **`reco_core.py`** — I/O ROOT: apre la `TChain` di `h85`, applica i
  requisiti di evento e il gate opzionale, scrive l'albero di output. Non
  contiene fisica propria.
- **`reco_physics.py`** — la fisica pura: la combinatoria dei fotoni, il
  chi2, l'assegnazione η/π⁰. Funzioni su array numpy `(4,)` `[px, py, pz,
  E]`, senza ROOT — vedi [Ricostruzione chi2](03-analysis-chi2) e
  [Testing](testing) per il perché di questa separazione.

## La regola di design che rende il confronto significativo

`reconstruct_eta_pi0_chi2.py` e `reconstruct_eta_pi0_bdt.py` differiscono
**solo** per l'argomento `gate` passato a `run_reconstruction`: `None` nel
primo caso, uno `Stage1Gate` caricato nel secondo (vedi
[Gate BDT](03-analysis-bdt-gate)). Tutto il resto — lettura dell'albero,
requisiti sull'evento, combinazione chi2, scrittura — passa dalla stessa
funzione. Questo è deliberato: qualunque differenza tra `reco_eta_pi0_chi2`
e `reco_eta_pi0_bdt` si può attribuire al gate e a nient'altro, perché non
c'è nessun altro punto in cui i due percorsi di codice divergono.

## Il requisito "esattamente un protone"

Prima del gate e prima della combinatoria chi2, `run_reconstruction` scarta
ogni evento che non ha esattamente 4 fotoni ricostruiti e esattamente 1
protone:

```python
if chain.protons.size() != 1:
    n_no_proton += 1
    continue
```

Un evento senza protone (0 o 2+) viene scartato, non completato con un
protone fittizio a `(0,0,0,0)`: un protone a zero produce una massa mancante
artificiosa (~1.87 GeV, contro i ~0.75 GeV di un protone vero) che porta il
gate BDT — ma non il taglio chi2 — a scartare quegli eventi in modo diverso
dal run chi2. Applicare il requisito identicamente a entrambi i run, prima
di qualunque altra logica, tiene i due campioni identici tranne che per il
gate — che è l'intero punto del confronto. Il conteggio degli eventi
scartati (`Skipped (not exactly 1 proton)`) viene sempre stampato a fine
run, proprio per rendere visibile quanti eventi i due run condividono in
partenza.

## Perché non esiste un `reconstruct_2pi0_bdt.py`

`reconstruct_2pi0.py` gira sullo stesso nucleo (`TWO_PI0` invece di
`ETA_PI0` in `reco_physics.py`) ma senza gate. Non è un'omissione: il
modello BDT stage-1 è addestrato usando 2π⁰ **come fondo** (vedi
[BDT stage-1](05-analysis-bdt) e [Feature stage-1](05-analysis-bdt-features)
— `pi0pi0` è uno dei cinque canali di fondo nel CSV delle sezioni d'urto).
Far passare eventi 2π⁰ attraverso un gate addestrato a respingerli non
avrebbe senso: il gate esiste per separare η π⁰ dal fondo, e 2π⁰ *è* quel
fondo.

## Dove andare da qui

- [Ricostruzione chi2](03-analysis-chi2) — la tabella delle combinazioni, la
  formula del chi2, l'assegnazione η/π⁰, il taglio, il quadrimomento
  mancante.
- [Gate BDT](03-analysis-bdt-gate) — come funziona il gate oggi, e il bug
  che ha reso invalidi i risultati BDT prodotti prima del fix.
