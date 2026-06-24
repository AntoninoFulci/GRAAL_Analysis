# Spiegazione di `build_features.py`

Il cuore dello studio: trasforma il Monte Carlo in una **matrice di feature** `X`
e un vettore di **etichette** `y` pronti per la BDT. È il file più importante.

---

## Intestazione e costanti

```python
import numpy as np
import uproot

from analysis.ml import physics

SEED = 42
PAIRINGS = [((0, 1), (2, 3)), ((0, 2), (1, 3)), ((0, 3), (1, 2))]
PHOTON_BRANCHES = ["eta_gamma1", "eta_gamma2", "pi0_gamma1", "pi0_gamma2"]
```

- `uproot`: libreria che legge i file `.root` senza ROOT.
- `physics`: il modulo del passo precedente.
- `SEED = 42`: seme casuale fisso → risultati riproducibili.
- `PAIRINGS`: le **3 combinazioni** disgiunte dei 4 fotoni (indici di posizione).
  Es. `((0,1),(2,3))` = "fotoni 0+1 in una coppia, 2+3 nell'altra".
- `PHOTON_BRANCHES`: i nomi dei rami nel file MC. Per costruzione i primi due
  sono i fotoni dell'η, gli altri due del π⁰ (questo è il **truth**).

---

## `load_photons` — leggere i fotoni dal `.root`

```python
def load_photons(root_path, tree="mc", n_max=None):
    t = uproot.open(f"{root_path}:{tree}")
    arrays = t.arrays(PHOTON_BRANCHES, entry_stop=n_max, library="ak")
    n = len(arrays)
    out = np.empty((n, 4, 4), dtype=np.float64)
    for i, name in enumerate(PHOTON_BRANCHES):
        v = arrays[name]
        out[:, i, 0] = np.asarray(v["fE"])
        out[:, i, 1] = np.asarray(v["fP"]["fX"])
        out[:, i, 2] = np.asarray(v["fP"]["fY"])
        out[:, i, 3] = np.asarray(v["fP"]["fZ"])
    return out
```

- `uproot.open("file.root:mc")`: apre l'albero `mc`.
- `t.arrays(..., entry_stop=n_max)`: legge i 4 rami; `n_max` limita il numero di
  eventi (utile per i test veloci). `library="ak"` = formato awkward.
- `out = np.empty((n, 4, 4))`: prepara l'array di uscita: N eventi × 4 fotoni × 4
  componenti.
- Il ciclo riempie, per ogni fotone `i`, le 4 componenti. I `TLorentzVector` di
  ROOT sono salvati come record con campo energia `fE` e impulso `fP` (a sua
  volta con `fX, fY, fZ`). Quindi:
  - `out[:, i, 0] = v["fE"]` → energia
  - `out[:, i, 1..3] = v["fP"]["fX/fY/fZ"]` → px, py, pz
- Ritorna `(N, 4, 4)`. Ordine fotoni = `[η, η, π⁰, π⁰]` (truth).

---

## `load_beam` e le feature del fascio

`load_beam` legge il ramo `beam` (un `TLorentzVector` `(0,0,E,E)`) e ritorna
`(N,4)`. Il `TARGET` (protone a riposo) è una costante.

In `_feature_block`, dopo aver costruito i due mesoni, si calcola il sistema
CM `W = beam + target`, il suo boost `beta_cm = W_p3 / W_E`, e si portano i due
mesoni nel CM con `physics.boost`. Da lì:

- `cosstar_low/high` = cos(theta*), angolo polare del mesone rispetto all'asse
  del fascio (avanti/indietro);
- `pstar_low/high` = modulo dell'impulso nel CM.

Queste 4 colonne portano il blocco da 18 a 22 feature. In `build`, dopo i 3
blocchi ordinati per chi2 (66 colonne), si aggiunge **una** colonna globale
`beam_E` (energia del fascio): il vettore finale è di **67** feature. La massa
mancante *totale* non è usata perché è identica per le 3 combinazioni (somma dei
4 fotoni) e non discrimina il pairing.

---

## Nomi delle feature

```python
_BLOCK_FEATURES = [
    "m_low", "m_high", "dm_pi0", "dm_eta",
    "asym_low", "asym_high", "theta_low", "theta_high",
    "E1", "E2", "E3", "E4", "cos_mesons",
    "pt_low", "pt_high", "beta_low", "beta_high", "chi2",
    "cosstar_low", "cosstar_high", "pstar_low", "pstar_high",
]

def _feature_names():
    names = []
    for b in range(3):
        for f in _BLOCK_FEATURES:
            names.append("chi2_block{}".format(b) if f == "chi2" else "{}_block{}".format(f, b))
    names.append("beam_E")
    return names

FEATURE_NAMES = _feature_names()
```

- `_BLOCK_FEATURES`: i **22 nomi** delle feature di una singola combinazione
  (le ultime 4 sono le feature del fascio: cos(theta*) e |p*| di low/high).
- `_feature_names()`: poiché concateniamo 3 combinazioni, genera 3×22 = 66
  nomi con suffisso `_block0/1/2`, più **una** colonna globale `beam_E` in coda
  = **67** nomi totali. Servono per leggere/etichettare le colonne e per il
  grafico di feature importance.

---

## `shuffle_photons` — mescolare per non barare

```python
def shuffle_photons(photons, seed=SEED):
    rng = np.random.default_rng(seed)
    n = photons.shape[0]
    perm = np.argsort(rng.random((n, 4)), axis=1)
    P = np.take_along_axis(photons, perm[:, :, None], axis=1)
    return P, perm
```

Se lasciassimo i fotoni nell'ordine `[η, η, π⁰, π⁰]`, il modello imparerebbe la
risposta dalla **posizione**. Quindi li permutiamo a caso, per evento.

- `rng = np.random.default_rng(seed)`: generatore casuale con seme fisso.
- `perm = np.argsort(rng.random((n, 4)), axis=1)`: trucco per generare una
  permutazione casuale di `{0,1,2,3}` per ognuno degli N eventi in modo
  vettorizzato (ordinando 4 numeri casuali si ottiene un ordine casuale).
- `P = np.take_along_axis(...)`: applica la permutazione → `P[n, j]` è il fotone
  che finisce in posizione `j` dell'evento `n`.
- Ritorna sia i fotoni mescolati `P` sia la permutazione `perm` (serve per sapere
  qual era la combinazione vera).

---

## `truth_pairing_index` — qual era la combinazione giusta

```python
def truth_pairing_index(perm):
    n = perm.shape[0]
    is_eta = perm < 2  # eta photons had original index 0,1
    truth = np.full(n, -1, dtype=np.int64)
    for k, ((i, j), _) in enumerate(PAIRINGS):
        in_pair = is_eta[:, i].astype(int) + is_eta[:, j].astype(int)
        grouped = (in_pair == 2) | (in_pair == 0)
        truth = np.where(grouped & (truth < 0), k, truth)
    return truth
```

Trova, dopo il mescolamento, quale delle 3 combinazioni rimette insieme i due
fotoni dell'η.

- `is_eta = perm < 2`: maschera booleana — `True` dove la posizione contiene un
  fotone dell'η (indice originale 0 o 1).
- `truth = -1`: inizializza a "non ancora trovato".
- Per ogni combinazione `k`, guarda la **prima coppia** `(i, j)`:
  - `in_pair`: quanti fotoni dell'η ci sono in quella coppia (0, 1 o 2).
  - `grouped = (in_pair == 2) | (in_pair == 0)`: la combinazione è quella giusta
    se i due fotoni dell'η stanno **entrambi** nella prima coppia (==2) oppure
    **entrambi** nell'altra (==0, cioè la prima coppia è tutta π⁰).
  - `np.where(grouped & (truth<0), k, truth)`: assegna `k` agli eventi che hanno
    fatto match e non erano già stati assegnati.
- Risultato: per ogni evento, l'indice (0/1/2) della combinazione vera.

---

## `_feature_block` — le 22 feature di una combinazione

```python
def _feature_block(P, pairing):
    (i, j), (k, l) = pairing
    mA = physics.invariant_mass(P[:, i], P[:, j])
    mB = physics.invariant_mass(P[:, k], P[:, l])
    a_low = mA <= mB

    def sel(a, b):
        return np.where(a_low, a, b)
```

- Spacchetta gli indici delle due coppie.
- `mA, mB`: masse invarianti delle due coppie.
- `a_low = mA <= mB`: maschera — `True` dove la coppia A è la più leggera.
- `sel(a, b)`: helper che sceglie `a` dove la coppia A è leggera, altrimenti `b`.
  Serve per assegnare ogni quantità alla coppia "low" (π⁰-like) o "high"
  (η-like) **in modo coerente**, eliminando l'ambiguità di quale coppia venga
  prima.

```python
    asymA = physics.energy_asymmetry(P[:, i], P[:, j])
    asymB = physics.energy_asymmetry(P[:, k], P[:, l])
    thA = physics.opening_angle(P[:, i], P[:, j])
    thB = physics.opening_angle(P[:, k], P[:, l])
    mesonA = P[:, i] + P[:, j]
    mesonB = P[:, k] + P[:, l]
    ptA, ptB = physics.pt(mesonA), physics.pt(mesonB)
    beA, beB = physics.beta(mesonA), physics.beta(mesonB)
```

Calcola, per ciascuna delle due coppie: asimmetria energetica, angolo di
apertura, e (sui mesoni ricostruiti = somma dei due fotoni) impulso trasverso e
boost β.

```python
    m_low, m_high = np.minimum(mA, mB), np.maximum(mA, mB)
    asym_low, asym_high = sel(asymA, asymB), sel(asymB, asymA)
    th_low, th_high = sel(thA, thB), sel(thB, thA)
    pt_low, pt_high = sel(ptA, ptB), sel(ptB, ptA)
    be_low, be_high = sel(beA, beB), sel(beB, beA)
    cos_mes = physics.cos_angle(mesonA, mesonB)
    chi2 = physics.chi2_pairing(m_low, m_high)
    e_sorted = np.sort(P[:, :, 0], axis=1)[:, ::-1]  # (N,4) energies desc
```

- Ordina tutte le quantità in "low"/"high" usando `sel` (e `min`/`max` per le
  masse).
- `cos_mes`: coseno dell'angolo tra i due mesoni.
- `chi2`: il χ² della combinazione (low↔π⁰, high↔η).
- `e_sorted`: le 4 energie dei fotoni ordinate dalla più grande alla più piccola
  (`[:, ::-1]` inverte l'ordine crescente di `np.sort`).

```python
    block = np.column_stack([
        m_low, m_high, np.abs(m_low - physics.MPI0), np.abs(m_high - physics.META),
        asym_low, asym_high, th_low, th_high,
        e_sorted[:, 0], e_sorted[:, 1], e_sorted[:, 2], e_sorted[:, 3], cos_mes,
        pt_low, pt_high, be_low, be_high, chi2,
        cosstar_low, cosstar_high, pstar_low, pstar_high,
    ])
    return block, chi2, m_low, m_high
```

- `np.column_stack`: impila le 22 quantità come 22 colonne → matrice `(N, 22)`.
  L'ordine corrisponde esattamente a `_BLOCK_FEATURES`. Le ultime 4 (cos(theta*)
  e |p*| di low/high) vengono dal boost nel sistema CM (vedi sezione fascio).
- Ritorna il blocco, più χ², m_low, m_high separati (servono dopo per
  l'ordinamento e per gli spettri di massa).

---

## `build` — assemblaggio finale + etichette

```python
def build(photons, beam, seed=SEED):
    P, perm = shuffle_photons(photons, seed=seed)
    n = P.shape[0]
    blocks, chi2s, masses = [], [], []
    for pairing in PAIRINGS:
        blk, c, ml, mh = _feature_block(P, pairing, beam)
        blocks.append(blk)
        chi2s.append(c)
        masses.append(np.column_stack([ml, mh]))  # (N,2): [pi0-ish, eta-ish]
    blocks = np.stack(blocks, axis=1)   # (N,3,22)
    chi2s = np.stack(chi2s, axis=1)     # (N,3)
    masses = np.stack(masses, axis=1)   # (N,3,2)
```

- Mescola i fotoni una volta.
- Per ognuna delle 3 combinazioni calcola il blocco di feature, il suo χ², e le
  masse (low, high).
- `np.stack(..., axis=1)`: impila lungo un nuovo asse → `blocks` ha forma
  `(N, 3, 22)` (N eventi, 3 combinazioni, 22 feature); `chi2s` `(N, 3)`;
  `masses` `(N, 3, 2)`.

```python
    order = np.argsort(chi2s, axis=1)   # (N,3) ascending chi2
    rows = np.arange(n)[:, None]
    blocks_ord = blocks[rows, order]    # (N,3,22)
    masses_ord = masses[rows, order]    # (N,3,2)
    X = np.column_stack([blocks_ord.reshape(n, -1), beam[:, 0]])  # (N,67)
```

**L'idea chiave.**

- `order = np.argsort(chi2s, axis=1)`: per ogni evento, l'ordine delle 3
  combinazioni dal χ² più piccolo al più grande.
- `blocks[rows, order]`: riordina i blocchi secondo `order` → il **blocco 0 è
  sempre la combinazione col χ² minimo** (= la scelta del metodo classico).
- `X = np.column_stack([blocks_ord.reshape(n, -1), beam[:, 0]])`: appiattisce
  `(N, 3, 22)` in `(N, 66)` e aggiunge in coda la colonna globale `beam_E` →
  `(N, 67)`: una riga per evento, 67 colonne (3 blocchi + beam_E).

```python
    truth = truth_pairing_index(perm)
    y = np.argmax(order == truth[:, None], axis=1).astype(np.int64)  # slot of truth
    return X, y, masses_ord, FEATURE_NAMES
```

- `truth`: indice della combinazione vera (0/1/2 nello spazio `PAIRINGS`).
- `order == truth[:, None]`: trova **in quale posizione** (dopo l'ordinamento per
  χ²) è finita la combinazione vera; `argmax` ne dà l'indice (0, 1 o 2).
- Quindi `y` = "in quale blocco ordinato sta la verità". Conseguenza:
  - `y == 0` → la verità coincide con la scelta del χ² (caso più frequente).
  - `y == 1 o 2` → il χ² ha sbagliato; la BDT dovrebbe correggere.
- L'accuratezza del χ² è quindi semplicemente la frazione di eventi con `y == 0`.

Ritorna `X` (feature), `y` (etichette), `masses_ord` (masse per fare gli spettri)
e i nomi delle feature.

---

## `main` — interfaccia da riga di comando

```python
def main():
    import argparse
    ap = argparse.ArgumentParser(description="Build features.npz from MC")
    ap.add_argument("--input", default="simulation/eta_pi0_mc.root")
    ap.add_argument("--output", default="analysis/ml/data/features.npz")
    ap.add_argument("--n-max", type=int, default=None)
    ap.add_argument("--seed", type=int, default=SEED)
    args = ap.parse_args()

    print(f"Loading photons from {args.input} ...")
    photons = load_photons(args.input, n_max=args.n_max)
    print(f"Loaded {len(photons)} events; building features ...")
    X, y, masses, names = build(photons, seed=args.seed)
    np.savez_compressed(args.output, X=X, y=y, masses=masses,
                        feature_names=np.array(names))
    frac = np.bincount(y, minlength=3) / len(y)
    print(f"Wrote {args.output}: X={X.shape}, label fractions={frac.round(3)}")
    print(f"chi2 baseline accuracy (label==0): {frac[0]:.4f}")
```

- `argparse`: definisce le opzioni da riga di comando (file in/out, `--n-max`,
  `--seed`) con valori di default.
- Carica i fotoni, costruisce le feature, salva tutto in un `.npz` compresso.
- `frac = np.bincount(y)/len(y)`: la frazione di eventi per classe; stampa anche
  l'accuratezza del χ² (frazione con `y==0`).

```python
if __name__ == "__main__":
    main()
```

Esegue `main()` solo se il file è lanciato direttamente
(`python -m analysis.ml.build_features`), non quando viene importato dai test.
