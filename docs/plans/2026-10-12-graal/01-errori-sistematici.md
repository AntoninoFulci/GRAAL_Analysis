# 1 — errori, correlazioni e sistematici

## Esecuzione del 13 ottobre 2026

Verificato con graphify e lettura del codice: piano non già completato.
Su indicazione esplicita dell'utente, realizzate infrastruttura e diagnostica;
**inferenza finale sospesa**. Relazione, inventario, audit ROOT e prove:
[2026-10-13-systematics-infrastructure.md](../../research/2026-10-13-systematics-infrastructure.md).

- Completati tracciamento barre, disponibilità per sorgente, chiavi ROOT e
  validazione matrici, propagazione congiunta del fondo, bootstrap appaiato
  diagnostico, conservazione repliche fallite, etichette e prove software.
- 155 test Stage 07 passati; toy multi-seed/multi-repliche riproducibile.
- Restano aperti ensemble eventi/Poisson, decisioni fisiche, classificazione
  delle sorgenti, intervalli corretti di likelihood e inferenza di produzione.
  Le checkbox originarie sotto descrivono la chiusura fisica completa e non
  vengono marcate indiscriminatamente come concluse.


> Esecuzione futura isolata con `superpowers:executing-plans`; nessun cambio statistico approvato implicitamente dal piano.

**Obiettivo:** rendere espliciti significato delle barre e covarianza statistica/sistematica, comprese correlazioni bin-bin e tra confronti.

**Architettura:** estendere `core/systematics.py` e orchestrazione Stage 07; riusare writer ROOT e grafici. **Stack:** NumPy, SciPy, PyROOT, pytest. **Spec:** [vincoli comuni](README.md), [stato verificato](00-stato-verificato.md).

## Già fatto e limite

Matrici nominate e somma totale esistono; chiusura numerica verificata nei ROOT storici. Bootstrap per run esiste ma copre solo nominale ed è spento nel launcher. Figure 4 disegna rami stat, mentre correzione fondo opzionale può già includere in essi incertezze di f e del fondo. Catalogo dei sistematici non equivale a componenti tutte eseguite. Non riscrivere questa infrastruttura.

## Invarianti, dipendenze e decisioni

- Chiave ordinata univoca per punto: campagna/selezione/profilo/periodo/campione/stimatore/coppia/bin energia/bin massa. Ogni matrice deve salvare stessa mappa.
- Separare Poisson/fit condizionato, statistica correlata, nuisance sperimentali e variazioni di modello. Nessuna somma due volte della stessa sorgente.
- Correlazioni ignote restano ignote; zeri in matrice storica non sono misura di indipendenza.
- Usare baseline senza 6C per nuovi risultati. Togliere raw_vs_kinematic_fit dalle sorgenti operative; mantenere traccia di disattivazione.
- Prima di inferenza finale concordare: figura indicata dall'utente; natura di incertezza f; quali sorgenti sono globali o per periodo; trattamento dispersione run; precisione richiesta per bootstrap e politica sui bin non stimabili.

## File candidati

`07_observable_extraction/core/systematics.py`, `core/background.py`, `beam_asymmetry.py`, `io/root_output.py`, `io/root_input.py`, `plotting/figure4.py`, `plotting/diagnostics.py`, `scripts/run_pipeline.py`; test omonimi e `test_beam_asymmetry_cli.py`. Aggiornare `wiki/07-systematics-and-outputs.md` e relazione del passo sotto `docs/research/`.

## Passi e metodo

- [ ] Tracciare ogni barra dal ROOT alla figura. Tabella: formula, sorgenti, condizioni, unità, stat/syst, correlazione assunta, esclusioni. Leggere provenance per distinguere archivio e nuovo codice.
- [ ] Costruire inventario per ogni voce di `REQUIRED_SYSTEMATICS`: eseguita/non applicabile/non disponibile, input, variazione nominale±, unità della Δ, ragione di omissione. Una variazione nulla e una mancante devono essere distinguibili.
- [ ] Definire ensemble: per conteggi a esposizione fissata valutare bootstrap eventi/Poisson con identità comune fra proiezioni; per clustering run, ricampionare blocchi entro periodo/profilo accoppiando eventi ed esposizioni. Chiarire quale effetto misura ciascuno prima di combinarli. Includere run a zero eventi selezionati nell'universo appropriato; non confondere esposizione inesistente e zero conteggi.
- [ ] Applicare stesse repliche a tutti i campioni/stimatori confrontati; rieseguire fondo e relative frazioni quando fanno parte del risultato. Conservare covarianze incrociate e diagnostica repliche fallite. Non cancellare selettivamente repliche fino a ottenere risultato desiderato.
- [ ] Per fondo usare `Σs=(Σobs−fΣb)/(1−f)` con Jacobiano rispetto a `(Σobs,Σb,f)` e `Cout=J Cin Jᵀ`, inclusi termini incrociati e f condivisa tra bin. Non considerare automaticamente shift correzione-fondo una seconda misura indipendente dell'incertezza di f.
- [ ] Per nuisance sistematici propagare variazioni firmate coerenti. `ΔΔᵀ` è valido per un solo nuisance comune; indipendenza fra sorgenti deve essere motivata. Estimator/pairing/cut variations sugli stessi eventi contengono rumore statistico: misurarlo con differenze appaiate prima di trattarlo come sistematico.
- [ ] Pubblicare Cstat, Csyst per sorgente, Ctot, correlazioni e stati di disponibilità; barre statistiche e banda sistematica distinguibili. Se mostra totale, dichiararlo. Preservare intervalli asimmetrici di likelihood: diagonale simmetrizzata non li sostituisce.

Per differenze A−B usare `CΔ = CA + CB − CAB − CBA`. Per significatività globale, matrice PSD con rango dichiarato; niente inversa arbitraria di matrici singolari, niente χ² diagonale in presenza di correlazioni note.

## Verifica e criteri di chiusura

- [ ] Toy a Σ nota: copertura e bias, caso stessi eventi (Δ identica zero), campioni disgiunti, nuisance comune con segni opposti, run a zero yield, bin vuoto e perdita di bin in replica.
- [ ] Test matrice simmetrica/PSD entro tolleranza numerica, dimensione/chiavi e `Ctot=Cstat+ΣCsyst`; permutare ordine punti deve permutare coerentemente matrici.
- [ ] Controllare stabilità con repliche crescenti e più seed; registrare errore Monte Carlo sulla covarianza, numero effettivo di run e rango. Non scegliere un numero “di produzione” senza prova.
- [ ] Test writer/reader e grafico con errori volutamente diversi per stat/syst/totale: identificare quale viene disegnato.

```bash
python3 -m pytest -q 07_observable_extraction/tests/test_systematics.py \
  07_observable_extraction/tests/test_background.py \
  07_observable_extraction/tests/test_root_output.py \
  07_observable_extraction/tests/test_figure4.py \
  07_observable_extraction/tests/test_beam_asymmetry_cli.py
```

**Consegna:** report per sorgente, matrici ROOT con chiavi e figure etichettate. Risultato attuale: infrastruttura verificata, correlazioni fisiche non ancora quantificate. Un toy dimostra implementazione/coverage nel proprio modello, non assenza di bias detector.
