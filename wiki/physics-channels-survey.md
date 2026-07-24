# Canali di fisica investigabili con i dati GRAAL

Survey dei canali di fotoproduzione accessibili con l'apparato GRAAL/LAGRANγE,
ordinati per leva (payoff fisico × riuso dell'infrastruttura esistente).
Riferimenti esterni ai paper e riferimenti al codice in-repo.

> **Stato epistemico:** questa pagina è una survey/roadmap, non un risultato
> dell'analisi. Percentuali di riuso, rese previste e priorità sono stime di
> pianificazione. Richiedono feasibility study sui dati e non vanno citate come
> misure.

## Vincoli dell'apparato

- **Fascio**: fotoni **linearmente polarizzati** da backscattering Compton su
  laser (linea UV) contro elettroni ESRF a 6.03 GeV. Copertura **Eγ ≤ ~1.5–1.55
  GeV** → **W ≤ ~1.92 GeV**. Tagging event-by-event, risoluzione 16 MeV (FWHM).
- **Polarizzazione crescente con Eγ** (fino a ~0.96 sulla linea UV): la qualità
  è massima proprio al bordo alto del range. Questo rende GRAAL la macchina
  giusta per l'**asimmetria di fascio Σ**, il suo osservabile-firma.
- **Bersagli**: LH2 (protone libero), LD2 (protone/neutrone quasi-free),
  deutone (coerente).
- **Rivelatore**: BGO Rugby Ball (calorimetro EM, ottima risoluzione fotoni),
  muro TOF forward per protoni (θ ≤ ~16° a queste energie, momento ~2.5%) e
  shower wall per neutroni (TOF, efficienza bassa, **niente momento**).
- **Bordo UV nominale ~1.49 GeV**. Il massimo numerico ~1.72 GeV visto nel
  branch `beam` del campione selezionato è una coda/outlier, non prova di
  copertura fisica fino a 1.72 GeV. Canali vicino a soglia, come η′, hanno
  quindi spazio di fase molto limitato.

Osservabile-firma: **Σ**, estratta dalla dipendenza cos2φ
`NV/FV / (NV/FV + NH/FH) = ½[1 + P(Eγ)·Σ·cos2φ]`
(metodo Ajaka [PhysRevLett.100.052003], Levi Sandri [1407.6991]).

## Stato del codice (fit cinematico integrato in `main`)

Canale attuale: **γp → p η π0**, ricostruito da 4 fotoni (η→2γ, π0→2γ), con
BDT stage-1 + **fit cinematico 6C** e taglio sul CL. Fondi pesati per
cross-section reale integrata sul flusso.

Punti architetturali rilevanti per l'estensione:
- Massa del partner di rinculo **già parametrica** (`RecoConfig.partner_mass`,
  `05_reconstruction/reco_physics.py` `PARTNER_MASSES` conosce `proton`,
  `neutron` e `deuteron`); taglio missing-mass sul rinculo già presente
  (`05_reconstruction/reco_core.py`).
- **Nessuna gestione della polarizzazione**: il generatore MC non scrive lo
  stato ⊥/∥, e non esiste codice di estrazione Σ. È il blocco mancante per ogni
  misura di asimmetria.
- Generatore η' già presente (`03_mc_simulation/generate_etaprime_dataset.C`),
  canale in registro (`00_common/channels.py`, oggi usato come **fondo**).

## Canali, in ordine di leva

| # | Canale | Bersaglio | Perché | Eγ [GeV] | Riuso codice |
|---|--------|-----------|--------|----------|--------------|
| 1 | **Σ(Mpη) su struttura ~1700 (a0/triangle singularity)** | p libero | Metag trova struttura Mpη~1700, picco Eγ≈1485 — dentro GRAAL. Fascio pol → Σ mai misurata sulla struttura; discrimina singolarità vs risonanza | 1400–1550 | ~90% |
| 2 | **Σ+σ completo γp→pηπ0, mappa Δ(1700)** | p libero | Estende Ajaka con statistica + kin-fit CL odierni. Σ(pη),Σ(pπ0),Σ(ηπ0) vincolano D33 | soglia(0.93)–1.55 | ~95% |
| 3 | **Quasifree γn→nηπ0, isospin σn/σp e Σn** | p+n (LD2) | Δ*: ampiezze n=p attese; Jaeglé trova σn>σp → contributi N*. Σn mai fatta | soglia–1.55 | ~70% |
| 4 | **γp→pη singolo, Σ regione S11(1535)** | p libero | Classico GRAAL, filtro isospin, normalizzazione, aηN | soglia(0.71)–1.55 | ~50% |
| 5 | **η' Σ su neutrone (γn→nη')** | p+n (LD2) | Novità assoluta; A½ⁿ degli N* nel resonance gap. Ma alto rischio/bassa resa (vedi sotto) | 1.45–1.55 | ~40% (topologia nuova) |
| 6 | **Coerente γd→π0ηd** | d nucleo | Sonda ηd, dibarioni, η-mesic. Ma serve ID deutone magnetico — GRAAL ha solo TOF | soglia–1.55 | ~30% |
| — | η' Σ su **protone** | p libero | **GIÀ PUBBLICATO** da GRAAL (Levi Sandri 2015). Nessun dato nuovo dal 2008 | 1.45–1.50 | n/a |

## Osservabili raccomandati

- **#1/#2** (ηπ0, p): **Σ(Mpη), Σ(Mπ0η), Σ(Mpπ0)**; dσ/dMpη con taglio
  Mpπ0<1190 MeV (replica Metag Fig.7); dσ/dΩ; angoli di apertura pη, π0η.
- **#3** (ηπ0, n): σn/σp(Eγ), Σn(Mpη), dσ/dcosθ; selezione quasi-free via
  missing-mass sul neutrone.
- **#4** (η): σ(Eγ), Σ(Eγ,cosθ), coefficienti di Legendre Ai.
- **#5** (η', n): Σ(θη'_cm) in 1–2 bin sopra soglia (se la statistica regge).
- **#6**: dσ/dΩ forward, IM(ηd), IM(π0d) — cerca low-mass ηd enhancement.

## Approfondimento — canale η' (correzione)

Il canale η' **non è morto sul protone**: GRAAL lo ha misurato per primo
(Levi Sandri et al., EPJ A / [1407.6991], 2015). Σ per γp→pη' a Eγ=1.461 e
1.480 GeV, 12121 eventi su 8 stretch, tre modi di decadimento (η'→2γ, π0π0η→6γ,
π+π−η). Risultato: interferenza P-D (o S-F), i modelli SOTA falliscono.

**Perché l'analisi protone è pulita**: cinematica a **due corpi**. L'angolo del
protone di rinculo (forward TOF) fissa l'angolo del mesone nel c.m. senza fit
cinematico; missing-mass dal rinculo dà il picco η' pulito.

**Si può rifare sul neutrone (γn→nη')?**
- **Fisica**: sì, motivata e nuova. η' = filtro isospin (solo N*); A½ⁿ ≠ A½ᵖ →
  Σn vincola i fotoaccoppiamenti al neutrone nel resonance gap. Prima assoluta.
- **Fattibilità: bassa/media**, per tre ostacoli che si sommano:
  1. **Il metodo protone non trasferisce**: il neutrone bersaglio su D2 non è a
     riposo (Fermi) → cinematica a due corpi rotta → niente mappa θn→θη'_cm.
     Bisogna ricostruire l'η' **interamente dai decadimenti** (η'→2γ dà l'angolo
     c.m.) e usare il neutrone solo come tag.
  2. **Rivelazione neutrone**: shower wall via TOF, efficienza ~0.25, **niente
     momento**; Fermi allarga la missing-mass di selezione.
  3. **Statistica**: partendo da 12121 (protone), fattore 5–10 in meno →
     ~1000–2000 eventi utili; soglia a coltello → al più 1–2 bin, smussati.
     Al limite dell'estraibilità di Σ.
- **Come farlo**: reco piena η'→2γ (+π0π0η per statistica) nel BGO; tag
  neutrone forward + veto tracce cariche; missing-mass allargata per Fermi;
  eventuale sottrazione fondo protone-quasi-free con dati LH2 normalizzati per
  flusso (tecnica BGOOD).
- **Verdetto**: canale reale ma ad alto rischio. **Condizionato a un
  feasibility-count** sui dati D2 archiviati: contare gli eventi η'→2γ +
  tag-neutrone sopravvissuti nelle stretch UV. ≥1000 puliti → vale; sotto → no.

## Sintesi operativa

**Priorità 1 — canale 1.** Intersezione tra ciò che GRAAL fa meglio di chiunque
(Σ polarizzata) e una struttura fresca (Metag ~1700, singolarità triangolare)
che cade dentro il suo range. Nessuno ha la Σ su quella struttura, e Σ è
l'osservabile che discrimina l'interpretazione. Riusa quasi tutta la catena.

Percorso minimo #1:
1. Modulo di estrazione Σ dal cos2φ (metodo Ajaka/Levi Sandri): serve φ (piano
   di decadimento vs piano di reazione) e binning per stato di polarizzazione.
   Nuovo modulo in `06_plots/` o `05_reconstruction/`.
2. Far scrivere al generatore MC (`03_mc_simulation/generate_eta_pi0_dataset.C`)
   lo stato di polarizzazione del fascio — oggi assente.
3. dσ/dMpη con taglio Mpπ0<1190 MeV, overlay Σ(Mpη).

**Priorità 2 — canale 3** (isospin n su ηπ0): `partner_mass`→M_NEUTRON (già
supportato) + gestione Fermi/spettatore su D2. Reco meson intatta.

**Secondari/stretch — canale 5** (η'-n): solo dopo feasibility-count sulla
statistica. Stesso blocco abilitante del #1 e #3 (formato dati polarizzazione +
tag nucleone di rinculo su D2).

**Non fare — canale 6** (coerente d) senza studio ID-deutone (probabile stop col
solo TOF). **Chiuso — η' su protone** (già pubblicato, nessun dato nuovo dal 2008).

**Blocco che richiede input umano**: formato dei dati di polarizzazione del
fascio (codifica ⊥/∥ negli eventi reali; se/come il generatore MC deve
riprodurla) — non deducibile dal repo.

## Riferimenti

- [Ajaka et al., PRL 100, 052003 (2008)](https://doi.org/10.1103/PhysRevLett.100.052003) — γp→ηπ0p, GRAAL, Σ, Δ(1700).
- [Levi Sandri et al. (2015), arXiv:1407.6991](https://arxiv.org/abs/1407.6991) — prima Σ per γp→pη' a GRAAL.
- [Metag et al. (2021), arXiv:2110.05155](https://arxiv.org/abs/2110.05155) — struttura Mpη~1700 e interpretazione triangle singularity a0(980).
- [Döring (2010), arXiv:1010.2180](https://arxiv.org/abs/1010.2180) — η su neutrone, soglia KΣ e isospin breaking.
- Jaeglé (2009), *Chinese Physics C* 33, 1340 — η'/π0η quasi-free e coerente su deutone; riferimento da verificare prima dell'uso editoriale.
- [Clara Figueiredo et al. (BGOOD, 2024), arXiv:2405.09392](https://arxiv.org/abs/2405.09392) — coerente γd→π0ηd forward.
