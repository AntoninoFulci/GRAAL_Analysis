# Feature stage-1

`05_analysis_bdt/build_background_features.py::compute_stage1_features`
calcola il vettore a 24 feature che il BDT stage-1 vede, sia in training sia
in inferenza. Questa pagina elenca le 24 feature nell'ordine reale del
codice e registra la regola che il bug del gate (vedi
[Gate BDT](03-analysis-bdt-gate)) ha lasciato dietro di sé.

## `FEATURE_NAMES_S1`, nell'ordine

```python
FEATURE_NAMES_S1: list[str] = [
    # C(4,2)=6 invariant masses
    "m_gg_01", "m_gg_02", "m_gg_03",
    "m_gg_12", "m_gg_13",
    "m_gg_23",
    # pair counts near meson poles
    "n_pairs_near_pi0",     # |m_gg - 0.135| < 0.040 GeV
    "n_pairs_near_eta",     # |m_gg - 0.548| < 0.080 GeV
    # best chi2 for any assignment of 4γ to η+π⁰
    "best_chi2_eta_pi0",
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
4 fotoni per evento, mai di più — e restituisce `(N, 24)` in `float32`. Un
`assert len(FEATURE_NAMES_S1) == 24` nel modulo tiene la lista dei nomi e la
lunghezza reale del vettore sincronizzate.

## La regola che il bug ha prodotto

Il vecchio `reconstruct_eta_pi0.py` costruiva un secondo vettore a 24
feature a mano, con un layout diverso (impacchettava fino a 15 masse di
coppia negli slot 0-14, invece delle 6 reali negli slot 0-5), e il modello
finiva per essere interrogato su rumore — vedi
[Gate BDT](03-analysis-bdt-gate) per la cronologia completa. La riparazione
non è stata correggere quella seconda implementazione: è stata eliminarla.

**`compute_stage1_features` è l'unico punto del codice in cui un vettore di
feature stage-1 può essere costruito.** Sia `build_background_features.py`
(che costruisce il set di addestramento da MC, vedi
[BDT stage-1](05-analysis-bdt)) sia `stage1_gate.py` (che costruisce il
vettore per un evento in inferenza, vedi [Gate BDT](03-analysis-bdt-gate))
chiamano questa stessa funzione. Non deve mai esistere una seconda
implementazione, nemmeno temporanea o "equivalente": è esattamente quello
che ha reso invisibile il bug la prima volta — le due implementazioni
sembravano fare la stessa cosa finché nessuno le ha confrontate numero per
numero. Il test di regressione in
`03_analysis/tests/test_stage1_gate.py` esiste per rendere impossibile
ripetere l'errore senza che un test fallisca.
