# Gate BDT

`05_reconstruction/stage1_gate.py` è il filtro che `reconstruct_eta_pi0_bdt.py` applica a ogni evento prima della combinatoria chi2: un classificatore BDT (stage-1, vedi [BDT stage-1](04-bdt-training)) addestrato a distinguere il segnale dal fondo. 

## Come funziona

```python
from bdt_training.build_background_features import compute_stage1_features

class Stage1Gate:
    def accepts_many(self, photons, protons, beams):
        X = compute_stage1_features(photons, protons, beams, self.hypothesis)
        scores = self.model.predict_proba(X)[:, 1]
        return scores >= self.threshold
```

`Stage1Gate.load(model_dir)` carica `bdt_stage1.json` (il booster XGBoost) e `stage1_threshold.txt` (la soglia operativa), poi `accepts_many` chiama `compute_stage1_features` — **la stessa funzione**, non una riscrittura, usata da `04_bdt_training/build_background_features.py` per costruire il set di addestramento (vedi [Feature stage-1](04-bdt-training-features)).

### Perché a blocchi e non evento per evento

Il gate ML è stato ottimizzato passando da una valutazione evento per evento a una valutazione **a blocchi da 20.000 eventi**. La versione precedente introduceva un forte overhead dovuto alle milioni di chiamate separate al modello (**0,335 ms/evento**), che su 17 milioni di eventi rappresentavano circa **75 degli 85 minuti** totali.

Il batching permette a NumPy e XGBoost di lavorare in modo vettoriale, riducendo il tempo di esecuzione di circa **300 volte**, senza modificare la logica di selezione degli eventi.

La correttezza è stata verificata: l'output è **bit-per-bit identico** alla versione evento per evento e un test di regressione garantisce che il modello riceva sempre le stesse feature usate durante l'addestramento.


## Dopo il gate: il fit cinematico

Gli eventi che superano il gate e l'accoppiamento chi2 passano poi dal fit cinematico 6C, che gira sui sopravvissuti e la cui confidence level — non più la massa mancante — seleziona l'evento finale. Vedi
[Fit cinematico](05-reconstruction-kinematic-fit).