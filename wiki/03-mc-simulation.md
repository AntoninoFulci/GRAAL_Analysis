# 03 — Simulazione Monte Carlo

`03_mc_simulation/` genera i nove canali usati per addestrare (e valutare)
il BDT stage-1: il segnale η π⁰ e otto fondi fisici.

## I nove canali

```python
CHANNELS = [
    "eta_pi0", "pi0pi0", "3pi0", "eta_2pi0", "omega_pi0", "etaprime",
    "eta_via_3pi0", "4pi0", "eta_pi0_via_3pi0",
]
```

(`00_common/channels.py::CHANNEL_NAMES`, l'ordine in cui `mc_status` li
riporta e in cui la fase 3 li genera). Ogni canale ha una propria macro ROOT
generatrice (`generate_<canale>_dataset.C`) che scrive
`03_mc_simulation/data/<canale>_mc.root` — il file viene creato dalla
macro stessa (`TFile *fout = new TFile("pi0pi0_mc.root", "RECREATE")`),
girata dalla cartella dati.

I primi sei sono il campione originale. Gli ultimi tre sono stati aggiunti
perché coprono un buco reale nella copertura del fondo:

| canale | stato finale prodotto | fotoni veri | perché è nel campione |
|---|---|---|---|
| `eta_via_3pi0` | γp → p η, η→3π⁰ | 6 | il più importante dei tre: un η **vero**, con 2 dei suoi 6 fotoni scartati dall'accettanza, lascia 4 fotoni con una massa η reale e una massa π⁰ reale — cade **sul minimo del chi2 del segnale**, non nelle code. Prima non era nel campione e portava peso zero pur avendo una sezione d'urto più grande di `eta_2pi0` ed `etaprime`, che invece ci sono da sempre proprio perché portano un η vero. |
| `4pi0` | γp → p 4π⁰ | 8 | stato finale a 8 fotoni, essenzialmente non misurato in letteratura; deve perdere 4 fotoni su 8 per entrare nel gate a 4, quindi la sua accettanza — e perciò il suo peso — è piccola comunque, ma non zero. |
| `eta_pi0_via_3pi0` | γp → p η π⁰, η→3π⁰ (invece di η→2γ) | 8 | è la **reazione di segnale stessa**, con il decadimento sbagliato dell'η. Un evento a 8 fotoni che ne perde 4 nel modo giusto ricostruisce dai fotoni **sbagliati** e contamina proprio la misura η→2γ. Non ha una sezione d'urto propria — è vincolato (*slaved*) al segnale via i branching ratio PDG, vedi sotto. |

Tutti e nove passano per lo stesso modello di perdita fotoni (vedi sotto),
segnale compreso.

## Un canale deliberatamente escluso

`γp → n π⁺ π⁰ π⁰` (un neutrone di rinculo, un pione carico, due π⁰) **non è
nel registry**, e non per svista. Nel calorimetro BGO i pioni carichi si
separano dai fotoni con un taglio dE/dx-vs-impulso (la "banana"); un π⁺ che
perde energia in modo da cadere nella banana neutra si comporterebbe, nel gate
a 4 fotoni, come un fondo neutro in più. Aggiungerlo al registry richiederebbe
un numero per quella frazione di leakage — e quel numero non è ancora stato
misurato. Finché non lo è, un valore qui sarebbe una stima infondata esibita
come input fisico, esattamente il tipo di errore che il resto del registry
lavora per evitare (vedi sotto, e i commenti su `eta_2pi0`/`4pi0` per lo
stesso principio applicato a stime già accettate ma dichiarate come tali).
Il canale resta fuori finché non c'è una leakage misurata da anteporgli.

## Il fascio dei generatori non è il fascio di GRAAL

Ogni generatore estrae l'energia del fotone taggato così:

```cpp
double Ebeam = rng.Uniform(threshold, 1.75);
```

Piatta, dalla soglia di produzione del canale a un tetto fisso — **1.75 GeV**,
non più 1.55: il vecchio tetto tagliava fuori la coda del fascio reale, che
misurato arriva fino a 1.72 (vedi sotto). Il fascio di GRAAL non somiglia
comunque a questo: è luce laser retrodiffusa Compton sull'anello, e lo
spettro **sale fino a un bordo Compton** che sta dove lo mette la linea
laser. Misurato su `data/selected` (17.15M fotoni taggati, min 0.644, mediana
1.087, max 1.718): due bordi sovrapposti — le linee verde e UV usate in periodi
di presa dati diversi — una spalla verso 0.79, e una coda fino a 1.72.

`beam_E` è una delle 26 feature stage-1, e il resto della cinematica è
correlata con essa: un fascio piatto nel MC non è una discrepanza cosmetica, è
un classificatore calibrato su un fascio che l'esperimento non ha mai avuto.

La fase 4 misura `p_data(E)` dai file veri e riponderа il MC con
`p_data(E) / p_mc(E)` (`04_bdt_training/beam_spectrum.py`). Riponderare la
marginale del fascio basta a trascinarsi dietro tutto il resto, perché i
generatori estraggono prima l'energia del fascio e costruiscono la cinematica
da quella.

**Non è più opzionale.** `build_background_features.py --beam-spectrum` è
obbligatorio: senza uno spettro misurato non c'è integrale di flusso su cui
basare i pesi dei canali (vedi sotto), e `run_pipeline.sh` si ferma con un
errore esplicito se `SELECTED_DIR` non esiste, invece di proseguire con un
fascio piatto come faceva prima — vedi [Pipeline](pipeline).

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

## Il peso di un canale: flusso integrato, non un numero fisso

Il registry `00_common/channels.py` porta la sezione d'urto di riferimento **a
una energia** per gli otto fondi. Il segnale (`eta_pi0`) non ne ha, e
`eta_pi0_via_3pi0` nemmeno — vedi sotto per entrambi.

| canale | `sigma_ref_ub` | `e_ref_gev` | fonte |
|---|---|---|---|
| `eta_pi0` | — | — | **è la misura**, vedi sotto |
| `pi0pi0` | 4.5 | 2.2 | CB-ELSA/TAPS, Sarantsev *et al.*, EPJ A 25 (2005) 441 |
| `3pi0` | 1.8 | 1.26 | Kashevarov *et al.* (A2-MAMI), PRC 85 (2012) 064610, arXiv:1101.3744 Tab. I |
| `eta_2pi0` | 0.3 (STIMA) | 1.90 | nessuna misura dedicata; tetto stimato dal totale η′, arXiv:0909.1248 |
| `omega_pi0` | 0.49 | 1.60 | Junkersfeld *et al.* (CB-ELSA/TAPS), EPJ A 31 (2007) 365, arXiv:0704.0710 Tab. 3 |
| `etaprime` | 0.35 | 1.6 | Crede *et al.* (CB-ELSA), PRC 80 (2009) 055202, arXiv:0909.1248; PDG BR(η′→ηπ⁰π⁰)=0.228 |
| `eta_via_3pi0` | 0.65 (= 2.0 × BR 0.327) | 1.03 | McNicoll *et al.* (A2), PRC 82 (2010) 035208, arXiv:1007.0777; PDG BR(η→3π⁰)=0.327 |
| `4pi0` | 0.2 (STIMA/tetto) | 1.45 | nessuna misura esclusiva pubblicata; scalato in ordine di grandezza da `3pi0` |
| `eta_pi0_via_3pi0` | — | — | vincolato al segnale, vedi sotto |

`sigma_ref_ub` a `e_ref_gev` **non è** il peso: il peso è quella sezione
d'urto integrata su tre cose insieme — il flusso del fascio misurato, la forma
`sigma(E)` (il "turn-on" del canale sopra la sua soglia), e l'accettanza del
rivelatore. Prima non era così: un `sigma_ref` piatto su tutto l'intervallo del
fascio ignorava che un canale non esiste sotto soglia — `omega_pi0` apre a
1.366 GeV ed `etaprime` a 1.447, negli ultimi punti percentuali dell'intervallo
di GRAAL, eppure entrambi venivano pesati al loro valore misurato ben sopra
soglia. Il fix è in tre pezzi:

**La forma `sigma(E)`** (`00_common/cross_sections.py::sigma_at`):

```
sigma(E) = sigma_ref * min(1, Phi_n(W(E)) / Phi_n(W(E_ref)))
```

`Phi_n` è il volume di spazio delle fasi a n corpi dello stato finale di
**produzione** (non del decadimento — `eta_pi0` ed `eta_pi0_via_3pi0`
condividono le stesse `production_masses` proprio perché il decadimento
dell'η non cambia come si accende la sezione d'urto). Saturato a 1 sopra
`E_ref`: senza il tetto, un canale misurato vicino al suo picco verrebbe
scalato verso l'alto di più volte al bordo superiore dell'intervallo del
fascio — inventando struttura dal nulla, e facendolo proprio a `pi0pi0`, il
fondo più grande. Il tetto può solo ridurre un peso, mai aumentarlo.

**La separazione generato/sopravvissuto**
(`build_background_features.py::channel_yield`): il peso di un canale divide
per il suo **conteggio generato** (`n_gen`), non per il totale dei
sopravvissuti. Sono due cose diverse che per molto tempo sono state confuse:
il conteggio generato è una scelta di bookkeeping arbitraria (quanti eventi
simulare) e va cancellato dal peso; la frazione di sopravvivenza `p_surv` è
l'accettanza del rivelatore per quella topologia, ed è fisica — non va
cancellata. Entrambe vivono nello stesso totale dei sopravvissuti, e
normalizzare su quel totale le cancellava insieme: un canale a 8 fotoni finiva
pesato come se ricostruisse con la stessa efficienza di uno a 4. Dividendo per
`n_gen` invece di `n_survived`, `p_surv` resta nel peso dove deve stare.

**Il canale vincolato** (`eta_pi0_via_3pi0`): non ha una `sigma_ref_ub` perché
la sua sezione d'urto **è** quella del segnale (`sigma(γp → pηπ⁰) ×
BR(η→3π⁰)`), e mettere un numero lì sarebbe circolare — un'assunzione della
stessa quantità che l'analisi misura. Il suo peso è invece vincolato
(*slaved*) a quello del segnale tramite il rapporto dei branching ratio PDG,
`BR(η→3π⁰) / BR(η→2γ) = 0.327 / 0.394`, moltiplicato per il rapporto delle
sue accettanze (`compute_shares` in `build_background_features.py`): il
`sigma(segnale)` compare identico a numeratore e denominatore e si cancella
algebricamente, senza mai dover essere nominato. Sul solo rapporto dei BR il
canale prenderebbe il 41.5% del peso totale a `signal_prior=0.5`, schiacciando
ogni fondo reale — è per questo che il rapporto di accettanza non è un
raffinamento opzionale ma parte necessaria del vincolo.

### Perché il segnale non ha una sezione d'urto

Misurare σ(γp → pηπ⁰) **è quello per cui questa analisi esiste**. Un numero nel
registry sarebbe una risposta, usata per pesare gli eventi da cui la risposta
si estrae: circolare, e in silenzio — il training riprodurrebbe semplicemente
il prior che gli è stato passato.

Fra i fondi con una sezione d'urto propria, invece, le grandezze relative sono
fisica vera e il BDT deve saperle: dicono quanto della contaminazione è π⁰π⁰
piuttosto che η′. Quello che non possono dire è quanto segnale ci sia rispetto
a tutto il resto. Quel rapporto è una **scelta**, dichiarata con
`--signal-prior` (default 0.5, bilanciato), non una misura.

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

`04_bdt_training/photon_loss.py` modella l'inefficienza del rivelatore come
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

Ogni canale, segnale compreso, viene passato attraverso
`sample_surviving_photons`, che applica la perdita evento per evento e tiene
solo gli eventi in cui sopravvivono **esattamente** 4 fotoni — lo stesso
numero che il gate stage-1 vede in produzione. Il segnale ha 4 fotoni veri, i
fondi da 4 a 8 (vedi la tabella dei canali sopra e
[Formati dati](data-formats) per i nomi dei rami su disco); tutti passano per
lo stesso filtro, così l'accettanza non diventa una funzione dell'etichetta di
classe.

## `mc_status`: cosa controlla

```bash
python -m mc_simulation.mc_status --data-dir 03_mc_simulation/data
```

Per ciascuno dei 9 canali controlla se `<canale>_mc.root` esiste in
`--data-dir` e, se sì, quanto è vecchio (`age_days`). La soglia di
staleness è 10 giorni (`STALE_DAYS = 10`): un file più vecchio genera un
`WARNING` a schermo ma **non cambia l'esito** — la staleness avvisa, non
blocca.

## Exit code: 0, 1, 2, e perché la distinzione conta

| Exit | Significato |
|---|---|
| 0 | tutti e 9 i canali presenti |
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
avvierebbe la rigenerazione di tutti e nove i canali — ore di calcolo — che in
realtà erano già tutti sul disco. `main()` avvolge l'intera logica in un
`try/except Exception` che stampa l'errore su `stderr` e restituisce 2;
solo `SystemExit` (da `--help` o argomenti non validi di argparse) passa
inalterato.
