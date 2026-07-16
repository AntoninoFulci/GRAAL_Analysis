# Ricostruzione chi2

La fisica della combinatoria vive interamente in `00_common/pairing.py` —
funzioni pure su array numpy, senza ROOT (vedi [Testing](testing) per il
perché). Sta in `00_common/` e non in `03_analysis/` perché non è solo della
ricostruzione: è **lo stesso chi2** che il BDT riceve come feature 8. Erano due
implementazioni separate — un ciclo guidato da tabella di qua, un'espressione
vettorizzata di là — che concordavano a ispezione ed erano libere di divergere.

## Il problema: quattro fotoni, due mesoni

η→γγ e π⁰→γγ danno quattro fotoni nello stato finale. Dati quattro fotoni
etichettati 0-3, ci sono tre modi di dividerli in due coppie disgiunte:
(01|23), (02|13), (03|12). Per ciascuna divisione, quale coppia è l'η e
quale il π⁰ è una seconda domanda.

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

Tre divisioni × due assegnazioni = sei accoppiamenti per η+π⁰; tre per 2π⁰,
dove scambiare "heavy" e "light" rietichetta le coppie senza porre una domanda
diversa.

Questo elenco **stava su disco**, in `03_analysis/data/combinations_eta_pi0.txt`:

```
0 1 2 3 0.547862 0.134977
0 1 2 3 0.134977 0.547862
0 2 1 3 0.547862 0.134977
...
```

Quel file non conteneva informazione: ogni riga era derivabile dall'ipotesi, e
duplicava le masse dei mesoni dentro un file dove erano libere di divergere dal
registry. È stato cancellato — dopo aver verificato che `pairings()` riproduce
tutte e nove le righe dei due file, in ordine — e con lui il requisito che un
canale avesse un file su disco per poter essere ricostruito: un'ipotesi nuova
ora si ricostruisce senza che nessuno le scriva prima una tabella.

Gli indici dei fotoni sono sempre 0-3:
`run_reconstruction` richiede almeno 4 fotoni ricostruiti proprio perché la
tabella non referenzia mai un quinto fotone, anche quando l'evento ne ha
di più.

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

Le masse target vengono dall'**ipotesi**, non da due colonne di una riga:
`best_pairing` calcola le sei masse di coppia una volta sola, punteggia ogni
accoppiamento e tiene quello col chi2 più basso. La stessa funzione, con
`.min()` al posto di `argmin`, è la feature 8 del BDT.

La risoluzione dell'8% è applicata alla massa target, non a quella misurata —
è il denominatore di normalizzazione dello scarto, non un errore di misura
calcolato evento per evento.

## Assegnazione η/π⁰

```python
@dataclass(frozen=True)
class Pairing:
    heavy: tuple[int, int]
    light: tuple[int, int]
```

Quale coppia sia l'η non è più una domanda separata da porre dopo. Ogni
accoppiamento *è già* l'assegnazione: `pairings()` costruisce entrambe le
alternative, il chi2 le punteggia, e quella vincente dice direttamente quali
fotoni sono il mesone pesante. Prima l'informazione stava nell'ordine delle
colonne della tabella e andava recuperata a posteriori confrontando `row[4]`
con una soglia a 0.4 GeV, scelta a metà fra le due masse nominali — un numero
scritto a mano che descriveva le masse invece di venirne.

Per 2π⁰ la degenerazione la fa `hypothesis.is_degenerate`, non una flag: i due
mesoni sono lo stesso, quindi non c'è un pesante da promuovere.

## Il taglio chi2 < 10

```python
pairing, chi2_val = pr.best_pairing(photons, channel.hypothesis)
chi2[0] = chi2_val
if chi2_val >= cfg.chi2_cut:
    return
```

`cfg.chi2_cut` di default è `10.0` (configurabile via `--chi2-cut` su
entrambi gli entrypoint `reconstruct_eta_pi0_*`). Un evento la cui migliore
combinazione ha chi2 ≥ 10 non viene scritto nell'albero di output — non
solo la combinazione peggiore viene scartata, l'intero evento lo è.

## Il taglio degli eventi impossibili

```python
if heavy.E() > beam.E() or light.E() > beam.E():
    n_impossible += 1
    return
```

Il bersaglio è un protone fermo: contribuisce la sua massa e nessun impulso.
Quindi nessuno dei due mesoni può portarsi via più energia di quanta il fotone
di fascio ne abbia portata dentro. Un evento che dice il contrario non è un
evento misurato male, è un evento **sbagliato** — quasi sempre il tagger che
associa al trigger il fotone di fascio sbagliato. Né il chi2 né il gate BDT
possono ripararlo, perché entrambi guardano i fotoni e il protone e mai quella
associazione.

Il taglio sta dentro il percorso condiviso da entrambi i run, così le due
analisi perdono esattamente gli stessi eventi e l'unica differenza fra loro
resta il gate. Il conteggio è stampato a fine run.

Il limite cinematico del Dalitz (M(ηp) oltre W − m_π⁰) è invece **contato e non
tagliato**: quella coda è in gran parte risoluzione al bordo, non eventi
impossibili.

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
