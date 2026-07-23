# Fit cinematico 6C

`05_reconstruction/kinematic_fit.py` gira **dopo** il gate BDT e dopo
l'accoppiamento chi2 (vedi [Gate BDT](05-reconstruction-bdt-gate) e
[Ricostruzione chi2](05-reconstruction-chi2)), su ciascuno dei sopravvissuti.
Aggiusta le quantità misurate — entro la loro risoluzione — fino a far
rispettare esattamente all'evento la conservazione del quadrimpulso e le
masse di η e π⁰. Non è un taglio in più: è un affinamento della fisica
sull'evento che il chi2 ha già accoppiato.

## Perché

Il taglio sulla massa mancante (vedi sotto) centra l'η ricostruita ma non la
restringe — *rimuove* circa il 45% degli eventi invece di correggere quelli
la cui energia fotonica il BGO ha sovra-misurato. Il fit fa di meglio: dà

- un centro **e** una risoluzione migliorata, non sull'η vincolata in sé
  (vedi sotto perché non è la massa il posto giusto dove guardarla), ma sugli
  assi del Dalitz plot, M(ηp) e M(π⁰p), che sono la vera resa in risoluzione;
- quadrivettori aggiustati che alimentano un Dalitz plot più netto;
- un unico discriminante statisticamente motivato — il chi2 del fit / la sua
  confidence level — che racchiude sia il vincolo di conservazione sia i due
  vincoli di massa in un numero con una distribuzione nota, al posto della
  finestra di massa mancante fatta a mano;
- una correzione evento per evento della non linearità del calorimetro, senza
  bisogno di una calibrazione globale.

## Le sei costrizioni

`f(η) = 0`, sei equazioni:

- **conservazione del quadrimpulso** (4 equazioni, E, px, py, pz):
  `(fascio + bersaglio) - (protone + Σ fotoni) = 0`, con il bersaglio un
  protone fermo, `(0, 0, 0, M_PROTON)`;
- **massa dell'η**: `m²(γ_a + γ_b) - m_η² = 0`;
- **massa del π⁰**: `m²(γ_c + γ_d) - m_π0² = 0`.

L'accoppiamento (quali due fotoni vanno all'η, quali al π⁰) è quello già
scelto dal chi2 — il fit non lo rimette in discussione, usa
`pairing.heavy=(0,1), pairing.light=(2,3)` fissato sull'ordine in cui i
fotoni arrivano dall'accoppiamento migliore (vedi
[Ricostruzione chi2](05-reconstruction-chi2)). Fittare tutti e tre gli
accoppiamenti e tenere il chi2 migliore è fuori scope: sarebbe un
raffinamento solo se l'accoppiamento si rivelasse il collo di bottiglia.

## Parametrizzazione e covarianza

Le quantità misurate y (16 numeri) sono in **(E, theta, phi)** per ciascun
fotone e **(P, theta, phi)** per il protone (con `E = sqrt(P² + m_p²)`),
più l'energia del fascio (direzione fissata lungo z):

- 4 fotoni × (E, theta, phi) = 12
- protone × (P, theta, phi) = 3
- fascio × E = 1

Questa scelta, non cartesiana, mantiene la covarianza **diagonale**: le
risoluzioni in energia e in angolo sono indipendenti, mentre in coordinate
cartesiane si mescolerebbero. La covarianza V è presa dal modello di
smearing del Monte Carlo, `03_mc_simulation/smearing.h` — lo stesso che
genera gli eventi simulati — e vive in un unico posto, il dataclass
`FitCovariance` in `kinematic_fit.py`:

```python
@dataclass(frozen=True)
class FitCovariance:
    photon_E_rel: float = 0.10      # sigma_E = 10% * E
    photon_theta: float = 5°
    photon_phi: float = 3°
    proton_P_rel: float = 0.04      # sigma_P = 4% * P
    proton_theta: float = 3°
    proton_phi: float = 2°
    beam_E: float = 0.016           # assoluto, GeV
```

Questo è l'input che regge tutto il fit: se i sigma non riflettono il
rivelatore vero, il chi2 del fit è mal calibrato. Per questo è validato con
gli pull (vedi sotto) prima di fidarsene, ed è un dataclass apposta perché
un eventuale riscalamento resti una modifica di una riga sola, in un unico
posto.

## Il solutore: moltiplicatori di Lagrange, iterativo

```
minimizza  chi2 = (y - eta)^T V^-1 (y - eta)   soggetto a   f(eta) = 0

per ogni iterazione:
  F   = df/deta            (Jacobiano 6 x 16, differenze finite centrate)
  r   = f(eta) + F (y - eta)
  S   = F V F^T             (6 x 6)
  lam = S^-1 r
  eta = y - V F^T lam
  chi2 = r^T S^-1 r
ripeti (ri-valutando f, F) finché |f| < tol e il chi2 è stabile
covarianza del fit: V_eta = V - V F^T S^-1 F V
```

Lo Jacobiano è **numerico** (differenze finite), non analitico: più semplice
e meno soggetto a errori delle derivate a mano delle sei costrizioni, e
abbastanza economico sul campione che sopravvive al gate — una frazione dei
~17M eventi grezzi. Le iterazioni sono limitate a 10; se non convergono, `converged =
False` e il chi2 resta grande apposta, così l'evento fallisce comunque il
taglio sulla CL. Una `S` singolare viene intercettata e trattata come non
convergenza, non come un crash.

`ndf = 6`: sei costrizioni, nessun parametro non misurato da stimare — ogni
quantità del vettore y è una misura, nessuna è incognita. Per questo il chi2
del fit segue una distribuzione chi2(6) sul segnale vero, ed è la base del
taglio sulla confidence level.

## Il taglio in confidence level sostituisce la massa mancante

Quando il fit è attivo, la selezione finale è sulla sua confidence level:

```python
if not res.converged or confidence_level(res.chi2, res.ndf) < cfg.fit_cl:
    n_fit_cut += 1
    return
```

con `cfg.fit_cl` di default **0.01** (configurabile via `--fit-cl` su
entrambi gli entrypoint). Il vincolo di conservazione del quadrimpulso del
fit include già l'informazione che il taglio sulla massa mancante
approssimava (vedi [Ricostruzione chi2](05-reconstruction-chi2) per quel
taglio) — il fit lo sussume, non lo affianca.

`--missing-mass-window` (default 0.06 GeV) **resta** per la modalità
`--no-fit`: con il fit disattivato, la selezione torna a essere la finestra
sulla massa mancante attorno alla massa del partner (di default il
protone), esattamente come prima dell'introduzione del fit.

## Rami di output

Accanto ai rami grezzi (`eta`, `pi0`, `proton`, ..., vedi
[Formati dati](data-formats)), il fit scrive:

```cpp
eta_fit,        TLorentzVector   // somma dei due fotoni fittati dell'eta
pi0_fit,        TLorentzVector   // somma dei due fotoni fittati del pi0
proton_fit,     TLorentzVector   // protone fittato

eta_fit_gamma1, TLorentzVector
eta_fit_gamma2, TLorentzVector
pi0_fit_gamma1, TLorentzVector
pi0_fit_gamma2, TLorentzVector

fit_chi2/F        // chi2 del fit
fit_ndf/I         // sempre 6
fit_converged/I   // 0/1
```

`06_plots/dalitz.py` usa i quadrivettori fittati (più stretti) per il
Dalitz plot, tenendo quelli grezzi per il confronto prima/dopo.

## Validazione su MC di segnale

`05_reconstruction/validate_kinematic_fit.py` fitta un campione del MC di
segnale (`eta_pi0_mc.root`) e confronta il risultato con la verità del
generatore, che serve leggere dai rami `*_true` (`eta_gamma1_true`,
`eta_gamma2_true`, `pi0_gamma1_true`, `pi0_gamma2_true`, `proton_true`,
`beam_true` — i quadrivettori **prima** dello smearing, scritti da
`generate_eta_pi0_dataset.C` apposta per questa validazione; vedi
[Formati dati](data-formats)):

```bash
python -m reconstruction.validate_kinematic_fit \
    --signal 03_mc_simulation/data/eta_pi0_mc.root --out-dir results/plots
```

Calcola gli **pull**, `(fittato - vero) / sigma_fittato`, che sono il modo
in cui la covarianza si calibra: attesi N(0, 1) — media 0 se il fit non è
distorto, larghezza 1 se i sigma in `FitCovariance` sono quelli giusti. Una
larghezza diversa da 1 direbbe che la covarianza è sbagliata di quel
fattore, da correggere in `FitCovariance` e rivalidare.

### Risultati misurati

- **Convergenza del fit: 99.9%** degli eventi di segnale.
- **chi2 del fit / ndf = 6.12 / 6 = 1.02** — conferma che la covarianza
  (presa da `smearing.h`) è calibrata correttamente **così com'è**: non è
  stata riscalata.
- **Larghezza dello pull** (energia del fotone dell'η, normalizzata sul
  sigma **fittato**): **1.03**, media **-0.03** — il fit è non distorto e ha
  larghezza unitaria.
- **La massa dell'η fittata è esattamente al polo (0.547862)**, per
  costruzione: è il vincolo di massa a metterla lì, non una misura
  migliorata — la sua deviazione standard è ~0. Il "restringimento" della
  massa dell'η visto nei plot non è quindi risoluzione recuperata, è il
  vincolo stesso. **La risoluzione guadagnata davvero è sugli assi del
  Dalitz, M(ηp) e M(π⁰p)** — quelle non sono vincolate, e su quelle si vede
  l'effetto reale del fit. Chi guarda questi risultati in futuro non deve
  confondere le due cose: la massa dell'η stretta è un vincolo geometrico, la
  risoluzione del Dalitz è fisica recuperata.
- **Risoluzione sugli assi del Dalitz** — larghezza del residuo
  `M_reco − M_true` sul MC di segnale (dove il valore vero cancella lo spread
  fisico e resta la sola risoluzione):

  | osservabile | σ prima (raw) | σ dopo (fit) | guadagno |
  |-------------|---------------|--------------|----------|
  | M(ηp)       | 52 MeV        | **10 MeV**   | 5.0×     |
  | M(π⁰p)      | 22 MeV        | **10 MeV**   | 2.3×     |

  L'η parte peggio (fotoni più energetici, σ_E = 10%·E) e il fit ne recupera
  5×; il π⁰ parte già stretto e satura ~10 MeV, limitato dalla risoluzione del
  **protone** (che il fit muove solo entro σ_P = 4%). Sui dati veri la
  larghezza della distribuzione mescola risoluzione e fisica, quindi si
  stringe di meno (M(ηp) 61 → 46 MeV) — ed è giusto così: il fit non deve
  cancellare la struttura fisica vera.

### Plot di questi risultati

`06_plots/kinfit_resolution.py` (`python -m plots.kinfit_resolution`) rigenera
le sei figure, ed è nel `run_pipeline.sh` subito dopo il Dalitz:

- `risoluzione_{eta,pi0}_p.pdf` — i residui MC, raw vs fit (la risoluzione pura);
- `massa_{eta,pi0}_p_mc.pdf` — lo spettro MC con la verità sovrapposta: il fit
  riporta la curva grezza sulla verità, la soglia cinematica torna netta;
- `massa_{eta,pi0}_p.pdf` — lo spettro sui dati ricostruiti, raw vs fit.

Fa girare il fit dal vivo sul MC di segnale (stessa chiamata di `reco_core`) e
legge i rami fittati già scritti nel file ricostruito per le curve sui dati.

## Dove andare da qui

- [Ricostruzione chi2](05-reconstruction-chi2) — l'accoppiamento che il fit
  eredita, il taglio chi2 < 10, il quadrimomento mancante che il fit
  sostituisce come discriminante.
- [Gate BDT](05-reconstruction-bdt-gate) — il filtro statistico che gira
  prima, sul campione grezzo.
- [Formati dati](data-formats) — schema completo dei rami, grezzi, fittati e
  `*_true`.
