# Piano 05 — audit dei fondi BDT

Data: 13 ottobre 2026. Revisione: `f568c6b`, più modifiche locali preesistenti. **Il piano non era già completato:** generatori e registro esistevano; mancavano audit delle fonti, quote dopo selezione e confronto indipendente. Questa attività completa l'audit e lo studio diagnostico sui campioni VIS disponibili. **Non certifica una nuova miscela fisica né chiude lo studio UV o la coverage dell'estrazione Σ di produzione.**

Script: [`scripts/audit_bdt_backgrounds.py`](../../scripts/audit_bdt_backgrounds.py). Fonti: [verifica primaria separata](../research/2026-10-13-bdt-background-sources.md). Artefatti finali: [`results/background-audit-20261013/vis-final/`](../../results/background-audit-20261013/vis-final/). La directory sorella `vis/` conserva la prima esecuzione, precedente all'aggiunta del riepilogo della risposta nel toy; usare `vis-final/` come consegna.

Nessun registro, generatore, peso o modello di produzione modificato. Nessun MC rigenerato; nessuna inferenza sui dati reali. Modifiche altrui preservate. Nuovi modelli esplicitamente diagnostici, fuori dalle directory dei bundle di produzione.

## Metodo e provenienza

Graphify interrogato con vocabolario del grafo: `background channel eta decay photon loss weights acceptance training`. Il grafo del 29 settembre ha identificato `MCChannel`, `sigma_at`, `channel_yield`, `compute_shares`, `build_channel_features`, `sample_surviving_photons` e training. Verifica successiva sui sorgenti correnti: il grafo non prova lo stato di ottobre.

Sono stati aperti tutti i sei ROOT `test_data/vis/mc/*_mc.root`, un milione di eventi per canale. `manifest.json` registra percorsi assoluti, dimensioni e SHA-256 dei sei input, dello spettro energetico e dei sorgenti effettivi, revisione, seed, feature, selezioni e versioni. Copia dei sorgenti conservata in `source_snapshot/`, verificata contro gli stessi hash. NumPy 2.5.0, uproot 5.7.4, XGBoost 3.2.0, scikit-learn 1.9.0. Il manifest identifica il codice usato, senza attribuire agli archivi MC una revisione o un seed di generazione che non memorizzano. Modifiche concorrenti di altre attività sono rimaste intatte; i sorgenti del calcolo sono stati controllati nuovamente alla chiusura.

Stesso modello di photon-loss per tutte le classi, parametri `LossParams()`; esattamente quattro fotoni osservati; ordinamento casualizzato; 26 feature condivise immutate. Parametri della baseline senza 6C: χ²<10, risoluzione relativa 0.08, energie dei due candidati non superiori al fascio, |M(missing)−mₚ|<0.06 GeV. Quest'ultima massa è quella del protone mancante dopo aver sottratto i quattro fotoni, **non** la feature `missing_mass`, che sottrae il protone misurato.

Il campionamento è stato confrontato con il calcolo esatto Poisson-binomiale della probabilità di osservare quattro fotoni, condizionato agli eventi e al modello di efficienza. Tutti gli scarti sono inferiori a 0.92 errori standard del campionamento.

## Matrice dei canali

In tabella, σ indica il valore **attuale del registro**, non una misura nuovamente validata. Nγ conta i decadimenti forzati dai generatori. La produzione iniziale include sempre il protone di rinculo.

| Canale | Produzione e decadimento forzato | Nγ | Soglia Eγ [GeV] | Normalizzazione attuale | MC locale / esito |
|---|---|---:|---:|---|---|
| `eta_pi0` | pηπ⁰; η→γγ, π⁰→γγ | 4 | 0.931311 | Prior di training 0.5, nessuna σ assoluta | VIS presente; segnale |
| `pi0pi0` | pπ⁰π⁰; 2π⁰→4γ | 4 | 0.308789 | σ=4.5 μb a 2.2; citazione errata | VIS presente; ancora da rivalidare |
| `3pi0` | p3π⁰; 3π⁰→6γ | 6 | 0.492309 | σ=1.8 μb a 1.26; Tab. I verificata | VIS presente; η sottratta nella fonte |
| `eta_2pi0` | pηπ⁰π⁰; η→γγ, 2π⁰→4γ | 6 | 1.174228 | 0.3 μb a 1.90: stima, non bound dimostrato | Assente; sopra VIS; UV non valutabile |
| `omega_pi0` | pωπ⁰; ω→π⁰γ, 2π⁰→4γ | 5 | 1.366365 | 0.49 μb: media bin 1.383–1.817 | Assente; sopra VIS; UV non valutabile |
| `etaprime` | pη′; η′→ηπ⁰π⁰, η→γγ | 6 | 1.446627 | 0.35 μb a 1.60: valore non confermato | Assente; sopra VIS; UV non valutabile |
| `eta_via_3pi0` | pη; η→3π⁰→6γ | 6 | 0.707812 | 0.65 μb ≈2×0.327 a 1.03; ancora contestata | VIS presente; distinto da `3pi0` |
| `4pi0` | p4π⁰; 4π⁰→8γ | 8 | 0.695247 | 0.2 μb a 1.45: stima, non bound dimostrato | VIS presente; continuo da definire |
| `eta_pi0_via_3pi0` | pηπ⁰; η→3π⁰, totale 4π⁰→8γ | 8 | 0.931311 | Prior segnale ×0.327/0.394 ×rapporto accettanze | VIS presente; nessuna nuova σ assoluta |

**Tutti i MC UV sono assenti localmente**, anche per i sei canali presenti in VIS. Non si estendono i numeri VIS all'UV.

## Decadimenti, quattro-momento e accettanza

| Canale VIS | P(4γ) analitica | Eventi con 4γ | Dopo tagli senza 6C, prima BDT | Quota training corrente |
|---|---:|---:|---:|---:|
| `eta_pi0` | 0.288999 | 288959 | 222344 | 0.500000 |
| `pi0pi0` | 0.264983 | 264910 | 13758 | 0.085663 |
| `3pi0` | 0.355314 | 355450 | 3556 | 0.070178 |
| `eta_via_3pi0` | 0.349334 | 349751 | 3 | 0.078765 |
| `4pi0` | 0.186198 | 185982 | 0 | 0.000289 |
| `eta_pi0_via_3pi0` | 0.184708 | 184374 | 0 | 0.265105 |

Denominatore: 1,000,000 eventi generati per riga. Quote di training prima della selezione osservabile, calcolate con la convenzione corrente e il prior scelto; **non frazioni di contaminazione misurate**. Gli eventi senza peso, prevalentemente fuori supporto energetico, sono contati in `audit.json` (9513, 8570, 11402, 11211, 5931, 5851 rispettivamente).

Molteplicità 6/8 verificate in tutti gli eventi e contro i rami effettivi. Salvate distribuzioni delle masse delle coppie figlie, della somma dei sei fotoni η e dei residui del quattro-momento dopo smearing. Solo `eta_pi0` conserva vettori truth completi: chiusura massima per componente ≤1.45×10⁻¹⁵ GeV. I fondi memorizzano soltanto vettori smeared: **la conservazione esatta e le masse on-shell a livello truth non sono verificabili su questi file**. Verifica strutturale dei generatori non equivale a prova della provenienza dei vecchi campioni.

Zero eventi accettati non prova assenza fisica. Per zero su 10⁶, il limite binomiale superiore unilaterale al 95% è circa 3×10⁻⁶ **solo condizionato al generatore, finestra e detector semplificato usati**; non è un limite sulla sezione d'urto o sul fondo nei dati. Tre eventi η→6γ sono statistica troppo bassa per un'estrapolazione affidabile.

La randomizzazione nel training elimina l'etichetta del genitore nei sei slot di massa. Inferenza usa la medesima funzione di feature sui fotoni osservati, senza uno shuffle esplicito. Non è dimostrata invarianza esatta del BDT alle permutazioni, né equivalenza statistica con l'ordinamento del detector reale.

## Risultati della code review fisica

1. **P1 — reweighting dei sopravvissuti cancella la forma dell'accettanza.** In `04_bdt_training/dataset/mc_samples.py:110`, il denominatore MC è stimato dopo la perdita fotoni. Con densità generata q(E), accettanza A(E), qₛ(E)∝q(E)A(E): ripesare i sopravvissuti con p(E)/qₛ(E) produce forma p(E), invece di p(E)A(E). Dividere successivamente per N generati non recupera A(E). Controesempio riprodotto: due bin generati equipopolati, A=(0.2,0.8), p=(0.9,0.1); rendimento corrente **0.50**, integrale richiesto **0.26**. Nel ristretto VIS disponibile, cambiamento integrato piccolo; non elimina il difetto generale.

2. **P1 — σ(E) non compare nel peso degli eventi all'interno del canale.** `build_background_features.py:217` usa solo `w_beam` dopo aver fissato la quota integrata. La forma energetica di un fondo dovrebbe includere σ(E), non soltanto il suo totale. La variante `proposal_weights` sposta il denominatore prima della perdita, ma **non pretende di correggere anche questo difetto**, l'uso dell'energia smeared o la normalizzazione fuori supporto.

3. **P1 — convenzione BR non uniforme.** I generatori forzano i decadimenti. `eta_via_3pi0` incorpora già BR(η→3π⁰) nell'ancora; `omega_pi0` usa invece la sezione della produzione senza BR(ω→π⁰γ). `etaprime` non applica esplicitamente BR(η′→ηπ⁰π⁰)×BR(η→γγ); il significato dell'ancora non è documentato abbastanza per correggerlo moltiplicando alla cieca. Analoga scelta serve per `eta_2pi0`. I BR dei π⁰ sono trattati implicitamente come unitari; nel rapporto completo 8γ/4γ manca il fattore BR(π⁰→γγ)³, salvo convenzione dichiarata. Occorre fissare sezioni di produzione versus sezioni del decadimento prima della nuova miscela.

4. **P1 — fonti e sovrapposizioni non giustificano la miscela nominale.** La citazione π⁰π⁰ tratta canali strani. Le ancore η e η′ non coincidono con le figure citate; valori grafici indicativi nella nota fonti, non nuovi centrali adottati. Le stime 0.3 e 0.2 μb non hanno intervalli motivati verificati. `eta_2pi0` inclusivo contiene η′; `4pi0` inclusivo contiene ηπ⁰→4π⁰. Definire il residuo non risonante prima di sommarli. Nessuna variazione ±fattore arbitrario presentata come errore fisico.

5. **P2 — BR non elimina una forma energetica ignota in un rapporto di integrali.** `channel_weights.py:121` usa il rapporto delle accettanze integrate senza σ del segnale. Evita una normalizzazione assoluta circolare, ma il rapporto fisico è ∫pσA₈/∫pσA₄. σ(E) si cancella punto per punto, non in generale tra questi due integrali. La forma energetica o la costanza del rapporto A₈/A₄ è un'assunzione da dichiarare.

6. **P2 — commento cinematico η→6γ errato.** `channels.py:270–275` e il generatore attribuiscono a una coppia γγ una vera massa η. Fotoni dello stesso π⁰ hanno mπ⁰; scegliendoli da due π⁰ resta almeno un π⁰ integro, quindi mγγ≤mη−mπ⁰≈0.413 GeV. Fondo possibile per risoluzione/combinatoria, non per un vero picco η→γγ. I tre sopravvissuti misurati non giustificano cancellare il canale.

Anche `beam_spectrum.measure()` legge lo spettro degli eventi **preselezionati**, non il flusso incidente calibrato. L'audit usa questo target per riprodurre il training, senza promuoverlo a misura del flusso fisico.

## Ablation su hold-out comune

Per ogni canale: campione casuale fissato di 80000 eventi con quattro fotoni, seed 20261013+indice; identità salvata come indice di riga nel ROOT identificato da SHA-256. Split indipendente 60% train / 20% development / 20% test. Stesse righe nei cinque confronti; nessun riuso del test per soglie o iperparametri. 100 alberi, profondità 5, learning rate .05, subsample e colsample .8. Soglia F1 scelta solo sul development della variante; si confrontano quindi anche punti operativi differenti, non esclusivamente classificatori a efficienza fissata.

| Variante | Soglia | Eff. segnale BDT+tagli | Eff. π⁰π⁰ BDT+tagli | Eff. 3π⁰ BDT+tagli |
|---|---:|---:|---:|---:|
| Corrente, sei canali | 0.53693 | 0.76383 | 0.02258 | 0.00583 |
| Senza entrambi i decadimenti η | 0.48769 | 0.76305 | 0.01905 | 0.00507 |
| Riaggiunta sola η→6γ | 0.47784 | 0.76355 | 0.02068 | 0.00559 |
| Senza stima 4π⁰ | 0.49754 | 0.76383 | 0.02305 | 0.00592 |
| Denominatore prima della perdita | 0.54186 | 0.76383 | 0.02203 | 0.00561 |

Denominatore: eventi hold-out con quattro fotoni, pesati con **gli stessi pesi di riferimento** della miscela corrente per tutte le varianti. Non efficienza assoluta detector. Rigetto per canale =1−efficienza; conteggi, efficienza BDT da sola e tagli da soli salvati nei `metrics.json`. Nessun sopravvissuto combinato degli altri tre fondi nel hold-out: limite di statistica esplicito, non certificazione di rigetto perfetto.

Togliere entrambi i decadimenti η cambia l'efficienza segnale di **−0.000772±0.000263**, π⁰π⁰ di **−0.003537±0.000494** e 3π⁰ di **−0.000757±0.000268**. Errori da differenze evento per evento con covarianza condivisa e pesi fissi; non includono nuove realizzazioni del training o incertezza dei pesi. Gli scarti piccoli non convalidano la miscela fisica.

Sculpting salvato per ogni canale/variante: istogrammi pesati prima/dopo di M(η), M(π⁰), Eγ e φη di laboratorio, con bordi e conteggi fuori intervallo. Modelli distinti, score test, maschere di selezione e split sono tutti archiviati. Sono bundle diagnostici, non sostituti dei bundle di produzione. La rimozione di 4π⁰ è una prova di sensibilità al componente non misurato, **non** un intervallo d'incertezza fisico.

## Injection e coverage: limite esplicito

200 pseudoesperimenti appaiati, 2000 eventi prima dei tagli, P=0.6, Σ segnale=0.3, Σ fondi=0. Stati di polarizzazione assegnati da 1−sPΣcos(2φη truth); stima dal momento dell'azimuth η ricostruito. Stesse estrazioni di righe e numeri casuali per le varianti. Campione, pesi e risposta fissati: il test esercita selezione e migrazione angolare del MC, **non i fit ratio/likelihood, flussi, periodi o covarianze della produzione**.

Nel caso corrente: bias grezzo **−0.11275±0.00592**, coverage dell'intervallo nominale 68% **0.35**. La frazione segnale simulata dopo selezione è 0.99390: la diluizione da fondi non spiega quel bias. La risposta condizionata calcolabile nel toy è R=0.64421; correggendo con questo valore *noto soltanto nel MC*, bias **−0.00933**, coverage **0.71**. Errore Monte Carlo della coverage circa 0.032–0.034 per 200 repliche. Il controllo con azimuth uniforme perfettamente ricostruito ha R=1 e chiude nel test automatico.

Questa risposta non è una calibrazione applicabile ai dati. Non attribuire il bias grezzo ai soli fondi né affermare coverage verificata di Σ di produzione. `injection.json` conserva tutte le repliche appaiate, risposte e riepiloghi.

## Inclusione/esclusione dei candidati

| Candidato | Supporto / via a 4γ+p | Decisione di questo audit |
|---|---|---|
| η→6γ e ηπ⁰→8γ | Già presenti, perdita di 2/4 fotoni misurata nel modello | Riusati, nessun duplicato |
| ω singola→π⁰γ→3γ | Soglia ≈1.109 GeV, UV; servirebbe un cluster aggiuntivo | Non modellabile col solo photon-loss; non inserito a peso zero |
| ω→π⁰π⁰γ→5γ | BR raro misurato; può perdere un fotone | Candidato UV separato, nessun MC locale o rendimento verificato |
| K⁰SΣ⁺→p3π⁰ | Soglia ≈1.05 GeV; incluso nella σ 3π⁰ della fonte sopra soglia | Non sommare senza sottrazione/convenzione esclusiva |
| K⁰π⁰Σ⁺→p4π⁰ | Soglia ≈1.300 GeV; misura Nanova con bin 1.4–1.5 | Candidato UV supportato; prima decidere separazione dal continuo 4π⁰ |
| Cluster sdoppiati, merge, accidentali/tagging | Possono cambiare molteplicità o energia attribuita | Non modellati dal photon-loss indipendente; servono campioni/risposta dedicati |
| Canali carichi con PID errata | Richiedono probabilità di misidentificazione e selezione detector | Non rappresentati da nuovi fotoni veri; nessuna normalizzazione inventata |

Fonti primarie e branching ratio nella [nota dedicata](../research/2026-10-13-bdt-background-sources.md). Nuovi generatori non giustificati prima di una scelta fisica della composizione; quello a 6γ non va rifatto.

## Verifica e stato di consegna

```bash
python3 -m scripts.audit_bdt_backgrounds --output results/background-audit-20261013/vis-final
python3 -m pytest -q -p no:cacheprovider tests/test_bdt_background_audit.py \
  00_common/tests/test_channels.py 00_common/tests/test_cross_sections.py \
  03_mc_simulation/tests/test_generator_physics.py \
  04_bdt_training/tests/test_channel_weights.py \
  04_bdt_training/tests/test_build_background_features.py \
  04_bdt_training/tests/test_mc_samples.py 04_bdt_training/tests/test_photon_loss.py \
  04_bdt_training/tests/test_beam_spectrum.py
```

**157 passed in 7.25s.** Lo script rifiuta una directory di output esistente: per replicare usare un nuovo percorso. Verificati SHA dei sorgenti, split disgiunti, identiche identità test in tutte le varianti, campionamento entro gli errori attesi. Review indipendente del codice nuovo: nessun problema critico/importante; richiesto e mantenuto il limite statistico sui conteggi nulli. La suite completa del repository non è stata rilanciata: nessun codice di produzione modificato.

**Decisione utente del 13 ottobre 2026:** mantenere 4π0 e ηπ0π0 come scenari diagnostici; produzione invariata. La scelta sul trattamento delle due stime è quindi risolta per questa consegna. Non vengono adottati nuovi pesi, esclusioni o generatori nella miscela di produzione; il mantenimento della produzione non ne certifica le normalizzazioni.

Per un eventuale seguito fisico restano necessari: normalizzazioni con BR e componenti esclusive concordate, punti energetici/tabulazioni verificati per nuove curve, MC UV e truth dei fondi, validazione del detector e injection negli stimatori Σ reali. Non esistono qui intervalli motivati per le due stime. Queste attività rimangono distinte dall'audit diagnostico completato.
