# Asimmetrie per periodo — 13 ottobre 2026

## Esito

Piano 02 non era implementato. Grafo esistente interrogato con graphify
(`period asymmetry manifest flux exposure runs`), poi verificato sui sorgenti:
l'estrazione salvava solo `period=pooled`. Implementato il piano riusando il
motore Stage 07, senza secondo stimatore e senza riattivare il fit cinematico.

Checkout iniziale `f568c6b` con modifiche del piano 01 già presenti, conservate.
Creazione worktree bloccata dal sandbox sui metadati Git; lavoro nel workspace
corrente. Nessun commit, merge o push. Baseline scientifica e archivi precedenti
non sovrascritti. Nuova campagna: [results/periods-20261013](../../results/periods-20261013/).

## Metodo e contratti

- CLI `--by-period`, attivata dal launcher. Interfaccia standalone senza flag
  conserva percorso aggregato precedente.
- Universo inclusivo da `reconstruction_provenance.counts_by_run_state`;
  include run entrati nella ricostruzione ma con zero eventi finali. Manifest
  esplicito alternativo tramite `--run-universe-manifest`, verificato contro
  manifest canonico e contro cutflow quando presente.
- Join esclusivamente su numero run; etichette esatte `source_period`. Errori
  su run sconosciuto/duplicato, profilo incompatibile, classificazione CSV
  discordante, etichetta non sicura o riservata `pooled`. Nessuna fusione UV/VIS
  o protone/deuterio.
- Raw, BDT e sideband devono condividere universo inclusivo. Stessa maschera
  run su eventi ed esposizioni; strati con zero yield mantenuti. Flusso ROOT
  resta atomico per tripletta POL1/POL2/BREM, con esclusioni inventariate.
- Ogni periodo disponibile usa `_run_single`: stessi selettori, stimatori,
  binning, correzioni, covarianze provvisorie e diagnostici dell'aggregato.
  Fit non convergenti conservati come chiavi/diagnostica in metadati, esclusi
  dal vettore delle misure. Nessun periodo non stimabile trasformato in Σ=0.
- Directory pubblicata atomicamente dopo estrazione e chiusura. ROOT per
  periodo con schema ordinario, `extraction_metadata`, conteggi V/H/BREM,
  cutflow, esposizioni per strato, polarizzazioni, bin stimabili e mancanti.
  Periodi senza fit valido: albero punti vuoto, stato `not_estimable`, nessuna
  matrice fittizia. Periodi senza input: `not_available` nell'indice.
- Chiusura: ricostruzione indipendente dell'unione disgiunta, verifica eventi,
  esposizioni, bin e Σ prima della correzione fondo con tolleranza 1e-8. Non
  si media la Σ dei periodi. Nella campagna locale non è attiva correzione fondo.
- Stabilità: stesse chiavi bin, colori periodo stabili, barre condizionali/
  propagate. Differenze fra periodi disgiunti salvate senza pull o significatività.
  Risposte firmate alla scala di polarizzazione conservano nuisance globale
  comune: blocco incrociato ottenibile dal prodotto esterno delle risposte.
  Altre covarianze incrociate restano ignote; non si assume indipendenza.

## Artefatti e risultati locali

Input riusati dalla baseline senza 6C del 13 ottobre: quattro ricostruzioni
raw/BDT UV/VIS, flusso calibrato della stessa campagna e manifest canonico.
Nessuna ricostruzione, calibrazione o training ripetuti. Identità con dimensione,
SHA-256 e percorsi, sorgenti con hash/revisione, comandi, opzioni e versioni
Python/NumPy sono salvati in ciascun indice e nei metadati ROOT.

| Profilo / periodo | Run input | Run con esposizioni | Pairing selezionati | BDT selezionati | Punti Σ aggregati/per-periodo |
|---|---:|---:|---:|---:|---:|
| UV / 1998_uv | 178 | 170 | 14.443 | 11.674 | 382 |
| VIS / 1999_vis | 110 | 109 | 6.160 | 2.682 | 64 |

UV: pairing V/H/BREM = 7.381/7.062/2; BDT = 5.969/5.705/1.
VIS: pairing = 3.042/3.118/0; BDT = 1.335/1.347/0.
Esclusi per esposizione: UV pairing 719, BDT 586; VIS pairing 59, BDT 24.

Universo inclusivo recupera 3 eventi pairing UV e 13 VIS rispetto al vecchio
universo derivato dal BDT nominale. Le esposizioni aggiunte modificano anche
il ratio BDT, pur lasciando invariati gli eventi BDT e la likelihood BDT.
Massima |ΔΣ| rispetto alla precedente baseline, su chiavi comuni:

| Profilo / campione | Ratio | Likelihood |
|---|---:|---:|
| UV pairing | 0.0423422 | 0.0465453 |
| UV BDT | 0.000913239 | 0 |
| VIS pairing | 0.0110266 | 0.00874874 |
| VIS BDT | 0.000587297 | 0 |

Queste differenze descrivono il cambio di universo, non una significatività
statistica. Chiusura nuova unione/aggregato: stessi conteggi e bin, massimo
|ΔΣ| **0** per entrambi i profili. Un solo periodo disponibile per profilo:
risultato per-periodo e aggregato coincidono. Non è disponibile una misura
sperimentale della stabilità fra anni; il caso multiperiodo è provato con toy.

Prodotti: 4 ROOT e 30 PDF, più 2 indici, comandi, log e validazione:

- [Indice UV](../../results/periods-20261013/uv/beam_asymmetry/periods/index.json)
- [Indice VIS](../../results/periods-20261013/vis/beam_asymmetry/periods/index.json)
- [Validazione numerica e hash](../../results/periods-20261013/validation.json)
- [Comandi eseguiti](../../results/periods-20261013/commands.json)

## Prove e review

Baseline mirata: 74 passati. Regressioni osservate fallire prima delle correzioni:
join/partizione, inclusione run a zero yield, missing POL2, round-trip non
stimabile, metadati di binning vuoti, conflitto CSV/manifest, run sconosciuto,
sideband con universo diverso, etichetta riservata e fit non convergente.
Toy con Σ=0.40 e −0.25, yield disuguali: periodi distinti recuperati; aggregato
estratto dall'unione e diverso dalla media aritmetica. Confini energetici
inclusi secondo selettore esistente; BREM mantenuto separato.

142 test di integrazione mirati passati prima delle regressioni aggiuntive.
Suite completa: **821 passati in 119.51 s**. Primo passaggio completo aveva
819 passati e un fallimento preesistente nel contratto dei titoli wiki:
ripristinati quattro titoli attesi, preservando il testo del piano 01.

Review indipendente: corretti controllo universo inclusivo sideband e collisione
con nome `pooled`, con regressioni. Nessun altro finding importante nel perimetro.
Controllo visivo grafico stabilità UV; riapertura ROOT, chiavi covarianza,
identità per-periodo/aggregato e hash input/sorgenti verificati. Ultima verifica su estrazione per-periodo e diagnostica: **14 test passati in 33.92 s**.

File di implementazione: `beam_asymmetry.py`, nuovo `core/periods.py`,
`calibration/flux_v2.py`, `io/reconstructed_events.py`, `io/root_output.py`,
`io/root_input.py`, `plotting/diagnostics.py`, launcher e plotting campagna.
Nuovi test `test_period_extraction.py`, esteso contratto launcher; aggiornati
runbook, wiki, piano e indice. Modifiche preesistenti alle sistematiche preservate.

## Limiti

- UV senza esposizioni utilizzabili: 1382, 1388, 1409, 1416, 1425, 1442, 1474,
  1505; VIS: 2071. Cause individuali nell'indice; assenza di esposizione valida
  non equivale sempre a istogramma mancante. Nessun flusso ricostruito/inventato.
- Altri 7 periodi UV e 4 VIS del manifest non disponibili negli input locali.
- Sistematico molteplicità UV indisponibile per perdita di bin nella variante;
  indisponibilità esplicita ereditata dal motore. VIS mantiene componente.
- Covarianze pubblicate restano modello provvisorio del punto 01; inferenza
  finale sospesa. Nessun bootstrap attivato nella campagna locale, nessuna
  significatività fra periodi o rispetto ad aggregati sovrapposti dichiarata.
- Cutflow ricostruzione certifica universo dei suoi input, non completezza
  dell'intera presa dati sperimentale.
