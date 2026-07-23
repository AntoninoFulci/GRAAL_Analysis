# Ricostruzione chi2

La fisica della combinatoria vive interamente in `00_common/pairing.py` funzioni su array numpy.
Sta in `00_common/` e non in `05_reconstruction/` perché non è solo della ricostruzione: è **lo stesso chi2** che il BDT riceve come feature 8.

## Il problema: quattro fotoni, due mesoni

η→γγ e π⁰→γγ danno quattro fotoni nello stato finale. Dati quattro fotoni etichettati 0-3, ci sono tre modi di dividerli in due coppie disgiunte: (01|23), (02|13), (03|12). Per ciascuna divisione, quale coppia è l'η e quale il π⁰ è una seconda domanda.

## Gli accoppiamenti sono derivati, non elencati

`pairings(hypothesis)` genera entrambe le scelte:

```python
def pairings(hypothesis: Hypothesis) -> list[Pairing]:
    out = []
    for a, b in PARTITIONS:                  # (01|23), (02|13), (03|12)
        out.append(Pairing(heavy=a, light=b))
        if not hypothesis.is_degenerate:
            out.append(Pairing(heavy=b, light=a))
    return out
```

Tre divisioni × due assegnazioni = sei accoppiamenti per η+π⁰; tre per 2π⁰, dove scambiare "heavy" e "light" rietichetta le coppie senza porre una domanda diversa.

## La formula del chi2

```python
CHI2_RESOLUTION = 0.08  # 8% della massa target

def chi2(m_heavy_measured, m_light_measured, hypothesis):
    d_heavy = (m_heavy_measured - hypothesis.heavy_mass) / (
        CHI2_RESOLUTION * hypothesis.heavy_mass
    )
    d_light = (m_light_measured - hypothesis.light_mass) / (
        CHI2_RESOLUTION * hypothesis.light_mass
    )
    return d_heavy**2 + d_light**2
```

Le masse target vengono dall'**ipotesi**, non da due colonne di una riga: `best_pairing` calcola le sei masse di coppia una volta sola, punteggia ogni accoppiamento e tiene quello col chi2 più basso. La stessa funzione, con `.min()` al posto di `argmin`, è la feature 8 del BDT.

La risoluzione dell'8% è applicata alla massa target, non a quella misurata — è il denominatore di normalizzazione dello scarto, non un errore di misura calcolato evento per evento.

## Assegnazione η/π⁰

```python
@dataclass(frozen=True)
class Pairing:
    heavy: tuple[int, int]
    light: tuple[int, int]
```

L'assegnazione della coppia η non viene più determinata con un controllo separato a posteriori: ogni possibile accoppiamento viene già costruito da `pairings()`, valutato tramite chi2 e la soluzione migliore identifica direttamente i fotoni associati al mesone pesante.

Prima questa informazione era ricavata dall'ordine delle colonne e da una soglia fissa sulla massa (**0,4 GeV**), un valore scelto manualmente. Ora l'assegnazione deriva direttamente dalla minimizzazione del chi2.


## Il taglio chi2 < 10

```python
pairing, chi2_val = pr.best_pairing(photons, channel.hypothesis)
chi2[0] = chi2_val
if chi2_val >= cfg.chi2_cut:
    return
```

`cfg.chi2_cut` di default è `10.0` (configurabile via `--chi2-cut` su entrambi gli entrypoint `reconstruct_eta_pi0_*`). Un evento la cui migliore combinazione ha chi2 ≥ 10 non viene scritto nell'albero di output — non solo la combinazione peggiore viene scartata, l'intero evento lo è.

## Il taglio degli eventi impossibili

```python
if heavy.E() > beam.E() or light.E() > beam.E():
    n_impossible += 1
    return
```

È stato introdotto un taglio sugli eventi cinematicamente impossibili: un mesone non può avere un'energia superiore a quella del fotone di fascio incidente.

Questi eventi non sono recuperabili né dal chi² né dal gate BDT, perché il problema deriva dall'associazione errata del fotone di fascio al trigger, non dalla ricostruzione dei fotoni o del protone.

Il taglio è applicato nel percorso comune a entrambi i run, garantendo che le due analisi differiscano solo per il gate applicato. Gli eventi rimossi vengono inoltre conteggiati a fine run.

Il limite cinematico del Dalitz non viene invece tagliato, ma solo monitorato, perché la coda osservata è principalmente dovuta alla risoluzione sperimentale vicino al bordo cinematico.


## Il quadrimomento mancante

```python
target = ROOT.TLorentzVector(0.0, 0.0, 0.0, rp.M_PROTON)  # protone bersaglio, fermo
...
missing_v = (beam + target) - (heavy + light)
```

`missing` rappresenta il quadrimpulso mancante, calcolato come differenza tra il sistema iniziale (**fotone di fascio + protone bersaglio fermo**) e la somma dei due mesoni ricostruiti.

Il protone di rinculo ricostruito non entra nel calcolo: viene salvato separatamente nel ramo `proton` per il confronto. Quindi `missing` indica ciò che manca rispetto allo stato iniziale, non rispetto a un sistema che include già il protone ricostruito.


## Rami di output

Vedi [Formati dati](data-formats) per lo schema completo di
`reco_eta_pi0_chi2` / `reco_eta_pi0_bdt`, identico nei due file tranne per
quali eventi sopravvivono.
