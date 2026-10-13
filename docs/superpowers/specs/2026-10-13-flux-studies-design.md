# Stage 07 — audit e studio dei flussi mancanti

Data: 13 ottobre 2026.
Stato: struttura approvata in conversazione; specifica scritta da revisionare.
Origine: `docs/plans/2026-10-12-graal/03-flussi-mancanti.md`.

## Obiettivo e perimetro approvato

Aggiungere uno stage numerato autonomo per identificare assenze reali di
POL1/POL2/BREM, diagnosticare le differenze tra flussi grezzi e calibrati e
confrontare ricostruzioni semplici con un modello ML mediante mascheramento
di istogrammi misurati. L'esito può essere negativo: nessun missing reale,
metadati insufficienti oppure nessun metodo validato.

Lo stage non modifica misure, non sostituisce calibrazioni e non abilita
l'impiego dei sintetici nell'estrazione di Σ. Quest'ultimo richiede uno studio
e una decisione successivi, esterni al presente intervento.

## Posizione, proprietà e migrazione

La sequenza dei componenti diventa:

```text
06_calibration/              package calibration
07_flux_studies/             package flux_studies
08_observable_extraction/    package observable_extraction
```

Lo stage 07 dipende dalla calibrazione per contratti di manifest e strip;
lo stage 08 continua a leggere esclusivamente gli artefatti misurati correnti.
La numerazione esprime la dipendenza dei componenti, non impone di eseguire
lo studio in ogni campagna.

Spostare l'attuale directory 07 in 08 preservando tutti i file, compresi quelli
modificati o non tracciati già presenti. Aggiornare mapping setuptools, percorsi
dei test, launcher, script, esempi e documentazione operativa. Conservare il
nome pubblico Python `observable_extraction` e gli schemi degli output fisici.
Gli script invocati tramite il vecchio percorso numerato richiederanno il nuovo
percorso; documentare questa migrazione. Non riscrivere artefatti di campagne,
provenienze storiche, grafo o resoconti datati per fingere che usassero già 08.

Moduli iniziali dello stage 07:

- `audit_flux.py`: CLI e inventario diagnostico.
- `study_missing_flux.py`: CLI, split, confronto e pubblicazione dello studio.
- `metadata.py`: validazione delle condizioni e delle esposizioni esterne.
- `methods.py`: baseline e regressione regolarizzata.
- `validation.py`: mascheramento, metriche e repliche d'incertezza.
- `tests/`: contratti e prove scientifiche controllate.

Riusare lettori e tipi esistenti dove il loro contratto è adeguato. Il lettore
produttivo interrompe il caricamento su triplette malformate: l'inventario deve
invece registrarle e proseguire. Eventuali helper comuni di ispezione restano
in `calibration`; non introdurre una dipendenza 06 → 07 né un secondo modello
del manifest. Nessun refactoring estraneo allo studio.

## Evidenza iniziale e limite interpretativo

L'audit del 12 ottobre documenta una chiave per stato per tutti i 1.831 run P
nel grezzo, contro 1.290 triplette complete in una campagna calibrata.
Questi conteggi vanno ricalcolati sui file scelti, non incorporati nel codice.
Il writer corrente omette istogrammi senza calibrazione run/stato sufficiente;
le 541 differenze documentate non sono quindi prova di assenze grezze.

Il manifest classifica periodo, target e beam, ma non fornisce tempi,
configurazione strumentale o esposizioni indipendenti. Tali informazioni non
si possono ricavare dalla sola distanza tra numeri di run.

## Input e contratti

L'audit richiede `--manifest`, `--raw-flux` e `--output-dir`.
Accetta `--calibrated-flux`, `--calibration-qa` e `--run-metadata` opzionali.
Target predefinito P; filtro beam/periodo esplicito e registrato nell'output.
Il calibrato può mancare: questo consente la diagnosi quando la calibrazione
produttiva si arresta proprio per un istogramma grezzo assente.

Persistenza aggiunta allo stage 06: sidecar JSON versionato vicino a
`flux_calibrated.root`, con identità degli input, copertura h80 per run/stato,
copertura delle strip, gruppi accettati/scartati e motivazioni già calcolate.
Scrittura temporanea e pubblicazione atomica dei singoli file. Il consumatore
verifica l'identità del calibrato associato: un sidecar vecchio o non abbinato
non può certificare la copertura. Un errore fatale non pubblica QA di successo.

Il JSON opzionale dei metadati ha `schema_version: 1` e record per run/stato.
Ogni record identifica `run_number`, `state` e fonte delle informazioni.
Le condizioni disponibili comprendono intervallo temporale UTC di acquisizione,
`configuration_id`, `laser_id` e identificatore del gruppo sperimentale, incluso
Vinci quando noto. Periodo, target e beam devono concordare con il manifest.
L'esposizione, quando disponibile, specifica valore positivo, unità, definizione
fisica, errore e identificatore di eventuale incertezza condivisa. Normalizzazioni
con unità o definizioni differenti non sono intercambiabili.

Record duplicati, contraddizioni con il manifest, tempi invalidi e numeri non
finiti sono errori d'input. Campi assenti restano sconosciuti e disabilitano
soltanto le operazioni che li richiedono. Non introdurre metadati fittizi.

## Inventario e classificazione

Una riga per run/stato nell'universo richiesto, con dettagli per strip separati:

- presenza grezza e calibrata, nomi delle chiavi e cicli, duplicati e alias;
- classe ROOT, dimensione, numero bin, assi e loro validità;
- contenuti, errori disponibili, underflow/overflow, integrali e bin invalidi;
- copertura h80 e calibrazione, ove attestata da input compatibili;
- problemi distinti e stato di utilizzabilità per audit, studio ed estrazione.

Non ridurre cause concorrenti a una singola etichetta. Distinguere almeno:
istogramma grezzo assente, duplicato, oggetto malformato, contenuto non finito,
contenuto negativo, calibrazione assente/insufficiente, run non coperto e
copertura sconosciuta. Separare difetti dell'oggetto da esclusioni di singole
strip nell'estrazione. POL non positivo non è esposizione valida; BREM zero è
valido, ma un istogramma a integrale zero non ha forma normalizzabile.

Il grezzo usa coordinate strip; il calibrato usa energia. Il confronto dei
contenuti mantiene l'indice fisico di strip, senza trattare assi diversi come
errori o rebinning impliciti. Annotare anche trasformazioni note, come il clamp
dei contenuti negativi applicato dal writer corrente.

Un file illeggibile o un contratto d'input invalido causa uscita non zero.
Difetti scientifici inventariabili producono un rapporto completo e uno stato
esplicito; non interrompono la scansione del resto dei run.

## Studio e prerequisiti

`study_missing_flux.py` esegue prima lo stesso audit. Donor e target devono
avere periodo, target, beam, laser e configurazione compatibili e documentati.
Ordine e distanza temporale provengono dai metadati di acquisizione.
Con metadati insufficienti salva protocollo e motivi di esclusione, senza
emettere predizioni numeriche per quei casi.

Metodi da confrontare:

1. Donor compatibile temporalmente più vicino.
2. Template medio e mediano robusto della forma nel gruppo compatibile.
3. Interpolazione lineare temporale tra due donor che racchiudono il target.
4. Regressione Ridge multi-output sulla forma dei 128 bin, con predittori
   effettivamente disponibili quando il target manca.

In assenza di normalizzazione indipendente si confrontano esclusivamente forme
a integrale unitario. L'integrale misurato del target mascherato serve soltanto
alla valutazione, mai alla predizione. Per una stima assoluta usare esposizioni
indipendenti e compatibili per apprendere tassi e ricostruire l'integrale.
Anche la loro incertezza deve entrare nelle repliche.

Le predizioni di forma vengono proiettate su valori non negativi e normalizzate;
predizioni non finite o con somma nulla falliscono esplicitamente. La medesima
trasformazione fa parte della validazione. PCA non è necessaria nella prima
implementazione; può essere introdotta soltanto se giustificata dai risultati.

Un solo lato disponibile non è interpolazione: il confronto a un donor resta
etichettato come tale e richiede valutazione separata dell'incertezza. Nessun
donor compatibile implica non ricostruibilità. Confronti Vinci r−1/r/r+1 sono
prodotti solo per run identificati e verificati compatibili; i numeri non
sostituiscono il controllo dei tempi.

## Split, metriche e decisione

Separare modalità offline, che ammette donor futuri, da modalità causale, che
ammette solo informazioni precedenti. Suddividere per blocchi temporali entro
ciascun gruppo compatibile e mascherare interi istogrammi o combinazioni di stati.
Nessuna copia del target nascosto entra in feature, template, scaling o tuning.
Per la previsione causale anche training e calibrazione degli intervalli devono
rispettare l'ordine temporale.

Tuning e calibrazione degli intervalli usano dati interni al training esterno;
il blocco di test resta escluso. Registrare fold, run, stati mascherati e donor.
Usare gli stessi target per confronti appaiati; riportare separatamente la
copertura dei metodi, senza selezionare soltanto i casi più facili per il ML.

Metriche: errore e bias per strip, distanza L1 della forma, residui, bias
relativo dell'integrale ove identificabile e copertura empirica degli intervalli.
Separare bordi di periodo, donor unico, assenze multiple e run anomali.
Campioni insufficienti non producono una dichiarazione di validazione.

Stimare incertezza mediante residui fuori campione e ricampionamento per blocchi
di donor/modello. Repliche con identità condivisa preservano correlazioni tra
strip e target che condividono donor o esposizioni. Salvare matrici per target
e repliche allineate per ricostruire la covarianza congiunta senza una matrice
densa obbligatoria sull'intera campagna.

Il report confronta metodi ma non assegna automaticamente validità fisica sulla
sola MSE. Eventuali soglie di adozione devono essere esplicite e registrate prima
della valutazione finale. In loro assenza l'esito resta esplorativo; un ML non
migliore non sostituisce la baseline. Predizioni per missing reali restano
marcate come candidati sperimentali, mai misure o flussi di produzione.

## Output e integrazione

Directory predefinita di campagna: `results/<campagna>/missing_flux/`.

```text
audit.json                 riepilogo, problemi, copertura e provenienza
inventory.csv              inventario per run/stato
strip_inventory.csv        diagnostica per strip
study.json                 prerequisiti, metodi, split, metriche ed esito
validation.csv             predizioni hold-out e metriche per target
study.root                 confronti, matrici e repliche d'incertezza
synthetic_flux.root         solo se esistono candidati per missing reali
plots/                     confronti assoluti/forme e diagnostica hold-out
```

Audit-only produce soltanto artefatti pertinenti. Studio non eseguibile produce
`study.json` con ragioni e protocollo; non crea file ROOT sintetici vuoti che
possano sembrare risultati. Artefatti ROOT di studio hanno namespace e schema
distinti dal calibrato produttivo, metadati measured/synthetic, metodo, donor,
seed, dominio e ragione. Nessun consumatore produttivo li carica automaticamente.

Launcher: `--flux-study off|audit|study`, default `off`; metadati opzionali
tramite `--flux-study-metadata`. Quando richiesto, nuovo stage comune dopo la
calibrazione e prima delle estrazioni UV/VIS. Il comando standalone rimane
disponibile anche se la calibrazione fallisce. Mancanza di prerequisiti
scientifici viene registrata come studio non eseguibile, non come crash né
successo scientifico. Errori tecnici di esecuzione fermano il launcher.

Registrare comandi, identità degli input e hash degli originali prima/dopo lo
studio. Vietare destinazioni coincidenti con gli input, anche tramite symlink.
Pubblicare output in modo atomico secondo i helper del repository e rifiutare
collisioni non autorizzate. Nessuna nuova cache o dipendenza obbligatoria;
importare dipendenze ML solo quando necessarie allo studio.

## Verifiche e criteri di completamento

- Fixture ROOT: stato assente, duplicati/cicli, alias, bin/assi invalidi,
  calibrazione assente con raw presente, BREM zero, integrale zero e contenuti
  negativi trasformati dal calibratore.
- Contratti: sidecar associato al calibrato corretto, copertura sconosciuta,
  manifest incompatibile, input mancanti, output protetti e hash immutati.
- Leakage: target mascherato escluso da fit/tuning/template, split a blocchi,
  confini di periodo e nessun donor futuro nella modalità causale.
- Metodi: esempi controllati con interpolazione nota, singolo donor, nessun
  donor, forme valide, assenze multiple e integrale non identificato.
- Incertezze: covarianza coerente con repliche condivise e coverage riportata
  su hold-out indipendente; test software non equivale a validazione fisica.
- Integrazione: installazione/mapping dei package, percorsi rinumerati, CLI,
  ordine del launcher e default senza studio; regressioni mirate di 06 e 08.
- Audit reale sui file locali disponibili, con conteggi e limiti documentati;
  nessuna ricostruzione massiva h80 o nuova inferenza di Σ necessaria per chiudere
  questo intervento.

Consegna: codice, test, guida operativa e relazione sui risultati ottenibili con
i dati disponibili. Mancanza di metadati scientifici non impedisce di consegnare
il sistema completo, ma impedisce di dichiarare una ricostruzione validata.
