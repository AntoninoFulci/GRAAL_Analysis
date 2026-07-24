# Fit cinematico 6C

Il fit cinematico **6C** viene applicato dopo il gate BDT e l'accoppiamento chi² sugli eventi sopravvissuti. 
Il suo scopo è correggere le quantità misurate entro le loro risoluzioni per imporre la conservazione del quadrimpulso e le masse note di η e π⁰.

Rispetto al semplice taglio sulla massa mancante, il fit usa tutte le quantità
misurate e le loro risoluzioni per correggere le variabili cinematiche del
Dalitz plot (**M(ηp)** e **M(π⁰p)**). La frazione di eventi rimossa dipende dal
campione e dalla calibrazione; non viene fissata qui perché il repository non
versiona un cut-flow che supporti un numero universale.

Inoltre fornisce quadrivettori corretti evento per evento e un discriminante
fisicamente motivato (χ² del fit o confidence level). Non corregge da solo
non-linearità sistematiche del calorimetro: queste devono essere assorbite da
una calibrazione e da un modello di covarianza validato.


## I 6 Constraint

Il fit 6C impone sei vincoli:

* **conservazione del quadrimpulso** (energia e tre componenti dell'impulso): il sistema iniziale (**fotone di fascio + protone fermo**) deve essere uguale al sistema finale (**protone + quattro fotoni**);
* **massa dell'η** fissata al valore nominale;
* **massa del π⁰** fissata al valore nominale.

L'accoppiamento dei fotoni non viene ricalcolato: il fit utilizza quello già scelto dal chi², con la coppia di fotoni assegnata a η e quella assegnata a π⁰. Considerare tutti i possibili accoppiamenti e scegliere quello con miglior χ² non è incluso, perché avrebbe senso solo se l'associazione dei fotoni fosse il principale limite della ricostruzione.


## Parametrizzazione e covarianza

Le quantità misurate usate dal fit sono 16 parametri espressi in coordinate **(energia/momento, angolo)**:

* 4 fotoni × `(E, θ, φ)` = 12 parametri;
* protone × `(P, θ, φ)` = 3 parametri;
* energia del fascio = 1 parametro.

Questa parametrizzazione mantiene la matrice di covarianza **diagonale**, perché le risoluzioni in energia e angolo sono considerate indipendenti; in coordinate cartesiane invece le componenti risulterebbero correlate.

La matrice di covarianza deriva dal modello di smearing del Monte Carlo ed è definita in un unico punto (`FitCovariance` in `kinematic_fit.py`), condividendo lo stesso modello usato per generare gli eventi simulati.


```python
@dataclass(frozen=True)
class FitCovariance:
    photon_E_rel: float = 0.10      # sigma_E = 10% * E
    photon_theta: float = 5°
    photon_phi: float = 3°
    proton_P_rel: float = 0.04      # sigma_P = 4% * P
    proton_theta: float = 3°
    proton_phi: float = 2°
    beam_E: float = 0.0067946       # sigma assoluta, GeV
```

`FitCovariance` definisce le risoluzioni sperimentali usate dal fit:

* fotoni: **10% in energia**, **5° in θ**, **3° in φ**;
* protone: **4% in momento**, **3° in θ**, **2° in φ**;
* fascio: **FWHM = 16 MeV**, quindi **σE = 6.795 MeV**.

Questi parametri determinano la calibrazione del χ² del fit: se le risoluzioni non rappresentano correttamente il rivelatore, anche il risultato del fit risulta mal calibrato. Le risoluzioni di fotoni, protone e angoli attualmente presenti sono assunzioni legacy non ancora calibrate per energia, angolo, regione del rivelatore e periodo di presa dati.

Per questo vengono verificati tramite i **pull** prima dell'utilizzo definitivo. 
La struttura `dataclass` centralizza tutti i parametri, rendendo eventuali riscalamenti delle risoluzioni modificabili in un unico punto.


## Il risolutore: moltiplicatori di Lagrange, iterativo

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

Il fit utilizza un risolutore iterativo basato sui **moltiplicatori di Lagrange**, che minimizza il χ² delle correzioni applicate alle misure imponendo contemporaneamente i sei vincoli cinematici.

A ogni iterazione vengono ricalcolati il **Jacobiano** dei vincoli, la matrice di covarianza dei vincoli e la correzione dei parametri fino alla convergenza. Lo Jacobiano è calcolato numericamente tramite differenze finite, evitando derivate analitiche più complesse e mantenendo una precisione sufficiente sul campione già filtrato.

Il fit è limitato a 10 iterazioni: in caso di mancata convergenza o matrice singolare l'evento viene marcato come fallito e il χ² rimane alto, così da essere escluso dal taglio sulla confidence level.

Poiché ci sono **6 vincoli indipendenti e nessun parametro libero non
misurato**, il codice usa **ndf = 6**. Il χ² segue una distribuzione χ²(6) solo
se modello di misura, covarianza, linearizzazione e associazione dei fotoni sono
adeguati; l'uniformità della confidence level va quindi verificata, non assunta.


## Il taglio in confidence level sostituisce la massa mancante

Quando il fit è attivo, la selezione finale è sulla sua confidence level:

```python
if not res.converged or confidence_level(res.chi2, res.ndf) < cfg.fit_cl:
    n_fit_cut += 1
    return
```

Il fit utilizza una **confidence level minima di 0,01** come requisito di selezione, configurabile tramite `--fit-cl`.

Il vincolo di conservazione del quadrimpulso incluso nel fit incorpora già l'informazione contenuta nel precedente taglio sulla massa mancante: il fit lo sostituisce, invece di aggiungerlo come ulteriore selezione.

Il parametro `--missing-mass-window` rimane disponibile solo con `--no-fit`: in assenza del fit cinematico, la selezione torna a basarsi sulla finestra della massa mancante attorno alla massa attesa del partner (di default il protone).


## Rami di output

Accanto ai rami grezzi (`eta`, `pi0`, `proton`, ..., vedi [Formati dati](data-formats)), il fit scrive:

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

`06_plots/dalitz.py` usa i quadrivettori fittati (più stretti) per il Dalitz plot, tenendo quelli grezzi per il confronto prima/dopo.

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

La validazione del fit 6C viene eseguita su un campione **MC di segnale**, confrontando il risultato del fit con la verità del generatore salvata nei rami `*_true` (prima dello smearing).

Il controllo principale è sugli **pull**, definiti come:

$(\text{valore fittato} - \text{valore vero}) / \sigma_{\text{fit}}$

Per una covarianza correttamente calibrata i pull devono seguire una distribuzione **N(0,1)**: media vicina a zero indica assenza di bias, mentre una larghezza diversa da uno indica che le risoluzioni in `FitCovariance` sono sovra- o sotto-stimate.

Il MC di segnale e il fit condividono oggi lo stesso modello di smearing. Questa
procedura è quindi una **closure validation**, non una calibrazione indipendente
del rivelatore. Il comando stampa esplicitamente questo stato e verifica anche
uniformità della confidence level, condition number e cause dei fallimenti:

```bash
python -m reconstruction.validate_kinematic_fit --validation-mode closure
```

`--validation-mode calibration` richiede `--provenance` con identificazione del
campione indipendente; senza provenance il comando rifiuta di dichiarare una
calibrazione.
