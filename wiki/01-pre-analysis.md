# 01 — Pre-analisi

`01_pre_analysis/PreAnalysis.C` è il primo stadio della pipeline: legge le run grezze del rivelatore e le trasforma in un albero ROOT compatto, `h80`, un'entry per evento, con i quadrivettori delle particelle già ricostruite.

## Cosa fa `PreAnalysis::Loop`

Per ogni evento, il loop scorre le tracce centrali (`Nass_3`) e quelle in avanti (`Nparf`) e classifica ogni traccia in una delle categorie seguenti, usando i cut geometrici (vedi [Cuts](01-pre-analysis-cuts)):

| Categoria | Provenienza | Come viene identificata |
|---|---|---|
| `gammas` | tracce neutre centrali (`Itipo_track == 11`) e regione fotoni in avanti (`7.5 <= Tof_trf <= 12.5`, angolo soltanto) | energia/angolo del cluster |
| `protons` | tracce cariche centrali dentro `ProtonCntCut`, oppure tracce in avanti dentro `ProtonFwdCut` | cut su (E, dE/dx) al centro, su (tof, dE) in avanti |
| `neutrons` | tracce neutre in avanti con tempo di volo lungo (`Tof_trf >= 12`, regione neutroni) | beta ricavato dal tempo di volo |
| `deuterons` | tracce cariche in avanti dentro `DeuteronFwdCut` | cut su (tof, dE) |
| (scartate) | tracce cariche centrali che non superano né `ProtonCntCut` né `PionCntCut` | nessuna categoria |

Per le particelle massive (protoni, neutroni, deutoni) l'impulso si ricava dal tempo di volo/energia depositata via `E_tot^2 = p^2 + m^2`, usando le masse (in GeV):
- `RMP = 0.9382720813`
- `RMN = 0.939485`
- `RMD = 1.877`

> Un dettaglio del codice degno di nota: se il quadrato dell'impulso viene negativo (`Ppro_sq < 0`, ecc.) la candidata viene scartata silenziosamente — non c'è controllo aggregato su quante candidate vengono perse così.

> Da notare anche una regione esclusa a mano: per le run `2005_d1` (`4577 < Idrun < 4606`) le tracce cariche in avanti non vengono processate affatto (non entra nel blocco che le classifica come protone/pione/deutone), un'eccezione specifica per quella run scritta direttamente nel codice.

## Rami del `h80`

I quadrivettori (`ROOT::Math::PxPyPzEVector`) sono i rami che il resto della pipeline legge:

```cpp
output_tree->Branch("beam",      "ROOT::Math::LorentzVector<...>", &beam);
output_tree->Branch("gammas",    "vector<ROOT::Math::LorentzVector<...>>", &gammas);
output_tree->Branch("neutrons",  "vector<ROOT::Math::LorentzVector<...>>", &neutrons);
output_tree->Branch("protons",   "vector<ROOT::Math::LorentzVector<...>>", &protons);
output_tree->Branch("deuterons", "vector<ROOT::Math::LorentzVector<...>>", &deuterons);
```

## Rami letti dalla pre-analisi

`PreAnalysis(input, output)` limita la lettura dell'albero grezzo a un sottoinsieme esplicito di rami per velocizzarne la lettura (`branches` in `PreAnalysis.C`):

```
Eg_tag_strip, Idrun, Ipol, Nass_3, Thet_centr_track, Phi_centr_track,
Itipo_track, Eclusc_track, Dedx_track, Nparf, Theta_trf, Phi_trf,
Index_trf, Iass_trf, Tof_trf, De_trf
```

Attivare solo questi rami (invece dell'intero albero DAQ) è quello che rende leggibile un'intera run in tempi ragionevoli.

## `AnalyzeAll(base_in, base_out, cuts_dir)`

È la funzione che il resto della pipeline invoca (vedi [Pipeline](pipeline)):

```cpp
AnalyzeAll("RAW_DIR", "PRE_DIR", "01_pre_analysis/cuts")
```

Funzionamento del codice:

1. Controlla che `base_in` e `cuts_dir` esistano; se manca uno dei due, stampa un errore e chiama `gSystem->Exit(1)`. 
   >Nota per chi legge `AccessPathName`: il suo valore di ritorno è invertito rispetto all'intuizione — `AccessPathName` restituisce `false` quando il percorso esiste — e il commento nel codice lo dice esplicitamente perché è un punto facile da leggere al contrario.
2. Costruisce la mappa dei cut una sola volta con `BuildCutMap` (vedi [Cuts](01-pre-analysis-cuts)), prima di processare qualunque run.
3. Elenca le sottocartelle di `base_in` (una per run) e per ciascuna chiama `PreAnalysis(base_in/<run>/*.root, base_out/pre_analisi_<run>.root)`.
4. Se non trova nessuna sottocartella (`n_runs == 0`) il codice si blocca.

## Prefisso `pre_`

Il nome di output è `pre_analisi_<run>.root`, un file per periodo. Il prefisso `pre_` è ciò che `02_event_selector/select_events.py` cerca per elencare i file da processare (`f.startswith("pre_")`): senza quel prefisso, la fase 2 non troverebbe nulla da leggere — vedi [Selezione eventi](02-event-selector).

## Dove andare da qui

- [Cuts](01-pre-analysis-cuts) — i 95 file di `01_pre_analysis/cuts/`,
  come un run viene abbinato al proprio cut, cosa succede a un run senza
  cut corrispondente.
- [Formati dati](data-formats) — lo schema completo di `h80`.
