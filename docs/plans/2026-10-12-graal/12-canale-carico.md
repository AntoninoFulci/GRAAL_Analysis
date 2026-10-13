# 12 — fattibilità del canale γp → pπ+π−

> Valutazione prima del test; futuro passo isolato con `superpowers:executing-plans`.

**Obiettivo:** decidere se e come usare un canale carico con selezioni e campioni compatibili.

**Architettura:** riusare detector/manifest e infrastruttura training quando compatibili; topologia carica e schema feature distinti dal contratto a quattro fotoni. **Stack:** strumenti ROOT/Python già presenti; nessuna dipendenza nuova necessaria per audit. **Spec:** [README](README.md), [pipeline corrente](00-stato-verificato.md).

## Già presente e incompatibilità

Preanalisi identifica candidati centrali e salva `pions_theta/pions_phi`; ciò non dimostra disponibilità di segno di carica e quadrimpulso completo. Stage 02 richiede almeno due fotoni; Stage 1 BDT accetta esattamente quattro fotoni. Questi campioni/features non possono rappresentare direttamente pπ+π−. Mai riempire fotoni mancanti con zeri per forzare compatibilità.

## Decisioni e dipendenze

Chiarire ruolo: controllo indipendente, fondo con misidentificazione, oppure nuova misura del canale carico. Verificare capacità effettiva di distinguere π+ e π−, PID p/π, momento/energia e risposta detector nei dati disponibili. Punto 11 aiuta dizionario tracce; letteratura e campioni detector servono prima di affermare fattibilità. Tutto senza 6C nella fase corrente.

## File candidati

Audit `01_pre_analysis/PreAnalysis.h`, `PreAnalysis.C`, `02_event_selector/select_events.py`, `00_common/physics/channels.py`, `04_bdt_training/dataset/`, `00_common/stage1/features.py`. Primo deliverable soltanto `docs/research/<data>-charged-channel-feasibility.md`. File di implementazione successivi si definiscono dopo fattibilità: niente scaffold di classifier generico ora.

## Passi e metodo

- [ ] Mappare osservabili disponibili: tracce centrali/forward, carica, PID, energia/momento, vertice/tempi, qualità e identificatori. Ispezionare schema e campioni reali per periodo, distinguendo assente/non calibrato/disponibile.
- [ ] Definire selezione candidata pπ+π− con bilanci cinematici senza fit, accettanza e controlli di PID; non imporre tre tracce perfettamente identificate se detector non lo consente. Eventuale topologia con particella mancante è altra ipotesi da concordare.
- [ ] Inventariare campione dati di controllo e MC con risposta cariche compatibile. Phase space neutro o solo photon loss non simulano efficienza/PID delle cariche.
- [ ] Se ruolo è fondo del 4γ+p: richiedere modello o controllo misidentificazione/cluster, non usare puro pπ+π− come se avesse quattro fotoni osservati. Se ruolo è nuova analisi: ramo selezione e feature specifici, con ipotesi/massa/pi± e provenienza separati.
- [ ] Decisione fattibilità scritta con evidenze. Senza segno carica/PID sufficiente, dichiarare quali osservabili restano possibili e fermare test del canale identificato.
- [ ] Solo dopo scelta del ramo e input: pilot BDT con split per run/evento, classi/fondi definiti e confronto con tagli tradizionali. Test indipendente, nessuna contaminazione con neutral training, metriche di efficienza/bias e cutflow. Nessuna asimmetria del canale carico interpretata come ηπ0.

**Verifica:** tabella schema e lettura di eventi reali, conteggi di eleggibilità, controlli carica/kinematica e validazione MC se disponibile. **Consegna:** go/no-go motivato, selezioni e campioni necessari; non promessa di BDT carico già addestrabile. Un esito negativo completa correttamente la valutazione.
