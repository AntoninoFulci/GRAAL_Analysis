# Feature stage-1

`04_bdt_training/build_background_features.py::compute_stage1_features` calcola il vettore a 26 feature che il BDT stage-1 vede, sia in training sia in inferenza. 
Questa pagina elenca le 26 feature nell'ordine reale del codice e registra la regola che il bug del gate (vedi [Gate BDT](05-reconstruction-bdt-gate)) ha lasciato dietro di sé.

## `feature_names(hypothesis)`, nell'ordine

Cinque nomi su 26 dipendono dall'**ipotesi**: quali due mesoni i 4 fotoni stanno venendo testati contro.
Non è una proprietà dell'evento, è la domanda che gli si fa, e cambia con `--signal-channel`.
Sotto, i nomi per l'ipotesi di default `eta_pi0`; con `2pi0` le stesse posizioni diventano `n_pairs_near_pi0_2`, `n_pairs_near_pi0_1`, `best_chi2_2pi0`.
Il nome si porta dietro l'ipotesi proprio perché non vada ricordata a mente.

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
        # kinematics of the chi2-best pairing's two meson candidates
        f"{hypothesis.heavy_label}_E_asym",
        f"{hypothesis.heavy_label}_{hypothesis.light_label}_angle",
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
| 24-25 | 2 cinematiche dei candidati mesoni | `eta_E_asym` (asimmetria di energia normalizzata \|E₁−E₂\|/(E₁+E₂) della coppia η candidata), `eta_pi0_angle` (coseno dell'angolo lab fra i due mesoni ricostruiti) — entrambe sul pairing a chi2 minimo |