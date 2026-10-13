# GRAAL — piani per esecuzione isolata

Data: 12 ottobre 2026. Revisione esaminata: `3afff75ead89be7e14ad6473ee1d0deff97e7094`.

**Aggiornamento al 13 ottobre 2026:** prerequisito **00 completato sulla baseline locale UV/VIS** e integrato in `main` (`cf2022f`); vedere [relazione](../../reports/2026-10-13-baseline-no-fit.md). Piani 01–13 restano in sola pianificazione, non avviati. Le evidenze del 12 ottobre sotto descrivono l’audit iniziale, precedente all’implementazione dello 00.

## Decisioni ricevute durante l'audit

- Il riferimento tradizionale è il **pairing χ² senza BDT**. Non serve inventare un altro fit.
- Nell'implementazione futura vanno disattivate tutte le attività legate al **fit cinematico 6C**. Restano necessari i fit azimutali che estraggono Σ: sono un oggetto diverso.
- I due bin aggiuntivi riguardano **energia**, non masse invarianti. Mancano bordi e significato operativo di “sotto soglia VIS” e “per tutti gli intervalli UV”.
- Il taglio 2D riguarda **M(η) contro M(π0)**, non gli assi Dalitz M(pη), M(pπ0). Il contorno azzurrino non è ancora definito numericamente.
- La definizione delle “tracce strane” non è disponibile. Verrà chiarita prima dell'implementazione; nessun messaggio a Giuseppe inviato.

## Documenti

Prima leggere [stato verificato e contratti](00-stato-verificato.md). Ogni piano dichiara riuso, file candidati, metodo, prove, dipendenze e decisioni mancanti.

| Passo | Piano | Stato |
|---|---|---|
| Prerequisito | [Baseline senza fit cinematico](00-baseline-senza-fit-cinematico.md) | Completato: default senza 6C, provenienza e nuova baseline locale verificati |
| 1 | [Errori e sistematici](01-errori-sistematici.md) | Matrici già presenti; correlazioni statistiche incomplete |
| 2 | [Asimmetrie per periodo](02-asimmetrie-per-periodo.md) | Manifest già classifica periodi; output Σ non li separa |
| 3 | [Flussi mancanti](03-flussi-mancanti.md) | Filtri/inventari riutilizzabili; ricostruzione sintetica non verificata |
| 4 | [Dalitz](04-dalitz.md) | Plot e ROOT già implementati; completare metadati/verifica |
| 5 | [Fondi BDT](05-fondi-bdt.md) | Nove canali registrati, inclusi decadimenti η a 6γ |
| 6 | [Confronto tradizionale](06-confronto-tradizionale.md) | Pairing condiviso già presente; nuova baseline senza 6C necessaria |
| 7 | [Variabili di allenamento in ROOT](07-variabili-allenamento-root.md) | 26 feature condivise; distribuzioni complete in ROOT non trovate |
| 8 | [Energia e binning](08-energia-binning.md) | Profili nominali rigidi; bordi nuovi da concordare |
| 9 | [BDT condiviso UV/VIS](09-bdt-condiviso.md) | Due modelli nel launcher; split attuale non è test indipendente |
| 10 | [Taglio 2D](10-taglio-2d.md) | Istogramma già esiste; contorno richiesto ancora mancante |
| 11 | [Tracce strane](11-tracce-strane.md) | Tre candidati verificati; significato non confermato |
| 12 | [Canale carico](12-canale-carico.md) | Topologia e feature attuali incompatibili direttamente |
| 13 | [Letteratura](13-letteratura.md) | Bibliografia locale presente; ricerca aggiuntiva da eseguire |

## Ordine e dipendenze

L'utente sceglie quale passo avviare. Ordine tecnico consigliato: baseline senza 6C → 1 → 2; 4 e 7 sono poi incrementi a basso accoppiamento. Il punto 13 può precedere gli studi fisici; 5 precede il confronto finale del punto 9. Il punto 8 fissa il dominio energetico comune per un eventuale confronto UV/VIS nella zona sovrapposta. I punti 6 e 10 consumano la baseline e la procedura di covarianza del punto 1. Il punto 3 resta studio futuro separato: diagnostica prima, dati sintetici solo dopo validazione. Il punto 11 precede qualsiasi selezione su tracce strane e aiuta la fattibilità del punto 12.

Nessun punto richiede di implementare tutti gli altri. Se una dipendenza non è pronta, eseguire solo la parte diagnostica e dichiarare il limite; non sostituire una covarianza ignota con indipendenza.

## Regole comuni di esecuzione

1. Rileggere codice, artefatti e questo stato: se il risultato esiste, verificarlo e riusarlo.
2. Prima delle modifiche, mostrare invarianti, dipendenze, file effettivi e decisioni fisiche del singolo passo. Confermare soltanto scelte ancora aperte.
3. Identificare input tramite percorso, dimensione, revisione e impronta riproducibile; registrare comando, versioni, seed, selezioni, campione, profilo, periodo e binning. Non assumere aggiornato un artefatto perché esiste.
4. Scrivere ogni variante in nuova directory `results/<campagna>/<studio>/`; preservare dati misurati e campagne precedenti. Riusare cache solo se i contratti corrispondono.
5. Per confronti su eventi condivisi usare differenze appaiate e covarianza incrociata. Non trattare raw/BDT, ratio/likelihood o proiezioni dello stesso evento come campioni indipendenti.
6. Contare esclusioni, bin non stimabili e input mancanti. “Non disponibile” non significa zero. Niente risultato inventato, interpolazione nascosta o selezione ottimizzata su Σ desiderata.
7. Concludere ogni passo con: file cambiati, metodo, prove eseguite, risultati numerici realmente ottenuti, limiti e decisioni rimaste.

## Chiarimenti rimasti, da risolvere al relativo passo

- Baseline 00: tagli confermati dall’utente il 13 ottobre 2026 e applicati: χ² < 10, risoluzione relativa 0.08, finestra missing mass ±0.06 GeV. Il punto 6 resta da avviare separatamente.
- Punto 1: identificare figura/ROOT dove gli errori mostrati includono sistematici; scegliere copertura e modello delle correlazioni, classificare incertezza del fondo.
- Punto 3: identificativi Vinci, disponibilità dei vicini, esposizione/tempo vivo e criterio di accettazione dei sintetici.
- Punto 8: bordi dei due bin energetici e significato di “sotto soglia”. La soglia fisica γp→pηπ0 è circa 0.931311 GeV: sotto essa non si interpreta un segnale on-shell come misura ordinaria di Σ.
- Punto 10: contorno numerico, inclusione dei bordi e campione su cui definire la regione.
- Punto 11: dizionario ufficiale e conferma di Giuseppe, senza inferire equivalenze fra nomi simili.
- Punto 12: ruolo del canale carico (controllo separato, fondo o nuova analisi), PID/carica/momenti e campioni disponibili.

## Audit iniziale del 12 ottobre 2026

Ricostruzione dei contratti principali, lettura di codice/documentazione, ispezione ROOT in sola lettura, inventario dei periodi e delle chiavi di flusso, 108 test mirati passati. Salvati tredici piani e prerequisito senza 6C. Risultati e limiti delle verifiche sono in [00-stato-verificato.md](00-stato-verificato.md). A quella data implementazione ed estrazione senza 6C restavano da avviare. Il prerequisito 00 è stato poi completato il 13 ottobre; training aggiuntivo, interpolazione ML, ricerca bibliografica e piani 01–13 restano non avviati.
