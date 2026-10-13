# Canale carico pπ+π−: fattibilità e MC diagnostico

Data: 13 ottobre 2026. Piano: [12 — canale carico](../plans/2026-10-12-graal/12-canale-carico.md).

## Decisione e richiesta chiarita

L'utente richiede **pπ+π− come fondo opzionale nel BDT neutro**, per confrontare i risultati con/senza questo contributo; non un veto pionico e non una misura separata del canale carico. Ha inoltre confermato che il MC deve essere creato.

**Esito: GO per un generatore cinematico truth; NO-GO, con gli input attuali, per il fondo BDT validato.** Il generatore è implementato e invocabile esplicitamente. L'inserimento nel BDT resta incompleto: occorre una risposta detector o un controllo etichettato che descriva la migrazione pπ+π− → candidati 4γ+p. Non esiste ancora una misura dell'effetto sui risultati finali.

Il piano originale autorizza uno stop motivato prima del pilot BDT quando mancano gli osservabili/campioni necessari. La successiva richiesta dell'utente estende il deliverable al MC cinematico. Nessuna efficienza di misidentificazione, sezione d'urto o quadrivettore fotonico è stato inventato. Nessun parametro della selezione nominale è cambiato.

## Verifica dell'esistente e invarianti

Graphify è stato consultato senza ricostruire il grafo condiviso: `graphify reflect --if-stale`, quindi `graphify query 'pion preanalysis selector track channel features' --budget 2300`. Espansione ricavata dal vocabolario del grafo. Fonti individuate: `PreAnalysis.h:L11`, `features.py:L80`, `mc_samples.py:L79`, `tests/test_event_selector.py:L61`; le conclusioni sono state verificate sul codice corrente e sui file ROOT. Il risultato del grafo è troncato: non costituisce un inventario esaustivo.

- `01_pre_analysis/PreAnalysis.C`: candidati centrali con `Itipo_track == 13 || 14`; PID mediante tagli energia depositata/dE/dx. Il pion cut centrale è valutato dopo il fallimento del proton cut. Nel forward i tagli protone e pione sono indipendenti: non assumere candidati disgiunti.
- `02_event_selector/select_events.py`: `gammas.size() > 1 && fcharged_theta.size() == 1`; conserva i rami. Non identifica pπ+π−.
- `00_common/stage1/features.py`: 26 feature su esattamente quattro candidati fotonici e un protone. Il canale di verità può essere diverso, ma gli osservabili passati al modello devono avere questo stesso significato.
- `04_bdt_training/dataset/mc_samples.py` e `photon_loss.py`: caricano fotoni e ne simulano la perdita fino a esattamente quattro. Non generano cluster spuri, interazioni adroniche o errori di PID. Per pπ+π− senza decadimenti radiativi il generatore cinematico ha zero fotoni: photon loss non risolve la migrazione.
- `00_common/physics/channels.py`: registro dei canali neutri usato anche dai default. Aggiungervi semplicemente pπ+π− lo includerebbe nei fondi predefiniti, violando sia l'opzionalità richiesta sia il contratto dei campioni.

Nessun generatore pπ+π− né relazione di fattibilità già completata è stato trovato prima di questo lavoro.

## Osservabili: disponibili e mancanti

| Osservabile | Raw h70 | Preanalisi h80 | Conseguenza |
|---|---|---|---|
| Direzioni centrali | `Thet_centr_track`, `Phi_centr_track` | `pions_theta/phi` per candidati PID, in gradi | Possibili conteggi e distribuzioni angolari |
| PID centrale | `Itipo_track`, `Eclusc_track`, `Dedx_track` | Solo esito implicito nella lista pionica | Nessuna probabilità PID o calibrazione indipendente in h80 |
| Segno π+/π− | Nessun campo di segno documentato identificato nello schema esaminato | Assente | Non interpretare 13/14 come segni di carica |
| Quadrimpulso pionico | Deposito calorimetrico, tempi e geometria; nessun quadrivettore pionico calibrato identificato | Assente | Deposito di energia non equivale automaticamente a energia totale del pione |
| Tracce forward | Angoli, `Tof_trf`, `De_trf`, associazioni | `fcharged_theta/phi` in radianti, beta, TOF, `fcharded_de` | Nessun indice che leghi ciascun candidato pionico alla lista forward |
| Protone | PID e osservabili detector | Quadrivettori `protons` | Presenza non dimostra esclusività pπ+π− |
| Vertice/qualità | Coordinate cilindro, `Status_traces_cyl`, tempi | Non propagati come qualità pionica | Da validare prima di definire tagli |
| Identità evento | `Idrun`, `Idevt` | `RunNumber`, senza `Idevt` | Per split raggruppato servono identità stabili; indice locale va associato al file |

Disponibilità non significa calibrazione: il significato di carica/PID nei raw va confermato con dizionario detector. Non è stata svolta una nuova ricerca di letteratura; nessuna fattibilità completa viene dedotta dalla sola presenza dei rami.

## Lettura di eventi reali

Audit in sola lettura con uproot 5.7.4, Python 3.14, ROOT 6.40.04. Letti i **primi 10.000 eventi** di ciascun h80, senza randomizzazione. Questo campione contiene un solo run per file e non stima efficienze o contaminazioni dell'intero periodo.

| Conteggio | 1998 UV, run 1321 | 1999 VIS, run 1964 |
|---|---:|---:|
| Righe totali nel file h80 | 90.279.078 | 94.402.268 |
| Righe lette | 10.000 | 10.000 |
| Almeno due candidati pionici | 950 | 252 |
| Almeno due candidati pionici e un candidato protone | 237 | 126 |
| Preselezione corrente | 726 | 354 |
| Preselezione e almeno un candidato pionico | 336 | 42 |
| Preselezione e esattamente quattro fotoni | 61 | 32 |
| Preselezione e almeno quattro fotoni | 94 | 51 |
| Preselezione, almeno quattro fotoni, candidato pionico | 16 | 4 |
| Lunghezze θ/φ pioniche discordanti | 0 | 0 |
| Valori θ/φ pionici non finiti | 0 | 0 |

Questi conteggi **non etichettano pπ+π−**: segno, esclusività e migrazione non sono provati. Nessun conteggio di eventi del canale identificato è disponibile; non equivale a zero eventi fisici.

Letti anche schema e prime 10.000 righe del raw `test_data/raw/1998_uv/run1321.root`: 585.613 righe totali, run 1321. Gli altri periodi del manifest non hanno ricevuto una verifica evento-per-evento. Il codice esclude il forward per `4577 < run < 4606`; non confondere questo stato con assenza di cariche e non mescolare automaticamente i periodi di deuterio nel canale su protone.

Identificazione dei file (dimensione e UUID ROOT, non hash integrale):

| Percorso | Byte | UUID ROOT |
|---|---:|---|
| `test_data/raw/1998_uv/run1321.root` | 284770796 | `340b4e60-d71b-11eb-90db-ec01a8c0beef` |
| `test_data/pre_analyzed/pre_analisi_1998_uv.root` | 8795289414 | `108a480c-a5f0-11f1-ab17-2b0210acbeef` |
| `test_data/pre_analyzed/pre_analisi_1999_vis.root` | 7529903161 | `8088f410-a5fe-11f1-ab17-2b0210acbeef` |

Per riprodurre il cutflow, leggere con uproot `entry_stop=10000`, `library='ak', how=dict`: `RunNumber`, `pions_theta`, `pions_phi`, `fcharged_theta`, `protons/protons.fCoordinates.fT`, `gammas/gammas.fCoordinates.fT`. Le molteplicità sono `ak.num` di ciascuna lista; la preselezione è `(ng > 1) & (nf == 1)`. Leggere il leaf `gammas.fCoordinates.fT`: `ak.num` sul record composito `gammas` non restituisce direttamente una singola lista di molteplicità.

MC già presenti in `test_data/vis/mc`, ciascuno con 1.000.000 righe `mc`: `eta_pi0`, `pi0pi0`, `3pi0`, `4pi0`, `eta_via_3pi0`, `eta_pi0_via_3pi0`. Verificati schemi: fotoni neutri e protone, nessuna risposta alle cariche. La ricerca dei nomi `*_mc.root` in `test_data`, `data` e `03_mc_simulation` non ha identificato un fondo carico. Nessun controllo dati con etichetta pπ+π− validata disponibile; l'utente conferma che manca il MC.

## MC implementato, esclusivamente opzionale

Macro: `03_mc_simulation/studies/generate_pip_pim_truth.C`.

- Reazione γp → pπ+π−, protone fermo; mp = 0.938272 GeV, mπ± = 0.13957039 GeV.
- Energia del fascio uniforme nella finestra richiesta, troncata inferiormente alla soglia fisica. Nessun peso di sezione d'urto e nessuna struttura risonante assunti.
- Spazio delle fasi Lorentz-invariante a tre corpi, con rejection sampling tramite `GenerateUnweighted` già presente. Seed esplicito governa sia `TGenPhaseSpace` sia fascio/reiezione; il generatore globale ROOT viene ripristinato al termine.
- Tree `mc_truth`: `beam_true`, `target_true`, `proton_true`, `pi_plus_true`, `pi_minus_true`, `event_id`, `n_true_gamma=0`. Quadrivettori in GeV, nessuno smearing o fit 6C.
- Metadati per tipo campione, seed, numero generato, intervallo energetico e masse. `event_id` è locale: combinare file richiede identità del campione oltre all'indice.
- Apertura `NEW`: rifiuta di sovrascrivere output esistenti. Destinazione e parent directory devono esistere/essere scrivibili secondo il normale contratto ROOT.
- Tree separato `mc_truth`, fuori dal registro e dalla generazione nominale: il loader neutro non può consumarlo accidentalmente come `mc`.

Esempio, dalla root del repository, con directory di destinazione già creata:

```bash
root -l -b -q '03_mc_simulation/studies/generate_pip_pim_truth.C(100000,1.10,1.50,"results/charged-channel-20261013/truth/pip_pim_uv.root",12001)'
root -l -b -q '03_mc_simulation/studies/generate_pip_pim_truth.C(100000,0.931311,1.10,"results/charged-channel-20261013/truth/pip_pim_vis.root",12002)'
```

Questi intervalli sono campioni diagnostici espliciti, non una nuova impostazione globale della pipeline.

Entrambi i comandi sono stati eseguiti: **100.000 eventi UV e 100.000 VIS**. La rilettura indipendente con uproot trova residuo massimo per componente di `beam + target − proton − pi_plus − pi_minus` pari a **1,36×10⁻¹⁵ GeV (UV)** e **1,11×10⁻¹⁵ GeV (VIS)**. Il file `results/charged-channel-20261013/truth/manifest.json` registra hash SHA-256 del generatore e dei campioni, seed, finestre e conteggi. Gli hash identificano i file prodotti; la riproducibilità del seed riguarda gli eventi, non i byte ROOT che includono UUID e timestamp.

## Condizioni per abilitare il fondo nel BDT

1. Simulare/validare risposta alle cariche: materiali, geometria, interazioni adroniche, energia e molteplicità dei cluster, associazioni traccia-cluster e PID per periodo. In alternativa, costruire un controllo dati con purezza e contaminazioni misurate. I dati con candidati pionici non costituiscono da soli tale controllo.
2. Produrre gli stessi **candidati ricostruiti** della selezione neutra, compreso il meccanismo che crea quattro candidati γ e il candidato protone. Non sostituire pioni con fotoni né riempire fotoni mancanti con zeri.
3. Validare accettanza e normalizzazione del fondo (sezione d'urto o prior sperimentale dichiarato, con incertezza); conservare conteggio generato e identità degli eventi. Non applicare una seconda volta photon loss a campioni già ricostruiti dal detector.
4. A quel punto estendere il builder responsabile con opzione esplicita, **disattivata per default**, e artefatti/provenienza separati. Stesso schema delle feature all'inferenza; nessuna selezione nuova implicita sui dati.
5. Confrontare con/senza fondo carico su split identici per evento originario/run, validation per la soglia e test indipendente. `fit_stage1` corrente usa split per righe, non raggruppamento per evento. Registrare cutflow, efficienza segnale, rejection, bias e stabilità nei bin; per differenze di Σ usare covarianza appaiata. Non selezionare la variante perché sposta Σ verso un valore desiderato.

Una selezione esclusiva pπ+π− richiederebbe quadrimpulsi calibrati e PID sufficienti per verificare `beam + target − p − π+ − π−` senza fit. Le tolleranze vanno derivate dalle risoluzioni; oggi non sono definibili dai soli angoli. Nessuna ipotesi con particella mancante è stata introdotta.

## Verifiche e limiti della consegna

Prima delle modifiche: 17 test mirati passati su selettore, campionamento MC e contratti Stage-1. Il nuovo test fisico è stato osservato fallire perché il generatore non esisteva, prima di implementarlo. Test dedicati controllano masse, conservazione, finestra, riproducibilità, ripristino RNG, richieste non valide, assenza di fotoni inventati e protezione degli output.

Verifica finale: **57 test passati in 25,95 s**, con il comando:

```bash
python3 -m pytest 03_mc_simulation/tests/test_charged_truth.py 03_mc_simulation/tests/test_generator_physics.py tests/test_event_selector.py 04_bdt_training/tests/test_mc_samples.py tests/test_stage1_contracts.py -q
```

Review indipendente in sola lettura sui tre nuovi file: nessun rilievo azionabile. La suite completa non è stata eseguita: i test coprono il nuovo generatore e i contratti adiacenti, non le modifiche concorrenti dell'intero repository.

Sono stati modificati soltanto nuovi file di questo studio. I moduli condivisi già modificati da altri agenti non sono stati riscritti. L'inserimento opzionale nel BDT e il confronto dei risultati finali restano da realizzare dopo disponibilità del modello detector; il solo MC truth non li completa.
