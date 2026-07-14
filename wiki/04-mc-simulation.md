# 04 — Simulazione Monte Carlo

`04_mc_simulation/` genera i sei canali usati per addestrare (e valutare)
il BDT stage-1: il segnale η π⁰ e cinque fondi fisici.

## I sei canali

```python
CHANNELS = ["eta_pi0", "pi0pi0", "3pi0", "eta_2pi0", "omega_pi0", "etaprime"]
```

(`04_mc_simulation/mc_status.py`). Ogni canale ha una propria macro ROOT
generatrice (`generate_<canale>_dataset.C`) che scrive
`04_mc_simulation/data/<canale>_mc.root` — il file viene creato dalla
macro stessa (`TFile *fout = new TFile("pi0pi0_mc.root", "RECREATE")`),
girata dalla cartella dati.

## Sezioni d'urto e abbinamento per nome file

`04_mc_simulation/cross_sections/cross_sections.csv` porta la sezione
d'urto di riferimento e la sopravvivenza attesa per ciascun fondo:

```csv
channel,sigma_ref_ub,p_survival,sigma_eff
pi0pi0,4.5,0.82,3.69
3pi0,1.8,0.61,1.10
eta_2pi0,0.6,0.55,0.33
omega_pi0,1.2,0.58,0.70
etaprime,0.35,0.52,0.18
```

Il canale segnale (`eta_pi0`) non compare in questo CSV — non ha bisogno di
un peso relativo, entra nel training con peso 1. Nella fase di
[costruzione delle feature](05-analysis-bdt-features), ogni file di fondo
viene abbinato alla propria riga del CSV per **nome file**, mai per
posizione nella lista `--backgrounds`:

```python
def channel_from_filename(bg_file: str) -> str:
    stem = Path(bg_file).name
    if not stem.endswith(_BG_FILE_SUFFIX):
        raise ValueError(...)
    return stem[: -len(_BG_FILE_SUFFIX)]
```

(`05_analysis_bdt/build_background_features.py`). Un file che non finisce
per `_mc.root`, o un nome canale assente dal CSV, sono entrambi errori
fatali (`ValueError` / `KeyError`), non un peso di default silenzioso: legare
il peso alla posizione in lista avrebbe permesso a un riordino innocente di
`--backgrounds` di abbinare silenziosamente un file al peso sbagliato, senza
alcun errore.

## Il modello di perdita fotoni

`05_analysis_bdt/photon_loss.py` modella l'inefficienza del rivelatore come
una probabilità di perdita indipendente per fotone:

```
P_loss(E, theta) = 1 - (1-P_thr(E)) * (1-P_fwd(theta)) * (1-P_bwd(theta))
```

tre sigmoidi indipendenti: `P_thr` (soglia in energia), `P_fwd` (buco del
fascio in avanti), `P_bwd` (buco all'indietro). L'accettanza a due lati
riflette la geometria reale della palla di cristalli BGO del GRAAL: da
`theta_min_acc = 0.436` rad (~25°) a `theta_max_acc = 2.705` rad (~155°),
con parametri di default:

```python
@dataclass
class LossParams:
    E_thr: float = 0.050
    sigma_E: float = 0.020
    theta_min_acc: float = 0.436
    theta_max_acc: float = 2.705
    sigma_theta: float = 0.050
```

Il segnale (η π⁰) entra nel training con i suoi 4 fotoni originali, senza
perdita applicata (l'MC li genera già a 4). I fondi, che nella realtà del
generatore hanno più di 4 fotoni finali, vengono passati attraverso
`sample_surviving_photons`, che applica la perdita evento per evento e
tiene solo gli eventi in cui sopravvivono **esattamente** 4 fotoni — lo
stesso numero che il gate stage-1 vede in produzione.

## `mc_status`: cosa controlla

```bash
python -m mc_simulation.mc_status --data-dir 04_mc_simulation/data
```

Per ciascuno dei 6 canali controlla se `<canale>_mc.root` esiste in
`--data-dir` e, se sì, quanto è vecchio (`age_days`). La soglia di
staleness è 10 giorni (`STALE_DAYS = 10`): un file più vecchio genera un
`WARNING` a schermo ma **non cambia l'esito** — la staleness avvisa, non
blocca.

## Exit code: 0, 1, 2, e perché la distinzione conta

| Exit | Significato |
|---|---|
| 0 | tutti e 6 i canali presenti |
| 1 | almeno un canale manca |
| 2 | errore interno di `mc_status` stesso |

`run_pipeline.sh` decide se rigenerare i canali in base a questo codice
(vedi [Pipeline](pipeline)). L'exit 2 è tenuto distinto da 1 di proposito:
il docstring del modulo lo dice esplicitamente —

> The caller MUST NOT treat this the same as exit 1: doing so once made a
> bare `python` interpreter that could not import the package look like
> "MC missing" and triggered a multi-hour regeneration of six channels that
> were sitting on disk the whole time.

Un `python` che non ha visto `pip install -e .` (vedi [Home](Home)) non
riesce a importare `mc_simulation`, e quell'errore va segnalato come
"guasto interno" (2), non come "MC assente" (1): leggerlo come 1
avvierebbe la rigenerazione di sei canali — ore di calcolo — che in realtà
erano già tutti sul disco. `main()` avvolge l'intera logica in un
`try/except Exception` che stampa l'errore su `stderr` e restituisce 2;
solo `SystemExit` (da `--help` o argomenti non validi di argparse) passa
inalterato.
