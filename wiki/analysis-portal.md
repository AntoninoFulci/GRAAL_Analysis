# Portale dei risultati e GitHub Pages

Il portale statico raccoglie figure, report, configurazione e provenienza di campagne esplicite. Si rivolge alla consultazione scientifica: non esegue calcoli, non modifica risultati e non sostituisce i controlli descritti nello [stato scientifico](status). Il generatore usa la libreria standard Python; Poppler (`pdftoppm`) aggiunge anteprime della prima pagina dei PDF. Senza Poppler restano disponibili gli originali completi.

## Completamento e selezione

Entrambi i launcher scrivono `metadata/report_manifest.json` soltanto dopo l'esecuzione e la pubblicazione riuscite degli stage richiesti. Il manifesto registra modalità, data con fuso orario, revisione Git, presenza di modifiche locali e SHA-256 di figure e metadati. Certifica il completamento del software, non la validazione scientifica. Non comprende i grandi file ROOT o le cache. Un errore prima di questo confine non produce il manifesto; un errore in modalità diagnostica conserva il ripristino della campagna precedente.

L'esportazione verifica elenco e contenuto dei report: modifiche, rimozioni e nuove figure successive al completamento bloccano la pubblicazione. Nessuna ricerca del file più recente e nessun assemblaggio fra esecuzioni. Lo storico comprende soltanto le campagne nominate nel comando. La pagina iniziale sceglie la produzione completa più recente **fra quelle incluse**; una diagnostica più nuova non la sostituisce. Date mostrate in Europe/Rome. Campagne senza manifesto richiedono `--historical`: stato storico, data e modalità non attestate, mai promosse a ultima produzione completata. Gli originali storici restano invariati.

## Generazione locale

Dalla radice del checkout, con il package installato dall'ambiente del progetto:

```bash
export PYTHONDONTWRITEBYTECODE=1
report_build="$PWD/results_test/analysis-site-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$report_build/tmp" "$report_build/mpl"
export TMPDIR="$report_build/tmp"
export MPLCONFIGDIR="$report_build/mpl"
python scripts/build_analysis_site.py results/production \
  --output "$report_build/site" --zip
```

L'output deve essere una directory nuova; una build fallita non sostituisce un sito precedente. Per includere storico, passare altri percorsi di campagna prima delle opzioni. `--no-thumbnails` evita Poppler. `--repo-root` seleziona esplicitamente il checkout da cui leggere `wiki/`. Il comando installato equivalente è `graal-analysis-site`.

Aprire `site/index.html` oppure servire la directory con `python -m http.server --directory "$report_build/site"`. Il sito funziona anche senza server: indice incorporato, asset relativi, nessuna API. Filtri per testo, profilo e area, navigazione delle campagne e caricamento progressivo rendono consultabili anche molte figure. I PDF identici nello stesso profilo condividono la scheda, mantenendo percorsi originali e copie nel manifesto. Le aree sono raggruppamenti di navigazione dedotti dai nomi, non certificazioni dello stage produttore.

La documentazione corrente rimane in `wiki/`: il portale offre collegamenti ai sorgenti mantenuti e copie Markdown della pubblicazione. La revisione della documentazione è distinta dalla revisione dell'analisi. Configurazione e avvisi sono letti dai metadati; valori scientifici assenti non sono ricostruiti o inventati.

## Attivazione GitHub Pages

L'integratore porta su `main` il [workflow](https://github.com/AntoninoFulci/GRAAL_Analysis/blob/main/.github/workflows/analysis-pages.yml) e i sorgenti. Nelle impostazioni del repository, **Pages → Build and deployment → Source: GitHub Actions**. L'environment `github-pages` deve consentire `main` per l'avvio manuale e i tag `analysis-report-*` per gli eventi release. URL previsto dopo il primo deployment riuscito: `https://antoninofulci.github.io/GRAAL_Analysis/`.

L'archivio `graal-report.zip` contiene solo il portale esportato, figure e metadati selezionati. Nessun dato scientifico pesante viene aggiunto alla cronologia Git. Prima di pubblicare, l'integratore verifica il contenuto e l'audience del sito; accesso al repository e accesso a Pages sono impostazioni distinte.

Con GitHub CLI autenticata, creare una release in bozza, caricare il pacchetto e pubblicarla soltanto a caricamento riuscito:

```bash
report_tag="analysis-report-$(date +%Y%m%d-%H%M%S)"
printf '%s\n' 'Report statico della campagna esplicitamente selezionata; vedere manifesto e limiti nel portale.' > "$report_build/release-notes.txt"
gh release create "$report_tag" "$report_build/graal-report.zip" \
  --draft --target main --latest=false --title "$report_tag" \
  --notes-file "$report_build/release-notes.txt" &&
gh release edit "$report_tag" --draft=false --latest=false
```

La pubblicazione della release avvia `Analysis Pages`: scarica l'asset esatto, verifica percorsi, hash e integrità dei riferimenti, poi distribuisce il sito. Il limite conservativo del pacchetto estratto è 900 MB, sotto il limite Pages di 1 GB. Un pacchetto non valido blocca il deployment e lascia online la versione precedente. Per ripubblicare o ripristinare una release conservata, avviare manualmente il workflow indicando `release_tag`.

Per aggiornare a ogni analisi, concatenare sulla farm **pipeline riuscita → esportazione riuscita → pubblicazione release** con `&&`, usando directory di campagna e build nuove. Non cambiare campagne già avviate. Il launcher non esegue operazioni di rete: autenticazione e pubblicazione appartengono all'integratore. Un rilascio storico intenzionale può sostituire il portale corrente; verificare sempre il catalogo incluso prima della pubblicazione.

Conservare le release necessarie per riferimento e ripristino. Dopo verifica e pubblicazione, eliminare build locali, cache e anteprime riproducibili; mantenere solo evidenze necessarie con ragione esplicita, secondo [manutenzione](maintenance).
