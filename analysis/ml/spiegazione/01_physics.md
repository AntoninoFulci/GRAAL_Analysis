# Spiegazione di `physics.py`

Modulo di **matematica dei quadrivettori**, scritto in forma *vettorizzata*:
ogni funzione lavora su array numpy la cui ultima dimensione è `[E, px, py, pz]`,
e si applica in un colpo solo a milioni di eventi (nessun ciclo `for`).

Convenzione: un quadrivettore è `[E, px, py, pz]` (energia, poi le 3 componenti
dell'impulso). Un array di forma `(N, 4)` sono N quadrivettori; `(N, 4, 4)` sono
N eventi × 4 fotoni × 4 componenti.

---

```python
import numpy as np

MPI0 = 0.134977
META = 0.547862
CHI2_RES = 0.08  # fractional mass resolution used by the baseline chi2
```

- `MPI0`, `META`: masse nominali (PDG) del π⁰ e dell'η, in GeV.
- `CHI2_RES = 0.08`: risoluzione di massa dell'8% usata nel χ² (cioè σ ≈ 8% della
  massa). È lo stesso valore del metodo classico in `reconstruct_eta_pi0.py`.

---

```python
def _p3(v):
    return v[..., 1:4]
```

Helper privato (underscore = "uso interno"). Estrae la **parte spaziale**
dell'impulso `(px, py, pz)`, scartando l'energia. `v[..., 1:4]` significa: su
qualunque numero di dimensioni iniziali (`...`), prendi gli indici 1,2,3
dell'ultimo asse. Funziona sia su un singolo vettore sia su array enormi.

---

```python
def invariant_mass(a, b):
    s = a + b
    e = s[..., 0]
    p2 = np.sum(s[..., 1:4] ** 2, axis=-1)
    m2 = e * e - p2
    return np.sqrt(np.clip(m2, 0.0, None))
```

Massa invariante della coppia di quadrivettori `a` e `b`. Formula fisica:
m² = E² − |p|², con E e p del sistema somma.

- `s = a + b`: somma i due quadrivettori (componente per componente).
- `e = s[..., 0]`: energia totale.
- `p2 = np.sum(s[..., 1:4]**2, axis=-1)`: |p|² = px²+py²+pz² (somma sull'ultimo
  asse).
- `m2 = e*e - p2`: la massa al quadrato.
- `np.clip(m2, 0.0, None)`: **protezione numerica**. Lo smearing può rendere m²
  leggermente negativo (per fotoni quasi collineari); senza clip avremmo
  `sqrt(negativo) = NaN`. Il clip lo porta a 0. Poi `np.sqrt`.

---

```python
def energy_asymmetry(a, b):
    ea, eb = a[..., 0], b[..., 0]
    return np.abs(ea - eb) / (ea + eb)
```

Asimmetria energetica A = |E_a − E_b| / (E_a + E_b). Vale 0 se i due fotoni hanno
la stessa energia, →1 se molto sbilanciati. **Discriminante chiave**: i veri
decadimenti π⁰/η → γγ tendono a essere più simmetrici delle coppie sbagliate
(combinatoriche).

---

```python
def cos_angle(a, b):
    pa, pb = _p3(a), _p3(b)
    na = np.linalg.norm(pa, axis=-1)
    nb = np.linalg.norm(pb, axis=-1)
    denom = np.where((na * nb) == 0.0, 1.0, na * nb)
    c = np.sum(pa * pb, axis=-1) / denom
    return np.clip(c, -1.0, 1.0)
```

Coseno dell'angolo tra i due impulsi, dalla definizione di prodotto scalare:
cos θ = (p_a · p_b) / (|p_a| |p_b|).

- `pa, pb`: le parti spaziali.
- `na, nb`: i moduli |p_a|, |p_b| (`np.linalg.norm` sull'ultimo asse).
- `denom = np.where(...)`: se un modulo è 0 (vettore nullo), sostituisce il
  denominatore con 1 per **evitare la divisione per zero**.
- `c = somma(pa*pb)/denom`: il coseno.
- `np.clip(c, -1, 1)`: errori di arrotondamento potrebbero dare 1.0000001;
  il clip garantisce che resti in [−1, 1] (necessario prima di `arccos`).

---

```python
def opening_angle(a, b):
    return np.arccos(cos_angle(a, b))
```

Angolo di apertura tra i due fotoni (in radianti), `arccos` del coseno. È legato
alla massa: per due fotoni m² ≈ E_a·E_b·(1 − cos θ); angoli piccoli → massa
piccola.

---

```python
def pt(v):
    return np.sqrt(v[..., 1] ** 2 + v[..., 2] ** 2)
```

Impulso trasverso p_T = √(px² + py²) (componente perpendicolare al fascio, che è
lungo z).

---

```python
def beta(v):
    p = np.linalg.norm(_p3(v), axis=-1)
    e = v[..., 0]
    return p / e
```

Velocità relativistica β = |p| / E (in unità di c). Per un mesone è una misura di
quanto è "boostato". π⁰ ed η hanno distribuzioni di β diverse → utile a
distinguerli.

---

```python
def chi2_pairing(m_low, m_high):
    return (
        ((m_low - MPI0) / (CHI2_RES * MPI0)) ** 2
        + ((m_high - META) / (CHI2_RES * META)) ** 2
    )
```

Il **χ² classico** della combinazione: somma di due scarti normalizzati al
quadrato. `m_low` (coppia più leggera) confrontata col π⁰, `m_high` (più pesante)
con l'η. Il denominatore `CHI2_RES * massa` è la σ all'8%. χ² piccolo = masse
ricostruite vicine a quelle nominali = combinazione probabilmente giusta.

Questa funzione fa **due cose** nello studio: (1) è il baseline da battere, (2)
viene usata anche come feature in pasto alla BDT.
