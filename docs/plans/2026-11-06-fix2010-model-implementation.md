# Ricostruzione del modello di Fix 2010 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: usare `superpowers:executing-plans` per eseguire questo piano task per task. Le checkbox indicano risultati verificati.

**Goal:** ricostruire la soluzione I di Fix et al. (2010) per γp → ηπ⁰p, recuperando dalla Figura 6 il rapporto delle ampiezze della Δ(1700), e ottenere un calcolo verificabile della sezione d'urto e dell'asimmetria lineare Σ per **1,0 ≤ Eγ laboratorio ≤ 1,4 GeV**.

**Architecture:** nuovo modulo teorico autonomo (il 09), con ingressi scientifici versionati, cinematica a tre corpi, somma coerente delle ampiezze e integrazione degli osservabili. Recupero delle figure e ricerca bibliografica producono ingressi documentati prima di implementare la dinamica. Il collegamento ai dati dello stage 08 appartiene a una fase successiva.

**Tech Stack:** Python ≥3.10; libreria standard, NumPy, SciPy e Matplotlib già dichiarati in `pyproject.toml`; pytest per verifiche significative. Niente dipendenza obbligatoria da ROOT per il nucleo teorico. Consultare Context7 prima di usare documentazione o API specifiche di librerie, secondo `AGENTS.md`.

**Spec:** decisioni dell'utente del 6 novembre 2026 riportate sotto; [inventario scientifico](../../wiki/theory-fix-inputs.md), [confine della ripartenza](../../wiki/09-theory.md), [convenzione dei bin finiti](../../wiki/finite-bin-correction.md). Leggere piano e inventario prima di operare.

## Decisioni dell'utente e risultato richiesto

1. Autorizzato recuperare da Fig. 6 del lavoro 2010 il rapporto `ρ(Eγ) = A₃/₂/A₁/₂` della Δ(1700), soluzione I. L'errore di lettura deve restare riconoscibile.
2. Cercare e verificare formule, valori, normalizzazioni, fasi e dipendenze bibliografiche necessarie. Non sostituire numeri mancanti con valori arbitrari.
3. Intervallo attuale **[1,0; 1,4] GeV in laboratorio**. La precedente richiesta 0,93–1,50 GeV è superata per questa implementazione. Anche gli eventuali fit successivi saranno limitati al nuovo dominio.
4. Rinviati prodotti stage 08, binning sperimentale, flusso, accettanza, covarianze, sovrapposizione ai dati e fit dei dati del gruppo. Questo piano prepara il modello; non sceglie tali ingressi e non esegue fit sperimentali.

Il riferimento operativo è la **soluzione I del 2010**, proposta nella discussione e assunta qui come baseline da ricostruire. Il risultato dovrà chiamarsi **ricostruzione della soluzione I con rapporto di elicità ricavato dalla figura**; non codice originale degli autori né riproduzione numerica esatta del loro programma. Le curve di Σ saranno calcolate dalle ampiezze; un eventuale recupero grafico di curve pubblicate servirà esclusivamente da benchmark.

## Global Constraints

- Rispettare `AGENTS.md`: fonti e output storici protetti, nessuna riscrittura di risultati per soddisfare test, nessun riuso automatico di parametri o routine ritirati.
- L'archivio dello stage 09 ritirato il 26 ottobre resta inattivo. Il codice proposto sotto è una nuova implementazione; non ripristinare l'archivio e non collegare automaticamente la teoria al launcher sperimentale.
- Input curati in `data/theory/fix2010/`; note di derivazione in `docs/reference/theory/`; documentazione corrente in `wiki/`; piano attivo in `docs/plans/`.
- Tutti i diagnostici, render, confronti, log e build in `results_test/fix2010-rebuild/`. `results/` resta riservato a prodotti di produzione approvati.
- Impostare `PYTHONDONTWRITEBYTECODE=1`, `TMPDIR` e `MPLCONFIGDIR` assoluti; pytest con `--basetemp` e `cache_dir` nella campagna. Rimuovere temporanei al termine; conservare solo evidenze compatte con motivazione.
- Workspace già modificato da altri lavori. L'esecutore possiede soltanto i file teorici elencati e le modifiche strettamente necessarie al packaging/documentazione. Non è solo nel repository: non revertire modifiche altrui; rileggere i file condivisi prima di modificarli.
- Nessun invio agli autori o ad altri senza istruzione esplicita. Ricerca pubblica e lettura delle fonti sono autorizzate; non caricare dati privati su servizi esterni.
- Nessun commit, push o integrazione automatici: spettano all'integratore designato. Ogni task lascia un diff revisionabile.
- Non mescolare dati 2009, soluzione II/III del 2010, legge energetica 2018 o parametri Döring con la baseline I del 2010.
- Nuove lacune fisiche: completare le attività indipendenti, registrare fonte cercata e conseguenza, poi porre una sola domanda comprensibile all'utente. Non trasformare la lacuna in un default nascosto.

## Review Focus

1. **Curva o variabile sbagliata:** Fig. 6 contiene tre soluzioni; `ρ` non è `a = ρ²`, e l'ascissa è Eγ laboratorio. T1 deve identificare linea continua, assi e trasformazione; T2 verifica conversione Eγ↔W↔ωγ.
2. **Normalizzazione e soglie:** la massa nominale Δ(1700) può trovarsi sotto la soglia nominale η+Δ(1232), pur con stato finale a tre corpi accessibile. T2/T3 devono rispettare il trattamento della larghezza finita degli isobari; vietato chiudere il canale con una soglia a due corpi inventata.
3. **Interferenza o polarizzazione perse:** sommare intensità, usare soltanto moduli delle ampiezze o perdere le fasi fra elicità cambia Σ. T4/T5 verificano somma coerente e stati di polarizzazione.
4. **Bin vuoti, fuori dominio o errore nascosto:** nessuna extrapolazione/clamp energetico, nessun `Σ=0` per denominatore nullo, nessun clipping per nascondere violazioni. Test in T1/T3/T5/T7.
5. **Confronto circolare:** Fig. 6 è un ingresso; riprodurla non valida Σ. T6 richiede controlli analitici, convergenza e benchmark di osservabili distinti; i pesi energetici pubblicati non vanno inventati per far coincidere le curve.

## Fonti e stato iniziale

| Ruolo | Fonte locale | Passaggi iniziali |
| --- | --- | --- |
| Baseline | `docs/reference_papers/Fix_2010_1004.5240v1.pdf` | Sec. II, Eqs. (2)–(13), Tab. I–II; Fig. 6 p. 8; Figg. 8–10; Sec. III B |
| Sorgente della figura | `docs/reference_papers/Fix_2010_1004.5240v1_source.tar.gz` | `Text.tex`, `fig6.ps`; archivio con un TeX e undici figure |
| Formalismo precedente | `docs/reference_papers/Fix_2008_0803.1755v1.pdf` | Verificare i rinvii del 2010 per vertici, propagatori e normalizzazioni |
| Osservabili polarizzati | `docs/reference_papers/Fix_2011_1010.4213v2.pdf` | Cinematica, matrici di polarizzazione, Sec. V e appendici; controllare compatibilità con baseline 2010 |
| Antecedente da non importare automaticamente | `docs/reference_papers/Kashevarov_2009_0901.3888v5.pdf` | Eqs. (10)–(13): valori di `a`, modello con sola D₃₃ |
| Controllo successivo | `docs/reference_papers/Fix_2013_1307.2353v1.pdf` | Introduzione e rinvio al 2010; non fornisce una tabella completa di ρ(Eγ) |
| Versione diversa, esclusa dalla baseline | `docs/reference_papers/Sokhoyan_2018_1803.00727v2.pdf` e relativo `_source.tar.gz` | Eq. (4) e nuovo fondo Eq. (9); coefficienti del fondo non recuperati |

DOI principali: 2010 `10.1103/PhysRevC.82.035207`; 2008 `10.1140/epja/i2007-10551-x`; 2011 `10.1103/PhysRevC.83.015503`. I preprint sono disponibili; equivalenza integrale al testo editoriale ancora non verificata. Un tentativo pubblico APS ha restituito HTTP 401: non insistere su accessi autenticati indisponibili; documentare versioni effettivamente lette.

Hash dell'archivio 2010: `703501be0948d5a68ce189fd69968c26819aa3e13c9ea80f69fcd2b438674f11`; del membro `fig6.ps`: `10180ad940497afd6dc4886b48ad4865e17faa6ce4582efb3b57b98616eebf1f`. Verificare prima dell'estrazione. Altri hash e inventari sono nei log delle ricognizioni elencati nella wiki; includere un manifest degli input effettivamente usati nel nuovo prodotto, senza dipendere dall'esistenza futura di quei log diagnostici.

## Struttura prevista e proprietà dei file

La struttura segue il mapping già presente in `pyproject.toml`: directory numerata su disco, nome di package importabile distinto. `09_theory/` non esiste al momento della stesura. L'esecutore deve verificare di nuovo lo stato e accomodare eventuali nuovi file altrui.

| File da creare | Responsabilità |
| --- | --- |
| `scripts/extract_fix2010_helicity.py` | Recupero riproducibile dell'ingresso dalla figura; nessun calcolo di Σ |
| `data/theory/fix2010/helicity_ratio_fig6_solution_i.json` | Nodi recuperati, supporto energetico, errore di lettura e provenienza |
| `data/theory/fix2010/parameters_solution_i.json` | Ingressi numerici verificati del modello con fonte/unità per ogni gruppo |
| `data/theory/fix2010/source_manifest.json` | Versioni e hash di fonti, membri usati e ingressi curati |
| `docs/reference/theory/fix2010-derivation.md` | Registro di formule, convenzioni, derivazioni e lacune |
| `09_theory/__init__.py`, `09_theory/__main__.py` | Package nuovo `graal_theory`; avvio esplicito autonomo |
| `09_theory/helicity.py` | Lettura e interpolazione del rapporto ricavato dalla figura |
| `09_theory/parameters.py` | Ingressi immutabili, provenienza e validazione del contratto numerico |
| `09_theory/kinematics.py` | Quadrimpulsi, boost, masse invarianti e misura di fase |
| `09_theory/model.py` | Vertici, propagatori, spin e somma coerente dei contributi 2010 |
| `09_theory/observables.py` | Polarizzazioni, integrazione e proiezioni teoriche di σ e Σ |
| `09_theory/cli.py` | Comandi diagnostici espliciti e output con metadata |
| `09_theory/tests/` | Test scientifici/software legati ai task, senza copie dell'implementazione |

Modifiche condivise previste: `pyproject.toml` per mapping/installazione/test discovery; `wiki/theory-fix-inputs.md`, `wiki/09-theory.md`, `wiki/status.md` per risultati e limiti reali. Conservare tutte le modifiche preesistenti in questi file. Se `model.py` diventa troppo grande, separare i vertici nello stesso package mantenendo queste responsabilità; non introdurre una piattaforma generica per modelli futuri.

Le masse delle particelle stabili hanno già un proprietario: `graal_common.physics.channels` (`00_common/physics/channels.py`). Riusarle se compatibili con la ricostruzione scelta; registrarle nel manifest. Se la fonte richiede valori storici diversi, dichiarare un insieme esplicito del modello con fonte e confronto; non cambiare le costanti condivise né le masse delle risonanze per adeguarle al PDG odierno.

## Sequenza e criteri per proseguire

| Task | Dipende da | Risultato verificabile |
| --- | --- | --- |
| T0 | — | Inventario delle fonti e matrice degli ingredienti |
| T1 | T0 | Rapporto ρ ricavato dalla figura e lettore verificato |
| T2 | T0, T1 | Contratto numerico completo o elenco preciso di lacune bloccanti |
| T3 | T0, convenzioni cinematiche di T2 | Cinematica e spazio delle fasi verificati |
| T4 | T2, T3 | Ampiezze complete, contributi separabili e interferenze |
| T5 | T1–T4 | Sezioni d'urto polarizzate e Σ integrate |
| T6 | T5 | Convergenza e confronto con benchmark pubblicati |
| T7 | T6 | Comando autonomo, packaging e consegna documentata |

T1 è già autorizzato. T0/T2 devono cercare le dipendenze dalle pubblicazioni; possono avanzare senza attendere decisioni su dati sperimentali. T3 può procedere quando masse e convenzioni cinematiche sono verificate, anche mentre restano aperti ingredienti dinamici di T2; T4 richiede invece la chiusura di G0. Se T2 resta incompleto, consegnare i componenti verificati e la matrice delle lacune: non dichiarare completo il modello e non nascondere contributi mancanti.

## T0 — Inventario e matrice degli ingredienti

**Files:** creare registro di derivazione e manifest; aggiornare la scheda wiki. Leggere originali, non modificarli.

**Interfaces:** registro con colonne `ingrediente, simbolo, valore/formula, unità, fonte/versione, pagina/equazione, dipendenze, stato, conseguenza`; stato `verified|derived|missing|ambiguous`. `derived` richiede passaggi riproducibili. Il manifest contiene hash SHA-256 e versione di ogni fonte usata.

- [x] Registrare baseline, dominio e autorizzazione alla lettura grafica, distinguendo ingressi originali da ingressi ricostruiti.
- [x] Inventariare sei risonanze della Tab. II: D₃₃(1700), P₃₃(1600), P₃₁(1750), F₃₅(1905), P₃₃(1920), D₃₃(1940); scegliere la prima riga di ogni gruppo. Le etichette nominali non sostituiscono le masse adattate della tabella.
- [x] Inventariare anche Δ(1232), S₁₁(1535), due percorsi ηΔ/πN*, vertici elettromagnetici, termini Born, propagatori e larghezze dipendenti dall'energia. Individuare per ogni rinvio l'articolo richiesto.
- [ ] Verificare visivamente formule/tabelle, compresi segni, fattori di spin/isospin e potenze dei momenti. Controllare errata/versioni pubbliche pertinenti; registrare i controlli non riusciti.
- [x] Produrre elenco di lacune con effetto sul calcolo, senza presumere che il solo recupero di ρ completi il modello. Verificare hash, link e coerenza del registro.

**Accettazione:** ogni ingrediente ha fonte e stato; numeri non rintracciati restano esplicitamente assenti. Il primo elenco non deve simulare completezza.

## T1 — Recuperare ρ(Eγ) dalla Figura 6

**Files:** script di estrazione, JSON del rapporto, `09_theory/helicity.py`, `09_theory/tests/test_helicity.py`, `09_theory/tests/test_helicity_extraction.py`. Per eseguire i test introdurre soltanto il mapping minimo `graal_theory` in `pyproject.toml`, preservando il resto.

**Interfaces:** `extract_ratio(archive_path: Path, output_path: Path, diagnostic_dir: Path) -> None`; `load_ratio(path: Path) -> HelicityRatio`; `HelicityRatio.evaluate(egamma_gev: float) -> float`. Il JSON conserva `energy_lab_gev`, `rho`, descrizione dell'errore di lettura, trasformazione degli assi, hash di archivio/membro, selezione della curva e identificativo della soluzione.

- [x] Scrivere test che falliscono per hash errato, ascisse duplicate/non ordinate, NaN e richieste fuori dal supporto; testare `evaluate(0.99)` e `evaluate(1.41)` come errori. Fixture sintetica con curva nota e assi traslati/scalati: verificare il recupero delle coordinate fisiche, non soltanto il round trip dello stesso codice.
- [x] Leggere in sicurezza il solo membro atteso dell'archivio e verificarne l'hash. Non fare estrazioni indiscriminate né eseguire codice contenuto negli originali.
- [x] Recuperare il tracciato vettoriale di `fig6.ps` con un lettore limitato agli operatori necessari; rifiutare strutture non supportate invece di interpretarle silenziosamente. Usare il PDF/render come riscontro visivo. Separare assi, lettere, barre d'errore, linea continua I, tratteggiata II e puntinata III; conservare gli identificativi dei tratti selezionati.
- [x] Calibrare assi lineari usando almeno due riferimenti per asse e un riferimento aggiuntivo per controllare la trasformazione. Ascissa Eγ laboratorio [GeV], ordinata `ρ`, non `ρ²`.
- [x] Conservare i vertici significativi e interpolare linearmente a tratti. Non adattare un polinomio scelto per ottenere un migliore accordo con Σ; non riscalare tutta la curva sul valore della Tab. II.
- [x] Quantificare l'errore di lettura da coordinate, spessore e calibrazione degli assi; trattare spostamento/scala degli assi come errori correlati. Una densità elevata di vertici non crea misure indipendenti. Obiettivo diagnostico: errore verticale ricostruibile ≤0,01 in ρ; se non raggiunto, riportare il valore ottenuto e l'effetto richiesto sui benchmark, senza abbassare a posteriori l'errore dichiarato.
- [x] Verificare gli estremi: supporto effettivo della curva deve coprire il dominio usato. Se un estremo cade entro la precisione della lettura sul bordo 1,0/1,4, registrare la riconciliazione e l'intervallo d'errore; se manca davvero un tratto, segnalarlo. Nessun prolungamento costante o lineare implicito.
- [x] Generare un overlay leggibile figura/tracciato recuperato e controllarlo visivamente in più punti, inclusi incroci delle curve. Eseguire i test e salvare JSON+manifest. Render e overlay sono diagnostici in `results_test/`, non nuovi originali.

**Accettazione:** rapporto ricostruibile dal file sorgente corretto, linea I identificata, errore dichiarato e test di dominio passati. Questo valida l'estrazione dell'ingresso; non ancora la dinamica.

## T2 — Chiudere e congelare il contratto numerico

**Files:** `parameters_solution_i.json`, `parameters.py`, `tests/test_parameters.py`, registro di derivazione.

**Interfaces:** `load_parameters(path: Path) -> ModelParameters`; record immutabile con versione modello, dominio laboratorio, masse, risonanze, prescrizioni dei vertici/propagatori e riferimenti. Non creare campi numerici fittizi per elementi sconosciuti. Il loader rifiuta baseline/soluzione diverse, unità mancanti, valori non finiti e ingressi richiesti assenti.

- [x] Scrivere test negativi per parametri essenziali mancanti, soluzione II mescolata alla I, MeV letti come GeV e massa nominale usata al posto di quella adattata. Per J=1/2 l'elicità 3/2 è vietata fisicamente: rappresentare questa proprietà, non una cella di tabella mancante trasformata genericamente in zero.
- [ ] Trascrivere e verificare tutti i parametri della soluzione I e i valori dei due isobari. Conservare anche errori riportati e unità originali; convertirli in **GeV** nel nucleo. Angoli in radianti. Gli errori marginali pubblicati non costituiscono una matrice di covarianza.
- [ ] Derivare dalla fonte i legami fra prodotti `sqrt(β) A`, rapporto `r` dei due decadimenti, accoppiamenti e normalizzazioni. Non scegliere separatamente fattori che la fonte determina solo attraverso il loro prodotto. `r` in tabella è definito alla massa della risonanza, non automaticamente a ogni W.
- [ ] Verificare Γ(W), propagatori degli isobari e risonanze, trattamento delle soglie e integrazione sulle masse degli isobari instabili. Un'isobara di massa variabile non va sostituita automaticamente da una particella stabile.
- [ ] Congelare la prescrizione elettromagnetica 2010: A₁/₂ della D₃₃(1700) segue Eq. (5), A₃/₂ deriva da ρ(Eγ) ricostruito. Per le altre risonanze verificare gli esponenti della stessa fonte. Convertire Eγ laboratorio in W e in ωγ del centro di massa prima di usare Eq. (5).
- [ ] Fissare convenzioni di spin, fasi relative, coordinate, coefficienti angolari e normalizzazione assoluta della sezione d'urto, compreso il fattore di conversione delle unità. Controllare le ampiezze Born: la loro piccolezza non autorizza l'omissione nel modello completo.
- [ ] Chiudere ogni elemento essenziale nel registro. Per ambiguità che richiedano una modifica del modello, fermare il relativo task e spiegare all'utente una sola scelta alla volta. Routine di sola cinematica e verifica delle fonti possono continuare indipendentemente.
- [ ] Eseguire i test del loader e revisionare il contratto con le fonti aperte. Etichettare eventuali risultati intermedi con i contributi realmente presenti.

**Accettazione G0:** ingresso dinamico completo e tracciato; unico recupero grafico già autorizzato è ρ. La distinzione fra calcolo completo e sola parte risonante resta esplicita. Un rapporto che varia nell'energia non viene ridotto al singolo valore alla massa della risonanza.

## T3 — Cinematica a tre corpi

**Files:** `kinematics.py`, `tests/test_kinematics.py`.

**Interfaces:** `make_point(egamma_gev, m_pi_p_gev, cos_theta_eta, cos_theta_pi_star, phi_pi_star_rad, *, masses) -> PhaseSpacePoint`; il record conserva quadrimpulsi CM, invarianti e coordinate originarie. `phase_space_density(point) -> float` restituisce la misura nelle variabili scelte, con unità esplicite. Energia e masse in GeV.

- [x] Scrivere controlli analitici a Eγ=1,2 GeV: `W² = mp² + 2 mp Eγ`; per ogni particella `p² = m²`; somma finale `(W,0,0,0)`; identità della somma dei tre invarianti a due corpi. Tolleranza iniziale in doppia precisione: `atol=1e-10` nelle unità delle quantità confrontate.
- [x] Implementare boost e ricostruzione seguendo i sistemi definiti dalle fonti. Testare andata/ritorno del boost, direzioni collineari e orientazioni casuali riproducibili.
- [x] Rifiutare coseni non fisici, masse fuori dal Dalitz plot, energie fuori [1,0;1,4] e non finiti. Eventuali arrotondamenti di bordo devono avere una tolleranza numerica esplicita; non correggere punti realmente non fisici.
- [x] Derivare e implementare Jacobiano/limiti dello spazio delle fasi. Confrontare l'integrale di un'ampiezza costante con un calcolo indipendente della fase a tre corpi tramite fattorizzazione in due fasi a due corpi, usando la stessa convenzione di 2π dichiarata in T2.
- [x] Controllare soglie fisiche e limiti al bordo senza inventare una soglia η+Δ stabile. Eseguire i test e registrare unità e precisione ottenuta.

**Accettazione G1:** conservazione dei quadrimpulsi, invarianti e misura d'integrazione concordano con controlli indipendenti.

## T4 — Ampiezze e interferenze

**Files:** `model.py`, `tests/test_amplitudes.py`; estendere il registro di derivazione.

**Interfaces:** `Fix2010Model(parameters: ModelParameters, helicity: HelicityRatio)`; `model.amplitudes(point: PhaseSpacePoint, *, sector="full") -> complex ndarray` con assi **[spin finale mf, elicità fotone μ, spin iniziale mi]**, ciascuno di dimensione 2. Ordine e fasi dei valori ± devono essere documentati. I settori diagnostici permettono `full`, `resonances`, `born` e contributi identificati, senza presentarli come modelli completi.

- [ ] Scrivere test dei coefficienti angolari contro identità/valori tabulati indipendenti: normalizzazione e ortogonalità, selezione degli spin, coefficienti vietati nulli. Testare la mappa fra λ delle formule e coppia (μ,mi), includendo elicità negative secondo la convenzione della fonte.
- [ ] Implementare un percorso e una risonanza alla volta, con traccia verso equazione e parametri. Verificare dipendenza dai momenti, fattori di isospin, propagatori e fasi. Le matrici devono conservare informazione complessa fino al calcolo dell'intensità.
- [ ] Implementare entrambi i percorsi ηΔ e πN* e le sei risonanze della soluzione I. Confrontare contributi separati, somme parziali e somma coerente.
- [ ] Implementare i termini Born documentati e verificarne normalizzazione relativa al settore risonante. Se mancano ingredienti essenziali, dichiarare lo stato incompleto; non promuovere una variante `resonances` al risultato finale.
- [ ] Testare interferenza con ampiezze sintetiche note: contributi uguali si rafforzano; opposti si cancellano; una fase globale comune lascia le intensità invariate. Aggiungere test fisici delle identità di parità/rotazione effettivamente applicabili nella convenzione adottata.
- [ ] Verificare contributi spenti senza divisioni 0/0, propagatori finiti sul dominio fisico e assenza di dipendenze casuali dallo stato globale. Eseguire test di T2–T4.

**Accettazione G2:** tutte le ampiezze richieste sono presenti, documentate e verificabili separatamente; nessuna somma prematura delle probabilità.

## T5 — Polarizzazione, integrazione e Σ

**Files:** `observables.py`, `tests/test_observables.py`, `tests/test_integration.py`.

**Interfaces:** `polarized_intensity(amplitudes, polarization_angle_rad: float) -> float`; `project(model, egamma_gev: float, mass_edges_gev, *, pair: str, quadrature) -> Projection`. `pair` è uno di `pi_p`, `eta_p`, `pi_eta`. `Projection` conserva bordi, integrali `sigma_perp_ub`, `sigma_parallel_ub`, numeratore, denominatore, Σ e indicatore di supporto; una densità per unità di massa deve essere identificata separatamente dagli integrali nei bin.

- [ ] Derivare lo stato di polarizzazione lineare nella base μ=±1 con le fasi del formalismo scelto. Mediare spin iniziale e sommare spin finale con i fattori corretti. Verificare che la media delle due polarizzazioni ortogonali dia la sezione non polarizzata.
- [ ] Definire il piano di reazione per ciascuna coppia e la trasformazione delle coordinate CM; verificare il collegamento fra momento della coppia e particella spettatrice. Ricostruire il segno di Σ dalla definizione pubblicata, senza aggiustarlo per ottenere accordo grafico.
- [ ] Per il proiettato pertinente usare `Σ = (σ_perp − σ_parallel)/(σ_perp + σ_parallel)`, dopo aver integrato le variabili non osservate. Nel caso completamente differenziale a tre corpi può comparire anche un termine in sin(2φ): non imporne l'assenza prima delle integrazioni/simmetrie che lo eliminano.
- [ ] Scrivere test sintetici con intensità indipendente dalla polarizzazione (Σ=0), un solo stato lineare non nullo (limiti ±1), rotazione comune di evento e polarizzazione, e denominatore nullo. Quest'ultimo produce un risultato non definito con indicatore, mai uno zero fisico.
- [ ] Implementare integrazione deterministica delle variabili rimanenti e gestione di bordi/supporto delle masse. Integrare numeratore e denominatore separatamente. Test sintetico con due regioni di pesi diversi: il rapporto degli integrali deve differire dalla media aritmetica delle due Σ note.
- [ ] Confrontare ordini di quadratura crescenti su pochi punti, poi usare una parametrizzazione alternativa della fase come controllo indipendente. Controllare positività e `|Σ|≤1` entro la precisione numerica, senza clipping dei risultati.
- [ ] Propagare almeno scenari correlati dell'errore di lettura di ρ attraverso il calcolo. Chiamarli **sensibilità all'ingresso ricostruito**, non banda completa d'incertezza teorica o intervallo di confidenza. Non assumere indipendenza fra ogni vertice della figura.

**Accettazione G3:** σ polarizzate e Σ rispettano definizione, supporto e convergenza. Il nucleo non applica correzioni dei bin φ sperimentali.

## T6 — Benchmark distinti dall'ingresso e convergenza

**Files:** test di integrazione; `docs/reference/theory/fix2010-benchmarks.md`; report compatti in `results_test/fix2010-rebuild/`.

**Interfaces:** matrice dei benchmark con `fonte/versione, quantità, energia o bin, contributi inclusi, unità, integrazione/pesi, precisione di lettura, tolleranza numerica, esito, limiti`. Esiti `pass|fail|inconclusive`; non chiamare `pass` un confronto con ricetta non specificata.

- [ ] Prima di confrontare i grafici fissare obiettivi numerici diagnostici: variazione di Σ ≤0,005 fra due raffinamenti successivi; sezioni d'urto entro `max(0,005 × |σ|, 1e-6 μb)` per gli integrali considerati. Sono obiettivi di convergenza del software, non accuratezza fisica del modello. Se non raggiunti, riportare l'esito; non ampliare le soglie per accettare il risultato.
- [ ] Applicare controlli a energia fissa, iniziando da Eγ=1,2 GeV e da una piccola griglia nel dominio. Per energie agli estremi verificare prima il supporto del rapporto ricostruito. Evitare campagne estese finché i controlli locali falliscono.
- [ ] Riprodurre un limite analitico del settore D₃₃ riportato nelle fonti, rispettandone tutte le ipotesi. Un limite con un contributo spento è un test diagnostico, non la baseline completa.
- [ ] Confrontare sezione totale/contributi di Fig. 8 e, ove specificate, distribuzioni angolari della soluzione I. Il recupero grafico di un benchmark deve essere tracciato e separato dal JSON di ρ; nessun tuning sul benchmark per nascondere incongruenze.
- [ ] Confrontare Σ con Fig. 9 nei tre intervalli pubblicati 1,1–1,2, 1,2–1,3 e 1,3–1,4 GeV, per le proiezioni effettivamente mostrate. Verificare prima la ricetta della media energetica: se i pesi non sono rintracciabili, mantenere un confronto illustrativo con pesi dichiarati e stato `inconclusive` per la riproduzione esatta della curva mediata. Non confondere il centro del bin con una media.
- [ ] Stabilire le tolleranze del confronto pubblicato usando la precisione di recupero del benchmark e l'errore numerico stimato; congelarle prima della valutazione. Non usare gli errori statistici dei dati come tolleranza della riproduzione del calcolo teorico.
- [ ] Documentare differenze residue e loro sensibilità a ρ, quadratura e contributi separati. L'accordo con dati usati dagli autori per scegliere/adattare la soluzione non costituisce validazione fisica indipendente.

**Accettazione G4:** risultati verificabili con esiti separati per implementazione, convergenza e riproduzione dei grafici. Una corrispondenza qualitativa non autorizza la dicitura «modello validato».

## T7 — Comando autonomo e consegna

**Files:** `cli.py`, `__main__.py`, mapping `pyproject.toml`, `tests/test_cli.py`; wiki corrente e stato.

**Interfaces:** `python -m graal_theory inspect --parameters PATH --helicity PATH`; `python -m graal_theory predict --parameters PATH --helicity PATH --energy-gev E --pair PAIR --mass-edges PATH --output PATH`. Il file dei bordi è un JSON di sole masse in GeV per proiezioni diagnostiche, non un contratto di binning sperimentale. Ogni output identifica versione, ingressi/hash, contributi, convenzioni, unità, metodo d'integrazione e precisione.

- [ ] Scrivere test per ispezione degli ingressi, rifiuto di energia fuori range, file mancanti, output esistente e input incompleto. Nessun overwrite implicito di risultati; nessuna lettura automatica dei dati sperimentali.
- [ ] Collegare il nuovo package al mapping di setuptools e alla discovery dei test secondo lo schema esistente, senza modificare il launcher degli stage sperimentali. Usare path degli input espliciti: un'installazione non deve dipendere per caso dalla directory corrente.
- [ ] Eseguire installazione/build in ambiente isolato secondo le regole del repository; verificare import e CLI da una directory esterna al checkout. Rimuovere build/ambiente temporanei dopo la verifica.
- [ ] Eseguire test focalizzati e controlli d'integrazione del packaging toccato. Riportare separatamente eventuali fallimenti preesistenti o di attività altrui; non cambiare output scientifici per farli passare.
- [ ] Aggiornare `wiki/09-theory.md`, scheda degli ingressi e riga teoria di `wiki/status.md` con funzionalità realmente disponibili, esiti dei benchmark e limiti. Non lasciare dichiarazioni «implementazione assente» dopo una nuova implementazione effettivamente consegnata, né descrivere come attivo il vecchio archivio.
- [ ] Consegnare una nota semplice all'utente: cosa è stato ricostruito, quali approssimazioni sono autorizzate/usate, quali controlli sono passati, quali lacune restano. Conservare prove essenziali e rimuovere temporanei dopo aver verificato che nessun processo li usi.

**Accettazione finale:** il modello è eseguibile autonomamente, gli ingressi hanno provenienza, i controlli hanno esiti espliciti e nessun confronto ai dati del gruppo è stato presunto. Se G0/G2 sono incompleti, consegnare il componente effettivo e lo stato delle lacune, senza dichiarare raggiunto questo traguardo.

## Verifiche operative minime

Esempio di ambiente per le verifiche, da eseguire dalla root e con l'interprete appropriato all'ambiente del repository:

```bash
mkdir -p results_test/fix2010-rebuild/tmp results_test/fix2010-rebuild/mplconfig
export PYTHONDONTWRITEBYTECODE=1
export TMPDIR="$PWD/results_test/fix2010-rebuild/tmp"
export MPLCONFIGDIR="$PWD/results_test/fix2010-rebuild/mplconfig"
python -m pytest 09_theory/tests --basetemp="$PWD/results_test/fix2010-rebuild/pytest-tmp" -o cache_dir="$PWD/results_test/fix2010-rebuild/pytest-cache"
git diff --check
```

Il package deve essere installato tramite il mapping prima di usare `python -m graal_theory`. Non correggere gli import aggiungendo percorsi privati o `sys.path` dipendenti dalla macchina. Comandi dei benchmark e installazione riproducibile vanno documentati dopo averli eseguiti realmente.

## Fase successiva rinviata: dati e fit

Il vincolo futuro è **[1,0;1,4] GeV laboratorio**. Un bin di energia che attraversa uno dei due bordi non si include automaticamente perché il centro cade dentro: bisognerà selezionare dati/integrazioni coerenti, oppure escludere quel bin. La scelta dipenderà dai prodotti sperimentali, ancora rinviati.

Prima di un fit occorreranno: prodotti stage 08 e loro provenienza, binnings, definizione degli angoli, medie/pesi energetici, eventuale accettanza, covariance e convenzioni dell'estimatore. Scegliere anche quali parametri eventualmente adattare e quali mantenere fissati; questo piano non autorizza un fit indiscriminato di tutti i parametri. La correzione dei bin φ già applicata all'estimatore sperimentale non deve essere riapplicata alla Σ fisica teorica.

Queste informazioni non servono per chiedere di nuovo il permesso di estrarre Fig. 6 o leggere articoli: entrambe le attività sono già autorizzate. Serviranno quando si passerà effettivamente al confronto con i dati.

## Stato alla consegna del piano (storico)

- [x] Decisioni dell'utente registrate; dominio ristretto a 1,0–1,4 GeV.
- [x] Fonti esistenti e struttura del repository controllate; piano revisionato per coerenza dei task e dei confini scientifici.
- [ ] Rapporto estratto e verificato (T1).
- [ ] Inventario scientifico chiuso e contratto numerico congelato (T0/T2).
- [ ] Implementazione, test scientifici e benchmark completati (T3–T7).

L'utente ha scelto l'esecuzione da parte di un altro agente. La presente consegna termina con piano e aggiornamento della documentazione; l'esecutore dovrà leggere gli originali e lavorare secondo i gate, senza assumere che le attività future siano già state svolte.


## Esecuzione 6 novembre 2026 — stato effettivo

| Task/gate | Esito | Evidenza e limite |
| --- | --- | --- |
| T0 | Inventario consegnato | Registro completo degli ingredienti con stati; preprint 2005 aggiunto; G0 non dedotto dalla sola tabella |
| T1 | Componente verificato; accettazione piena non raggiunta | 80 vertici linea I; supporto termina a 1,394805194805 GeV, non 1,4; errore conservativo 0,0150204 supera obiettivo 0,01 |
| T2 / G0 | Incompleto | Numeri Tab.II verificati; loader impedisce uso dinamico; larghezze/Born/normalizzazione e identità angolare irrisolte |
| T3 / G1 | Verificato | Conservazione, invarianti, boost, volume Dalitz e limite senza masse; convenzione invariante separata dalle ampiezze |
| T4 / G2 | Bloccato da G0 | Nessuna ampiezza inventata |
| T5 / G3 | Bloccato da T4 | Nessuna sigma o Sigma calcolata |
| T6 / G4 | Bloccato da T5 | Nessun benchmark degli osservabili dichiarato passato |
| T7 | Consegna parziale | Package autonomo e `inspect`; `predict` assente finché i gate restano aperti |

Le checkbox originarie restano aperte dove il task completo non è soddisfatto.
Dettagli: [registro e lacune](../reference/theory/fix2010-derivation.md),
[verifiche](../reference/theory/fix2010-benchmarks.md),
`results_test/fix2010-rebuild/progress.md`.
Il piano resta attivo; nessun commit/push, dato stage 08 o archivio teorico riattivato.
