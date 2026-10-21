# Scansione dei criteri di accettazione dei flussi ricostruiti

Protocollo definito il 20 ottobre 2026, prima dell'esecuzione della scansione.
Obiettivo: quantificare il compromesso fra eventi recuperati, precisione e
distorsione degli osservabili, scegliendo quando una ricostruzione può essere
considerata plausibile. Questo documento registra metodo, decisioni e stato
dell'esperimento per la futura stesura dell'articolo.

## Terminologia

- **Donatore:** run buona con flusso misurato, precedente o successiva al
  bersaglio nello stesso periodo e stato.
- **Bersaglio mascherato:** run buona il cui flusso viene nascosto al modello,
  conservato separatamente per valutare l'errore.
- **Politica di accettazione:** insieme dei limiti che una ricostruzione deve
  rispettare. Tutti gli stati mancanti di una run devono rispettarli.
- **Oracle appaiato:** estrazione con il flusso vero e gli stessi eventi/run
  della corrispondente estrazione con flusso ricostruito.
- **Replica:** variazione del flusso ottenuta ricampionando blocchi di training
  e residui di validazione, mantenendo le correlazioni assunte nel metodo.
- **Copertura:** frequenza con cui l'intervallo predetto contiene il valore
  vero. Una banda etichettata 95% non garantisce da sola copertura 95%.

## Scelte congelate

Extra Trees ibrido è il modello principale: forma dal modello, integrale
dall'interpolazione dei flussi per evento fra due donatori. Kernel Ridge
fornisce un controllo di disaccordo sulla forma. La grid search dei parametri
resta confinata ai blocchi interni del training. Le dodici run della
[policy condivisa](../../config/run_quality_exclusions.json) restano escluse
da tutti i campioni e da qualsiasi recupero.

Le durate sono assunte uguali a 15 minuti come concordato. La distanza è quella
fra posizioni nel manifesto delle run, non la differenza aritmetica fra numeri
di run. Si lavora sulle 128 strip native; nella prova su run note la conversione
in energia è indipendente dalla predizione. Questo non valida automaticamente
l'asse energetico di uno stato realmente privo di calibrazione.

### Cinque livelli annidati

Questi numeri sono scelte iniziali dell'analista, non costanti fisiche né soglie
già dimostrate ottimali. Allargando il livello, una run già accettata resta
accettata. La decisione non legge mai il vero flusso del bersaglio, il suo
errore spettrale o l'asimmetria estratta.

| Livello | Distanza massima da ciascun donatore | Intervallo quantili dei conteggi di training | Disaccordo normalizzazione donatori | L1 forme Extra Trees/Kernel Ridge | Incertezza L1 al 95% |
|---|---:|---:|---:|---:|---:|
| `strict_1` | 15 min | 10–90% | 10% | 3% | 5% |
| `strict_2` | 30 min | 5–95% | 20% | 5% | 10% |
| `moderate_3` | 45 min | 2,5–97,5% | 35% | 8% | 20% |
| `loose_4` | 75 min | minimo–massimo | 50% | 12% | 35% |
| `loose_5` | 150 min | minimo–massimo | 100% | 20% | 50% |

Disaccordo di normalizzazione: differenza assoluta fra gli integrali dei
flussi/evento dei due donatori, divisa per la loro media. L1 delle forme:
somma degli scarti assoluti dopo normalizzazione a integrale uno.
Incertezza L1 al 95%: quantile 95% di
`sum(abs(replica - previsione_centrale)) / sum(previsione_centrale)`.
Quest'ultima è una diagnostica predittiva la cui calibrazione va verificata.

Requisiti fissi: spettri finiti e non negativi con integrale positivo; donatori
buoni ai due lati, nello stesso gruppo; conteggi entro il range del training;
almeno otto run di validazione accoppiate in quattro blocchi; almeno 32 repliche
valide e almeno il 90% delle repliche richieste disponibili. Una misura
indisponibile provoca rifiuto, mai un'incertezza assegnata uguale a zero.

## Separazione dei campioni e ripetizioni

Si riserva prima circa il 20% delle run, in blocchi da tre, con seed 20261021.
Queste run non entrano nel training, nella calibrazione delle incertezze o nella
scelta delle soglie della nuova scansione. I periodi troppo piccoli restano
esplicitamente insufficienti, senza fabbricare una verifica indipendente.

Dieci ripetizioni di sviluppo usano seed `20261020 + 101*i`, `i=0..9`, alternando
blocchi da una e tre run. In ciascuna ripetizione i blocchi separano training,
validazione e test. Gli stati nascosti seguono la frequenza empirica dei gruppi
di stati realmente mancanti nel periodo, dopo aver rimosso le anomalie.
Le distanze dei buchi da una/tre run sono prove di stress controllate: non
riproducono esattamente ogni sequenza di buchi osservata.

Si generano 128 repliche Extra Trees per ripetizione. Le stesse predizioni,
repliche e selezioni di eventi sono riutilizzate a ogni livello. Due livelli
che accettano esattamente le stesse run riutilizzano gli stessi risultati,
registrando questa equivalenza.

Le ripetizioni condividono dati e non sono dieci esperimenti indipendenti.
Anche il campione riservato proviene dalla campagna già esaminata: la verifica
finale è una **conferma interna alla nuova scansione**, non una conferma su
dati sperimentali mai osservati. Tale limite va mantenuto nell'articolo.

## Confronti degli osservabili

Per ogni soglia vengono confrontati:

1. **Senza recupero:** tutte le run mascherate sono escluse, anche quelle che
   altre soglie potrebbero accettare. Questo riferimento resta fisso.
2. **Con recupero:** entrano soltanto le run accettate, con flussi ricostruiti.
3. **Oracle appaiato:** medesime run del punto 2, usando i flussi veri.

Le run rifiutate non entrano nell'oracle appaiato. Altrimenti una differenza
dovuta al campione sarebbe erroneamente attribuita alla ricostruzione.
I casi senza recupero sono identificati come tali: nessun apparente guadagno
da un elenco vuoto di misure.

Si registrano conteggi di run/eventi, fallimenti, spostamenti di Σ, errori
statistici e contributo condizionale del flusso, per periodo e punto cinematico.
Le finestre restano quelle UV/VIS della produzione. Il numero di eventi
ricostruiti non è una resa di segnale estratta da un fit.

## Selezione e criterio di arresto

La scelta avviene soltanto sui risultati di sviluppo completi. Il controllo
iniziale è deliberatamente conservativo: effetto della rappresentazione
≤0,05 σ_stat, massimo scostamento appaiato per punto ≤0,10 σ_stat,
contributo del flusso ≤0,30 σ_stat, nessuna perdita di punti richiesta,
almeno 90% di repliche complete e copertura 68/95% compatibile nei gruppi
valutabili. Il limite sul singolo punto è più stringente del precedente
budget sul bias medio; non sostituisce una stima indipendente del bias medio.

Gli intervalli sulla copertura ricampionano gruppi di bersagli con donatori
o blocchi condivisi. Restano diagnostiche condizionali: non eliminano tutta
la dipendenza dal modello e dal campione di residui. Il protocollo non
trasforma un superamento diagnostico in certificazione fisica.

Fra le politiche che superano tutti i controlli si minimizza la mediana,
fra ripetizioni, della mediana del rapporto fra errore statistico+flusso
con recupero ed errore statistico senza recupero, su punti confrontabili
fissati. A parità si preferisce il livello più stringente. Una politica
senza eventi recuperati non può vincere. Se nessuna è ammissibile,
il risultato è **nessuna soglia scelta**, senza allargamenti a posteriori.

Solo dopo aver scritto e congelato la scelta si esegue la conferma interna
con seed 20271103 e blocchi da tre. Non si provano altre soglie su quel
campione se la soglia scelta fallisce. Un'eventuale revisione del protocollo
diventa un nuovo studio di sviluppo e va documentata come tale.

## Riproducibilità ed esecuzione

La preparazione salva protocollo JSON, impronte SHA-256 degli input, seed,
partizioni, esclusioni e audit delle strip. Ogni prova salva griglie complete,
predizioni e riferimenti, repliche, decisioni per stato, run rifiutate con
motivazioni, confronti degli osservabili, diagnostiche di copertura e grafici.
La raccolta conserva anche il numero atteso di prove e i risultati mancanti.

Le prove sulla farm usano uno snapshot isolato del codice, senza modificare
la produzione né lo studio storico. Dieci job da quattro core richiedono al
massimo **40 core contemporanei**; i thread BLAS sono limitati a uno.
La raccolta e l'eventuale conferma dipendono dal completamento dei job.

Implementazione verificata: 1.355 test locali superati (un avviso preesistente
su una legenda vuota) e 79 test mirati superati sulla farm. La revisione ha
individuato e fatto correggere tre problemi prima delle prove complete:
isolamento delle run riservate anche dagli osservabili di sviluppo; verifica
del denominatore e dei seed congelati; identità delle politiche negli artefatti.
I test di regressione verificano anche che alterare eventi/flussi delle run
riservate non cambi il confronto di sviluppo.

La preparazione contiene 1.278 run buone, 3.834 spettri in dodici periodi con
almeno una run buona. Le run riservate sono 239; quelle disponibili allo
sviluppo 1.039. Il periodo 2001 UV non ha run complete buone; 2003 VIS ha solo
sei run e non offre un blocco riservato con questa regola.

Snapshot isolato sulla farm:
`/data/graal/GRAAL_Analysis/results/flux-acceptance-scan-20261020`.
Il [protocollo congelato](../../results/farm-acceptance-launch-20261020/protocol.json)
ha SHA-256
`2e27a9569153916acbdc4b65edd7caa5acefc357e9246b692b07432b9b0cc97b`.
Il [manifesto del codice](../../results/farm-acceptance-launch-20261020/source_manifest.json)
contiene le impronte di 395 file; il sorgente comprende anche le modifiche
locali autorizzate e non ancora committate.

Prova tecnica preliminare: job Slurm 5, periodo 1999 UV, 32 repliche, quattro
core. Questa prova usa un protocollo distinto; non entra nella selezione delle
soglie. Le soglie della prova completa sono già congelate e non vengono
modificate in base al suo risultato.

La prova tecnica e il lanciatore Slurm 6 hanno completato il passaggio:
l'array 7 è stato sottomesso alle 10:47:22 UTC del 20 ottobre 2026.
L'array ha atteso la conclusione del job di lancio, evitando di allocare 41
core durante il passaggio. Seguono raccolta (job 8) e conferma condizionale
(job 9); se non
esiste una politica ammissibile, la conferma registra il motivo senza
eseguire nuovi fit. Gli identificativi e le impronte sono conservati nel
[registro dei job](../../results/farm-acceptance-launch-20261020/jobs.json).

Al controllo delle 12:01 UTC (14:01 ora italiana), tutte le dieci prove
erano in esecuzione da circa 74 minuti, con quattro core ciascuna.
I job 8 e 9 attendevano le rispettive dipendenze:
**la scansione completa non ha ancora risultati conclusivi**.
Al ricontrollo delle 14:14 UTC (16:14 ora italiana), le prove 3, 5 e 9
hanno prodotto il rispettivo `trial.json`; per la prova 9 Slurm conserva
anche lo stato `COMPLETED`, con `ExitCode=0:0`. Le altre sette prove sono
ancora attive (28 core complessivi), dopo circa 3 ore e 27 minuti.
L'accounting Slurm è disabilitato e i record dei job 3 e 5 non sono più
disponibili tramite `scontrol`: per questi resta l'evidenza degli artefatti.
Selezione e conferma attendono ancora le dipendenze; nessuna scelta viene
effettuata sui soli risultati parziali.
Lo [stato di lancio](../../results/farm-acceptance-launch-20261020/launch-status.txt)
riporta orario UTC, job, dipendenze e avanzamento. Sono conservati anche
l'[ambiente software](../../results/farm-acceptance-launch-20261020/environment.json)
e il [log dei test sulla farm](../../results/farm-acceptance-launch-20261020/farm-tests.log).
Nessuna nuova adozione in produzione.
