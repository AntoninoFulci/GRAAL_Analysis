# 10 — taglio 2D su M(η) e M(π0)

> Stato 13 ottobre 2026: infrastruttura opzionale implementata; plot raw UV/VIS prodotti. Utente ha scelto **poligono** e fornito immagine di riferimento, che conferma gli assi ma non contiene un contorno disegnato. Vertici e convenzione sui bordi restano da fissare prima dello studio reale delle asimmetrie.

**Obiettivo:** confrontare asimmetrie prima/dopo selezione nella regione azzurrina dell'istogramma delle masse dei mesoni.

**Architettura:** selettore puro delle due masse, condiviso tra estrazione e visualizzazione, con parametri persistiti; riusare istogramma 2D esistente. **Stack:** NumPy, ROOT, pytest. **Spec:** [README](README.md), [baseline senza 6C](00-baseline-senza-fit-cinematico.md).

**Vincolo utente aggiunto:** taglio solo come opzione extra di verifica, disattivato per default. La nuova CLI `observable_extraction.compare_mass_selection` lascia invariati launcher e analisi nominale. Senza `--mass-polygon` la selezione è identità; con file esplicito applica lo stesso poligono a tutti gli eventi. Nessun contorno predefinito o ricavato automaticamente dalla palette.

## Già fatto e invarianti

`plots/dalitz.py` produce `masse_2d_*` su Mη 0.3–0.8 e Mπ0 0.05–0.25 GeV, 90×90 bin. Il colore azzurro è una densità rappresentata dalla palette: non costituisce contorno numerico. Non trasformarlo automaticamente in soglia su contenuto bin.

Usare masse raw ricostruite prima di ogni vincolo cinematico, nella nuova baseline mai selezionata dal 6C. Masse fitted sono vincolate ai poli e renderebbero il taglio sostanzialmente degenere. Il pairing χ² applica già una selezione ellittica sui pull: misurare quanto il nuovo taglio aggiunge o duplica. Non cambiare pairing quando si aggiunge la regione.

## Chiarimento bloccante

Ricevere figura/file o descrizione numerica, orientamento assi, contorno (poligono/ellisse/rettangolo) e inclusione bordi. Definire regione su MC/controllo separato o campione di sviluppo; congelarla prima del test delle asimmetrie. Nessuna scelta del contorno per massimizzare ΔΣ o accordo teorico.

## File candidati e dipendenze

`07_observable_extraction/io/reconstructed_events.py`, `beam_asymmetry.py`, `core/systematics.py`; nuovo `07_observable_extraction/core/mass_selection.py` solo se manca helper adatto. `plots/dalitz.py` e `plotting/diagnostics.py` disegnano lo stesso contorno, non una copia approssimata. Test nuovo `test_mass_selection.py`, test CLI e Dalitz. Richiede punto 1 per confronto appaiato; punto 4 fornisce plot ma non deve essere reimplementato.

## Passi e metodo

- [ ] Congelare geometria/versione e sovrapporla all'istogramma raw; verificare manualmente assi/unità. Riportare sovrapposizione col taglio χ² esistente.
- [ ] Maschera evento unica, validazione parametri e bordi; stesso taglio per V/H e tutti i periodi. Salvare flag/identità del subset o definizione riproducibile, senza cancellare eventi originali.
- [ ] Estrarre prima/dopo con stessi bin, stimatore, flussi e polarizzazioni. Taglio su masse non riduce esposizione del fascio: mantenere universo run valido comune, anche se dopo taglio alcuni run non hanno eventi.
- [ ] Misurare ritenzione segnale/fondo, distribuzioni E/φ e per polarizzazione/periodo, migration e fit falliti. Se modello di fondo applicato, rivalutarne frazioni per selezione nuova, non riusare ciecamente f.
- [ ] Stesse repliche per prima/dopo; `CΔ=Cprima+Cdopo−Ccross−Ccrossᵀ`. Tabella ΔΣ, errori, significatività dove identificabile e bin non stimabili. Incertezza dei parametri del contorno è sorgente sistematica separata, solo se giustificata.
- [ ] Test punti dentro/fuori/sul bordo, NaN, assi scambiati, regione vuota/totale. Regione totale deve riprodurre nominale e Δ=0; nessuna selezione su vettori fitted.

**Consegna:** ROOT/figure prima-dopo, contorno e cutflow, differenze correlate. Nessun contorno inventato ora; fino alla sua definizione è possibile solo preparare diagnostica.

## Implementazione opzionale e stato verificato

- `07_observable_extraction/core/mass_selection.py`: poligono semplice, anche concavo; valida assi/unità, vertici finiti e distinti, area, auto-intersezioni, bordi inclusi/esclusi. Masse non finite non passano un taglio attivo. La modalità disattivata conserva esattamente eventi e ordine.
- `07_observable_extraction/compare_mass_selection.py`: comandi `plot` e `compare`, entrambi senza taglio per default. Riusa istogramma 2D di `plots.dalitz`, estrattori ratio/likelihood e bootstrap appaiato; estensione dei comparatori esistenti con nomi campione opzionali, mantenendo default pairing/BDT.
- Output separati: `study.json`, `selection_and_replicas.npz`, `mass_selection.root`, `mass_selection.png`; `compare` aggiunge `comparison.root` e `comparison.pdf`. ROOT contiene vertici esatti del poligono e istogrammi prima/dopo. Maschera sugli indici originali, hash input/configurazione/codice e repliche conservati. Pubblicazione esclusiva: nessuna sostituzione di studi esistenti, anche con avvii concorrenti.
- Universo run ricavato dal cutflow inclusivo prima del taglio; esposizioni identiche prima/dopo. Cutflow per run/periodo/energia/stato, distribuzioni E/φ per V/H, griglia completa dei fit non stimabili, covarianza incrociata e di ΔΣ. Nessuna migrazione delle coordinate dei sopravvissuti: pairing e quadrivettori restano identici.
- Confronto **diagnostico senza correzione di fondo** in entrambi i campioni. Nessun riuso di frazioni nominali. `--signal-mc` e `--background-mc` permettono ritenzioni non pesate condizionate alla ricostruzione; senza input indipendenti risultano non disponibili. Interpretazione finale, modello di fondo, bias/copertura e sistematico del contorno restano aperti.

Sequenza operativa concordata: prima plot, poi fissare poligono, infine asimmetrie.

```bash
python3 -m observable_extraction.compare_mass_selection plot \
  --input results/baseline-no-fit-20261013/uv/reco/reco_eta_pi0_bdt.root \
  --profile uv --output-dir results/mass-selection-preview-uv

# Solo dopo aver fissato polygon.json sul campione di sviluppo/controllo:
python3 -m observable_extraction.compare_mass_selection compare \
  --input results/baseline-no-fit-20261013/uv/reco/reco_eta_pi0_bdt.root \
  --profile uv --mass-polygon polygon.json \
  --flux-file results/baseline-no-fit-20261013/common/flux_calibrated.root \
  --run-manifest config/run_manifest.csv \
  --output-dir results/mass-selection-study-uv --replicas 64
```

Il JSON richiede esattamente: `schema: 1`, `name` (identità/versione), `defined_on` (campione usato per definire regione), `axes: ["eta_mass", "pi0_mass"]`, `units: "GeV"`, `boundary: "include"` oppure `"exclude"`, `vertices` (almeno tre coppie ordinate `[Mη, Mπ0]`). Nessun file con vertici scientifici è stato inventato. Tolleranza numerica del bordo: 32 epsilon macchina × max(1, massimo valore assoluto dei vertici), in GeV.

Diagnostica reale salvata in `results/mass-selection-readiness-20261013/`: plot BDT UV/VIS e audit delle quattro ricostruzioni. Tutti i 36.350 eventi sono raw, finiti e già dentro χ² < 10 (risoluzione relativa 0.08); ripetere esattamente quel contorno non aggiunge selezione. Assi verificati: x Mη, y Mπ0, GeV; 90×90 bin su [0.3, 0.8] × [0.05, 0.25]. I conteggi differiscono dall'immagine storica perché campagna/input non sono certificati identici.

Test nuovi coprono selezione totale/disattivata con ΔΣ = 0, selezione vuota, run svuotati con flusso preservato, maschera raw e contorno ROOT, geometrie invalide e modifiche concorrenti di output/configurazione. Il piano scientifico resta **incompleto** finché contorno non viene fissato e confronto reale non viene eseguito; nessuna conclusione di miglioramento ricavata dalle sole densità.

Verifica finale: **74 test mirati passati** (selettore, confronto, filesystem, bootstrap, Dalitz e lettura raw). Review indipendente: corretti due problemi riprodotti da test, prenotazione esclusiva dell'output e ordine hash/lettura del poligono con controllo finale prima della pubblicazione. Suite completa sul checkout condiviso: **954 passati, 4 falliti**, tutti nel lavoro concorrente `tests/test_shared_bdt_comparison.py`, per `ModuleNotFoundError: No module named 'scripts.compare_shared_bdt'`:

- `test_comparison_balances_profiles_and_preserves_baseline_splits`
- `test_comparison_rejects_cross_profile_leakage`
- `test_weighted_metrics_and_equal_efficiency_threshold`
- `test_three_bundles_load_and_test_rows_never_enter_fit`

Questi file non sono stati modificati da questo intervento. Prima esecuzione completa: 946 passati e un errore nel test concorrente del canale carico (`AttributeError: no field named 'sum'`), non più presente nella seconda esecuzione. Nessuna dichiarazione di suite globale verde su checkout in modifica parallela.
