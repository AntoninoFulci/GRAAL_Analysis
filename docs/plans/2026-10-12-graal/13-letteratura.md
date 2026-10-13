# 13 — letteratura su γp → pηπ0

> Eseguito il 13 ottobre 2026 su richiesta utente: ricerca mirata e registro verificato. [Sintesi e limiti](../../research/2026-10-13-eta-pi0-literature.md). Non revisione sistematica esaustiva.

**Obiettivo:** estendere bibliografia con riferimenti verificabili e collegare metodi/risultati alle scelte dell'analisi.

**Architettura:** partire da inventario locale, deduplicare DOI/arXiv, verificare fonti primarie e salvare registro con pagina/equazione/figura e limiti. **Strumenti:** skill di ricerca pertinente, ricerca web/archivi editoriali; PDF solo quando realmente necessario. **Spec:** [README](README.md), fonti elencate nell'[audit](00-stato-verificato.md).

## Inventario iniziale del 12 ottobre: semi allora da verificare

| Fonte locale | Riferimento/link | Uso da controllare |
|---|---|---|
| `theory/README.md` | Ajaka et al., PRL 100, 052003 (2008), [DOI](https://doi.org/10.1103/PhysRevLett.100.052003) | Asimmetrie GRAAL, convenzioni e Figure 4; selezioni esatte da leggere |
| `theory/references/sources.json` | Döring, Oset, Strottman, PRC 73, 045209 (2006), [DOI](https://doi.org/10.1103/PhysRevC.73.045209) | Modello della reazione e strutture risonanti/Dalitz |
| stesso registro | Döring, Oset, Strottman, PLB 639, 59–67 (2006), [DOI](https://doi.org/10.1016/j.physletb.2006.06.022) | Aggiornamento del modello/sezioni d’urto; attribuzione iniziale alle osservabili di polarizzazione corretta dalla ricerca |
| stesso registro | Inoue, Oset, Vicente Vacas, PRC 65, 035204 (2002), [DOI](https://doi.org/10.1103/PhysRevC.65.035204) | Ingredienti teorici; non misura diretta del canale richiesto |
| `docs/research/2026-10-09-finite-phi-bin-correction.md` | Zachariou et al., PRC 91, 055202 (2015), [arXiv:1503.05435](https://arxiv.org/abs/1503.05435) | Metodo finite-φ-bin; distinguere metodo generale da reazione studiata |

Masse/BR hanno anche riferimento PDG 2024 nel registro; verificarne edizione e valori prima di aggiornare costanti. Ulteriori citazioni di fondi nei commenti `channels.py` sono piste, non validazione automatica della normalizzazione corrente.

## Invarianti

Separare produzione pηπ0 da pη, pπ0π0, pηπ0π0 e bersagli deuterio/neutrone. Distinguere Σ lineare da osservabili con polarizzazione circolare e dagli altri coefficienti a tre corpi. Nessun risultato letto da abstract attribuito a selezioni/equazioni non controllate. Curve digitalizzate restano dati derivati con incertezza di digitizzazione, non predizioni teoriche validate.

## File di lavoro

Riusare `theory/references/sources.json`, `theory/references/` e nota finite-bin come inventario. Creare `docs/research/<data>-eta-pi0-literature.md` e `.bib` o registro strutturato coerente. Non cambiare modello teorico né costanti nella ricerca; eventuali aggiornamenti saranno task separati motivati.

## Passi e metodo

- [x] Deduplicare fonti locali per DOI/arXiv e segnare quali sono già state lette/verificate, reperibili ma non controllate, o solo citate. Non riscaricare articoli già disponibili con provenienza affidabile.
- [x] Cercare sinonimi `gamma p eta pi0`, `pi0 eta photoproduction proton`, `linear beam asymmetry eta pi0`, `Dalitz eta pion photoproduction`; filoni GRAAL, CBELSA/TAPS, A2/MAMI, modelli isobarici/unitari. Risalire e seguire citazioni di Ajaka e lavori successivi; registrare data/query e criteri di inclusione.
- [x] Per ogni nuovo riferimento verificare titolo, autori, anno, DOI, arXiv e versione su editore/arXiv; distinguere errata e duplicati. Nessun DOI completato per supposizione.
- [x] Scheda evidenza: target, Eγ/W, decadimenti, statistica, selezioni, pairing, accettanza, estrazione Σ, normalizzazione flussi/P, trattamento fondo/errori, covarianze pubblicate, pagine/figure utili. Per dati non pubblicati esplicitare “non disponibile”.
- [x] Collegare risultati ai punti: soglia/binning (8), Dalitz e risonanze (4), pesi/fondi e BR (5), pairing (6), convenzioni/correlazioni (1). Il fit cinematico dei lavori può essere descritto, ma resta disattivato nella nostra fase per decisione utente.
- [x] Costruire tabella comparabilità: identica reazione ma energia/tagli diversi non implica confronto punto-punto. Segnalare necessità di rebinning/accettanza/conversione convenzioni prima dell'uso.
- [x] Verificare link e che ogni affermazione quantitativa abbia locatore primario. Riportare anche fonti escluse e motivi; nessuna meta-analisi di numeri incompatibili.

**Consegna del 13 ottobre:** [sintesi](../../research/2026-10-13-eta-pi0-literature.md), [schede sperimentali](../../research/2026-10-13-eta-pi0-experiments.md), [schede teoriche](../../research/2026-10-13-eta-pi0-theory.md), registro canonico `theory/references/sources.json` esteso a 20 lavori e inventario `theory/references/eta_pi0_literature_audit.json`. Query, locatori, versioni, esclusioni e comparabilità registrati; 12 PDF locali inventariati senza riscaricarli. Sette test del lettore/risorse passati; DOI/arXiv unici, link locali e impronte verificati.

**Limiti residui:** lettura limitata ai passaggi indicati; covarianze non disponibili nei materiali controllati; equivalenza manoscritto/versione finale non sempre certificata; testo e DOI primario dell’erratum Sarkar non verificati. Nessuna garanzia di esaustività o assenza di altri errata. Questi limiti impediscono aggiornamenti automatici di parametri e confronti punto-punto, non vengono convertiti in numeri inventati. Modelli, costanti e codice non modificati.
