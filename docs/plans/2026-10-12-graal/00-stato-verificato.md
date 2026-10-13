# GRAAL — stato verificato e invarianti

Audit del 12 ottobre 2026 sul commit `3afff75ead89be7e14ad6473ee1d0deff97e7094`; working tree inizialmente pulito. Evidenze: sorgenti correnti, wiki, runbook e artefatti locali. Il grafo `graphify-out/graph.json` (2.480 nodi) è stato usato come mappa; le affermazioni sotto sono state ricontrollate direttamente. Nessun rebuild del grafo o della pipeline.

## Pipeline effettiva

| Strato | Dati, responsabilità e invarianti |
|---|---|
| `01_pre_analysis/PreAnalysis.C`, `.h`, `CutManager.h` | Raw `h70` → `h80`; classificazione tracce e cut detector per run. Il launcher completo parte già da `h80`, non ricrea preanalisi. |
| `02_event_selector/select_events.py` | `h80` → `h85`; filtro `gammas.size() > 1 && fcharged_theta.size() == 1`; conserva tutti i rami di input. Non è ancora selezione finale a quattro fotoni. |
| `06_calibration/build_strip_energy_flux.py`, `strip_energy_flux.py` | Calibrazione strip–energia su `h80` inclusivo; join con flussi per run/stato, manifest e QA. Il completamento di energie strip per interpolazione/estrapolazione esiste: non equivale a ricostruire un istogramma di flusso mancante. |
| `03_mc_simulation/generators/`, `00_common/physics/channels.py` | Canali MC, masse, branching, soglie e risoluzioni comuni. Smearing e perdita fotoni semplificati, non simulazione completa del detector. |
| `04_bdt_training/` | Spettro del fascio misurato sul selezionato, pesi MC di fascio/canale/accettanza; esattamente quattro fotoni sopravvissuti, ordine casualizzato; feature e training XGBoost. Launcher addestra separatamente UV e VIS. |
| `05_reconstruction/runtime/reco_core.py`, `core/event_logic.py` | Almeno quattro fotoni, candidati di rinculo validi; usa primi quattro fotoni, non cerca miglior quartetto. Stesso pairing χ² per ricostruzione tradizionale e BDT. Gate BDT è differenza intenzionale. |
| `07_observable_extraction/beam_asymmetry.py` | Campioni `raw`, `raw_bdt`, `raw_bdt_fit`; selezione stati polarizzati, profilo, energia ed esposizioni; ratio e likelihood; componenti sistematiche; ROOT e PDF. |
| `scripts/run_pipeline.py`, `scripts/plot_campaign.py` | Calibrazione comune, rami UV/VIS, cache di selezione/MC/BDT, ricostruzione ed estrazione per campagna, grafici aggregati. Cache produzione nominalmente valida dieci giorni solo se validata; test mode ricostruisce artefatti. |

Il nome `raw` significa vettori non fittati, **non** campione mai selezionato dal fit. Oggi ricostruzione usa 6C per default: gli eventi falliti sono già rimossi. La nuova istruzione dell'utente richiede una futura ricostruzione senza 6C; rami raw storici non recuperano eventi scartati.

## Dati e periodi osservati

`config/run_manifest.csv`: 2.711 run, di cui 1.831 su protone e 880 su deuterio. La reazione richiesta è su protone: non mescolare automaticamente D.

| Periodo | Gruppo | Run nel manifest |
|---|---|---:|
| 1998_uv | P_UV | 179 |
| 1999_uv | P_UV | 339 |
| 1999_vis | P_VIS | 110 |
| 2000_uv1 | P_UV | 204 |
| 2000_fuv | P_UV | 147 |
| 2000_vis | P_VIS | 129 |
| 2000_uv2 | P_UV | 102 |
| 2001_uv | P_UV | 137 |
| 2002_vis1 | P_VIS | 94 |
| 2002_uv1 | P_UV | 128 |
| 2002_uv2 | P_UV | 190 |
| 2002_vis2 | P_VIS | 25 |
| 2003_vis | P_VIS | 47 |

Periodi D presenti: `1999_d1`, `1999_d2`, `2001_d`, `2002_d1`, `2002_d2`, `2002_d3`, `2005_d1`, `2005_d2`, `2006_d`. `1999` da solo non è un'etichetta del manifest: conservarne le sottocategorie, eventuale aggregazione annuale va dichiarata.

Conteggi sopra = manifest, non run utilizzabili o realmente presenti nei campioni. `data/02_pre_analyzed/` non contiene i file produttivi richiesti. Esistono invece `test_data/pre_analyzed/pre_analisi_1998_uv.root` e `pre_analisi_1999_vis.root`, in layout storico diverso dal runbook `test_data/02_pre_analyzed/`. Nessun file spostato. La fixture UV contiene 90.279.078 righe `h80`: non è un piccolo toy.

Ispezione delle chiavi ROOT, contando anche cicli duplicati:

- `data/00_external/flux.root`: 9.057 chiavi; tutti i 1.831 run P del manifest hanno una chiave per ciascuno di `POL1/POL2/BREM`.
- `results/production-20261006-113738/common/flux_calibrated.root`: 1.290 run P con tripletto completo; 541 senza tripletto univoco rispetto all'intero manifest. Può essere mancata copertura della campagna/calibrazione, non prova di flussi grezzi mancanti.
- Non verificati in questo inventario: contenuto finito/positivo di ogni bin, validità assi, tempi vivi, altri periodi non nel manifest, run Vinci.

L'adapter `07_observable_extraction/calibration/flux_v2.py` richiede tripletto completo, TH1 1D con 128 bin e flussi POL positivi, BREM non negativo. Usa `POL1=vertical`, `POL2=horizontal`, `BREM=0` controllo. L'estrazione scarta eventi senza esposizione tramite `drop_missing=True`, con avviso. Esporre sempre questi scarti nel cutflow.

## Variabili e fit

Unità: quadrivettori `[px,py,pz,E]` in GeV; azimut in radianti. Masse comuni da `00_common/physics/channels.py`: mπ0=0.134977, mη=0.547862, mp=0.938272 GeV.

Le 26 feature sono ordinate e condivise tra training/inferenza in `00_common/stage1/features.py`:

1. Sei `m_gg_01`, `02`, `03`, `12`, `13`, `23`.
2. `n_pairs_near_pi0`, `n_pairs_near_eta`, `best_chi2_eta_pi0`.
3. `missing_mass`, `missing_E`, `missing_pz`, `missing_pt` (beam + target − proton).
4. `total_gamma_E`, `beam_E`, `max_gamma_E`, `min_gamma_E`, `gamma_E_rms`.
5. `sum_opening_angles`, `min_pair_mass`, `max_pair_mass`, `total_pt_gamma`.
6. `proton_p`, `proton_costheta`, `eta_E_asym`, `eta_pi0_angle`.

Non confondere questa missing mass con la missing mass del rinculo `beam+target−eta−pi0` nella ricostruzione. `total_pt_gamma` è somma scalare dei pT. I nomi dipendenti dall'ipotesi vanno generati dal contratto, non copiati in altro codice.

Pairing tradizionale: tre partizioni disgiunte e due assegnazioni η/π0, minimo della somma dei pull² delle due masse con risoluzione relativa 0.08; default χ² < 10. Dopo pairing: guardia energia mesone ≤ energia fascio. Con `--no-fit`, finestra missing mass del rinculo ±0.06 GeV attorno al protone; con 6C questa finestra è sostituita dal criterio di fit.

6C esistente, da disattivare nella nuova campagna: quattro vincoli energia-impulso e due masse, 16 misure, covarianza di risoluzione diagonale di default non calibrata indipendentemente, CL ≥ 0.01. I campioni storici salvano vettori raw e fitted ma solo dopo accettazione del fit. Non rimuovere libreria/archivio: disattivarne uso operativo e confronti correlati.

Training attuale: split stratificato train/validation 80/20, seed 42, pesi in entrambi; soglia massimizza F1 ponderato sulla validation. Quella validation serve anche per metriche/scelta e non è un test finale intatto. Dataset non espone attualmente identità evento/canale/split sufficienti per garantire confronti tra versioni MC derivate dallo stesso evento.

## Estrazione di Σ

Per ogni coppia `p_pi0`, `p_eta`, `eta_pi0`, massa e φ vengono dal quadrivettore somma; φ è azimut di laboratorio `atan2(py,px)` riportato in [0,2π). Stesso evento compare in tutte e tre le proiezioni.

Profili correnti: UV [1.10,1.20,1.30,1.40,1.50] GeV; VIS [0.9313,1.10] GeV. Dieci bin di massa: pπ0 1.0–1.4, pη 1.4–1.8, ηπ0 0.6–1.0 GeV. Phi 8/12/16 bin (default 12). La wiki contiene ancora affermazioni vecchie su phi fissato a 12 e provenienza a schema precedente: per queste parti prevalgono codice e contratti correnti.

Con yV=NV/FV, yH=NH/FH, il ratio è

`R(φ) = (yV−yH)/(PH*yV+PV*yH)`.

Fit nominale `Aφ cos(2φ)`, propagazione Poisson dei conteggi assumendo flussi/polarizzazioni fissati. Se p-value < 0.01, fallback diagnostico con offset e seno. Σ e errore sono divisi per 0.9003, 0.9549, 0.9745 per 8,12,16 bin. La likelihood condizionale usa strato `(run,strip)` di ogni evento, dominio fisico [-1,1] e intervalli ΔNLL=0.5; non riceve correzione finite-bin.

Il ratio include esposizioni valide anche in strati senza eventi selezionati entro l'universo di run caricato. L'universo attualmente parte dai run del campione nominale: verificare run completamente vuoti dopo selezione prima di affermare esposizione inclusiva completa.

## Errori: implementazione e limiti verificati

`beam_asymmetry.py` costruisce `Cfit = diag(((stat_low+stat_high)/2)^2)`. Bootstrap per run opzionale (default 0; launcher lo fissa a 0), stessi eventi e flussi riscalati con molteplicità del run. Se attivo, copia off-diagonali e usa `diag(Cstat)=max(diag(Cfit),diag(Cboot))`. Bootstrap copre solo campione/stimatore nominale, non tutte le covarianze incrociate fra alternative.

Ogni sistematico materializzato usa un vettore firmato Δ e `Csyst=ΔΔᵀ`; implica un singolo nuisance completamente correlato tra punti per quella sorgente. `Ctot=Cstat+ΣCsyst`. Questa struttura non prova che ogni sorgente sia indipendente dalle altre né che la correlazione sia fisicamente corretta. Catalogo `REQUIRED_SYSTEMATICS` più ampio dei componenti effettivamente calcolati.

Figure 4 corrente (`07_observable_extraction/plotting/figure4.py`) disegna `stat_low/stat_high`, non `sqrt(diag(Ctot))`. L'affermazione dell'utente su barre già totali richiede identificazione del grafico/versione. Inoltre, quando si attiva correzione fondo, `stat_low/high` vengono sostituiti dall'errore propagato di Σ osservata, frazione f e Σ del fondo, senza termini incrociati. Occorre verificare natura statistica/sistematica di f e covarianza condivisa per energia; il nome del ramo non è garanzia di statistica pura.

I bin disgiunti di conteggio non giustificano indipendenza dell'intero output: proiezioni, BDT subset, ratio/likelihood e nuisance condividono informazione. Replica bootstrap che perde bin è attualmente fatale. Inoltre il bootstrap parte dai run presenti negli eventi; strati di run senza eventi possono essere esclusi. La classificazione della dispersione fra run come statistica o stabilità sistematica va definita prima di sommare entrambe.

## Artefatti realmente aperti

Campagna `results/production-20261006-113738`:

| Verifica | UV | VIS |
|---|---:|---:|
| Righe `sigma_points` | 584 | 94 |
| Dimensione covarianza | 584×584 | 94×94 |
| Elementi statistici fuori diagonale non nulli | 0 | 0 |
| Punti con `syst_total` non nullo | 584 | 94 |
| Massimo residuo `Ctot−Cstat−ΣCsyst` | 5.56×10⁻¹⁷ | 7.27×10⁻¹⁸ |

Componenti presenti: scala polarizzazione 3%, differenza stimatori, raw/6C, seno fallback, molteplicità fotonica. Nessun `bootstrap_run`; `background=uncorrected`; profili ed energie coerenti con baseline storica. Anche `syst_total²=diag(ΣCsyst)` e diagonale statistica riproducono formule entro precisione numerica (residuo diagonale fit esattamente zero). Mancano metadati phi recenti: non certificare questi file come rigenerati dal codice del 12 ottobre, soprattutto dopo modifica della correzione finite-bin del 9 ottobre.

ROOT BDT UV della campagna: 236.951 eventi, rami raw e 6C presenti. Nessun risultato di questo archivio è presentato come nuova estrazione senza fit.

`plots/dalitz.py` produce già M(pη) vs M(pπ0), masse mesoni e M(η) vs M(π0), PDF e `istogrammi.root`; riempimento a peso unitario, non correzione d'accettanza. Variante protone misurato distinta da protone implicito/missing. L'adapter sceglie automaticamente vettori fitted se presenti. Nessun nuovo plot prodotto né QA visuale completa degli archivi in questa sessione.

Fondi registrati: `pi0pi0`, `3pi0`, `eta_2pi0`, `omega_pi0`, `etaprime`, `eta_via_3pi0`, `4pi0`, `eta_pi0_via_3pi0` più segnale `eta_pi0`. η singola a 6γ e ηπ0 a 8γ sono quindi già coperti strutturalmente. `eta_2pi0` e `4pi0` hanno normalizzazioni dichiarate stimate; le fonti dei pesi non sono state rivalidate esternamente.

Raw `test_data/raw/1998_uv/run1321.root`, TTree `h70`: rami `Itipo_track`, `Nparf_strange`, `Index_trf` presenti; `N_TIPO_TRACK` non trovato né in questo schema né nei sorgenti esaminati. `h80` UV non conserva questi rami. Codice usa `Index_trf−1` quando non zero e lookup `Iass_trf`; significato dei codici e caso indice zero richiedono dizionario ufficiale. Nessuna equivalenza fisica dedotta dal nome.

## Prova software eseguita

```bash
python3 -m pytest -q -p no:cacheprovider \
  07_observable_extraction/tests/test_systematics.py \
  07_observable_extraction/tests/test_root_output.py \
  07_observable_extraction/tests/test_ratio_fit.py \
  07_observable_extraction/tests/test_binning.py \
  plots/tests/test_dalitz.py \
  00_common/tests/test_channels.py \
  04_bdt_training/tests/test_stage1_training.py \
  06_calibration/tests/test_run_manifest.py
```

Esito: **108 passed in 38.71s**, exit 0. Interprete `/opt/local/bin/python3`, Python 3.14; moduli PyROOT, uproot e pacchetti locali disponibili. Questa prova riguarda contratti/unità selezionati, non intera pipeline, validità fisica dei pesi, accuratezza detector o chiusura di una nuova campagna. Le ispezioni ROOT sopra hanno letto metadati e matrici, non rigenerato risultati.

Verifica documentale finale: 16 Markdown (indice, audit, prerequisito e 13 piani), un piano per ogni punto 1–13, collegamenti locali risolti. File scritti da questa attività soltanto sotto `docs/plans/2026-10-12-graal/`. Durante il lavoro è comparso anche `results.zip` non tracciato, non creato né modificato da questa attività; non è stato usato come fonte.

## Fonti principali già presenti

`README.md`, `docs/runbooks/full-pipeline.md`, `docs/runbooks/vis-local-analysis.md`, wiki di stadi 01–07, `docs/research/2026-10-09-finite-phi-bin-correction.md`, `theory/README.md`, `theory/references/sources.json`. I piani del 1 ottobre descrivono parte del lavoro già implementato: non vanno rieseguiti integralmente. Per la letteratura distinguere fonti già inventariate e verifica bibliografica nuova, ancora da fare.
