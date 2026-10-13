# Binning energetico configurabile

Il profilo `uv`/`vis` identifica laser, target e polarizzazione. La griglia
energetica è separata: abbassare l'energia UV non seleziona il laser VIS.
Senza opzioni restano i bordi storici. Nessun fit cinematico 6C viene abilitato.

## Configurazioni versionate

| Config | UV, GeV | VIS, GeV |
|---|---|---|
| `config/energy/nominal.json` | 1.10, 1.20, 1.30, 1.40, 1.50 | 0.9313, 1.10 |
| `config/energy/split.json` | 1.10, 1.15, 1.20, 1.25, 1.30, 1.35, 1.40, 1.45, 1.50 | 0.9313, 1.01565, 1.10 |
| `config/energy/uv-low.json` | 0.9313, 1.10 | 0.9313, 1.10 |

Una configurazione contiene oggetti `uv` e/o `vis`, ciascuno con la sola chiave
`energy_edges_gev`. Un profilo omesso mantiene i default. Bordi finiti,
positivi, strettamente crescenti; griglie contigue senza overlap interno.
Bordi `[low, high)`, ultimo bordo incluso. Studi diversi possono sovrapporsi:
i loro risultati sono correlati.

```json
{"uv": {"energy_edges_gev": [0.9313, 1.10, 1.20, 1.30, 1.40, 1.50]}}
```

Questo esempio estende UV al basso mantenendo anche i pannelli nominali.
La griglia richiede dati, MC e modello che coprano tutto il dominio dichiarato.

## Campagna completa

Da repository root, con gli input previsti dal launcher disponibili:

```bash
python3 scripts/run_pipeline.py --mode production \
  --output-dir results/energy-split \
  --energy-config config/energy/split.json
```

Per tornare al nominale usare una **nuova directory di campagna** e
`--energy-config config/energy/nominal.json`, oppure omettere l'opzione.
Non riusare ROOT già ricostruiti su un intervallo più stretto.

Il launcher passa bordi risolti agli stadi interessati. MC e BDT vengono
invalidati tramite comandi e impronte delle dipendenze; selezione h85 resta
indipendente dal binning. Vengono generati soltanto canali cinematicamente
aperti. I generatori applicano ancora la soglia alla **vera** energia.
Gli endpoint storici hanno una piccola coda oltre l'endpoint Compton: il
loader continua a escludere singole esposizioni fuori dominio di polarizzazione.

## Rianalisi senza nuovo training

Se cambiano solo i bordi interni, la ricostruzione nominale copre già il nuovo
dominio. Esempio con la baseline locale senza 6C:

```bash
python3 -m observable_extraction.beam_asymmetry \
  --profile vis --energy-config config/energy/split.json \
  --raw results/baseline-no-fit-20261013/vis/reco/reco_eta_pi0_chi2.root \
  --raw-bdt results/baseline-no-fit-20261013/vis/reco/reco_eta_pi0_bdt.root \
  --flux-file data/00_external/flux_calibrated.root \
  --run-manifest config/run_manifest.csv --by-period \
  --output-dir results/my-energy-study/vis/beam_asymmetry
```

La stessa `--energy-config` è disponibile in `bdt_training.beam_spectrum`,
`bdt_training.build_background_features`, ricostruzioni chi2/BDT/sideband e
estrazione. Per una griglia diretta, aggiungere per esempio
`--profile uv --energy-edges 1.1 1.15 1.2 1.3 1.4 1.5`.
`--energy-edges` prevale sulla config per il profilo scelto; il file resta
validato interamente. Gli stadi standalone richiedono `--profile` quando
si specifica una griglia personalizzata.

## UV basso e controlli di supporto

Per il controllo pairing senza BDT:

```bash
python3 -m reconstruction.reconstruct_eta_pi0_chi2 \
  --input-dir test_data/selected --no-fit --profile uv \
  --energy-config config/energy/uv-low.json \
  --output-file results/my-uv-low/uv/reco/reco_eta_pi0_chi2.root

python3 -m observable_extraction.beam_asymmetry \
  --profile uv --energy-config config/energy/uv-low.json --nominal-sample raw \
  --raw results/my-uv-low/uv/reco/reco_eta_pi0_chi2.root \
  --raw-bdt results/my-uv-low/uv/reco/unavailable_bdt.root \
  --flux-file data/00_external/flux_calibrated.root \
  --run-manifest config/run_manifest.csv --by-period \
  --output-dir results/my-uv-low/uv/beam_asymmetry
```

Il percorso BDT assente è intenzionale: impedisce il caricamento automatico
di un vecchio campione nominale di confronto. Il loader segnala il campione
opzionale mancante. Un modello UV legacy è compatibile solo col dominio
nominale; un modello profilato deve corrispondere al dominio richiesto.
L'estrazione controlla anche il dominio dichiarato dai ROOT, inclusi sideband
e template MC: una selezione più stretta non può essere allargata a posteriori.
I ROOT storici senza nuovo contratto conservano la compatibilità nel dominio
nominale; per espansioni servono provenance e ricostruzione nuove.

Prima di registrare un dominio continuo di training, il feature builder
richiede esempi di segnale con peso positivo in **ogni bin dello spettro di
training**. La soglia preesistente `MIN_MC_PER_BIN=200` resta nel reweighting.
Bin senza dati o senza MC affidabile bloccano la dichiarazione di copertura:
aumentare statistiche o restringere il dominio, non extrapolare il modello.
Questo controllo è necessario ma non sostituisce la validazione fisica del BDT.

`0.9313–1.10` è sotto il range nominale UV, quasi interamente sopra soglia
fisica `gamma p -> p eta pi0`, circa 0.931311 GeV. La piccola coda sotto soglia
è energia taggata, non produzione on-shell sotto soglia.

## Output e confronti

ROOT conserva bordi effettivi e dichiarazione ridondante in provenance;
discordanze sono errori. Plot e combiner leggono la griglia salvata, senza
richiedere nuovamente il file di config. Confronti Ajaka compaiono solo su
intervalli fisicamente identici al riferimento, mai per semplice indice.

Con `--by-period`, `periods/index.json` contiene per ogni bin conteggi V/H/BREM,
esposizioni, polarizzazioni efficaci, fit disponibili/fallback/bordo e bin
non stimabili. Efficienza MC non valutata resta `null`, non zero. Covarianze
tra griglie sovrapposte e inferenza finale richiedono analisi dedicata.
Riunire sottobin significa rifare il fit su unione eventi/esposizioni:
non calcolare una media semplice delle Σ.
