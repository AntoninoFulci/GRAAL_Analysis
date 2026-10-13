# γp → pηπ⁰: evidenze sperimentali

Verifica: **2026-10-13**, Europe/Rome. Allegato alla ricerca del [punto 13](../plans/2026-10-12-graal/13-letteratura.md). Ricerca mirata, non revisione sistematica esaustiva. Nessun numero trasferito a codice, costanti o normalizzazioni.

## Provenienza e limiti

Metadati verificati su editore/arXiv; autori indicati come primo autore + *et al.*, elenchi completi disponibili nei link primari. Per Gutz/Kashevarov/Sokhoyan sono state lette le sezioni sperimentali HTML arXiv indicate, non ricertificata ogni formula teorica. Date anomale di ricompilazione mostrate nell'HTML non sostituiscono anno editoriale/versione arXiv.

Ajaka 2008 riusa il PDF già presente `tmp/pdfs/PhysRevLett.100.052003.pdf`, identità controllata su frontespizio e DOI APS; SHA256 `7fdf85fe56fa8b0e232d070269e3e58d4d7ca542dcd9ac2287291abaa6b4f1cb`. File ignorato da Git: disponibilità locale, non allegato distribuibile del repository. Nessun PDF riscaricato. Estrazione locale con `pdftotext`; caratteri greci alterati dall'encoding non usati per inferire segni ambigui.

**Covarianze:** matrici numeriche fra bin/normalizzazioni non disponibili nelle sezioni consultate di queste sette fonti; non equivale a prova di assenza in archivi esterni. Materiale supplementare/eventi non acquisiti. Campi «non verificato» restano aperti, senza trasformarli in dati mancanti dell'articolo.

## E1 — Ajaka/GRAAL 2008

J. Ajaka et al., *Simultaneous Photoproduction of η and π⁰ Mesons on the Proton*, **Physical Review Letters 100, 052003 (2008)**. [APS/DOI 10.1103/PhysRevLett.100.052003](https://journals.aps.org/prl/abstract/10.1103/PhysRevLett.100.052003). ArXiv non identificato; versione editoriale locale, pp. 052003-1–5 lette.

| Campo | Evidenza e locatore |
|---|---|
| Target/energia | H₂ liquido, 12 cm; soglia indicata 932 MeV–1.5 GeV; polarizzazione lineare 0.6–0.96 (p.1). |
| Decadimenti/statistica | η,π⁰→γγ; quattro neutri nel BGO e un carico; 61 000 eventi estratti (p.2). |
| Pairing/fondo | Sei assegnazioni η/π⁰; confronto con ipotesi 2π⁰, finestre di massa e sottrazione laterale; fondo residuo dichiarato 6% (p.2, Fig.1). |
| Accettanza/flussi | LAGGEN/GEANT3; ε(Eγ,θπ⁰,θη), buco in avanti ed estrapolazione; normalizzazione al flusso e BR storico η→γγ=0.3938; sistematica σ circa 7% (p.3, Fig.2). |
| Σ | Quattro intervalli 1.1–1.2, 1.2–1.3, 1.3–1.4, 1.4–1.5 GeV; dieci bin massa, dodici φ; φ del momento della coppia, z fascio, xz orizzontale; fit cos(2φ), metodo rinviato a Ref.14 (p.4, Fig.4 p.5). |
| Errori | Fig.4: errori da fit; sistematica polarizzazione 3% esclusa (p.4). |

## E2 — Kashevarov/A2 2009

V. L. Kashevarov et al. (Crystal Ball at MAMI, TAPS, A2), *Photoproduction of π⁰η on protons and the Δ(1700)D₃₃ resonance*, **European Physical Journal A 42, 141–149 (2009)**. [DOI 10.1140/epja/i2009-10868-4](https://doi.org/10.1140/epja/i2009-10868-4); [arXiv:0901.3888v5](https://arxiv.org/abs/0901.3888v5), 9 novembre 2009. [Testo letto: §2, Eqs.1–2, Figs.2–5](https://arxiv.org/html/0901.3888v5).

| Campo | Evidenza e locatore |
|---|---|
| Target/energia | H₂ liquido; misura fino a Eγ=1.4 GeV (§1–2). |
| Decadimenti/statistica | η,π⁰→γγ; quattro neutri, zero/un carico; circa 4×10⁵ eventi (§2). |
| Pairing/tagli | Minimo χ² fra π⁰η e 2π⁰; risoluzioni massa 10/25 MeV; χ²π⁰η<9; missing mass entro 3σ (Eqs.1–2, §2). |
| Fondo | Fit missing mass gaussiana+polinomio cubico; sottrazioni accidentali/target vuoto. Distribuzioni angolari escluse sotto 1 GeV (§2, Fig.4). |
| Accettanza/flussi | GEANT3; efficienza media 20%, **include BR**; flusso tagger corretto con tagging efficiency; sistematica complessiva 5% (§2). |
| Σ/P | Sezioni d'urto e angoli: nessuna misura Σ da questa fonte. |

## E3 — Gutz/CBELSA-TAPS 2010

E. Gutz et al., *Photoproduction of meson pairs: First measurement of the polarization observable Iˢ*, **Physics Letters B 687, 11–15 (2010)**. [DOI 10.1016/j.physletb.2010.02.076](https://doi.org/10.1016/j.physletb.2010.02.076); [arXiv:0912.2632v2](https://arxiv.org/abs/0912.2632v2), 26 febbraio 2010. [Testo letto: Eqs.2–3, Figs.1–6 e paragrafi sperimentali](https://arxiv.org/html/0912.2632v2).

| Campo | Evidenza e locatore |
|---|---|
| Target/energia | H₂ liquido 5 cm; Eγ=970–1650 MeV, lineare (abstract; testo presso Fig.2). |
| Decadimenti/statistica | p4γ, η/π⁰ ricostruiti da coppie; 65 431 eventi, fondo massimo circa 1% (Fig.3/testo). |
| Pairing/tagli | Cinque cluster, selezione cinematica; fit con CLπ⁰γγ>8%, CLπ⁰η>6%, veto CL2π⁰>1% (Fig.3). |
| Osservabili | φ misurato rispetto alla normale al piano di polarizzazione; fit A+P[B sin(2φ)+C cos(2φ)], Iˢ=B/A, Iᶜ=C/A; P evento per evento poi mediato per bin (Eqs.2–3, Fig.1). |
| Accettanza/errori | MC bidimensionale e PWA per stimare effetto dei buchi; non assumerne cancellazione globale; ΔP≤0.02 (testo presso Figs.2,5–6). |
| Flussi/Σ | Dettaglio flussi non verificato; Iᶜ integrato su φ* è collegato a Σ, non ogni bin Iᶜ (testo prima Eq.2). |

## E4 — Gutz/CBELSA-TAPS 2014

E. Gutz et al. (CBELSA/TAPS), *High statistics study of the reaction γp → pπ⁰η*, **European Physical Journal A 50, 74 (2014)**. [DOI 10.1140/epja/i2014-14074-1](https://doi.org/10.1140/epja/i2014-14074-1); [arXiv:1402.4125v1](https://arxiv.org/abs/1402.4125v1), 17 febbraio 2014. [Testo letto: §§4.5–6.6](https://arxiv.org/html/1402.4125v1).

| Campo | Evidenza e locatore |
|---|---|
| Target/energia | Protonico; σ soglia–2.5 GeV; polarizzazione: 0.970–1.200, 1.200–1.450, 1.450–1.650 GeV (§5.1). |
| Decadimenti/statistica | p4γ; circa 65 500 eventi polarizzati; σ: circa 40 000/145 000 nei due periodi (§5.2). |
| Pairing/fondo | Combinatoria cinque cluster, massimo CL; CLπ⁰η>0.06, CL2π⁰<0.01; fondo circa 1% (§5.2, Tab.1). |
| Accettanza/flusso | GEANT3/PWA; **flusso scalato ×0.85**, per accordare σ con misure precedenti; scala non indipendente (§6.1). |
| Σ/errori | Σ=B/A nel fit A+PB cos(2φ); P mediato per bin; confronto correzioni 2D/PWA 5D come sistematica (§6.6, Eqs.19–20, Fig.29). |
| Tre corpi | Eq.21 aggiunge Iˢ sin(2φ); figure delle asimmetrie 31–32: usare didascalie, alcuni rinvii HTML sono disallineati. |

## E5 — Kashevarov/A2 2010, polarizzazione circolare

V. L. Kashevarov et al. (Crystal Ball at MAMI, TAPS, A2), *First measurement of the circular beam asymmetry in the γp → π⁰ηp reaction*, **Physics Letters B 693, 551–554 (2010)**. [DOI 10.1016/j.physletb.2010.09.028](https://doi.org/10.1016/j.physletb.2010.09.028); [arXiv:1009.4093v2](https://arxiv.org/abs/1009.4093v2), 24 settembre 2010. [Testo letto: Eqs.1–7, testo presso Figs.1–3](https://arxiv.org/html/1009.4093v2).

| Campo | Evidenza e locatore |
|---|---|
| Target/statistica | H₂ liquido 10 cm, 300 ore; conteggio eventi e limiti energetici dei bin non verificati nel testo HTML (paragrafo sperimentale/Fig.2). |
| Selezione/decadimenti | Procedura rinviata a Kashevarov 2009 (Ref.6); non assumere identità di ogni taglio senza controllo. |
| Osservabile | Wᶜ(φ)=(2π/σ) I⊙(φ) dσ/dφ; **Wᶜ, I⊙ e Σ sono diversi** (Eqs.1–4). |
| Accettanza/flussi/P | Conteggi corretti per accettanza e flusso; altre normalizzazioni cancellano; Pγ da Pe e trasferimento bremsstrahlung; Pe=(80.9±2.5)% (testo dopo Eq.4). |
| Errori/fondo | Fig.2 solo statistica; sistematica dominata da polarizzazione, flusso/accettanza dichiarati trascurabili. Fondo: rinvio al metodo precedente, non riquantificato qui. |

## E6 — Sokhoyan/A2 2018

V. Sokhoyan et al. (A2), *Experimental study of the γp → π⁰ηp reaction with the A2 setup at the Mainz Microtron*, **Physical Review C 97, 055212 (2018)**. [APS/DOI 10.1103/PhysRevC.97.055212](https://journals.aps.org/prc/abstract/10.1103/PhysRevC.97.055212); [arXiv:1803.00727v2](https://arxiv.org/abs/1803.00727v2), 2 giugno 2018. Titolo abbreviato nella pagina abstract arXiv; titolo editoriale confermato da APS. [Testo letto: §§I–III,V](https://arxiv.org/html/1803.00727v2).

| Campo | Evidenza e locatore |
|---|---|
| Target/energia/statistica | Protonico, H₂; soglia–1.45 GeV; 1.5×10⁶ eventi, Run I/II (§§I–III). |
| Decadimenti/tagli | η,π⁰→γγ; 4/5 cluster; fit cinematico Pπ⁰η>8%/3%, P2π⁰<0.1%; fondo 2π⁰<1% (§III). Algoritmo di spareggio pairing non verificato. |
| Fondo/flussi | Target vuoto pesato con rapporto flussi pieno/vuoto; accidentali sottratti (§III). Dettaglio scala assoluta/BR non verificato. |
| Accettanza | GEANT3.21; Δ(1232)η con componente phase-space; sistematica modello circa 5–8% (§§III,V). |
| Binning/convenzioni | Dalitz 10 intervalli da 50 MeV, 0.95–1.45 GeV (Fig.1, §V); frame canonico e Gottfried-Jackson simili ma non identici (§V). |
| Σ/P | Fonte per σ/Dalitz/distribuzioni, non nuova estrazione Σ lineare; dati precedenti circolari distinti (§I). |

## E7 — Gutz/CBELSA-TAPS 2008, prima misura Σ

E. Gutz et al. (CBELSA/TAPS), *Measurement of the beam asymmetry Σ in π⁰η production off the proton with the CBELSA/TAPS experiment*, **European Physical Journal A 35, 291–293 (2008)**. [Editore/DOI 10.1140/epja/i2008-10566-9](https://link.springer.com/article/10.1140/epja/i2008-10566-9), pubblicazione online 2 aprile 2008. ArXiv non identificato. [Manoscritto degli autori, sito CBELSA](https://www.cb.uni-bonn.de/fileadmin/user_upload/internal/Publication/Publication_EurPhysJA_2008_GutzEEtAl.pdf), pp.1–3 lette; data/revisione non compilate. Il testo editoriale resta protetto: nessuna equivalenza completa delle due versioni certificata.

| Campo | Evidenza nel manoscritto e locatore |
|---|---|
| Target/energia | H₂ liquido; tre bin Eγ=1085±115,1325±125,1550±100 MeV (§§2–3, p.2). |
| Decadimenti/statistica | Cinque hit, η/π⁰→γγ; 83 964 eventi, fondo sotto 2% da MC (§3, p.2). |
| Selezione | Combinatoria protonica; fit CLπ⁰γγ>8%, CLπ⁰η>6%; veto CL2π⁰>1% (§3). |
| Σ/P | Eq.1 definisce Φ rispetto alla normale; fit A+P[B cos(2Φ)+C sin(2Φ)], P evento→media bin (Eq.3, p.2); risultati Fig.3, p.3. |
| Limiti | Flusso, correzione accettanza e budget sistematico non dettagliati nel breve manoscritto; usare E4 per approfondimenti, senza trasferire retroattivamente campione/metodo. |

## Metodo GRAAL richiamato: fonte separata dal canale

J. Ajaka et al., *New Measurement of Σ Beam Asymmetry for η Meson Photoproduction on the Proton*, **PRL 81, 1797–1800 (1998)**, [DOI 10.1103/PhysRevLett.81.1797](https://journals.aps.org/prl/abstract/10.1103/PhysRevLett.81.1797). Letto PDF locale `tmp/pdfs/PhysRevLett.81.1797.pdf`, pp.1798–1799, Eqs.1–2. È γp→ηp, non pηπ⁰. Eqs.1–2 descrivono segno positivo per fascio verticale/φ rispetto all'orizzontale e rapporto `2Nver/(Nver+Nhor)=1+PΣ cos(2φ)`, con N già normalizzati ai rispettivi flussi. Non estendere automaticamente formula al caso di polarizzazioni H/V diverse: occorre derivarla con i P effettivi.

## Uso nell'analisi e comparabilità

Raccomandazioni nostre, non nuove affermazioni sperimentali:

| Punto del piano | Uso | Condizione prima del confronto |
|---|---|---|
| 1, convenzioni/correlazioni | E1/E3/E4/E7 e metodo 1998 | Esplicitare φ, stato H/V, scelta coppia/recoil, integrazione φ*. Errori comuni di P/flusso non diventano errori indipendenti. |
| 4, Dalitz/risonanze | E2/E4/E6 | Uniformare energia, definizione massa, frame e accettanza. Non adattare curva digitalizzata come ampiezza teorica verificata. |
| 5, pesi/fondi/BR | E1/E2/E4/E6 | Distinguere efficienza comprensiva di BR da efficienza geometrica; documentare scala condivisa e sottrazioni. |
| 6, pairing | E1/E2 contro E3/E4/E6 | Confronto concettuale; risoluzioni e soglie dipendono dal rivelatore. Fit cinematico resta disattivato nella fase corrente. |
| 8, soglia/binning | E1/E2/E4/E6 | Confrontare integrali su intervalli comuni; interpolazione/rebinning richiede modello o dati originali e propagazione errori. |
| Osservabile circolare | E5 | Nessun confronto numerico diretto con Σ; non confondere Wᶜ con I⊙. |

E3/E4/E7 e E2/E6 possono condividere campioni originari: non contarli come misure statisticamente indipendenti senza studio dell'overlap. Non aggregati valori numerici incompatibili.

## Registro ricerca ed esclusioni

Query eseguite 2026-10-13 tramite ricerca web; risultati secondari usati solo per trovare pagine primarie. Aperture successive: pagine APS/abstract arXiv/versioni HTML sopra, seguendo riferimenti Ajaka→1998 e Sokhoyan→Kashevarov/Gutz.

| Query | Esito utile |
|---|---|
| `Ajaka 2008 052003 eta pi0 beam asymmetry GRAAL arxiv` | APS e identità E1. |
| `CBELSA TAPS eta pi0 photoproduction proton linear beam polarization arxiv` | E4; pista alla misura Σ precedente. |
| `A2 MAMI eta pi0 photoproduction proton beam helicity asymmetry arxiv` | Lavori quasi-liberi/nucleari, esclusi dal confronto protonico libero. |
| `site:arxiv.org pi0 eta photoproduction proton Kashevarov 2009 2014 2017` | E2 e modelli isobarici. |
| `site:arxiv.org Gutz measurement beam asymmetry Sigma pi0 eta 2008` | Ricerca pista Σ, nessuna scheda nuova dedotta solo dal risultato. |
| `site:arxiv.org "First measurement" "I^s" meson pairs` | E3. |
| `site:arxiv.org "eta" "Kashevarov" "helicity" "2013"` | Ricerca esplorativa, non usata per numeri. |
| `site:arxiv.org "pi0 eta" "A2" "2018"` | Pista E6. |
| `Ajaka 052003 2008 pdf GRAAL` | APS protetto; poi riusato PDF locale indicato dall'inventario esteso. |
| `"pi0 eta" "beam-helicity" "proton" Kashevarov` | Pista E5. |
| `"A2" "pi0 eta" "2018" "cross sections"` | E6, arXiv:1803.00727. |
| `"First measurement of the circular beam asymmetry" arxiv Kashevarov` e variante `site:arxiv.org` | E5, arXiv:1009.4093. |
| `"Measurement of the beam asymmetry" "eta" "Gutz" 2008 arxiv`; `"Gutz" "10566" arxiv pdf`; `"Measurement of the beam asymmetry" "CBELSA" "2008" pdf Gutz` | E7: DOI tramite Groningen, verificato poi su Springer; manoscritto tramite indice pubblicazioni ufficiale CBELSA. |

### Ricerca dedicata agli errata

Il 2026-10-13 eseguite separatamente query `"<DOI>" erratum OR correction` per tutti i sette DOI E1–E7 sopra. Aggiunte query per titolo/autore:

- `"Simultaneous Photoproduction" "Ajaka" erratum`
- `"Photoproduction" "Kashevarov" "2009" erratum pi0 eta`
- `"Photoproduction of meson pairs" "Gutz" erratum`
- `"High statistics study" "Gutz" erratum`
- `"First measurement of the circular beam asymmetry" erratum`
- `"Experimental study" "pi0 eta" "Sokhoyan" erratum`
- `"Measurement of the beam asymmetry" "pi0eta" "Gutz" erratum`

**Nessun erratum pertinente trovato nelle ricerche.** Non garantisce assenza di errata. Risultati relativi a γp→ηp o γp→p2π⁰ sono altri articoli, non correzioni delle fonti qui catalogate. Revisioni arXiv non etichettate automaticamente come errata.

Esclusi dalla comparazione diretta:

- [arXiv:1810.02778](https://arxiv.org/abs/1810.02778): quasi-free nucleons, target deuterated butanol, elicità/target; non Σ su protone libero. Solo abstract/metadati consultati tramite risultati, full text non letto.
- [arXiv:1907.00232](https://arxiv.org/abs/1907.00232): carbonio/alluminio/piombo e asimmetria circolare; bersaglio diverso. Solo abstract/risultati, full text non letto.
- Produzione singola η/η′ e doppia π⁰: non misure del canale richiesto; 1998 mantenuto soltanto come metodo richiamato esplicitamente da E1.
- Tesi, conferenze e pagine ResearchGate: piste di reperimento, non sostituiscono articolo primario.

Piste non approfondite: Horn 2008 e risultati LNS. Copertura sperimentale minima affidata alle sette schede sopra e alle fonti metodologiche; nessuna pretesa di completezza bibliografica. Duplicati arXiv/editore unificati per DOI; manoscritto E7 distinto dalla versione editoriale protetta.
