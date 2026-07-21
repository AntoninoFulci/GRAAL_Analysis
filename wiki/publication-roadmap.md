# Scaletta articoli pubblicabili

Roadmap dei paper derivabili dai dati GRAAL con la pipeline attuale
(BDT stage-1 + fit cinematico 6C) e dalle estensioni previste. Ordinati per
sequenza logica: il paper metodologico (P0) fa da fondamento e benchmark per
tutti gli altri. Vedi [physics-channels-survey.md](physics-channels-survey.md)
per i canali fisici e le leve.

Legenda dipendenze: quali blocchi di codice/dati servono prima di poter
scrivere. "Pol" = formato dati polarizzazione + estrazione Σ. "Fermi/n" =
gestione quasi-free su D2 + tag neutrone.

---

## P0 — Paper metodologico / benchmark *(fondamento, da fare per primo)*

**Titolo di lavoro**: *A modern reconstruction pipeline for GRAAL: multivariate
event selection and a 6C kinematic fit for γp→pηπ0, benchmarked against legacy
analyses.*

**Tesi**: dimostrare che la catena BDT + fit cinematico applicata ai dati GRAAL
archiviati **riproduce** i risultati storici della collaborazione e li
**migliora** in purezza, risoluzione e sistematica — stabilendo la pipeline come
riferimento riproducibile per i lavori futuri.

**Cosa mostra**:
- Ricostruzione γp→pηπ0 (canale attuale) sui dati LH2.
- **Confronto testa-a-testa con Ajaka et al. 2008** ([PhysRevLett.100.052003]):
  stessa σ(Eγ), stessi spettri di massa invariante IM(pπ0)/IM(pη)/IM(ηπ0),
  stessa Σ dove disponibile → **closure test** sulla fisica nota.
- **Guadagni quantificati** rispetto all'analisi a tagli quadratici legacy:
  - S/B prima/dopo il BDT stage-1;
  - risoluzione di massa con/senza fit cinematico 6C (pull width, CL);
  - riduzione dell'errore sistematico da selezione;
  - contaminazione residua dai fondi (pi0pi0, 3pi0, eta_via_3pi0, ...) misurata
    dal sample MC pesato per cross-section reale.
- **Validazione del fit**: distribuzioni dei pull (media 0, σ 1), covarianza
  fittata, invarianza chi2 (test già in `05_reconstruction/tests/`).
- **Cross-check indipendente**: rifare il closure test η di Levi Sandri 2015
  (Fig. 3 di [1407.6991]) — stesso stato finale, verifica dell'apparato.

**Osservabili**: σ, IM(3 coppie), Σ, pull/CL del fit.

**Novità**: primo uso di ML + kin-fit sui dati GRAAL; template metodologico
riproducibile; benchmark pubblico contro cui misurare P1–P5.

**Journal**: *Eur. Phys. J. A* (metodi/strumentazione) o *NIM A* se il taglio è
più strumentale.

**Dipendenze**: nessuna oltre il codice esistente + estrazione Σ per il pezzo di
asimmetria. **Scrivibile per primo.** Il core (σ, IM, S/B, pull) non richiede
nemmeno "Pol".

**Stato codice**: ~90% pronto (canale attuale). Manca solo l'estrazione Σ per la
parte asimmetria, e il tabulato dei guadagni vs legacy.

---

## P1 — Σ della struttura Mpη ~1700 (a0/triangle singularity) *(fisica di punta)*

**Titolo**: *Beam-spin asymmetry of the Mpη ≈ 1700 MeV structure in γp→pπ0η:
probing the a0(980) triangle singularity with polarised photons.*

**Tesi**: misurare Σ risolta in Mpη attraverso la struttura scoperta da Metag
([2110.05155], picco Eγ≈1485, dentro GRAAL). Metag usò fascio non polarizzato;
Σ è nuova e può discriminare singolarità triangolare (cinematica) da risonanza
(dinamica).

**Osservabili**: Σ(Mpη), Σ(Mπ0η), Σ(Mpπ0); dσ/dMpη con taglio Mpπ0<1190 MeV
(replica Metag Fig.7); angoli di apertura pη, π0η.

**Novità**: prima Σ polarizzata sulla struttura ~1700; discriminante di
interpretazione. Alto impatto.

**Journal**: *Physical Review Letters* (se il discriminante regge) o *PRC*.

**Dipendenze**: P0 (pipeline validata) + Pol.

**Stato codice**: ~90% reco riusata; serve Pol + binning Mpη.

---

## P2 — Mappa Σ+σ completa di γp→pηπ0 e la Δ(1700) *(consolidamento)*

**Titolo**: *High-statistics beam asymmetries in γp→pπ0η across the second
resonance region and the dynamically generated Δ(1700).*

**Tesi**: estendere Ajaka 2008 con statistica e kin-fit odierni; mappa fine
Σ+σ in tutte e tre le coppie per vincolare la Δ(1700)D33→ηΔ(1232).

**Osservabili**: σ(Eγ) totale/differenziale, Σ(Eγ,cosθ) per coppia, IM.

**Novità**: precisione e binning superiori al 2008; input per PWA
(Bonn-Gatchina).

**Journal**: *PRC* / *EPJ A*.

**Dipendenze**: P0 + Pol. Naturale continuazione di P1 (stesso canale/dati).

**Stato codice**: ~95%.

---

## P3 — Isospin: γn→nηπ0 quasi-free, σn/σp e Σn *(estensione al neutrone)*

**Titolo**: *Quasi-free π0η photoproduction off the neutron: isospin decomposition
and the first neutron beam asymmetry.*

**Tesi**: testare σn≈σp atteso per Δ*; Jaeglé trova σn>σp → contributi N*. Σn
mai misurata. Filtro isospin sull'ηπ0.

**Osservabili**: σn/σp(Eγ), Σn(Mpη), dσ/dcosθ.

**Novità**: prima Σn per ηπ0; decomposizione di isospin.

**Journal**: *PRC* / *EPJ A*.

**Dipendenze**: P0 + Pol + Fermi/n. `partner_mass`→M_NEUTRON già supportato.

**Stato codice**: ~70% (reco meson intatta; nuovo = quasi-free/spettatore).

---

## P4 — η' Σ sul neutrone *(stretch, condizionato)*

**Titolo**: *Search for the beam-spin asymmetry in γn→nη' near threshold.*

**Tesi**: prima Σ per η' sul neutrone; A½ⁿ degli N* nel resonance gap.
Complementare a Levi Sandri 2015 (protone).

**Osservabili**: Σ(θη'_cm) in 1–2 bin sopra soglia.

**Rischio**: alto. Cinematica a due corpi rotta dal Fermi (serve reco piena
η'→2γ), neutrone senza momento, statistica ~1000–2000 → al limite di Σ.
**Condizionato a feasibility-count** sui dati D2 archiviati.

**Journal**: *EPJ A* / *PLB* (se esce pulito).

**Dipendenze**: P0 + Pol + Fermi/n + reco η' (topologia 2γ/6γ, nuova).

**Stato codice**: ~40% (topologia η' nuova).

---

## P5 — η singolo, Σ regione S11(1535) *(opzionale, normalizzazione/aηN)*

**Titolo**: *Beam asymmetry in γp→pη and the S11(1535): a consistency benchmark.*

**Tesi**: classico GRAAL come normalizzazione e cross-check dell'apparato;
utile per aηN. Basso payoff marginale (terreno battuto), ma solido come
verifica e già parzialmente usato nel closure test di P0.

**Osservabili**: σ(Eγ), Σ(Eγ,cosθ), coefficienti di Legendre Ai.

**Journal**: *EPJ A*.

**Dipendenze**: P0 + Pol + reco η (topologia 2γ o 6γ).

**Stato codice**: ~50%.

---

## Sequenza consigliata

```
P0 (benchmark)  ──►  P1 (Σ struttura ~1700)  ──►  P2 (mappa Δ1700)
   │                                                   
   └──►  P3 (isospin neutrone)  ──►  P4 (η' neutrone, se feasibility OK)
                                                       
   P5 (η) — opzionale, in parte già dentro il closure test di P0
```

- **P0 prima di tutto**: senza il benchmark validato, ogni misura successiva è
  contestabile. È anche il paper a rischio più basso (dati e codice pronti).
- **P1** è la fisica di punta: da attaccare subito dopo P0, condivide il canale.
- **P2** è il consolidamento naturale di P1 (stesso dataset).
- **P3/P4** aprono il fronte neutrone; P4 solo dopo il feasibility-count.
- **P5** è di supporto; parte del suo contenuto vive già in P0.

## Blocchi abilitanti (da risolvere una volta, servono a più paper)

1. **Pol** — formato dati polarizzazione ⊥/∥ + modulo estrazione Σ (cos2φ).
   Serve a P0(parziale), P1, P2, P3, P4, P5. **Richiede input umano** sul
   formato dei dati reali. Priorità massima.
2. **Fermi/n** — quasi-free + tag neutrone su D2. Serve a P3, P4.
3. **Reco η'/η** — topologie 2γ e 6γ. Serve a P4, P5.
