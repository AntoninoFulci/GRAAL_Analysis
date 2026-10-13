# 6 — pairing tradizionale contro BDT+pairing

> Stato al 13 ottobre 2026: **software e confronto diagnostico locale UV/VIS eseguiti**. [Relazione, risultati e limiti](../../reports/2026-10-13-gate-comparison.md). Restano aperti efficienza/fondo indipendenti e inferenza finale. Riferimento: pairing χ².

**Obiettivo:** confrontare analisi tradizionale senza gate con BDT+stesso pairing, entrambe senza 6C.

**Architettura:** riusare `reconstruct_eta_pi0_chi2.py`, `reconstruct_eta_pi0_bdt.py`, core condiviso e stimatori Stage 07. Non implementare nuovo algoritmo di fit tradizionale. **Stack:** PyROOT, NumPy/SciPy. **Spec:** [decisioni](README.md), [prerequisito senza 6C](00-baseline-senza-fit-cinematico.md).

## Già fatto, invarianti e scelta residua

Il codice esistente distingue i percorsi tramite gate; pairing e cut di ricostruzione condivisi. Raw storici condizionati da selezione 6C esclusi: riusata nuova baseline certificata del prerequisito 00. Selezioni approvate e verificate: χ² < 10, risoluzione relativa 0.08, finestra rinculo ±0.06 GeV quando fit spento, molteplicità inclusiva con primi quattro fotoni. Non chiamare questo confronto riproduzione esatta di pubblicazione senza relativo protocollo.

Il BDT è subset correlato; stessi run utilizzabili, flussi, polarizzazioni, masse, φ, correzione finite-bin, trattamento fondo e selezione energia. Non scegliere solo eventi BDT per definire universo della baseline tradizionale. Dipende da punto 1 per covarianza delle differenze, punto 2 facoltativo per diagnosi temporale.

## File candidati

Riuso dei due entrypoint, `05_reconstruction/core/event_logic.py`, `00_common/physics/pairing.py`; estendere solo quanto manca in `07_observable_extraction/beam_asymmetry.py`, `plotting/diagnostics.py`, `scripts/plot_campaign.py`. Test `05_reconstruction/tests/test_event_logic.py`, `tests/test_stage1_contracts.py`, `07_observable_extraction/tests/test_diagnostics.py`. Identità evento stabile: valutare persistenza source-file/entry prima dei confronti appaiati, non affidarsi alla posizione di righe dopo filtri.

## Passi e metodo

- [x] Congelare contratto pairing e selezioni approvate; controllare nuova baseline senza 6C e prova di provenienza. Se già eseguito prerequisito, riusare artefatti validi.
- [x] Tabella cutflow per percorso, run/periodo, E, stato polarizzazione; stesso universo esposizioni. Audit del subset tramite cinematiche esatte, senza identità source-entry certificata; cutflow pre-ricostruzione disponibile solo per run/stato. Limiti espliciti nella relazione.
- [x] Estrarre stessi bin con ratio nominale e likelihood controllo. Mostrare Σ_pairing, Σ_BDT, ΔΣ e covarianza Δ appaiata; contare bin persi/non stimabili invece di confrontare griglie disallineate. Bootstrap diagnostico per run, nessuna inferenza finale.
- [ ] Misurare efficienza e fondo con MC/controlli indipendenti, stabilità E/φ e periodi, qualità fit azimutale, fallback e pressione ai limiti fisici. Riduzione barre o migliore accordo visivo non basta per dichiarare miglioramento.
- [x] Verificare caso gate sempre aperto: stessi eventi e risultati entro precisione numerica; gate selettivo su toy a Σ nota; nessun fitter cinematico chiamato.
- [x] Salvare figure/ROOT e relazione con selezioni, differenze, covarianza, disponibilità dei bin e limiti. Copertura frequentista non misurata; nessun confronto con figura pubblicata.

```bash
python3 -m pytest -q 00_common/tests/test_pairing.py \
  05_reconstruction/tests/test_event_logic.py tests/test_stage1_contracts.py \
  07_observable_extraction/tests/test_diagnostics.py
```

**Consegna diagnostica:** `results/gate-comparison-20261013/`; UV 184 punti comuni, covarianza per 160; VIS 30 comuni, covarianza per 28. Tagli approvati nel prerequisito 00 riusati. 64 repliche/seed 1208; fondo non corretto su entrambi, nessuna dichiarazione di miglioramento. Dettagli, prove e attività scientifiche ancora aperte nella relazione.
