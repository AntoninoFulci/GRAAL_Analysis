# 8 — intervalli energetici e binning

> Stato al 13 ottobre 2026: infrastruttura configurabile e campagne diagnostiche locali completate; validazione fisica estesa e inferenza finale ancora aperte. Usare `superpowers:executing-plans` alla ripresa.

**Obiettivo chiarito:** studiare UV nel range nominale VIS [0.9313,1.10] GeV e dividere a metà ogni intervallo nominale UV/VIS, con statistiche e stabilità di Σ documentate. Binning gestibile da CLI/config, con ritorno ai default storici.

**Architettura:** distinguere configurazione del fascio (laser/polarizzazione) dalla griglia di analisi nel layer comune; propagare lo stesso contratto a MC, training, ricostruzione, esposizioni, ROOT e plot. **Stack:** Python, ROOT, NumPy. **Spec:** [README](README.md), [profili correnti](00-stato-verificato.md).

## Stato iniziale e chiarimenti risolti

UV nominale [1.10,1.20,1.30,1.40,1.50], VIS [0.9313,1.10] GeV in `beam_profiles.py`. All'audit iniziale gli adapter di dataset/provenance e combinazione ROOT verificavano rigidamente questi intervalli. Il contratto è stato poi esteso: non è stato cambiato soltanto l'asse del grafico.

Chiarimento utente del 13 ottobre: UV basso usa esattamente il bin nominale VIS, mantenendo polarizzazione UV. Ogni intervallo attuale viene sdoppiato al punto medio: UV produce 8 bin da 0.05 GeV; VIS usa [0.9313,1.01565,1.10] GeV. Config separate e reversibili; nominale e sottobin si sovrappongono e sono correlati. Nessun bordo scelto in funzione della Σ ottenuta.

Con masse del registro, soglia on-shell è `((mp+mη+mπ0)^2−mp^2)/(2mp)=0.9313112447 GeV`. La parte 0.930–0.931311 è sotto soglia fisica. Tenere distinta energia taggata con risoluzione da energia vera: possibili code/controlli non sono produzione on-shell sotto soglia. La variante eseguita parte da 0.9313, non da 0.930 GeV: “sotto soglia UV” indica qui sotto il range nominale UV di 1.10 GeV. Non è stata richiesta né certificata una misura di produzione on-shell sotto soglia fisica.

## Invarianti e dipendenze

Baseline senza 6C; regola sui bordi `[low,high)` con ultimo bordo incluso coerente in tutti gli stadi. Ogni evento assegnato una volta entro una griglia; griglie sovrapposte in studi diversi sono correlate. Niente flusso nullo, polarizzazione fuori dominio, MC senza supporto o BDT extrapolato senza dichiarazione. Variazione del binning non deve cambiare target/laser.

Il BDT UV corrente è addestrato solo nel dominio nominale. Per studio UV basso: percorso pairing no-BDT offre controllo, mentre risultato BDT richiede training/validazione che copra intervallo nuovo; cambiare solo range runtime violerebbe contratto. Punto 1 per covarianze, punto 5 per canali aperti nel nuovo dominio; punto 9 può seguire ma non è prerequisito obbligatorio.

## File coinvolti e contratto comune

Proprietario delle griglie personalizzate: `00_common/physics/energy_binning.py`; default del fascio in `00_common/physics/beam_profiles.py`. Preset in `config/energy/{nominal,split,uv-low}.json`. Consumer e contratti coinvolti:

`00_common/physics/beam_profiles.py`, `07_observable_extraction/core/binning.py`, `beam_asymmetry.py`, `combine_profiles.py`, `plotting/figure4.py`, `calibration/flux_v2.py`, `io/root_output.py`; `04_bdt_training/beam_spectrum.py`, `dataset/stage1_dataset.py`, `00_common/stage1/artifacts.py`, `05_reconstruction/runtime/stage1_gate.py`; `scripts/run_pipeline.py`, `scripts/artifact_manifest.py`. Toccare solo consumer che assumono bordi nominali; un solo proprietario dei nuovi bordi, niente array locali discordanti.

## Checklist aggiornata

Le spunte indicano lavoro verificato nell'esecuzione locale del 13 ottobre;
non certificano copertura di tutti i periodi sperimentali o inferenza finale.

### Completato

- [x] Definire studi e bordi dal chiarimento utente: UV basso sul range VIS, VIS sdoppiato, UV nominale sdoppiato.
- [x] Creare config reversibili `nominal.json`, `split.json`, `uv-low.json`; esporre `--energy-config` e override standalone `--energy-edges`.
- [x] Separare griglia da target/laser/polarizzazione, mantenendo default storici e regola `[low,high)`, ultimo bordo incluso.
- [x] Propagare dominio a MC, spettro, feature builder, ricostruzioni, esposizioni, estrazione, periodi e diagnostica bootstrap; invalidare cache dipendenti e mantenere `check_profile`.
- [x] Registrare bordi effettivi nei ROOT/provenance; validarli in lettura e usarli nei plot/combiner. Associare Ajaka soltanto a intervalli fisicamente coincidenti.
- [x] Bloccare domini ROOT più stretti del richiesto, modelli fuori dominio e dichiarazioni di training senza supporto positivo del segnale; includere sideband/template MC nei controlli.
- [x] Inventariare eventi/run, flussi V/H/BREM, polarizzazione e canali aperti per gli studi locali; salvare yield/cutflow per periodo e bin, esclusioni e periodi non disponibili. Nessun nuovo training eseguito.
- [x] Eseguire pairing UV basso senza BDT e senza 6C: 3.803 eventi ricostruiti, 3.707 con flussi validi. Nessuna produzione MC sotto soglia vera introdotta.
- [x] Eseguire estrazione ratio/likelihood su split UV/VIS e UV basso raw, lasciando φ e masse nominali; registrare conteggi, esposizioni, P efficace, fit disponibili/fallback/bordo e bin non stimabili.
- [x] Verificare ricomposizione tramite unione eventi/esposizioni e nuovo fit, senza media semplice di Σ: quattro chiusure raw/BDT UV/VIS con ΔΣ = 0 a ordine eventi invariato. Conservare anche scarti numerici da riordinamento, fino a 3.91e-8.
- [x] Salvare 800 contrasti descrittivi figlio−padre e variazione degli errori, senza attribuire significatività a campioni correlati.
- [x] Verificare default, exact-edge, estremi, griglie invalide, ROOT discordanti, canali MC chiusi e modelli fuori dominio: 396 test passati (356 + 40), review indipendente e fix con regressioni.
- [x] Controllare visivamente PDF: 8 righe UV, 2 VIS, 10 nella composizione; salvare comandi, hash, log, report e istruzioni di riproduzione.

### Da completare prima di una misura estesa o finale

- [ ] Preparare/verificare MC e training BDT che coprano UV basso; validare il modello indipendentemente, poi confrontarlo con pairing sullo stesso dominio. Il BDT nominale non è valido per questa espansione.
- [ ] Calcolare efficienze per bin con MC validato e completare l'inventario del supporto MC effettivo. Nell'output attuale efficienza non valutata è `null`.
- [ ] Calcolare covarianze appaiate fra griglie sovrapposte e incertezze di ΔΣ. I contrasti salvati sono descrittivi; correlazioni non stimate non equivalgono a indipendenza.
- [ ] Completare sistematici/copertura necessari all'inferenza finale, in coordinamento con piano 01; fissare eventuali criteri di stimabilità prima di nuovi confronti, senza ottimizzarli sui risultati.
- [ ] Estendere campagne ai periodi non presenti localmente, quando dati e flussi saranno disponibili. Esecuzione attuale: `1998_uv` e `1999_vis` soltanto.
- [ ] Se si studia la coda sotto soglia fisica, usare campioni e risposta tagger dichiarati; migrazione tagger non valutata in questa esecuzione.

### Rifinitura non bloccante

- [ ] Aggiornare etichette PDF: mostrare esattamente 1.01565 e indicare intervalli semiaperti. Formattazione storica arrotonda a quattro decimali e usa notazione inclusiva; config, ROOT e assegnazione numerica sono corretti.

```bash
python3 -m pytest -q 00_common/tests/test_beam_profiles.py \
  07_observable_extraction/tests/test_binning.py \
  07_observable_extraction/tests/test_combine_profiles.py \
  04_bdt_training/tests/test_stage1_dataset.py tests/test_run_pipeline.py
```

**Consegna locale salvata:** `results/energy-binning-20261013/{split/uv,split/vis,uv-low/uv}`. Inventari nei rispettivi `beam_asymmetry/periods/index.json`; riepilogo in `REPORT.md`, contrasti/chiusure in `stability.json`, riproduzione in `check_stability.py`, comandi e hash in `audit.json` ed `extraction-commands.json`, prove in `tests.log` e `cli-tests.log`. Nessun nuovo risultato BDT UV basso o inferenza finale dichiarati.


## Esecuzione del 13 ottobre 2026

Chiarimento utente: UV basso usa intervallo nominale VIS; ogni intervallo
nominale UV/VIS può essere sdoppiato al punto medio. Config reversibili,
nessuna scelta manuale di bordi ottimizzata sui risultati.

Implementati contratto comune, config/CLI, propagazione e controlli di dominio,
cache dipendenti, ROOT auto-descrittivi e pannelli dinamici. Eseguite campagne
locali split UV/VIS e pairing UV basso senza 6C. Nuovo BDT UV basso, efficienze
e covarianze appaiate tra griglie non sono certificati da questa esecuzione.
Vedere [runbook](../../runbooks/energy-binning.md) e
[rapporto](../../reports/2026-10-13-energy-binning.md).
