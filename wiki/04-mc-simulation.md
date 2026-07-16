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

## Il fascio dei generatori non è il fascio di GRAAL

Ogni generatore estrae l'energia del fotone taggato così:

```cpp
double Ebeam = rng.Uniform(threshold, 1.55);
```

Piatta, dalla soglia di produzione del canale a un tetto fisso. Il fascio di
GRAAL non somiglia a questo: è luce laser retrodiffusa Compton sull'anello, e
lo spettro **sale fino a un bordo Compton** che sta dove lo mette la linea
laser. Misurato su `data/selected` (17.15M fotoni taggati, min 0.644, mediana
1.087, max 1.718): due bordi sovrapposti — le linee verde e UV usate in periodi
di presa dati diversi — una spalla verso 0.79, e una coda fino a 1.72 che il
tetto a 1.55 del MC non copre affatto.

`beam_E` è una delle 24 feature stage-1, e il resto della cinematica è
correlata con essa: un fascio piatto nel MC non è una discrepanza cosmetica, è
un classificatore calibrato su un fascio che l'esperimento non ha mai avuto.

La fase 4 misura `p_data(E)` dai file veri e riponderа il MC con
`p_data(E) / p_mc(E)` (`05_analysis_bdt/beam_spectrum.py`). Riponderare la
marginale del fascio basta a trascinarsi dietro tutto il resto, perché i
generatori estraggono prima l'energia del fascio e costruiscono la cinematica
da quella.

**Dove il MC non sa rispondere, non si riponderа.** Un generatore estrae dalla
soglia in su e poi smeara con la risoluzione del tagger: appena sotto quella
soglia il MC ha solo la coda dello smearing, mentre i dati lì sono pieni di
eventi. Quegli eventi sono veri ma non possono essere quel canale — sotto
soglia la reazione non avviene, sono fondo di qualcun altro. Dividere per
quella coda chiede al MC una domanda cui non può rispondere e torna un numero
enorme: sul campione `eta_pi0` (soglia 0.875) il bin 0.870-0.880 dava
`p_data = 1.196` contro `p_mc = 0.0006`, cioè un rapporto di **1994**.
`MIN_MC_PER_BIN` azzera il peso dove il MC ha troppi pochi eventi per stimare
la propria densità.

## Sezioni d'urto e abbinamento per nome file

Il registry `00_common/channels.py` porta la sezione d'urto di riferimento dei
**fondi**. Il segnale non ne ha:

| canale | `sigma_ref_ub` | fonte |
|---|---|---|
| `eta_pi0` | — | **è la misura**, vedi sotto |
| `pi0pi0` | 4.5 | CB-ELSA/TAPS, Sarantsev *et al.*, EPJ A 25 (2005) 441 |
| `3pi0` | 1.8 | CB-ELSA/TAPS, Thoma *et al.*, PLB 659 (2008) 87 |
| `eta_2pi0` | 0.6 | CB-ELSA, Kashevarov *et al.*, PRL 118 (2017) 212001 |
| `omega_pi0` | 1.2 | SAPHIR, Barth *et al.*, EPJ A 18 (2003) 117 |
| `etaprime` | 0.35 | CB-ELSA, Crede *et al.*, PRC 80 (2009) 055202 |

Il peso per evento è `sigma_ref_ub / Σ sigma_ref_ub`, e **non** è moltiplicato
per nessuna frazione di sopravvivenza: gli eventi nel campione sono già passati
per il modello di perdita fotoni, quindi la loro numerosità porta già
l'accettanza. Moltiplicarla di nuovo nel peso la contava due volte. Il vecchio
`cross_sections.csv` faceva esattamente questo, con una colonna `p_survival`
per giunta scollegata dal modello reale (diceva 0.82 per `pi0pi0`, dove il
modello ne misura 0.25). Quel CSV non è più letto da nessuno.

### Perché il segnale non ha una sezione d'urto

Misurare σ(γp → pηπ⁰) **è quello per cui questa analisi esiste**. Un numero nel
registry sarebbe una risposta, usata per pesare gli eventi da cui la risposta
si estrae: circolare, e in silenzio — il training riprodurrebbe semplicemente
il prior che gli è stato passato.

Fra i fondi, invece, le sezioni d'urto relative sono fisica vera e il BDT deve
saperle: dicono quanto della contaminazione è π⁰π⁰ piuttosto che η′. Quello che
non possono dire è quanto segnale ci sia rispetto a tutto il resto. Quel
rapporto è una **scelta**, dichiarata con `--signal-prior` (default 0.5,
bilanciato), non una misura. Il peso per evento diventa quindi:

- segnale: `signal_prior`, spalmato sui suoi eventi
- fondo *c*: `(1 − signal_prior) × σ_c / Σσ_fondi`

normalizzato per canale, così la quota che arriva è esattamente quella voluta,
qualunque sia il numero di eventi generati e qualunque cosa la riponderazione
del fascio abbia fatto ai totali.

Ogni file è abbinato al proprio canale per **nome file**, mai per posizione in
una lista:

```python
def channel_from_filename(path: str | Path) -> MCChannel:
    stem = Path(path).name
    if not stem.endswith(_MC_FILE_SUFFIX):
        raise ValueError(...)
    return get_channel(stem[: -len(_MC_FILE_SUFFIX)])
```

(`00_common/channels.py`). Un file che non finisce per `_mc.root`, o un nome
canale assente dal registry, sono entrambi errori fatali (`ValueError` /
`KeyError`), non un peso di default silenzioso: legare il peso alla posizione
in lista avrebbe permesso a un riordino innocente di abbinare silenziosamente
un file al peso sbagliato, senza alcun errore.

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
