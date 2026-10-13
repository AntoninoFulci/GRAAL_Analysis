# 11 — indice e variabile delle tracce strane

> Aggiornamento 13 ottobre 2026: audit e persistenza implementati. Conferma utente:
> «Da confermare: completa audit e persistenza, taglio bloccato finché manca definizione».
> Taglio futuro solo opzionale, disattivato per default. Nessun criterio fisico inferito.
> Evidenze, test e limiti: [relazione](../../reports/2026-10-13-raw-tracks.md).

**Obiettivo:** identificare nome, significato, cardinalità e indice corretto prima di qualsiasi selezione.

**Architettura:** audit dal raw h70 alla preanalisi; eventuale persistenza nel proprietario dello schema Stage 01. **Stack:** ROOT/C++, Python per ispezione/test. **Spec:** [README](README.md), [schema realmente letto](00-stato-verificato.md).

## Evidenza già ottenuta

In `01_pre_analysis/PreAnalysis.h` e nel raw `test_data/raw/1998_uv/run1321.root` esistono:

- `Itipo_track[291]`, dimensione logica `Nass_3`: tipo della traccia centrale, usato con codici 11,13,14 nella preanalisi.
- `Nparf_strange`: campo scalare `UChar_t`, nome da candidato contatore; significato fisico da confermare.
- `Index_trf[90]`, dimensione `Nparf`, usato per lookup di `Iass_trf` con conversione indice Fortran→C++ quando non zero.

`h80` disponibile non conserva i campi sopra: aggiungerli downstream senza raw sarebbe impossibile.
Questa variabile ce la vogliamo portare indietro in modo tale da poi poter tagliere su tutte le tracce strane.
Portiamoci tutte questa variabili fino in fondo.

## Invarianti e blocco

Non identificare contatore con tipo per-traccia né indice detector con identità evento. Zero/valori sentinella e conversione 1-based richiedono contratto. Non applicare tagli su questi campi prima di definizione autorevole.
## File candidati

`01_pre_analysis/PreAnalysis.h`, `PreAnalysis.C`, eventuale dizionario in `wiki/01-pre-analysis.md`; se nuova persistenza necessaria, `tests/test_stage1_contracts.py`, `tests/test_event_selector.py`. Nessun modello BDT o schema di ricostruzione da modificare prima del responso. Se necessario nuovo test circoscritto del mapping degli indici, senza rifattorizzazione detector generale.

## Passi e verifiche

- [x] Inventariare schema/typename/count-leaf su run campione per ciascun periodo/versione disponibile, includendo `Iass_trf`, sentinelle e limiti degli array. Raw locale disponibile solo per UV 1998, run 1321; VIS verificato esclusivamente come schema legacy h80/h85.
- [x] Tracciare quali branch sono attivati, letti e scritti. Chiave evento `(RawSourceFile,RawSourceEntry,RunNumber)`; aggiungere nome array e posizione raw zero-based per la traccia. Ordinamento raw conservato, identità indipendente dall'ordine dopo Snapshot/BDT.
- [x] Domanda preparata per Giuseppe (non inviata): “Con tracce strane intendi campo contatore `Nparf_strange`, codici di `Itipo_track` o classificazione tramite `Index_trf/Iass_trf`? Quale nome nel raw h70, codici, indice, sentinelle e periodi? Esiste `N_TIPO_TRACK` in altro schema? Puoi indicare run/evento esempio?”
- [ ] Registrare risposta e dizionario con fonte/data. Se conferma variabile già presente e preservata, documentare e fermarsi. Se manca in h80, proporre rigenerazione mirata e persistenza raw del valore/indice senza cambiarne significato.
- [x] Su autorizzazione aggiornata dell'utente, persistenza grezza senza interpretazione: test bound/sentinelle, mapping storico 0/1-based, lunghezze e valori sconosciuti. Round-trip h70→h80→h85→reco, identità attraverso cambio file e buffering BDT; nessun nuovo taglio fisico implicito.

**Consegna:** dizionario verificato e percorso della variabile, eventuale persistenza testata. Limite attuale: nome corretto ancora non confermato. Dipendenza utile per canale carico, ma non blocca le analisi neutre indipendenti.
