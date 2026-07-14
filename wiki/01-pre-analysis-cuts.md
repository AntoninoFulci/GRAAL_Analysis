# Cuts della pre-analisi

`01_pre_analysis/cuts/` contiene 95 file `.cpp`, ciascuno una macro ROOT che
ricostruisce un singolo `TCutG` (poligono di selezione) su una coppia di
variabili. Questa pagina spiega come quei 95 file diventano la mappa che
`PreAnalysis.C` interroga evento per evento, e cosa succede quando la mappa
non ha una risposta.

## Cosa c'è in un file di cut

Esempio, `DeuteronFwdCut_1999_d1.cpp`:

```cpp
TCutG* DeuteronFwdCut_1999_d1(){
   TCutG *cutg = new TCutG("DeuteronFwdCut_1999_d1",24);
   cutg->SetVarX("Tof_trf");
   cutg->SetVarY("De_trf");
   cutg->SetPoint(0,47.3894,19.8551);
   ...
   return cutg;
}
```

Un poligono a 24 vertici nel piano (tempo di volo, energia depositata). I
cut "Fwd" (in avanti) sono definiti su `(Tof_trf, De_trf)`; i cut "Cnt"
(centrali) — vedi `PreAnalysis.C` — sono usati su `(Eclusc_track,
Dedx_track)`. Il nome della funzione, del `TCutG` e del file coincidono
sempre: è quello che permette a `BuildCutMap` di caricare il file come
macro (`.x <file>.cpp`) ed eseguire una funzione il cui nome non conosce in
anticipo.

## Le cinque famiglie di cut

| Prefisso | Conteggio | Variabili | Usato per |
|---|---|---|---|
| `ProtonFwdCut_*` | 21 | `Tof_trf`, `De_trf` | protoni in avanti |
| `ProtonCntCut_*` | 22 | `Eclusc_track`, `Dedx_track` | protoni centrali |
| `PionFwdCut_*` | 22 | `Tof_trf`, `De_trf` | pioni in avanti |
| `PionCntCut_*` | 22 | `Eclusc_track`, `Dedx_track` | pioni centrali |
| `DeuteronFwdCut_*` | 8 | `Tof_trf`, `De_trf` | deutoni in avanti |

I `DeuteronFwdCut` esistono solo per le 8 cartelle "_d" (run su bersaglio di
deuterio); non ha senso cercare un deutone di rinculo in una run su
idrogeno, quindi quelle cartelle non hanno un file corrispondente — e non ne
hanno bisogno.

## Come un run viene abbinato al proprio cut

La logica vive in `BuildCutMap(dataPath, cutPath)`
(`01_pre_analysis/CutManager.h`), chiamata una sola volta da `AnalyzeAll`
prima di processare qualunque run:

1. **Run → cartella.** Scandisce le sottocartelle di `dataPath` (una per
   run) e, dentro ciascuna, i file che iniziano per `run` e finiscono per
   `.root` (pattern `run####.root`). Il numero estratto dal nome file è il
   run ID; la cartella che lo contiene è il suo "periodo" (`gRunToFolder`).
2. **File di cut → periodo.** Per ogni file in `cuts_dir`, estrae la parte
   dopo `Cut_` e prima di `.cpp` (es. `PionFwdCut_1999_uv.cpp` →
   `1999_uv`) e la usa come nome di periodo. Particella e rivelatore
   (Fwd/Cnt) vengono letti dal prefisso del nome file
   (`filename.find("Proton") == 0`, ecc.).
3. **Esecuzione della macro.** Il file viene caricato con
   `gROOT->ProcessLine(".x <file>")`, che esegue la funzione e restituisce
   il `TCutG*`.
4. **Popolamento della mappa.** Il cut caricato viene assegnato a *tutti* i
   run ID il cui periodo (passo 1) coincide col periodo del file di cut
   (passo 2): `gCutMap[particella][rivelatore][runID] = cut`.

Il motivo per cui i cut sono per-anno e per-run (non un cut fisso per tutta
la presa dati) è geometrico/strumentale: l'accettanza e la risposta dei
rivelatori (tempo di volo, perdita di energia) cambiano tra periodi di
presa dati diversi — un singolo poligono su tutta la statistica includerebbe
o escluderebbe candidate in modo sistematicamente sbagliato per i periodi
agli estremi.

## Cut assente per scelta, cut assente per errore

Un cut può mancare per due ragioni molto diverse, e finché non si distinguono la
fisica cambia in silenzio.

**Assente per scelta.** Un deutone può uscire solo da un bersaglio di deuterio.
Sui periodi a idrogeno (`_uv`, `_fuv`, `_vis`) il cut deutone non esiste, ed è
giusto così: quel canale non va nemmeno cercato. Lo stesso vale per l'intero
blocco in avanti nel range `2005_d1`, dove il rivelatore forward era
inutilizzabile.

**Assente per errore.** Qualcuno aggiunge un periodo di presa dati e dimentica un
file di cut. Quel run ha bisogno di quel cut e non ce l'ha.

### Il difetto che c'era (corretto il 14 luglio 2026)

`GetCut` restituiva `nullptr` in entrambi i casi, e ogni chiamante scriveva:

```cpp
TCutG *ProtonCntCut = GetCut("Proton", "Cnt", Idrun, false);
if (ProtonCntCut != nullptr && ProtonCntCut->IsInside(...)) {
   // protone
} else {
   // ...altrimenti prova come pione
}
```

Se il cut protone mancava, il `&&` corto-circuitava a `false` — che è
**indistinguibile da "la traccia non ha passato il cut"**. La traccia finiva nel
ramo `else` e veniva testata come pione. Un file di cut dimenticato non faceva
fallire la run: **riclassificava ogni candidato protone come pione**, e la fisica
cambiava senza che niente lo dicesse. L'unico segnale era una riga su `stderr` per
*ogni traccia*: un diluvio illeggibile, facilissimo da perdere.

### Come funziona adesso

Le due ragioni sono separate nel codice:

| funzione | cosa fa |
|---|---|
| `HasCut(p, d, run)` | chiede se il cut esiste, in silenzio, senza effetti |
| `IsDeuteriumRun(run)` | il periodo è a deuterio (`_d`)? Solo lì si cerca il deutone |
| `IsForwardExcluded(run)` | il range `2005_d1`, dove il blocco forward è escluso |
| `RequireCut(p, d, run)` | prende un cut **obbligatorio**: se manca, **esce con codice 1** |
| `ValidateRunCuts(run)` | controlla **una volta per run** che ci siano tutti i cut che quel run userà |

`ValidateRunCuts` viene chiamata dal loop sugli eventi la prima volta che si
incontra un run: una run malformata si ferma al primo evento, invece di produrre
fisica sbagliata per milioni. Il messaggio nomina il run, il periodo e il file che
si aspettava:

```
!!! Missing required cut: Proton Cnt for run 9000
    Run belongs to folder '9999_zz'; expected cut file: ProtonCntCut_9999_zz.cpp
    Refusing to continue: without this cut every candidate would be silently misclassified.
```

E il deutone non viene più chiesto sui run a idrogeno: non lo si cerca affatto,
invece di cercarlo, ricevere `nullptr` e saltarlo per caso.

Quali cut servono davvero a un dato run:

| cut | quando è obbligatorio |
|---|---|
| `Proton Cnt`, `Pion Cnt` | sempre |
| `Proton Fwd`, `Pion Fwd` | sempre, tranne nel range `2005_d1` |
| `Deuteron Fwd` | solo sui periodi `_d`, `2005_d1` escluso |

## Un file orfano

`PionFwdCut_2005_d1.cpp` esiste ma non viene mai usato: `PreAnalysis.C` esclude
tutto il blocco forward per quel range di run, perché il rivelatore in avanti era
inutilizzabile. Coerentemente, per `2005_d1` non esistono né `ProtonFwdCut` né
`DeuteronFwdCut` — è rimasto solo il file del pione, orfano. Non è un errore da
correggere: è il residuo di una scelta corretta.
