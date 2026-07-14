# Gate BDT

`03_analysis/stage1_gate.py` è il filtro che `reconstruct_eta_pi0_bdt.py`
applica a ogni evento prima della combinatoria chi2: un classificatore
BDT (stage-1, vedi [BDT stage-1](05-analysis-bdt)) addestrato a distinguere
il segnale η π⁰ dal fondo fisico (π⁰π⁰, 3π⁰, η2π⁰, ωπ⁰, η′). Prima di
spiegare come funziona oggi, questa pagina deve registrare un bug che ha
invalidato ogni risultato BDT prodotto prima del fix, perché tra sei mesi
qualcuno confronterà numeri vecchi con numeri nuovi e deve sapere perché
non coincidono.

## Il bug

> **I risultati BDT prodotti prima del 13 luglio 2026 sono da buttare.** Il
> vecchio `reconstruct_eta_pi0.py` costruiva a mano un vettore di 24
> feature con un layout diverso da quello su cui il modello era stato
> addestrato: impacchettava fino a 15 masse di coppia negli slot 0-14,
> spostando tutto il resto. Il modello veniva interrogato su rumore, quindi
> ogni decisione del gate era priva di significato.

Il modello stage-1 è addestrato su un vettore a 24 feature il cui layout è
`FEATURE_NAMES_S1` (vedi [Feature stage-1](05-analysis-bdt-features)): 6
masse invariante di coppia negli slot 0-5, poi conteggi di coppie vicine ai
poli dei mesoni, il miglior chi2, la cinematica mancante, le statistiche sui
fotoni, la cinematica del protone.

Il vecchio `reconstruct_eta_pi0.py` (rimosso dal repository — la versione
prima della rimozione è recuperabile con `git show abb20fd^:03_analysis/reconstruct_eta_pi0.py`)
costruiva questo vettore a mano, dentro `_stage1_pass`, invece di chiamare
la funzione che aveva costruito il set di addestramento. La sua versione
enumerava fino a `C(6,2) = 15` coppie di fotoni (l'evento può avere più di
4 fotoni ricostruiti a questo stadio) e le impacchettava negli slot 0-14:

```python
pair_masses = []
for i, j in _combinations(range(min(M, 6)), 2):
    ...
    pair_masses.append(...)
for k, m in enumerate(pair_masses[:15]):
    feat[k] = m
feat[15] = sum(1 for m in pair_masses if abs(m - _MPI0) < 0.040)
feat[16] = sum(1 for m in pair_masses if abs(m - _META) < 0.080)
...
```

contro il layout reale del modello, che ha solo 6 masse di coppia (slot 0-5,
sempre `C(4,2)=6`, mai 15) seguite dai conteggi negli slot 6-7. Ogni slot
dopo il primo era quindi allineato male — nella maggior parte degli eventi,
sistematicamente spostato. Il modello riceveva un vettore che assomigliava
al training set solo per caso, mai per costruzione: ogni predizione del
gate era una predizione su rumore, non su feature reali.

## Come funziona oggi

```python
from analysis_bdt.build_background_features import compute_stage1_features

class Stage1Gate:
    def accepts(self, photons, proton, beam):
        X = compute_stage1_features(photons[None], proton[None], beam[None])
        score = float(self.model.predict_proba(X)[0, 1])
        return score >= self.threshold
```

`Stage1Gate.load(model_dir)` carica `bdt_stage1.json` (il booster XGBoost) e
`stage1_threshold.txt` (la soglia operativa), poi `accepts` chiama
`compute_stage1_features` — **la stessa funzione**, non una riscrittura,
usata da `05_analysis_bdt/build_background_features.py` per costruire il
set di addestramento (vedi [Feature stage-1](05-analysis-bdt-features)). Non
esiste più una seconda implementazione che possa disallinearsi dal training:
c'è una sola funzione che sa come costruire il vettore a 24 feature, e sia
il training sia l'inferenza la chiamano.

Un test di regressione (`03_analysis/tests/test_stage1_gate.py::test_the_model_is_scored_on_the_features_it_was_trained_on`)
verifica esattamente questo: intercetta il vettore che il gate passa a
`predict_proba` e lo confronta, elemento per elemento, con una chiamata
diretta a `compute_stage1_features` sugli stessi eventi. Se qualcuno
reintroducesse una seconda implementazione — anche corretta al momento
della scrittura — questo test la scoprirebbe alla prima divergenza.

## Modello mancante: ora solleva un'eccezione

```python
if not model_path.exists():
    raise FileNotFoundError(
        f"stage-1 model not found: {model_path}. "
        "Train it with run_pipeline.sh, or use reconstruct_eta_pi0_chi2.py "
        "for the analysis without the BDT gate."
    )
```

Il vecchio codice, se non trovava il modello, stampava `"gate disabled"` e
proseguiva accettando ogni evento (`_stage1_pass` restituiva `True` quando
`_stage1_model is None`) — trasformando silenziosamente un run BDT in un
run chi2 puro. Questo rendeva impossibile fidarsi del confronto tra le due
analisi: un run etichettato "BDT" poteva in realtà non avere applicato
nessun gate, senza che nulla nell'output lo segnalasse. Oggi un modello
mancante ferma subito l'esecuzione con un errore che dice sia cosa è
mancante sia come procedere (allenare il modello, oppure usare
esplicitamente `reconstruct_eta_pi0_chi2.py` se l'assenza del gate è
intenzionale) — non c'è più una via che produca silenziosamente un risultato
diverso da quello richiesto.

## Dove andare da qui

- [Feature stage-1](05-analysis-bdt-features) — le 24 feature nell'ordine
  reale, e la regola che il bug ha lasciato: un solo punto del codice può
  costruire questo vettore.
- [BDT stage-1](05-analysis-bdt) — come il modello viene addestrato, le sue
  metriche correnti.
