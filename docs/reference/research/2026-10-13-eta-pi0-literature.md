# Letteratura γp → pηπ⁰: evidenze e comparabilità

Data di verifica: **13 ottobre 2026**. Esecuzione del [piano 13](../../../results_test/repository-refactor-20261023/task-9/archive/docs/plans/2026-10-12-graal/13-letteratura.md). Ricerca mirata con fonti primarie e citation chaining, non revisione sistematica esaustiva né meta-analisi. Ricerca e sintesi assistite da AI; nessuna attestazione di lettura attribuita all’utente.

## Stato iniziale e prodotti

Il piano non era completato: esistevano il registro teorico, audit delle ampiezze, digitizzazioni, nota finite-bin e ricerca sui fondi, ma mancavano inventario unificato, nuovi riferimenti sperimentali e tabella di comparabilità. Riusate queste evidenze senza ricertificare automaticamente ogni loro affermazione.

- [Registro bibliografico canonico](../../../09_theory/references/sources.json): DOI/arXiv deduplicati, metadati e livello di verifica.
- [Inventario e audit strutturato](../../../09_theory/references/eta_pi0_literature_audit.json): file locali, dimensioni, SHA-256, query, esclusioni e provenienza.
- [Schede sperimentali](2026-10-13-eta-pi0-experiments.md): GRAAL, CBELSA/TAPS e A2/MAMI, con locatori e campi non disponibili.
- [Schede teoriche](2026-10-13-eta-pi0-theory.md): modelli unitari/isobarici, formalismo di polarizzazione, PDG ed errata.

Graphify usato prima dell’ispezione: grafo del 29 settembre, 2.480 nodi; query `ajaka photoproduction eta asymmetry dalitz theory`, BFS. Nodi utili: `Gamma-p to p-eta-pi0 Photoproduction` (`wiki/scientific-foundations.md`), `Ajaka et al. chiral-unitary curves` (vecchio percorso `07_observable_extraction/theory/README.md`), `plots/dalitz.py:L2`. Grafo orientativo, precedente alla baseline: verificati percorsi e documenti attuali; nessuna edge inventata e nessuna pretesa di grafo aggiornato. CLI 0.9.68 segnala skill 0.9.63: interrogazione riuscita, installazione non modificata.

## Metodo e perimetro

Inclusione principale: fotoproduzione esclusiva ηπ⁰ su protone libero, misure di sezioni d’urto/distribuzioni/Σ e modelli relativi. Inclusione metodologica separata: convenzioni di polarizzazione, media sui bin, ingredienti teorici e PDG. Fonti editoriali/arXiv per identità e versione; lettura diretta dei passaggi citati per metodi e numeri. Preprint e articolo con stesso DOI costituiscono un lavoro, non due osservazioni indipendenti. «Letto» significa passaggi indicati nella scheda, non certificazione integrale.

Ricerca il 13 ottobre tramite motore web; query e URL nel registro e nelle schede. Stringhe principali: `gamma p eta pi0 photoproduction`, `pi0 eta photoproduction proton`, `linear beam asymmetry eta pi0`, `Dalitz eta pion photoproduction`, più autori/DOI e filtri testuali 2024–2026. Catena: Ajaka 2008 → riferimenti teorici e Ajaka 1998; lavori successivi CBELSA/TAPS, formalismi 2010–2011 e A2 2018. Le query recenti restituiscono anche η singola, decadimenti e GlueX: esclusi dal confronto GRAAL quando dominio o osservabile differiscono. Nessuna conclusione «non esistono lavori più recenti».

Copie originali trovate anche in `tmp/pdfs`, directory ignorata da Git: controllo esteso con `rg --files --hidden --no-ignore tmp`. Impronte ricalcolate; quelle pubblicate nell’inventario delle ampiezze coincidono con l’audit precedente. Non riscaricate queste copie. I PDF sotto `test_data/beam_asymmetry` e `theory/outputs` sono prodotti dell’analisi, non originali editoriali. Il registro conserva identificatori persistenti perché i PDF ignorati non accompagnano un clone.

## Due riferimenti di metodo controllati separatamente

**Ajaka 1998**, *New Measurement of Σ Beam Asymmetry for η Meson Photoproduction on the Proton*, PRL **81**, 1797, [DOI](https://doi.org/10.1103/PhysRevLett.81.1797): identità verificata su APS; PDF locale, pp. 1798–1799, Eqs. (1)–(2). È produzione **pη**, richiamata da Ajaka 2008 Ref. [14]. Per polarizzazione verticale e φ rispetto al piano orizzontale, Eq. (1) ha segno `+PΣ cos(2φ)`; Eq. (2) usa rese normalizzate ai rispettivi flussi. Non prova che il fit del 2008 includesse la media entro bin: il passaggio non la specifica. Confrontare definizioni degli angoli, segno e normalizzazioni prima di riusare una formula. Statistica, selezioni ed errori del canale pη non vengono trasferiti a pηπ⁰.

**Zachariou 2015**, *Determination of the beam-spin asymmetry of deuteron photodisintegration in the energy region Eγ = 1.1–2.3 GeV*, PRC **91**, 055202, [DOI](https://doi.org/10.1103/PhysRevC.91.055202), [arXiv:1503.05435v1](https://arxiv.org/abs/1503.05435v1), 18 marzo 2015; pubblicazione 13 maggio. Riletti §V, pp. 10–11, Eqs. (15)–(17), e §VI, p. 12 del manoscritto. L’attenuazione è `sin(Δφ)/Δφ`; richiede ipotesi sull’accettanza entro bin e tra polarizzazioni. Reazione **γd→pn**: fonte del metodo, non dato del canale. Dettagli e derivazione già nella [nota finite-bin](2026-10-09-finite-phi-bin-correction.md), riusata. Nessuna correzione aggiuntiva applicata da questa ricerca.

## Comparabilità prima di sovrapporre punti

| Famiglia | Informazione utilizzabile | Condizione per confronto con GRAAL |
|---|---|---|
| Ajaka 2008, Fig. 4 | Σ lineare nelle tre proiezioni di coppia | Stessi intervalli, definizione di φ, media energetica e convenzione finite-bin; tagli/accettanza da verificare. Digitizzazione resta dato derivato. |
| CBELSA/TAPS, Gutz | σ, Σ e coefficienti a tre corpi | Non identificare automaticamente `Iᶜ` con Σ né ignorare `Iˢ`; verificare integrazioni e segni. La scala della σ 2014 usa normalizzazione esterna: confronto non completamente indipendente. |
| A2, Kashevarov/Sokhoyan | Sezioni d’urto e distribuzioni con dominio vicino alla soglia | Rebinning con pesi fisici, accettanza ed efficienza; yield GRAAL grezzo non è σ. Fit cinematico negli articoli non riproduce la nostra selezione senza 6C. |
| A2, asimmetria circolare | Sensibilità ad ampiezze/interferenze | `I⊙` non è Σ lineare: niente confronto numerico diretto. |
| Döring e modelli isobarici | Ipotesi dinamiche e dipendenza dagli osservabili | Integrare ampiezze polarizzate su dominio e selezioni pertinenti; contributo tree non sostituisce somma coerente completa. |
| PDG | Masse, BR, definizioni | Verificare edizione, aggiornamento del PDF e specifica catena di decadimento prima di cambiare costanti. |

I dettagli quantitativi di queste righe sono nelle schede con locatori primari. Non è stata eseguita combinazione statistica. Covarianze non trovate nei materiali controllati sono **non disponibili**, non matrici diagonali implicite. La mancanza di una covarianza pubblicata non rende indipendenti bin, proiezioni o campioni sovrapposti.

## Raccomandazioni collegate ai tredici punti

Indicazioni operative della presente sintesi, non risultati sperimentali aggiuntivi:

| Punto | Conseguenza per l’analisi |
|---|---|
| 1 — errori/sistematici | Separare scala di polarizzazione, fondo, flusso e statistica; documentare covarianze mancanti. Bloccare confronto finale se convenzioni di Σ non coincidono. |
| 2 — periodi | Verificare stabilità di segno, orientamento e P per periodo; una pubblicazione integrata non valida i nostri periodi separati. |
| 3 — flussi | Normalizzazione esterna di una pubblicazione non autorizza ricostruzione di run mancanti. Servono esposizione e calibrazione locali. |
| 4 — Dalitz | Usare canali ηΔ e πN* come ipotesi; distinguere struttura dinamica, fase-spazio e accettanza. Dalitz a W integrato richiede trattamento evento per evento. |
| 5 — fondi/BR | Riusare [audit fondi](2026-10-13-bdt-background-sources.md). Non convertire σ inclusiva in peso esclusivo senza BR e accettanza; controllare sovrapposizioni fra catene. |
| 6 — pairing tradizionale | Confrontare χ² e BDT sulla stessa baseline; non copiare CL di fit cinematici da altri esperimenti. Fit 6C resta disattivato per decisione utente. |
| 7 — variabili ROOT | Conservare distribuzioni e selezioni necessarie alla comparabilità; letteratura non sostituisce tracciabilità delle nostre feature. |
| 8 — energia/binning | Rispettare soglia e supporto cinematico. Una curva a energia centrale non equivale alla media del bin vicino al bordo; riferimento operativo: [studio energia](../../../results_test/repository-refactor-20261023/task-9/archive/docs/reports/2026-10-13-energy-binning.md). |
| 9 — BDT condiviso | Accettanza/purezza possono dipendere dall’energia e dalla dinamica; test UV/VIS separati. Nessun lavoro qui valida il nostro classificatore. |
| 10 — taglio 2D | M(γγ)η contro M(γγ)π⁰ non è un Dalitz di coppie adroniche. Nessun contorno numerico nuovo ricavato dalle figure. |
| 11 — tracce strane | Nessuna fonte consultata definisce i codici locali: resta necessario dizionario del rivelatore. |
| 12 — canale carico | Distinguere target, stato di carica, PID e FSI. Dati quasi-liberi/deuterio non calibrano direttamente il protone libero. |
| 13 — bibliografia | Usare chiavi/DOI canonici, versione letta e locatore; registrare errata senza applicarli tacitamente ai parametri. |

## Esclusioni e limiti

- [Käser et al., arXiv:1810.02778v1](https://arxiv.org/abs/1810.02778v1), DOI `10.1016/j.physletb.2018.10.006`: pagina primaria/abstract verificati; bersaglio butanolo deuterato polarizzato e sezioni d’urto di elicità su nucleoni quasi-liberi. Escluso dal confronto diretto di Σ su protone libero; dettagli di selezione non letti.
- [Ng, GlueX-doc-5987-v1](https://halldweb.jlab.org/doc-public/DocDB/ShowDocument?docid=5987): tesi, abstract/identità controllati. Documento 2023 con metadati aggiornati 2024, dominio Eγ=8.5 GeV; utile pista ad alta energia, fuori confronto GRAAL. Non trasformato in articolo peer-reviewed né datato 2024 per il solo aggiornamento della pagina.
- pη, pπ⁰π⁰ e pηπ⁰π⁰: esclusi come misure del segnale; ammessi solo con ruolo esplicito di metodo/fondo. `BDT.pdf` è materiale didattico, non evidenza fisica del canale. P70 e Butler sono ingredienti teorici di secondo livello, inventariati senza nuova validazione di tutti i loro contenuti.
- PLB 639 (2006) non va descritto come articolo specifico sulle osservabili di polarizzazione. La scheda teorica identifica il lavoro pertinente del 2010. Erratum Sarkar e data dei PDF PDG richiedono attenzione prima di aggiornamenti fisici.

Verifica bibliografica non equivale a riproduzione dei modelli: restano validi i limiti di [theory/README](../../../results_test/repository-refactor-20261023/task-9/archive/09_theory/README.md) e [full production validation](../../../09_theory/references/full_production_validation.md). La ricerca non aggiorna ampiezze, costanti, selezioni, risultati ROOT o inferenza finale. Non stabilisce completezza della letteratura al 2026, assenza di errata non trovati, o indipendenza dei dataset. Campi non letti/non pubblicati restano espliciti nelle schede.


## Controlli di consegna

Registro finale: **20 lavori distinti**, sei già in `sources.json`; aggiunte sia fonti nuove sia fonti locali prima disperse. DOI/arXiv duplicati assenti; campi originali dei sei semi preservati. Inventariati 12 PDF locali con dimensione e SHA-256. Controllati collegamenti locali e documenti di evidenza, versioni lette e separazione fra mancata lettura e mancata disponibilità. Le pagine primarie usate sono nei link delle schede; alcune aperture DOI/ScienceDirect falliscono e restano dichiarate, soprattutto per il testo dell’erratum Sarkar. Non si dichiara che ogni resolver sia accessibile.

Controllo indipendente dell’allegato teorico/registro: corretti due locatori, Eq. (47) PRC73 a p. 13 e Tab. III PRC65 a p. 15, ricontrollati con `pdftotext`. Ricerca errata dedicata sulle sette fonti sperimentali: nessun erratum pertinente trovato nelle query registrate, senza garanzia di assenza.

Compatibilità con il codice esistente verificata mediante:

```bash
PYTHONPATH=theory/src python3 -m pytest -q \
  theory/tests/test_sources.py theory/tests/test_packaged_references.py
```

**7 test passati.** Verifica strutturale aggiuntiva: campi preesistenti invariati, unicità DOI/arXiv, link locali e impronte PDF. `git diff --check` sui file interessati superato. Nessun test della fisica o confronto delle curve inferito da questi controlli documentali.
