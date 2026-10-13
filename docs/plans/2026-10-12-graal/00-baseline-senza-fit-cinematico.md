# Prerequisito — baseline senza fit cinematico

> **Stato al 13 ottobre 2026: implementato e integrato in `main`** con commit `cf2022f` (baseline locale UV/VIS). Checklist verificata; prove e limiti nella [relazione di esecuzione](../../reports/2026-10-13-baseline-no-fit.md). Nessun piano successivo avviato.

**Obiettivo:** applicare la decisione dell'utente: nessun 6C, nessuna selezione CL o analisi basata su vettori fitted nella nuova campagna.

**Architettura:** riusare `--no-fit` e percorso raw già esistenti; coordinare launcher, estrazione e plotting. Conservare codice e artefatti storici del 6C come archivio, senza eseguirli nella baseline.

**Stack:** Python, PyROOT, NumPy, pytest. **Spec:** decisioni e vincoli nel [README](README.md), evidenze in [stato verificato](00-stato-verificato.md).

## Invarianti e tagli approvati

- Fit azimutali ratio/likelihood restano attivi: l'esclusione riguarda il fit cinematico, non estrazione di Σ.
- Entrambi i percorsi pairing e BDT+pairing devono condividere input, tagli e gestione fotoni/rinculo.
- Nessun riuso dei raw storici come campione senza 6C: ricostruire da `h85` o da `h80` selezionato, senza sovrascrivere.
- Tagli confermati dall’utente il 13 ottobre 2026 e applicati alla campagna: χ² < 10, risoluzione relativa 0.08 e finestra missing mass ±0.06 GeV attorno alla massa del protone. Senza 6C la finestra missing mass è attiva; nessuna selezione CL.
- I default delle CLI dirette e l'intento del launcher devono essere coerenti con “per ora disattivato”; nessun percorso operativo deve riattivarlo implicitamente.

## File e responsabilità verificate

- `05_reconstruction/runtime/cli_options.py`, `reco_core.py`: default/configurazione senza 6C; riusare `core/event_logic.py` se non servono cambiamenti.
- `scripts/run_pipeline.py`: comando senza fit per entrambi i percorsi, niente `--raw-bdt-fit`, identità della nuova campagna.
- `07_observable_extraction/beam_asymmetry.py`: campioni raw e raw_bdt; escludere confronto/sistematico raw_vs_kinematic_fit con motivo “disattivato”, non errore zero.
- `scripts/plot_campaign.py`: togliere requisito `require_fit=True` dalla modalità senza fit; non invocare confronti `comparison_raw_fit_*` e `plots/mass_comparison.py` che richiedono 6C.
- `plots/core/reconstruction_data.py`, `plots/dalitz.py`: riusare supporto raw; nessun misto raw/fitted né overlay 6C nella campagna.
- `scripts/artifact_manifest.py`, `tests/test_artifact_manifest.py`: verificare contratti/provenienza interessati; invalidare soltanto artefatti effettivamente dipendenti.
- Test: `tests/test_run_pipeline.py`, `tests/test_plot_campaign.py`, `05_reconstruction/tests/test_event_logic.py`, `plots/tests/test_reconstruction_data.py`, `07_observable_extraction/tests/test_beam_asymmetry_cli.py`.
- Documentare modalità in `docs/runbooks/full-pipeline.md` e relazione del passo.

## Passi e prove

- [x] Registrare tagli approvati, run utilizzabili e input; controllare se esiste già ricostruzione certificata `do_fit=false`. Riusarla solo con prova della provenienza.
- [x] Estendere test del launcher: entrambe le ricostruzioni senza 6C, estrazione priva del campione fit. Test della CLI diretta: default operativo non reintroduce fit.
- [x] Test evento con stub fitter che fallisce se chiamato: in modalità senza fit non deve essere invocato; evento viene deciso da pairing, guardie e missing mass. Test che fit-failure storico non determini selezione nuova.
- [x] Adattare integrazione usando funzioni esistenti. Test plotting su ROOT senza rami fit: Dalitz/raw e asimmetrie prodotti; prodotti 6C assenti e nessun PDF storico copiato per errore.
- [x] Eseguire test mirati e smoke su piccolo campione dichiarato, poi ricostruzione della nuova baseline da input reali quando disponibili. Il layout storico locale non va spostato senza necessità: passare percorsi espliciti o documentare input mancanti.
- [x] Verificare ROOT riaperto: provenienza `do_fit=false`, nessun ramo fit necessario, conteggi per run/stato, tagli effettivi e lista esclusioni. Confrontare cutflow storico solo come diagnostica, non attribuire differenze esclusivamente al BDT.

```bash
python3 -m pytest -q tests/test_run_pipeline.py tests/test_plot_campaign.py \
  05_reconstruction/tests/test_event_logic.py plots/tests/test_reconstruction_data.py \
  07_observable_extraction/tests/test_beam_asymmetry_cli.py
```

## Risultato atteso e limiti

Nuova baseline pairing e BDT+pairing senza 6C, ROOT/PDF coerenti e manifest di provenienza. Non basta cambiare etichetta o disegnare rami raw. Nessun risultato numerico senza nuova estrazione; nessun nuovo training obbligatorio se il modello e i suoi input restano validi. Questo prerequisito serve ai punti 1,2,4,6,8,9,10; inventari e letteratura possono proseguire indipendentemente.

## Evidenze di completamento

- Nessuna baseline storica riusata come campione senza fit. Nuova ricostruzione
  da `test_data/selected/analisi_1998_uv.root` (5.341.787 entrate) e
  `test_data/vis/selected/analisi_1999_vis.root` (3.207.538 entrate).
- Smoke separato: prime 20.000 entrate per profilo, poi processing completo
  degli input locali per pairing e BDT+pairing. Tagli e input comuni verificati.
- Suite completa dopo implementazione e review: **792 test passati**.
  Regressioni coprono default CLI, launcher, fitter vietato nel percorso raw,
  provenienza, Dalitz e rifiuto PDF storici. Verifica sul checkout integrato
  riportata nella relazione.
- Campagna `results/baseline-no-fit-20261013/`: UV 15.164 eventi pairing e
  12.261 BDT; VIS 6.219 pairing e 2.706 BDT. Quattro ROOT ricostruiti riaperti:
  `do_fit=false`, nessun ramo fit, conteggi per run/stato conservati.
- Estratte nuove asimmetrie raw/raw_bdt e prodotti 42 PDF. Nessun prodotto 6C;
  sistematico raw/fit assente con motivo `disabled`, non errore zero.
- `reconstruction_manifest.json`, `exclusions_and_validation.json`,
  `pipeline_artifacts.json` e `commands.json` conservano provenienza, tagli,
  comandi, run/stati, hash e liste di esclusione. Cache selected/MC/BDT
  verificate senza invalidazioni: disabilitare 6C cambia i soli consumatori.

## Limiti conservati alla chiusura

Baseline riferita agli input locali disponibili, non all’intera produzione.
Flussi incompleti e bin non stimabili restano esplicitamente esclusi; nessuna
interpolazione. Sistematico molteplicità UV non stimabile in alcuni bin.
Modello UV legacy riusato secondo compatibilità già prevista dal codice,
senza nuova certificazione del training. Confronto storico solo diagnostico:
uguaglianza input non certificata, differenze non attribuite al solo BDT.

Questi limiti sono registrati nella relazione e non riaprono attività dei
piani 01–13. Lavoro autorizzato e chiuso qui: solo prerequisito 00.
