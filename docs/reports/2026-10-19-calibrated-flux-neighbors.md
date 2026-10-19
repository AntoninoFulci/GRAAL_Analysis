# Flussi calibrati: primo confronto tra vicini e Ridge

Studio eseguito il 19 ottobre 2026. **Esito esplorativo: la normalizzazione
tramite conteggi aiuta; Ridge non è un sostituto validato dell'interpolazione.**
Nessun flusso di produzione è stato modificato o sostituito.

## Dati e ipotesi

Due h80: `1998_uv` (90.279.078 eventi) e `1999_vis` (94.402.268 eventi).
Le copie in `test_data/pre_analyzed/` hanno UUID ROOT e numero di entry uguali
ai file in `trima:/data/graal/pre_analisi/`, verificati via SSH. Non è stato
necessario trasferire nuovamente circa 15 GB. Conteggio di tutte le entry h80
per RunNumber/Polarization, senza selezioni di canale. Questi file storici
precedono il controllo attuale degli eventi senza tagger.

Flussi: `data/00_external/flux_calibrated.root`. Incrocio con
`config/run_manifest.csv`: **279 run con triplette complete e conteggi
disponibili**, 170 UV e 109 VIS, per 837 spettri. Nove ulteriori run presenti
negli h80 sono esclusi per triplette/conteggi incompleti; motivi conservati
in `summary.json`. I run senza h80 in questi due file non fanno parte del pilot.

Su indicazione dell'utente: durata **15 minuti per run**, trigger, prescale,
tempo morto, fondo e risposta inclusiva assunti costanti. Non esistono tempi
di acquisizione. L'ordine numerico dei run nel manifest del periodo è usato
come proxy dell'ordine di acquisizione; ogni posizione vale 15 minuti.
Questo non dimostra stabilità strumentale né ricostruisce pause reali.
Moltiplicare tutte le distanze per 15 non cambia i pesi dell'interpolazione.
Non si attribuiscono durate misurate ai singoli stati POL1/POL2/BREM.

## Metodo e controllo del test

Spettri ribinnati conservando i conteggi su 128 bin comuni, 0,5--2,0 GeV.
Intervallo fissato prima del fitting; include il dominio dei flussi locali.
Per un run nascosto, due vicini completi dello stesso periodo/stato forniscono
spettri divisi per i rispettivi conteggi. Interpolazione e Ridge predicono
flusso per evento, poi moltiplicato per il conteggio del run bersaglio.

Ridge usa 387 variabili: 128 bin del vicino precedente, 128 del successivo,
128 dell'interpolazione derivata, due distanze assunte e posizione relativa.
Nessuna nuova informazione nel vettore dell'interpolazione: rende direttamente
disponibile alla regressione la combinazione pesata dei due vicini.
Standardizzazione soltanto sul training; proiezione a valori non negativi
registrata nei risultati. Non usa flusso, calibrazione o asse del bersaglio,
né flussi degli altri stati del bersaglio.

Due esperimenti, seed 42: blocchi di uno e tre run. Blocchi interi assegnati
circa 60/20/20 a training, validazione delle bande e test, con ruoli uguali
tra stati dello stesso run. Ogni esempio training esclude il proprio blocco
dai vicini. Tre fold interni di blocchi distribuiti lungo il periodo scelgono
alpha tra 0,1, 1, 10, 100; i vicini sono ricostruiti entro ogni fold.
La validazione esterna calibra soltanto gli intervalli. Il test è escluso
da training, scelta di alpha, riferimenti e stima delle bande.

Per ogni esperimento risultano **162 spettri di test ricostruibili**,
corrispondenti a 54 run e tre stati. Sono gli stessi bersagli per tutti i
quattro metodi confrontati. Run ai bordi senza due riferimenti rimangono
esplicitamente esclusi. I due esperimenti non costituiscono 324 misure
indipendenti: alcuni run e molti riferimenti sono condivisi.

## Risultati

Errore mediano assoluto sull'integrale, percentuale:

| Mascheramento | Vicino singolo / eventi | Due vicini senza conteggi | Due vicini / eventi | Ridge / eventi |
|---|---:|---:|---:|---:|
| Run isolati | 3,53% | 17,18% | **2,78%** | 5,33% |
| Blocchi di tre run | **3,90%** | 21,11% | 4,81% | 5,31% |

Errore spettrale relativo L1 = somma degli scarti assoluti nei bin divisa per
l'integrale vero. Mediana sui 162 bersagli:

| Mascheramento | Due vicini / eventi | Ridge / eventi | Bersagli in cui Ridge ha L1 minore |
|---|---:|---:|---:|
| Run isolati | 8,56% | 8,17% | 48,1% |
| Blocchi di tre run | 9,66% | 7,81% | 64,8% |

La mediana dell'errore di forma L1 (spettri a integrale uno, scala 0--2)
passa da 0,0757 a 0,0674 per run isolati e da 0,0763 a 0,0633 per blocchi
di tre run. Questo miglioramento di forma non implica migliore normalizzazione.

Le medie globali sono molto sensibili a casi anomali. Per run isolati, la media
L1 relativa è 26,29 per interpolazione e 4,34 per Ridge: **non** sono percentuali
e non descrivono un run tipico. Non uso queste medie come prova di superiorità.

### Anomalia già nei flussi originali

Nel run **1322** il flusso BREM integrato vale 2.567.590.011, con 1.881
eventi h80 BREM: circa **1.365.013 fotoni per evento**. Nei run 1321, 1324,
1326 e 1328 il rapporto BREM vale rispettivamente circa 332, 324, 318 e 217.
Il valore anomalo è identico nel raw e nel calibrato: non è introdotto dal
ribinning o dal modello. Nello stesso run, POL1 ha integrale 537.987,786,
molto inferiore ai POL1 vicini. Questa struttura merita verifica delle
associazioni di stato; non prova uno scambio e non è stata corretta automaticamente.

Nel test a run isolati, usare 1322 come riferimento BREM produce errori enormi
nei run 1324 e 1326. Anche Ridge è vulnerabile: per BREM UV isolato la mediana
L1 è 20,52 (oltre 2000%), contro 0,218 dell'interpolazione. Per BREM VIS in
blocchi di tre run è 0,953 contro 0,199. **La ricostruzione BREM non è validata.**
Nessun caso è stato rimosso dopo aver visto il risultato finale.

## Incertezze

Bande empiriche 68/95% dai vettori di residui della validazione, scalati con
l'integrale previsto. Da 18 a 34 esempi di validazione per gruppo/metodo.
Sono intervalli esplorativi, senza garanzia di copertura o indipendenza fra run.
La copertura marginale dei bin attivi è riportata separatamente per gruppo.
Per esempio, Ridge BREM VIS a blocchi di tre run raggiunge circa il 71,4%
per bande nominali al 95%: ulteriore motivo per non adottare ancora il metodo.

## Plot e artefatti

Cartella finale: [results/calibrated-flux-neighbors-20261019](../../results/calibrated-flux-neighbors-20261019/).

| Esperimento | Confronti UV | Confronti VIS | Diagnostica |
|---|---|---|---|
| Run isolati | [Atlante UV](../../results/calibrated-flux-neighbors-20261019/block_1/overlays_1998_uv.pdf) | [Atlante VIS](../../results/calibrated-flux-neighbors-20261019/block_1/overlays_1999_vis.pdf) | [PDF](../../results/calibrated-flux-neighbors-20261019/block_1/diagnostics.pdf) |
| Tre run | [Atlante UV](../../results/calibrated-flux-neighbors-20261019/block_3/overlays_1998_uv.pdf) | [Atlante VIS](../../results/calibrated-flux-neighbors-20261019/block_3/overlays_1999_vis.pdf) | [PDF](../../results/calibrated-flux-neighbors-20261019/block_3/diagnostics.pdf) |

Ogni pagina dell'atlante mostra vero/interpolato/ML, bande, forma normalizzata,
rapporto previsione/verità e residui. L'indice run/stato/pagina è
`overlay_index.json`. Esempi PNG scelti per errore d'interpolazione mediano e
massimo, con criterio identico per i due metodi. I bin con verità nulla non
sono rappresentati nel rapporto ma rimangono nel residuo e negli errori.

Diagnostica: normalizzazione flusso/eventi, mappa split, integrale previsto
contro vero, errori di integrale e forma, coperture, confronto appaiato,
errore contro conteggi/distanza, mappe energia-run, bias energetico, curve
di regolarizzazione ed errori training/validazione/test. Scale simmetriche
logaritmiche nei riepiloghi degli errori rendono visibili anche i casi estremi.

`predictions.csv` e `spectra.npz` hanno lo stesso ordine delle righe;
`fits.json` conserva alpha, fold, riferimenti training e residui usati per
le bande. `summary.json` contiene metriche e denominatori per periodo/stato.
La cartella con suffisso `-pre-review` è un risultato preliminare superato,
conservato per tracciabilità, non la consegna finale.

## Verifica e prossimo passo

**47 test dello stage passati**, inclusi nove nuovi test: conservazione del
ribinning, conteggi/duplicati, interpolazione analitica, blocchi disgiunti,
assenza di dipendenza dalla verità test, contributo dei tre fold interni,
integrità durante il calcolo e pubblicazione dei plot. Revisione indipendente:
due rilievi importanti riprodotti e corretti; nessun rilievo materiale residuo.
Controllo hash dall'inizio della lettura alla fine della scrittura: quattro
input invariati. Plot ispezionati visivamente. Test di tutto il repository
non rieseguiti: nessuna modifica agli altri stage.

Prima dell'uso sui flussi mancanti: verificare le anomalie raw/calibrato per
stato, definire un criterio di qualità dei riferimenti usando solo dati di
sviluppo, poi validare su ulteriori periodi/test non utilizzati. Gli esiti di
questo pilot non autorizzano selezioni post-hoc o correzioni automatiche dei
flussi. Non sono stati prodotti sostituti per i 842 istogrammi mancanti.
