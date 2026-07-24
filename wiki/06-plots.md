# 06 — Plot

`06_plots/` è la fase finale della pipeline: legge gli alberi ROOT prodotti dalla ricostruzione e genera i **Dalitz plot** M(ηp) vs M(π⁰p), confrontando la ricostruzione solo-chi² con quella con gate BDT.

## Struttura

La cartella è divisa in tre moduli:

* **`kinematics.py`**: contiene solo funzioni matematiche su quadrivettori NumPy (`invariant_mass`, `sqrt_s`, `dalitz_limit`) e le costanti fisiche. Non usa ROOT.
* **`dalitz.py`**: gestisce lettura ROOT, creazione degli istogrammi e grafici.
* **`kinfit_resolution.py`**: studia il miglioramento del fit cinematico usando MC di segnale, leggendo con `uproot` e producendo grafici con matplotlib.

La separazione permette di testare la parte fisica senza dipendere da ROOT.

## Confronto chi² vs BDT

Il comando principale:

```bash
python -m plots.dalitz \
    --chi2 results/reco/reco_eta_pi0_chi2.root \
    --bdt results/reco/reco_eta_pi0_bdt.root
```

richiede entrambi gli alberi, perché lo scopo della fase è confrontare direttamente le due ricostruzioni.

Se un file manca o l'albero è vuoto, la fase termina con un errore esplicito invece di produrre grafici vuoti.

## Grafici prodotti

Per entrambi i campioni vengono prodotti:

* Dalitz plot con protone **misurato**;
* Dalitz plot con protone **implicito** ottenuto dalla massa mancante;
* distribuzioni delle masse η e π⁰;
* confronti raw-only delle masse η e π⁰, dopo il pairing χ² ma prima del fit
  cinematico:
  `massa_eta_raw_confronto.pdf` e `massa_pi0_raw_confronto.pdf`;
* correlazione M(η) vs M(π⁰).

Tutti i plot sono salvati in formato **PDF**. Inoltre gli istogrammi ROOT vengono salvati in `istogrammi.root` per eventuali modifiche successive senza rileggere gli alberi.

## Protone misurato e protone implicito

Vengono confrontate due definizioni del protone:

* **misurato**: usa il quadrimpulso del protone ricostruito dal rivelatore;
* **implicito**: usa il quadrimpulso mancante:

$missing = (beam + target) - (\eta + \pi^0)$

Il secondo caso è equivalente a una massa mancante e non contiene informazione indipendente sul protone misurato.

Per questo motivo solo il Dalitz con protone misurato permette di studiare eventuali problemi cinematici reali.

## Controlli cinematici

Il limite cinematico del Dalitz viene monitorato ma non usato come taglio: gli eventi oltre il limite vengono conteggiati, perché possono essere dovuti alla risoluzione sperimentale vicino al bordo.

Gli eventi realmente impossibili (ad esempio un mesone con energia superiore al fotone di fascio) vengono invece rimossi già nella ricostruzione, prima dei plot.

## Risoluzione del fit cinematico

`kinfit_resolution.py` confronta eventi MC prima e dopo il fit 6C.

Studia principalmente:

* **M(ηp)**;
* **M(π⁰p)**.

Il confronto usa i residui rispetto alla verità del generatore:

$M_{reco}-M_{true}$

per misurare direttamente la risoluzione.

Il fit migliora la risoluzione del Dalitz plot, ad esempio:

* M(ηp): circa **52 → 10 MeV**;
* M(π⁰p): circa **22 → 10 MeV**.

Le masse di η e π⁰ non sono usate per valutare il miglioramento perché sono già vincolate dal fit cinematico.

## Pipeline

La fase viene eseguita con:

```bash
python -m plots.dalitz \
    --chi2 reco_eta_pi0_chi2.root \
    --bdt reco_eta_pi0_bdt.root
```

e opzionalmente:

```bash
python -m plots.kinfit_resolution \
    --signal eta_pi0_mc.root
```

Se manca uno dei due file di ricostruzione, la fase viene saltata con un messaggio esplicito, perché senza entrambi i campioni il confronto non è possibile.
