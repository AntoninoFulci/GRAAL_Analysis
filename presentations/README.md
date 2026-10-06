# Presentazione GRAAL Analysis

`graal_analysis_framework_asimmetrie.pptx` presenta il framework di analisi
per `γp → pηπ⁰` in 17 slide (Aptos, blu e bianco). `build.py` rigenera il
file usando le immagini versionate in `assets/` (richiede pandoc, lxml e
Pillow). Ogni slide include barre di navigazione superiore e inferiore;
la numerazione corrente/17 compare soltanto in quella inferiore.
Gli XML in `assets/slide{2,4}_manual.xml` conservano le modifiche fatte
in PowerPoint alle slide 2 e 4. Il generatore le reinserisce aggiornando
numerazione e barre di navigazione.

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

La slide 6 documenta la generazione Monte Carlo con quattro coppie
«codice → spiegazione»: finestra energetica, eventi non pesati, smearing e
selezione di quattro fotoni osservati per il BDT. Gli estratti provengono dai
generatori C++/ROOT, da `smearing.h` e da `04_bdt_training/dataset/mc_samples.py`.
La slide 7 raggruppa gli otto fondi secondo il modo in cui possono imitare
il segnale; le soglie del registro dei canali spiegano perché tre di essi
restano fuori dalla regione VIS.

La slide 8 incorpora la revisione manuale dell'autore e riassume le pagine
10–11 della [presentazione BDT di A. Nayak (2024)](https://indico.global/event/8005/contributions/72298/attachments/35527/66183/BDT.pdf).
Il diagramma dell'albero, già scelto dall'autore nella slide, è versionato
in `assets/decision_tree_nayak.png`. Il testo ora usa normali caselle
modificabili di PowerPoint e descrive i pesi degli eventi, la scelta di
variabile e soglia a ogni nodo, la divisione ricorsiva, le foglie e i
criteri di arresto. La frase sui tagli conserva il senso della modifica
manuale: un evento segue un ramo invece di essere scartato subito.
La slide 9 presenta il classificatore del progetto: 26 variabili, modelli
separati UV/VIS, selezione sullo score e un grafico UV della campagna locale
`results/production-20261006-113738`. La distribuzione degli score mostra
densità non pesate e normalizzate separatamente per segnale e fondo; ROC,
AUC e F1 usano i pesi del MC. La soglia che massimizza F1 viene scelta
sullo stesso campione di validazione usato per riportare F1: il valore non
è una stima su un test indipendente né misura la purezza nei dati reali.

La slide 10 è stata verificata sul codice in
`06_calibration/build_strip_energy_flux.py` e `06_calibration/run_manifest.py`.
Mostra quattro coppie «codice → spiegazione»: validazione del manifest,
lettura di `h80`, tripletto dei flussi e fit `pol4` con pubblicazione ROOT.
Il manifest non contiene la polarizzazione: questa proviene dal ramo
`Polarization` di `h80`. La mediana di energia per run/strip appartiene al
lookup e ai controlli; l'asse energetico degli istogrammi pubblicati deriva
dal fit separato per run e polarizzazione, costruito sulle medie per cella.
La mancanza di uno degli istogrammi `POL1`, `POL2`, `BREM` è un errore di
lettura, non una semplice esclusione del run.

La slide 2 riassume GRAAL e l'obiettivo del lavoro. Lo schema di
LAGRANγE è tratto dalla presentazione di D. Rebreyend (MENU04),
[disponibile online](https://www.slideserve.com/balin/general-review-of-graal-physics-achievements-and-future),
e compare anche come figura 2 nell'[articolo di V. Nedorezov](https://inspirehep.net/files/5bd029fb512b4d1bcec10f146acc514a).
La [pagina della figura](https://www.researchgate.net/figure/Experimental-scheme-of-the-detector-LAGRANE-1-Compton-beam-2-target-3-BGO_fig1_323873310)
ne indica la licenza CC BY-NC-SA 1.0.
La descrizione di GRAAL è verificata sulle fonti del progetto e sul
[lavoro di Ajaka et al.](https://doi.org/10.1103/PhysRevLett.100.052003).

Le figure delle asimmetrie UV/VIS provengono dalla campagna locale
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
