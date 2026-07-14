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

## Cosa succede a un run senza cut corrispondente

`GetCut(particle, detector, runID)` (la funzione che `PreAnalysis.C`
interroga per ogni traccia candidata) fa tre controlli in cascata —
particella nella mappa, rivelatore nella mappa della particella, run ID
nella mappa del rivelatore — e al primo che fallisce:

- stampa un `ERROR:` su `std::cerr` con la causa specifica (e, se il run è
  comunque noto a un'altra combinazione particella/rivelatore, dice a quale
  periodo appartiene, per facilitare la diagnosi);
- **restituisce `nullptr`**, non lancia un'eccezione e non ferma
  l'esecuzione.

Il chiamante (`PreAnalysis.C`) tratta sempre `nullptr` come "nessuna
candidata in questa categoria":

```cpp
TCutG *ProtonCntCut = GetCut("Proton", "Cnt", Idrun, false);
if (ProtonCntCut != nullptr && ProtonCntCut->IsInside(Eclusc_track[i], Dedx_track[i])) {
   // ...
}
```

Quindi un run senza cut per una certa particella non fa fallire la
pre-analisi: perde silenziosamente ogni candidata di quella specie per
quel run, mentre le altre categorie (quelle con un cut valido) continuano a
essere popolate normalmente. Dato che `GetCut` viene chiamato per ogni
traccia candidata (non una volta per run), un cut mancante produce una riga
`ERROR` per ogni traccia che avrebbe dovuto passare da lì — su `stderr`,
non un'eccezione, quindi facile da perdere in un log lungo se non lo si
cerca esplicitamente.

## Un'anomalia trovata leggendo il codice

`PionFwdCut_2005_d1.cpp` esiste, ma non viene mai usato: `PreAnalysis.C`
esclude esplicitamente l'intervallo di run `2005_d1`
(`Idrun > 4577 && Idrun < 4606`) dal blocco che processa le tracce cariche
in avanti (proton/pion/deuteron Fwd), a causa di una nota nel codice su
quel range di run. Coerentemente, per `2005_d1` non esistono né
`ProtonFwdCut` né `DeuteronFwdCut` — solo il file `PionFwdCut` è rimasto,
orfano.
