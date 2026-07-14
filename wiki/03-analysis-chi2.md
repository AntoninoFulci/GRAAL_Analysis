# Ricostruzione chi2

La fisica della combinatoria vive interamente in `03_analysis/reco_physics.py`
— funzioni pure su array numpy, senza ROOT (vedi [Testing](testing) per il
perché). Questa pagina segue quel file riga per riga.

## Il problema: quattro fotoni, due mesoni

η→γγ e π⁰→γγ danno quattro fotoni nello stato finale. Dati quattro fotoni
etichettati 0-3, ci sono tre modi di dividerli in due coppie disgiunte:
(01|23), (02|13), (03|12). Per ciascuna divisione, quale coppia è l'η e
quale il π⁰ è una seconda domanda. La tabella delle combinazioni codifica
entrambe le scelte.

## La tabella delle combinazioni

`03_analysis/data/combinations_eta_pi0.txt`, sei righe, colonne `[i1, i2,
i3, i4, m_tgt_12, m_tgt_34]`:

```
0 1 2 3 0.547862 0.134977
0 1 2 3 0.134977 0.547862
0 2 1 3 0.547862 0.134977
0 2 1 3 0.134977 0.547862
0 3 1 2 0.547862 0.134977
0 3 1 2 0.134977 0.547862
```

Tre divisioni × due assegnazioni (quale coppia punta alla massa dell'η,
quale a quella del π⁰) = sei righe. Gli indici dei fotoni sono sempre 0-3:
`run_reconstruction` richiede almeno 4 fotoni ricostruiti proprio perché la
tabella non referenzia mai un quinto fotone, anche quando l'evento ne ha
di più.

## La formula del chi2

```python
CHI2_RESOLUTION = 0.08  # 8% della massa target

def chi2_value(m_meas_1, m_tgt_1, m_meas_2, m_tgt_2):
    d1 = (m_meas_1 - m_tgt_1) / (m_tgt_1 * CHI2_RESOLUTION)
    d2 = (m_meas_2 - m_tgt_2) / (m_tgt_2 * CHI2_RESOLUTION)
    return d1**2 + d2**2
```

Per ciascuna delle sei righe, `best_combination` calcola la massa invariante
delle due coppie di fotoni indicate dalla riga, il chi2 contro le due masse
target della riga, e tiene la riga con il chi2 più basso:

```python
M_PI0 = 0.134977
M_ETA = 0.547862
```

La risoluzione dell'8% è applicata alla massa target, non a quella
misurata — è il denominatore di normalizzazione dello scarto, non un errore
di misura calcolato evento per evento.

## Assegnazione η/π⁰: la soglia di 0.4 GeV

Una volta scelta la riga migliore, `assign_pairs` decide quale delle due
coppie è il mesone "heavy" (η nel canale η+π⁰) e quale "light" (π⁰):

```python
HEAVY_MASS_THRESHOLD = 0.4

if channel.split_by_target_mass and float(row[4]) <= HEAVY_MASS_THRESHOLD:
    return pair_b, pair_a
return pair_a, pair_b
```

`row[4]` è la massa target della prima coppia della riga vincente
(`m_tgt_12`). Se è ≤ 0.4 GeV — cioè se la prima coppia era quella puntata
al π⁰ (0.134977) e non all'η (0.547862) — le coppie vengono scambiate:
la prima coppia della riga (`pair_a`) diventa il mesone "light" e la
seconda (`pair_b`) il mesone "heavy". La soglia di 0.4 GeV siede a metà
strada tra le due masse nominali (0.135 e 0.548 GeV), con ampio margine da
entrambe le parti.

Il canale 2π⁰ (`TWO_PI0`, `split_by_target_mass=False`) non usa questa
logica: le due coppie mantengono l'ordine che dà loro la tabella
(`combinations_2pi0.txt`), perché non c'è un'ambiguità η/π⁰ da risolvere —
sono entrambi π⁰.

## Il taglio chi2 < 10

```python
idx, chi2_val = rp.best_combination(photons, combinations)
chi2[0] = chi2_val
if chi2_val >= cfg.chi2_cut:
    continue
```

`cfg.chi2_cut` di default è `10.0` (configurabile via `--chi2-cut` su
entrambi gli entrypoint `reconstruct_eta_pi0_*`). Un evento la cui migliore
combinazione ha chi2 ≥ 10 non viene scritto nell'albero di output — non
solo la combinazione peggiore viene scartata, l'intero evento lo è.

## Il quadrimomento mancante

```python
target = ROOT.TLorentzVector(0.0, 0.0, 0.0, rp.M_PROTON)  # protone bersaglio, fermo
...
missing_v = (beam + target) - (heavy + light)
```

`missing` è il quadrimomento non misurato direttamente: fascio più bersaglio
(protone fermo, massa `M_PROTON = 0.938272`) meno la somma dei due mesoni
ricostruiti. Non compare il protone di rinculo ricostruito in questa
sottrazione — `missing` misura cosa manca rispetto a fascio+bersaglio, non
rispetto a fascio+bersaglio-protone; il protone di rinculo è scritto come
ramo a parte (`proton`) per confronto.

## Rami di output

Vedi [Formati dati](data-formats) per lo schema completo di
`reco_eta_pi0_chi2` / `reco_eta_pi0_bdt`, identico nei due file tranne per
quali eventi sopravvivono.
