# Presentazione GRAAL Analysis

`graal_analysis_framework_asimmetrie.pptx` presenta il framework di analisi
per `γp → pηπ⁰` in 18 slide (Aptos, blu e bianco). `build.py` rigenera il
file usando le immagini versionate in `assets/` (richiede pandoc, lxml e
Pillow). Ogni slide include barre di navigazione superiore e inferiore;
la numerazione corrente/18 compare soltanto in quella inferiore.
Gli XML in `assets/slide{2,4,7}_manual.xml` conservano le modifiche fatte
in PowerPoint alle vecchie slide 2, 4 e 7 (quest'ultima è ora la 6). Il
generatore le reinserisce aggiornando numerazione e barre di navigazione.

La slide 3 adatta lo schema in `wiki/workflow.md` alle tre diramazioni principali
(dati, MC/BDT, flussi). La slide 4 unisce la precedente descrizione dei file
ROOT alla preselezione e accompagna due frammenti di codice con la spiegazione.
Il repository conferma che `PreAnalysis.C` legge il tree ROOT `h70`, applica
tagli PID per run e scrive `h80`; `select_events.py` usa PyROOT/RDataFrame
per filtrare gli eventi e scrivere `h85`. La conversione originaria dalle
routine Fortran ai file ROOT e l'attribuzione di conversione e tagli ad
Antonio Riggio derivano dalla ricostruzione storica fornita dal progetto:
il convertitore non è presente in questo repository.

La slide 5 descrive la ricostruzione dei candidati `pηπ⁰`: controllo della
topologia, sei assegnazioni dei quattro fotoni, scelta del minimo χ² delle
masse e costruzione dei due mesoni. I frammenti di codice sono tratti da
`05_reconstruction/runtime/reco_core.py`, `core/event_logic.py` e
`00_common/physics/pairing.py`; le spiegazioni affiancate riassumono i
passaggi. La precedente slide 5, ridondante rispetto allo schema, è stata
rimossa.

La slide 2 riassume GRAAL e l'obiettivo del lavoro. Lo schema di
LAGRANγE è tratto dalla presentazione di D. Rebreyend (MENU04),
[disponibile online](https://www.slideserve.com/balin/general-review-of-graal-physics-achievements-and-future),
e compare anche come figura 2 nell'[articolo di V. Nedorezov](https://inspirehep.net/files/5bd029fb512b4d1bcec10f146acc514a).
La [pagina della figura](https://www.researchgate.net/figure/Experimental-scheme-of-the-detector-LAGRANE-1-Compton-beam-2-target-3-BGO_fig1_323873310)
ne indica la licenza CC BY-NC-SA 1.0.
La descrizione di GRAAL è verificata sulle fonti del progetto e sul
[lavoro di Ajaka et al.](https://doi.org/10.1103/PhysRevLett.100.052003).

Le figure e le metriche UV/VIS provengono dalla campagna locale
`results/test_data/` del 5 ottobre 2026. Sono risultati di prova, non una
pubblicazione finale. Il confronto con Ajaka et al. (2008) usa i punti
sperimentali digitalizzati in
`07_observable_extraction/references/ajaka2008_figure4_digitized.csv`.

Fonti tecniche principali: `wiki/01-pre-analysis.md`,
`wiki/02-event-selection.md`, `wiki/03-monte-carlo-simulation.md`,
`wiki/04-bdt-training.md`, `wiki/06-calibration.md`,
`wiki/07-observable-extraction.md` e `wiki/known-limitations.md`.

La verifica numerica rispetto ai vecchi programmi `mergedateu` e `wnorm`,
lo studio delle sideband e il test di asimmetria piatta su MC sono attività
aperte. La spiegazione delle asimmetrie VIS tramite interferenza delle code
risonanti è presentata come ipotesi fisica da verificare.
