# Paper sul metodo — note di lavoro

Aggiornamento: **11 novembre 2026**, bozza v0.2. Testo inglese, note italiane.

- Sorgente principale: [draft.tex](draft.tex).
- Anteprima verificata: [draft.pdf](draft.pdf).
- Bibliografia: [references.bib](references.bib).
- Figure riproducibili: [make_figures.py](make_figures.py), [manifest di provenienza](figures/manifest.json).
- [draft.md](draft.md) conserva la prima stesura: non aggiornare in parallelo.

## Mandato e messaggio

Titolo approvato: **Preservation and modernisation of the GRAAL data and simulation framework: validation through ηπ⁰ photoproduction**.

Tema centrale: preservare la possibilità di fare fisica con l'archivio GRAAL. La conversione HBOOK/PAW → ROOT, il recupero Fortran → C++/Python, il porting GEANT3 → Geant4 e la selezione BDT sono parti della stessa continuità scientifica. Il benchmark ηπ⁰ dimostra le interfacce e dovrà dimostrare quantitativamente le prestazioni; non basta mostrare un picco più pulito.

NIM A e JINST restano possibili destinazioni. Il formato APS/PRD riproduce il template richiesto, non indica la rivista scelta. Nessuna garanzia di accettazione; nessuna submission o pubblicazione esterna eseguita.

## Confine con i lavori di fisica successivi

L'autore ha confermato: **fit PγΣ nel dominio Ajaka**. Sono autorizzati controlli metodologici, qualità della ricostruzione e confronto con risultati già pubblicati. Esclusi nuovi domini di osservabili, altri canali, sezioni d'urto, scansioni complete e risultati a binning più fine.

La formulazione iniziale «figure che ci sputtanano il lavoro successivo» è stata interpretata, coerentemente con «nulla di inedito», come protezione del lavoro successivo. Non sono state inserite griglie complete UV/VIS o risultati core/tails.

Scelta concreta per le figure di osservabili:

- Un solo intervallo: **1.20–1.30 GeV**, già in Fig. 4 di Ajaka.
- Solo posizioni di massa pubblicate; bin moderni da 40 MeV. Match entro 6 MeV per tollerare la digitalizzazione; non interpolare valori.
- Tre proiezioni pπ⁰, pη, ηπ⁰. Lo stesso campione contribuisce a tutte: non indipendenti.
- Fit esemplificativi: secondo punto di riferimento in ordine di massa per ciascuna proiezione. Scelta geometrica, non selezione sul p-value.
- Controlli di massa/cinematica: istogrammi UV integrati **0.93–1.50 GeV**. Sono diagnostiche della selezione, non una misura differenziale sotto 1.10 GeV. Dominio dichiarato in testo, caption e manifest; non sono filtrabili in energia dagli istogrammi 1D salvati. Per restringerli ulteriormente servono i file di eventi esatti citati nel metadata: non sostituirli con campagne locali diverse.

## Figure presenti

| Figura | Contenuto | Fonte / limite |
| --- | --- | --- |
| 1 | Schema preservazione → traduzione → rianalisi, con validazione e provenienza | Nuovo schema vettoriale; non certifica completamento |
| 2 | Schema migrazione simulazione e separazione verifica numerica / fisica | Nuovo schema vettoriale; ramo fisico aperto |
| 3 | Masse η e π⁰: convenzionale contro BDT | Istogrammi reali, normalizzati separatamente includendo flow; niente fit nuovo |
| 4 | Missing mass, coplanarità e residuo angolare del protone | Istogrammi reali dopo selezione; missing-mass cut già applicato |
| 5 | Tre fit azimutali nel dominio Ajaka | TGraphErrors e TF1 salvati; curva non rifittata |
| 6 | Benchmark ristretto Ajaka | Conditional likelihood, errori statistici condizionali; riferimento digitalizzato |

Tutti i PDF sono vettoriali in `figures/`. Nessuna immagine generata viene presentata come dato. Nessun nuovo dato scientifico è stato prodotto per costruire queste figure.

### Convenzione dei fit PγΣ

L'utente intende la modulazione azimutale legata a PγΣ. Il prodotto disponibile salva però il rapporto

`R = (yV - yH) / (PH*yV + PV*yH)`, con `y = N/F`.

R è già normalizzato alla polarizzazione: asse etichettato **R(φ)**, non PγΣ. Le curve sono riprodotte dai parametri TF1. Per 12 bin il coefficiente del coseno è `Sigma * 0.9549`; il controllo nello script verifica questa relazione e ricalcola il χ² dai punti. Nessuna seconda correzione. I tre fit mostrati hanno offset e seno fissati a zero. Il benchmark usa invece la likelihood: nessun divisore applicato.

### Risoluzione e significato delle larghezze

Il metadata degli istogrammi registra fit gaussiani η su 0.50–0.60 GeV:

| Selezione | Media [MeV] | Larghezza [MeV] | χ²/ndf |
| --- | ---: | ---: | ---: |
| Convenzionale | 545.18 | 33.15 | 579.70/17 |
| BDT | 547.39 | 29.50 | 335.33/17 |

La qualità del modello gaussiano è insufficiente per una misura precisa di risoluzione. Le larghezze sono citate solo come diagnostica della forma selezionata, senza percentuale di miglioramento, significatività o interpretazione come risoluzione del rivelatore. Servono risposta/pull, efficienze, fondo e bias indipendenti. Non sono state inventate curve ROC o closure mancanti.

## Provenienza e stato scientifico

Campagna delle figure: `results/trima_uv_vis_ajaka_phi0_gaussian_20261103/`.

Input letti, mai modificati:

- `root/uv/reconstruction/istogrammi.root`: TH1 e metadata `quality_metadata`, `dalitz_metadata`.
- `root/uv/beam_asymmetry/beam_asymmetry.root`: `sigma_points`, `ratio_objects`, mappatura degli ID, provenance.
- `08_observable_extraction/references/ajaka2008_figure4_digitized.csv`: 57 punti complessivi; solo 11 del secondo intervallo usati.

Hash SHA-256 e dimensioni effettive nel [manifest](figures/manifest.json). Per gli istogrammi, conservati anche percorsi/hash originali dei file di eventi dichiarati dal metadata. Le copie locali della campagna del 26 ottobre hanno hash diversi: **non sono state usate come sostituti**.

Il ROOT dell'asimmetria dichiara `final_inference=suspended`. Il benchmark non è un risultato finale validato: esposizioni, fondo, sistematiche complete, bias/copertura e covarianza con il risultato storico rimangono da chiudere. La proiezione pη mostra scostamenti visibili dal riferimento: non dichiarare closure o accordo dimostrato. Nessun test globale di compatibilità derivato sommando errori come se i campioni fossero indipendenti. La digitalizzazione non sostituisce i dati numerici originali; non è stata assegnata un'incertezza di digitalizzazione inventata.

Normalizzazione dei controlli: frazione di eventi per bin, dividendo per il totale comprensivo di underflow/overflow. Convenzionale: 257245; BDT: 171599. Il rapporto dei conteggi **non** è un'efficienza di segnale. Gli istogrammi angolari mostrano solo ±10° ma mantengono i flow nel denominatore. Nessuna correzione di accettanza o flusso.

## Fonti tecniche e affermazioni consentite

| Tema | Fonte locale | Limite |
| --- | --- | --- |
| Conversione e contabilizzazione | [Preanalisi](../../../wiki/01-pre-analysis.md) | Input = scritti + scartati per run/stato; non prova retroattiva HBOOK → ROOT |
| Originali e porting | [Mappa Fortran](../../../wiki/legacy-fortran-map.md) | Provenienza storica h70/PREAN e conversione HBOOK ancora incompleta |
| Selezione | [Stage 02](../../../wiki/02-event-selection.md) | Tagli per periodo; veto pioni non equivale ad assenza di tutte le cariche |
| Ricostruzione | [Stage 05](../../../wiki/05-reconstruction.md) | Pairing e missing mass comuni; non fit cinematico globale |
| BDT | [Stage 04](../../../wiki/04-bdt-training.md) | 26 feature ordinate; training fast MC distinto da Geant4 validato |
| Simulazione | [Migrazione](../../../wiki/geant4-migration.md), [validazione](../../../wiki/geant4-validation.md) | Componenti portati e test numerici distinti da calibrazione e validazione fisica |
| Estrazione | [Stage 08](../../../wiki/08-observable-extraction.md), [bin finito](../../../wiki/finite-bin-correction.md) | Rapporto, likelihood, esposizioni e divisore conservati |
| Qualità | [Plotting](../../../wiki/plotting-and-diagnostics.md) | Fit gaussiani diagnostici; tagli già presenti |
| Stato | [Stato scientifico](../../../wiki/status.md) | Fonte corrente, non sostituita dalle note del paper |

La vecchia v0.1 citava il pilot del 10 novembre (128 trasportati, 32 h70/h80, zero h85) come stato principale. La v0.2 elimina quella descrizione ormai storica dall'abstract: non la sostituisce con una dichiarazione di risposta fisica validata. Evidenza originale nel [rapporto del pilot](../../../results_test/geant4-reaction-pilot-20261110/reports/handoff.md), se ancora conservato. Nessun pilot o campagna farm lanciato per il manoscritto.

## Evidenza ancora necessaria prima della submission

1. Audit HBOOK → ROOT: originali, conversione, entry, schema, valori e linkage alla build storica. Non dichiarare conversione completa/lossless senza audit.
2. Inventario del software portato e copertura dei test contro gli originali; separare componenti implementati da configurazioni storiche dimostrate.
3. Confronti quantitativi di geometria/materiali e dati/simulazione, condizioni per periodo, efficienze e closure di Geant4.
4. BDT: implementazione e citazione, modello/threshold congelati, partizioni indipendenti, confronto a efficienza o fondo fissati, controlli di sculpting e bias dell'osservabile.
5. Benchmark finale: policy esposizioni, fondo e sistematiche complete, campioni condivisi, covarianze e convenzioni del riferimento.
6. Autori, affiliazioni, apparato/polarimetria, disponibilità dati/software, acknowledgments e disclosure richiesta dalla rivista.

Le figure mancanti necessitano evidenza scientifica, non semplici segnaposto grafici. I blocchi `TO COMPLETE` nel testo mantengono visibili tali punti. Le attività scientifiche restano governate da `wiki/status.md`; queste note non modificano priorità o campagne attive.

## Bibliografia

- Ajaka et al., PRL 100, 052003 (2008), DOI `10.1103/PhysRevLett.100.052003`. [PDF originale](../../reference_papers/Ajaka_2008_EtaPi0_Photoproduction_PRL100_052003.pdf). Benchmark e caratteristiche del fascio, non prova della validità del nuovo risultato.
- Basaglia et al. (DPHEP), EPJ C 83, 795 (2023), DOI `10.1140/epjc/s10052-023-11885-1`. Metadati verificati sulla pagina editoriale nella discussione precedente. Motivazione della preservazione completa, non certificazione del progetto.
- Agostinelli et al., NIM A 506, 250–303 (2003). Riferimento generale Geant4 verificato nella lista ufficiale e pagina editoriale.
- Brun e Rademakers, NIM A 389, 81–86 (1997). Riferimento generale ROOT.
- GEANT manual, CERN W5013: edizione/autori da verificare contro l'archivio preservato; nota esplicita nel BibTeX, anno non inventato.

LEPS/LEPS2 a SPring-8 è il confronto da documentare se si vuole discutere altri fasci laser-backscattering: non definirlo un esperimento «copiato». La bozza evita la pretesa di unicità e non introduce un confronto tecnico privo di bibliografia primaria specifica.

## Rigenerazione e compilazione

```bash
cd /Users/tonyf/Work/GRAAL/GRAAL_Analysis
PYTHONDONTWRITEBYTECODE=1 python3 docs/papers_to_publish/method/make_figures.py
cd docs/papers_to_publish/method
/Library/TeX/texbin/latexmk -pdf draft.tex
```

Lo script imposta `TMPDIR`, `MPLCONFIGDIR` e cache font sotto `results_test/method-paper-preservation-20261111/`. Legge soltanto gli input scientifici, genera sei PDF e un manifest e si interrompe se falliscono i controlli sul dominio o sui fit.

Compilare dalla cartella del manoscritto per caricare [.latexmkrc](.latexmkrc). REVTeX 4.2, 10 pt, due colonne come `/Users/tonyf/Work/BDX/Articolo_Neutroni/revtex.tex`; stile BibTeX copiato dal BDX con licenza conservata. La configurazione preferisce MacTeX: il TeX MacPorts locale non dispone della classe richiesta. Build sotto `results_test/method-paper-preservation-20261111/build/`, con jobname `method` per evitare il vecchio `draft.bbl` accanto al sorgente; dopo revisione copiare `build/method.pdf` in `draft.pdf`. La copia consegnata non si aggiorna automaticamente compilando.

Build e rendering temporanei rimossi dopo la verifica; log e rapporto minimo restano in quella campagna come evidenza del documento consegnato. I vecchi `draft.bbl`, `draft.synctex.gz` e `draftNotes.bib` locali preesistevano: non sono sorgenti da mantenere e non vengono eliminati arbitrariamente. Il build isolato usa i sorgenti attuali.
