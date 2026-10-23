# Protoni centrali: preselezione e confronto locale delle asimmetrie

## Modifica applicata

`02_event_selector/select_events.py` richiede ora esattamente quattro fotoni
centrali, esattamente un protone identificato e zero candidati pioni centrali
o forward. Il protone con theta <25 gradi richiede una carica forward; con
theta >=25 gradi richiede zero cariche forward. Confronto in radianti;
dimensione del vettore verificata prima di accedere al protone.
Assunzione richiesta dall'utente: tagli PID protone/pione disgiunti.

| Fotoni centrali | Protoni | Pioni identificati | Theta protone | Cariche forward | Esito |
|---:|---:|---:|---|---|---|
| 4 | 1 | 0 | <25 gradi | 1 | Passa |
| 4 | 1 | 0 | <25 gradi | 0 oppure >=2 | Scarta |
| 4 | 1 | 0 | >=25 gradi | 0 | Passa |
| 4 | 1 | 0 | >=25 gradi | >=1 | Scarta |
| diverso da 4 | qualsiasi | qualsiasi | qualsiasi | qualsiasi | Scarta |
| 4 | diverso da 1 | qualsiasi | qualsiasi | qualsiasi | Scarta |
| 4 | 1 | >=1 | qualsiasi | qualsiasi | Scarta |

I rami `protons` e `pions_theta` diventano obbligatori. Conservazione dei rami
e pubblicazione atomica del dataset restano operative. Nessuna modifica a
PID, ricostruzione, training, flussi o stimatori.

## Campioni e metodo

Studio in `results/central-proton-selection-20261023/`. Entrambi i bracci
ricostruiti dagli stessi h80 locali, anziche confrontare il dopo con una
campagna contenente altri periodi. Prima: filtro storico
`gammas.size() > 1 && fcharged_theta.size() == 1`.

| Periodo | Input h80 | h85 prima | h85 dopo | Centrali dopo | Forward dopo |
|---|---:|---:|---:|---:|---:|
| 1998 UV | 90.279.078 | 5.341.787 | 394.544 | 140.468 | 254.076 |
| 1999 VIS | 94.402.268 | 3.207.538 | 278.515 | 85.491 | 193.024 |

Centrali/forward definiti dalla soglia angolare concordata. Tutti i centrali
del nuovo h85 hanno zero cariche forward ed erano esclusi dal vecchio filtro.
Conteggi h85 includono eventi ancora soggetti ai tagli cinematici e sui flussi.

Stessi modelli locali UV/VIS, congelati; nessun retraining. Entrambe le
ricostruzioni, chi2 e BDT+chi2, senza fit cinematico; chi2 <10, risoluzione
relativa 0.08, finestra missing mass +/-0.06 GeV. Griglia nominale UV
1.1,1.2,1.3,1.4,1.5 GeV; VIS 0.9313-1.1 GeV. Ratio con algoritmo esistente
best-binning fra 8/12/16 bin phi e relativa correzione finite-bin;
likelihood non binnata. Stessa regola adattiva, ma la scelta per punto puo
cambiare con il campione: 44 degli 89 bin UV BDT comuni cambiano binning.

Flusso comune `results/common/flux_calibrated.root`, stessi manifest e
requisiti di qualita. Universo inclusivo ricavato prima della selezione:
178 run UV e 110 run VIS. Verificati identici insiemi di run nei quattro
percorsi di ciascun profilo e identiche esposizioni per run/strip prima/dopo.
Chiusura dell'estrazione per periodo superata; nessuna esposizione rimossa
in funzione del rendimento della nuova selezione.

## Eventi effettivamente usati per Sigma

Conteggi dopo ricostruzione, energia, POL1/POL2, qualita delle run e flusso valido.

| Profilo | Percorso | Prima | Dopo | Centrali dopo | Forward dopo |
|---|---|---:|---:|---:|---:|
| UV | chi2 | 14.024 | 15.129 | 2.323 | 12.806 |
| UV | BDT+chi2 | 11.342 | 11.701 | 1.333 | 10.368 |
| VIS | chi2 | 5.894 | 6.053 | 527 | 5.526 |
| VIS | BDT+chi2 | 2.572 | 2.433 | 25 | 2.408 |

Il BDT VIS conserva soltanto 25/527 = 4,7% dei candidati centrali che passano
chi2 e flussi, contro 2.408/5.526 = 43,6% dei forward. UV: 57,4% centrali,
81,0% forward. Sono quote osservate nei dati, non efficienze di segnale.
Il recupero centrale funziona nel selettore; il modello BDT VIS richiede
verifica dedicata per questa topologia prima di considerarlo adeguato.

## Cambiamenti delle asimmetrie

Delta Sigma = dopo - prima. Statistiche descrittive nei medesimi bin stimabili
in entrambi i bracci; nessuna significativita assegnata alle differenze.

| Profilo | Percorso | Estimatore | Bin comuni | Mediana assoluta Delta Sigma |
|---|---|---|---:|---:|
| UV | chi2 | ratio | 98 | 0,0369 |
| UV | chi2 | likelihood | 98 | 0,0273 |
| UV | BDT+chi2 | ratio | 89 | 0,0359 |
| UV | BDT+chi2 | likelihood | 89 | 0,0288 |
| VIS | chi2 | ratio | 17 | 0,0238 |
| VIS | chi2 | likelihood | 17 | 0,0169 |
| VIS | BDT+chi2 | ratio | 15 | 0,0140 |
| VIS | BDT+chi2 | likelihood | 15 | 0,0094 |

UV chi2 perde un bin e ne guadagna due per estimatore; UV BDT perde due bin
e ne guadagna tre. VIS chi2 mantiene tutti i bin; VIS BDT ne guadagna uno.
Bin mancanti non rappresentati come Sigma=0. Alcuni spostamenti locali sono
molto maggiori delle mediane; CSV completo e grafici conservano tutti i casi.

## Confronto Ajaka

Usati i 57 punti digitalizzati di Fig.4, associati ai corrispondenti bin
UV di energia e al bin di massa contenente l'ascissa pubblicata. Nessuna
interpolazione. Tre punti privi di errore recuperabile mostrati senza barre.
Il riferimento non contiene punti per la finestra VIS locale.

| Percorso UV | Estimatore | Mediana scarto assoluto da Ajaka prima | Dopo |
|---|---|---:|---:|
| chi2 | ratio | 0,1199 | 0,1155 |
| chi2 | likelihood | 0,1282 | 0,1042 |
| BDT+chi2 | ratio | 0,0837 | 0,0870 |
| BDT+chi2 | likelihood | 0,1150 | 0,0898 |

L'accordo non migliora uniformemente: likelihood si avvicina come mediana,
mentre ratio BDT cambia poco e peggiora leggermente su questo indicatore.
Restano differenze visibili, soprattutto in p-eta alla piu bassa energia UV.
La mediana non e un test di compatibilita e non separa fondi e accettanza.

## Artefatti e prove

- `report.html`: rapporto completo con quattro grafici prima/dopo/Ajaka,
  tabelle e collegamenti a comandi e input.
- `comparison_raw_bdt_ratio.png`, `comparison_raw_bdt_likelihood.png`,
  `comparison_raw_ratio.png`, `comparison_raw_likelihood.png`.
- `all_points.csv`, `summary.json`, `selection_inventory.json`:
  punti, errori condizionati, stato dei bin, variazioni e conteggi.
- `before/` e `after/`: h85, entrambe le ricostruzioni ROOT, estrazioni ROOT,
  PDF e metadati per periodo. Campagne precedenti preservate.
- `inputs.json`, `commands.json`, `settings.json`, `source_snapshot/`,
  `run_study.py` e `build_report.py`: identita SHA-256, comandi effettivi,
  filtri prima/dopo e riproduzione.

Regressioni osservate fallire sul vecchio filtro: 12 failure attesi.
Dopo modifica: 38 test selettore/metadati passati. Suite repository completa:
**1.483 test passati**, un UserWarning preesistente in
`test_closed_gate_writes_full_coverage_report` per legenda senza artisti.
`git diff --check` superato. Revisione indipendente senza problemi materiali.
Contabilita input = scritti + scarti verificata per run/stato; identiche
impostazioni, sorgenti e modelli prima/dopo verificate dagli hash ROOT.
Grafici PNG e PDF Ajaka finale ispezionati visivamente.

## Limiti

Campioni prima/dopo sovrapposti: nessun errore sulla differenza senza
covarianza appaiata, non calcolata in questo controllo. Errori locali
statistici condizionati, senza incertezza sistematica completa. Nessuna
indipendenza assunta rispetto alla pubblicazione GRAAL di Ajaka.

Cambio composto: recupero dei protoni centrali, esattamente quattro fotoni e
veto pionico cambiano insieme. Non attribuire ogni variazione al solo protone
centrale. Zero pioni identificati non esclude cariche centrali non identificate.
H80 locali legacy privi di metadati raw-track e provenienza della preanalisi:
nessuna nuova certificazione di tagger, PID, fondi o accettanza. Nuova selezione
non validata su MC in questo studio. Le run con forward escluso non appartengono
ai due periodi locali; in produzione il vettore vuoto non prova assenza fisica
di cariche forward quando quel rivelatore e escluso.
