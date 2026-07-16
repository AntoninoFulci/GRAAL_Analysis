# Feature stage-1

`04_bdt_training/build_background_features.py::compute_stage1_features`
calcola il vettore a 24 feature che il BDT stage-1 vede, sia in training sia
in inferenza. Questa pagina elenca le 24 feature nell'ordine reale del
codice e registra la regola che il bug del gate (vedi
[Gate BDT](05-reconstruction-bdt-gate)) ha lasciato dietro di sé.

## `feature_names(hypothesis)`, nell'ordine

Tre nomi su 24 dipendono dall'**ipotesi**: quali due mesoni i 4 fotoni stanno
venendo testati contro. Non è una proprietà dell'evento, è la domanda che gli
si fa, e cambia con `--signal-channel`. Sotto, i nomi per l'ipotesi di default
`eta_pi0`; con `2pi0` le stesse posizioni diventano `n_pairs_near_pi0_2`,
`n_pairs_near_pi0_1`, `best_chi2_2pi0`. Il nome si porta dietro l'ipotesi
proprio perché non vada ricordata a mente.

```python
def feature_names(hypothesis: Hypothesis = ETA_PI0_HYP) -> list[str]:
    names = [
        # C(4,2)=6 invariant masses
        "m_gg_01", "m_gg_02", "m_gg_03",
        "m_gg_12", "m_gg_13",
        "m_gg_23",
        # pair counts near the two mass poles
        f"n_pairs_near_{hypothesis.light_label}",   # |m_gg - 0.135| < 0.040 GeV
        f"n_pairs_near_{hypothesis.heavy_label}",   # |m_gg - 0.548| < 0.080 GeV
        # best chi2 for any assignment of the 4 photons to the two mesons
        f"best_chi2_{hypothesis.name}",
        # missing kinematics  (beam + target − proton)
        "missing_mass",
        "missing_E",
        "missing_pz",
        "missing_pt",
        # photon energy statistics
        "total_gamma_E",
        "beam_E",
        "max_gamma_E",
        "min_gamma_E",
        "gamma_E_rms",          # rms spread of photon energies
        # photon angular statistics
        "sum_opening_angles",   # sum of all 6 opening angles
        "min_pair_mass",
        "max_pair_mass",
        "total_pt_gamma",       # scalar sum of photon pT
        # proton
        "proton_p",
        "proton_costheta",
    ]
    assert len(names) == N_FEATURES_S1
    return names
```

Raggruppate come le raggruppa il codice:

| Slot | Gruppo | Feature |
|---|---|---|
| 0-5 | 6 masse invariante di coppia | `m_gg_01`, `m_gg_02`, `m_gg_03`, `m_gg_12`, `m_gg_13`, `m_gg_23` — tutte le `C(4,2)=6` coppie dei 4 fotoni |
| 6-7 | 2 conteggi di coppie | `n_pairs_near_pi0` (\|m − 0.135\| < 0.040 GeV), `n_pairs_near_eta` (\|m − 0.548\| < 0.080 GeV) |
| 8 | miglior chi2 | `best_chi2_eta_pi0` — il minimo su tutte e 3 le partizioni disgiunte dei 4 fotoni, provando entrambe le assegnazioni η/π⁰ per ciascuna |
| 9-12 | 4 valori di cinematica mancante | `missing_mass`, `missing_E`, `missing_pz`, `missing_pt` — da `(beam + target) − proton` |
| 13-17 | statistiche di energia dei fotoni | `total_gamma_E`, `beam_E`, `max_gamma_E`, `min_gamma_E`, `gamma_E_rms` |
| 18-21 | statistiche angolari dei fotoni | `sum_opening_angles` (somma dei 6 angoli di apertura), `min_pair_mass`, `max_pair_mass`, `total_pt_gamma` |
| 22-23 | 2 valori di cinematica del protone | `proton_p`, `proton_costheta` |

`compute_stage1_features` è vettorizzata (nessun ciclo Python sugli eventi):
prende `photons (N,4,4)`, `proton (N,4)`, `beam (N,4)` — sempre esattamente
4 fotoni per evento, mai di più — e restituisce `(N, 24)` in `float32`. Prende
anche l'ipotesi, che di default è `eta_pi0`. L'`assert` dentro `feature_names`
tiene la lista dei nomi e la lunghezza reale del vettore sincronizzate.

Quale ipotesi un modello abbia visto non è lasciato alla memoria di nessuno: il
training la scrive in `model/stage1_provenance.json`, e `Stage1Gate` la rilegge
per costruire le sue feature attorno agli stessi due mesoni. Se la
ricostruzione gli chiede di filtrare uno stato finale diverso, il gate si
rifiuta invece di rispondere: un modello trainato a cercare η+π⁰ restituisce
comunque un punteggio per ogni evento di qualunque canale, e quel punteggio
diventerebbe silenziosamente la differenza fra l'analisi chi2 e quella con il
gate — cioè esattamente la cosa che il confronto sta misurando.

## La regola che il bug ha prodotto

Il vecchio `reconstruct_eta_pi0.py` costruiva un secondo vettore a 24
feature a mano, con un layout diverso (impacchettava fino a 15 masse di
coppia negli slot 0-14, invece delle 6 reali negli slot 0-5), e il modello
finiva per essere interrogato su rumore — vedi
[Gate BDT](05-reconstruction-bdt-gate) per la cronologia completa. La riparazione
non è stata correggere quella seconda implementazione: è stata eliminarla.

**`compute_stage1_features` è l'unico punto del codice in cui un vettore di
feature stage-1 può essere costruito.** Sia `build_background_features.py`
(che costruisce il set di addestramento da MC, vedi
[BDT stage-1](04-bdt-training)) sia `stage1_gate.py` (che costruisce il
vettore per un evento in inferenza, vedi [Gate BDT](05-reconstruction-bdt-gate))
chiamano questa stessa funzione. Non deve mai esistere una seconda
implementazione, nemmeno temporanea o "equivalente": è esattamente quello
che ha reso invisibile il bug la prima volta — le due implementazioni
sembravano fare la stessa cosa finché nessuno le ha confrontate numero per
numero. Il test di regressione in
`05_reconstruction/tests/test_stage1_gate.py` esiste per rendere impossibile
ripetere l'errore senza che un test fallisca.
