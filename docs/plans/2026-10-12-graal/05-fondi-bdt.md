# 5 — fondi BDT e decadimenti η a 6γ

> Piano futuro isolato; usare `superpowers:executing-plans` quando richiesto.

**Aggiornamento 13 ottobre 2026:** audit implementato e svolto sui sei MC VIS locali (6 milioni di eventi), fonti rivalidate, cinque ablation con hold-out comune e toy condizionato di injection. [Relazione, risultati e criticità](../../reports/2026-10-13-bdt-background-audit.md). **Piano fisico ancora aperto:** MC UV/truth dei fondi assenti, normalizzazioni/BR e componenti esclusive da concordare, coverage degli stimatori Σ reali non verificata. Nessuna miscela di produzione modificata. Le note fisiche iniziali sotto sono ipotesi da confrontare con l'audit, non conclusioni convalidate.

**Obiettivo:** verificare copertura e plausibilità dei fondi, aggiungendo solo canali mancanti supportati da dati/modello dichiarato.

**Architettura:** registro `CHANNELS` e generatori esistenti rimangono proprietari di masse, decadimenti e pesi; feature comuni immutate salvo necessità dimostrata. **Stack:** ROOT/C++, Python, XGBoost. **Spec:** [README](README.md), [audit](00-stato-verificato.md).

## Già fatto e decisioni fisiche

`eta_via_3pi0`: γp→pη, η→3π0→6γ; `eta_pi0_via_3pi0`: reazione segnale con η→3π0, totale 8γ. Entrambi hanno generatori e registro; VIS li include già. Otto fondi registrati complessivamente: `pi0pi0`, `3pi0`, `eta_2pi0`, `omega_pi0`, `etaprime`, `eta_via_3pi0`, `4pi0`, `eta_pi0_via_3pi0`.

`eta_2pi0` e `4pi0` usano stime dichiarate, non misure. Alcuni pesi scalano da un'ancora con spazio delle fasi: non garantiscono forma energetica reale. Il contributo ηπ0 con diverso decadimento è legato al segnale dal branching, evitando normalizzazione circolare alla sezione d'urto da misurare.

## Invarianti e dipendenze

Il 6γ è decadimento di η, non nuovo nome per 3π0 non risonante. Non duplicare popolazioni, branching o accettanza nei pesi. Stessa perdita fotoni e selezione osservabile per classi; MC semplificato non prova risposta completa detector. Pesi segnale/prior di training non sono misure di sezione d'urto. Baseline senza 6C per test su dati; punto 13 per verifica fonti e punto 1 per impatto su Σ.

## File candidati

`00_common/physics/channels.py`, `cross_sections.py`, `03_mc_simulation/generators/`, `04_bdt_training/dataset/channel_weights.py`, `dataset/mc_samples.py`, `build_background_features.py`, `photon_loss.py`, `scripts/run_pipeline.py`. Test registro/pesi, `03_mc_simulation/tests/test_generator_physics.py`, `04_bdt_training/tests/test_channel_weights.py`, `test_build_background_features.py`. Nuovi generatori soltanto dopo scelta documentata del canale.

## Passi e metodo

- [ ] Matrice canale→reazione→decadimento→nγ→soglia→fonte/BR→normalizzazione→MC presente→quota accettata. Riaprire campioni esistenti e verificare decadimenti e quattro-momento prima di rigenerare.
- [ ] Confermare 6/8 fotoni veri e probabilità di osservarne quattro. Controllare branching contato una volta; perdita di 2/4 fotoni e ordinamento casualizzato identici fra train/inferenza per quanto applicabile.
- [ ] Verificare fonti delle ancore esistenti, specialmente η vicino soglia. Per stime non misurate fare scenari dichiarati con intervalli motivati, non numero centrale inventato.
- [ ] Valutare altri candidati: produzione singola ω→π0γ con cluster aggiuntivo, canali neutri con fotoni persi/cluster sdoppiati, accidentali/tagging, canali carichi con misidentificazione. Per ciascuno motivare soglia, topologia e via reale verso 4γ+p; se manca simulazione di fake/merge, dichiarare non modellabile dal solo photon-loss attuale. Non inserirlo con peso zero facendolo sembrare incluso.
- [ ] Accettare/escludere candidati tramite supporto energetico, sezioni d'urto/limiti, BR e accettanza. Chiedere scelta fisica prima di adottare stime che cambiano miscela. Isolare contributi risonanti/non risonanti per evitare sovrapposizioni.
- [ ] Ablation su stessi split: fondi correnti, aggiunta singola, variazione pesi. Misurare efficienza segnale, rigetto per canale, sculpting in masse/E/φ e bias/coverage Σ con injection nota. Nessun tuning su accordo con Σ pubblicata.
- [ ] Salvare tabella inclusione/esclusione, fonti verificate e quote prima/dopo selezione; bundle di training separati e riconoscibili.

```bash
python3 -m pytest -q 00_common/tests/test_channels.py \
  00_common/tests/test_cross_sections.py 03_mc_simulation/tests/test_generator_physics.py \
  04_bdt_training/tests/test_channel_weights.py \
  04_bdt_training/tests/test_build_background_features.py
```

**Consegna:** audit dei fondi già presenti, eventuali estensioni motivate, confronto quantitativo su hold-out. Limiti: fake detector e normalizzazioni senza misura non sono risolti aumentando MC o AUC. Non rifare η→6γ se i controlli esistenti bastano.

## Evidenze di esecuzione — 13 ottobre 2026

- [x] Matrice dei nove canali, soglie, normalizzazioni, disponibilità MC e quote prima/dopo selezione; riaperti tutti i sei campioni VIS.
- [x] Verificate molteplicità 6/8 e P(4 osservati), stesso photon-loss e feature. Chiusura truth verificata per il segnale; non verificabile dai ROOT dei fondi, che conservano soltanto vettori smeared.
- [x] Verificate fonti primarie e BR; rilevate ancore/citazioni errate o non supportate. Stime prive di intervallo motivato restano tali.
- [x] Tabella dei candidati con via verso 4γ+p, inclusione/esclusione e sovrapposizioni; nessun nuovo canale fittiziamente incluso a peso zero.
- [x] Cinque confronti sugli stessi split VIS, efficienza/rigetto, istogrammi di sculpting e differenze appaiate; modelli diagnostici separati.
- [x] Injection nota in toy di momento angolare, risposta di ricostruzione e coverage condizionata salvate; non certifica gli stimatori di produzione.
- [x] Script riproducibile, identità degli input e split salvati, 157 test mirati passati, review indipendente del codice nuovo.
- [x] Decisione utente del 13 ottobre 2026: mantenere 4π0 e ηπ0π0 come scenari diagnostici; produzione invariata. Nessuna nuova normalizzazione o esclusione dalla miscela di produzione adottata.
- [ ] Per un'eventuale futura miscela fisica: normalizzazioni/BR e separazione dei contributi risonanti/non risonanti supportate da fonti; fuori dall'attuale consegna diagnostica.
- [ ] Confronto quantitativo UV, truth dei fondi e bias/coverage Σ di produzione con risposta detector adeguata.
