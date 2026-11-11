# Modello di Fix: fonti e fattibilità

Ricognizione del **6 novembre 2026**, assistita da AI. Richiesta: ricostruire dalle risorse pubbliche il modello per γp → ηπ⁰p e ottenere Σ negli intervalli sperimentali, procedendo per piccoli passi. Dopo una richiesta iniziale 0,93–1,50 GeV, l'utente ha ristretto il dominio a **Eγ laboratorio = 1,0–1,4 GeV**, anche per gli eventuali fit successivi. Binning, prodotti stage 08 e pesi sperimentali sono rinviati. Nessun calcolo completo del modello eseguito; nuovo package autonomo con componenti verificati, [stage 09](09-theory.md) storico sempre inattivo.

## Decisioni approvate e piano per l'esecutore

Il 6 novembre l'utente ha autorizzato l'estrazione del rapporto dalla Figura 6 e la ricerca degli altri ingredienti negli articoli; ha limitato il dominio a 1,0–1,4 GeV e rinviato il collegamento ai dati sperimentali. Ha chiesto **un piano dettagliato da fare implementare a un altro agente**. Il [piano operativo](../docs/plans/2026-11-06-fix2010-model-implementation.md) assume come baseline la soluzione I del 2010 e specifica provenienza degli ingressi, controlli, file e criteri di accettazione. L'autorizzazione non significa che rapporto, codice o benchmark siano già stati prodotti.

## Esito esecuzione del piano, 6 novembre 2026

- **T0:** registro degli ingredienti e manifest indipendente dai vecchi log: [derivazioni/lacune](../docs/reference/theory/fix2010-derivation.md), `data/theory/fix2010/source_manifest.json`. Letto anche Fix–Arenhövel 2005, `nucl-th/0503042v1`, dipendenza del 2008; originale conservato in `docs/reference_papers/Fix_2005_nucl-th0503042v1.pdf`.
- **T1 parziale rispetto al dominio richiesto:** 80 vertici della linea continua I recuperati in sicurezza, con overlay controllato visivamente anche nell’incrocio circa 1,25 GeV. Supporto effettivo **[1,0;1,394805194805] GeV**; nessuna estrapolazione a 1,4. Errore verticale conservativo **0,0150204**: obiettivo 0,01 non raggiunto e non attenuato a posteriori. JSON e lettore disponibili.
- **T2/G0 incompleto:** sei righe I trascritte, masse adattate e segni verificati; contratto eseguibile rifiutato. Restano larghezze totali/isobare, Born e normalizzazioni, verifica dell’identità angolare stampata. Inventario immutabile ispezionabile; nessun parametro fittizio.
- **T3 verificato:** cinematica K, boost, invarianti e fase a tre corpi; confronto indipendente con area Dalitz e limite senza masse. Convenzione invariante dichiarata, senza attribuirla automaticamente all’ampiezza non relativistica degli autori.
- **T4–T6 bloccati**, T7 limitato a packaging e `inspect`; assenti ampiezze complete, sigma, Sigma, benchmark degli osservabili e `predict`. [Verifiche e limiti](../docs/reference/theory/fix2010-benchmarks.md).

Ulteriore controllo del 6 novembre, dopo conferma che l’utente non dispone di altre fonti: recuperati e letti nei passaggi pertinenti anche Gómez Tejedor–Oset 1996 (`hep-ph/9506209v3`) e Ochi–Hirata–Takaki 1997 (`nucl-th/9703058v2`). Le loro prescrizioni riguardano modelli a due pioni e risonanze differenti; non chiudono il contratto numerico ηπ⁰p del 2010. Originali e hash conservati, nessun parametro importato.

Le sezioni successive conservano la ricognizione precedente: frasi quali «nessuna curva estratta» descrivono quel momento, superato dall’esecuzione qui riportata.

## Fonti conservate

| Fonte | Versione pubblica e copia locale | Ruolo |
| --- | --- | --- |
| Fix, Ostrick, Tiator, EPJA **36**, 61–72 (2008), [DOI](https://doi.org/10.1140/epja/i2007-10551-x) | [arXiv:0803.1755v1](https://arxiv.org/abs/0803.1755v1), [PDF](../docs/reference_papers/Fix_2008_0803.1755v1.pdf) | Formalismo originario; dipendenza citata dal lavoro 2010. Identità verificata, lettura completa ancora da fare. |
| Fix, Kashevarov, Lee, Ostrick, PRC **82**, 035207 (2010), [DOI](https://doi.org/10.1103/PhysRevC.82.035207) | [arXiv:1004.5240v1](https://arxiv.org/abs/1004.5240v1), [PDF](../docs/reference_papers/Fix_2010_1004.5240v1.pdf) | Ampiezze, parametri e confronto con Σ. |
| Fix, Arenhövel, PRC **83**, 015503 (2011), [DOI](https://doi.org/10.1103/PhysRevC.83.015503) | [arXiv:1010.4213v2](https://arxiv.org/abs/1010.4213v2), [PDF](../docs/reference_papers/Fix_2011_1010.4213v2.pdf) | Cinematica, convenzioni e osservabili polarizzati. La sezione V rinvia ai parametri del 2010. |
| Sokhoyan et al., PRC **97**, 055212 (2018), [DOI](https://doi.org/10.1103/PhysRevC.97.055212) | [arXiv:1803.00727v2](https://arxiv.org/abs/1803.00727v2), [PDF](../docs/reference_papers/Sokhoyan_2018_1803.00727v2.pdf) | Revisione del modello Mainz. |
| Kashevarov et al., EPJA **42**, 141–149 (2009), [DOI](https://doi.org/10.1140/epja/i2009-10868-4) | [arXiv:0901.3888v5](https://arxiv.org/abs/0901.3888v5), [PDF](../docs/reference_papers/Kashevarov_2009_0901.3888v5.pdf) | Antecedente con un solo contributo D₃₃; valori per bin del rapporto quadratico delle ampiezze. |
| Fix, Kashevarov, Ostrick, NPA **909**, 1–7 (2013), [DOI](https://doi.org/10.1016/j.nuclphysa.2013.04.011) | [arXiv:1307.2353v1](https://arxiv.org/abs/1307.2353v1), [PDF](../docs/reference_papers/Fix_2013_1307.2353v1.pdf) | Controllo della letteratura successiva sulla stessa dipendenza. |

Le copie sono preprint: equivalenza integrale alle versioni editoriali e presenza di eventuali correzioni ancora da controllare. I sorgenti TeX degli articoli non equivalgono al programma numerico.

## Risultati della lettura

**2010.** Sezione II: contributi Born e risonanti, con percorsi ηΔ e πN*. Tabella II: tre soluzioni; I è candidata al primo riferimento. Punto critico: dopo Eq. (5), p. 3, A₃/₂ della D₃₃(1700) viene adattata separatamente nei bin energetici. Il rapporto alla massa della risonanza in tabella non specifica l'intera funzione; Fig. 6 ne mostra l'andamento. Fig. 9, p. 11, confronta Σ con Ajaka nei bin 1,1–1,2, 1,2–1,3 e 1,3–1,4 GeV. Testo ed Eq. (5), più bin e didascalia di Fig. 9, controllati anche visivamente.

**2011.** Offre il formalismo per passare dalle ampiezze agli osservabili, ma non sostituisce la determinazione degli ingredienti dinamici. Sezione V considera il settore risonante; occorre dichiarare questa approssimazione se adottata.

**2018.** Introduce un ulteriore fondo fenomenologico. Eq. (9), p. 5, usa polinomi quadratici con coefficienti complessi Cₙ; pagina controllata visivamente. Tabella I riporta parametri risonanti: non basta da sola a definire anche il fondo. I valori dei Cₙ non sono stati individuati nella ricognizione. I dati presentati arrivano a 1,45 GeV. Non è quindi giustificato trattare questa revisione come un semplice aggiornamento numerico del 2010.

**Limite della ricognizione iniziale.** Le fonti esaminate non certificavano una riproduzione su tutto l'intervallo allora richiesto 0,93–1,50 GeV. L'utente ha successivamente ristretto il dominio a 1,0–1,4 GeV. Rimane necessario distinguere intervallo dei dati usati nel fit, intervallo dei grafici e possibilità matematica di valutare le formule; la sola esecuzione del programma non lo valida.

## Prima lacuna da risolvere

Ricostruire la dipendenza energetica delle ampiezze elettromagnetiche nella versione scelta. È il modo in cui il fotone eccita le risonanze: può cambiare l'asimmetria, non soltanto la scala del grafico.

Per il candidato 2010, recuperare il rapporto dalla figura originale secondo l'autorizzazione ora ricevuta, con interpolazione ed errore di lettura documentati. Non fissare A₃/₂ arbitrariamente, non ricavare una legge completa da un solo numero e non sostituire la curva teorica finale con una digitalizzazione. Si tratta del recupero grafico di un **ingrediente intermedio**; le altre assunzioni fisiche restano soggette alla verifica delle fonti.

Nelle ricerche per autori, DOI, codice, Fortran e GitHub non è stato identificato un programma originale scaricabile. Non è una dimostrazione di inesistenza. Nessun autore contattato.

## Percorso proposto, non ancora implementato

### Esito del primo approfondimento: dipendenza energetica

Aggiornamento del 6 novembre, dopo la richiesta di procedere con il primo step. La ricerca ha individuato informazioni aggiuntive, ma **non ha chiuso gli ingressi del modello completo**.

- **2009, p. 7, Eqs. (10)–(13):** sono pubblicati i valori di `a = (A₃/₂/A₁/₂)²`: 0,7; 1,2; 1,7; 2,0 nei quattro bin consecutivi 1,0–1,1; 1,1–1,2; 1,2–1,3; 1,3–1,4 GeV. Sono valori del rapporto **al quadrato**, non delle singole ampiezze. Provengono dall'approssimazione con una sola D₃₃ e fondo trascurato; non completano la soluzione I del 2010.
- **2010:** l'archivio arXiv contiene `Text.tex` e undici figure, senza file numerici separati. Il TeX conferma la dipendenza dell'Eq. (5): per D₃₃(1700), A₁/₂ cresce con l'energia del fotone nel centro di massa, mentre A₃/₂ è adattata nei bin. Un vecchio commento proponeva lo stesso esponente per entrambe: è escluso dal testo compilato, quindi non costituisce una prescrizione accettata. `fig6.ps` conserva il tracciato vettoriale delle tre soluzioni; la soluzione I è la linea continua, rappresentata da 1,0 a 1,4 GeV.
- **2013, introduzione:** riporta per il rapporto un intervallo circa 0,95–1,3, rinviando al 2010. Non è una tabella né una legge energetica sufficiente a ricostruire il fit.
- **2018, p. 4, Eq. (4):** pubblica esplicitamente, per Δ(1700), `Aλ(W) = Aλ(MR) [ωγ(W)/ωγ(MR)]^(3/2)`, per entrambe le elicità. Qui ωγ è l'energia nel centro di massa. Ne segue un rapporto costante per questo vertice della singola risonanza, non un'asimmetria complessiva costante. Questa prescrizione appartiene alla revisione 2018: non va inserita tacitamente nel 2010. L'archivio contiene un TeX e diciotto figure; non sono stati individuati valori dei coefficienti Cₙ del fondo aggiuntivo.

I due archivi originali sono conservati senza modifiche: [2010](../docs/reference_papers/Fix_2010_1004.5240v1_source.tar.gz) e [2018](../docs/reference_papers/Sokhoyan_2018_1803.00727v2_source.tar.gz). Il tentativo di leggere il testo editoriale 2010 tramite APS Harvest ha restituito HTTP 401 ed è stato interrotto; equivalenza editoriale ancora non certificata. Le ricerche mirate non hanno individuato errata pertinenti o supplementi numerici, senza dimostrarne l'inesistenza.

**Proposta iniziale, ora adottata nel piano:** scegliere la soluzione I del 2010 come primo riferimento storico e recuperare dal tracciato originale di Fig. 6 il rapporto `A₃/₂/A₁/₂`. Sarà un ingresso ricostruito dalla figura, non una tabella originale del fit. Prima dell'uso occorrono identificazione della curva, calibrazione degli assi, confronto visivo e stima dell'errore di lettura, distinto dall'incertezza fisica dei parametri. Il calcolo delle ampiezze, delle interferenze e di Σ rimane da implementare e verificare.

Il dominio attuale è il tratto rappresentato **1,0–1,4 GeV**: la precedente richiesta **0,93–1,50 GeV** è stata ristretta dall'utente, quindi non si pianificano estrapolazioni ai due intervalli esterni. Nessuna curva numerica è stata estratta o usata come ingresso in questo approfondimento; nessuna nuova implementazione attivata. Il recupero grafico autorizzato non elimina la necessità di chiudere gli altri ingressi.

### Passi successivi

1. Chiudere la lacuna sopra e scegliere una versione riproducibile. Poi completare masse, larghezze dipendenti dall'energia, normalizzazioni, segni, fasi e termini di fondo, collegando ogni scelta alla fonte.
2. Dichiarare unità, sistemi di riferimento, definizione di Σ e un primo confronto numerico. Le figure pubblicate possono verificare la riproduzione del calcolo; non provano da sole la correttezza fisica del modello.
3. Implementare cinematica e ampiezze per contributi verificabili. Controllare conservazione del quadrimpulso, soglia, positività, dipendenza dalla polarizzazione e limiti analitici prima del confronto grafico.
4. Verificare integrazione e convergenza, poi confrontare sezioni d'urto e Σ con riferimenti della stessa versione. Tolleranze da fissare prima dei confronti.
5. Collegare i prodotti stage 08 dichiarati. Integrare numeratore e denominatore di Σ con i pesi pertinenti; non fare una media aritmetica delle asimmetrie. Rispettare la [convenzione dei bin finiti](finite-bin-correction.md).

Il programma completo non è ancora definito: rimangono lacune numeriche, oltre alla verifica delle formule. L'archivio Döring/Ajaka conserva valore storico; non fornisce automaticamente parametri per Fix.

## Tracciabilità

Ricerche web del 6 novembre: `Fix Kashevarov Lee Ostrick 2010 pi eta photoproduction model source code download`; `Mainz pi eta model Fix Sokhoyan 2018 055212 parameters`; `"Fix" "Kashevarov" photoproduction Fortran`; `"1004.5240" software github`; DOI del lavoro 2008. Consultati preprint arXiv e metadati APS/INSPIRE. Si riportano riscontri circoscritti, non una revisione esaustiva.

Hash delle quattro copie, pagine verificate e controlli documentali in `results_test/fix-source-audit-20261106/verification.log`. Estratti e immagini temporanee rimossi dopo la lettura; originali conservati. Nessuna validazione numerica o fisica dichiarata.

Approfondimento sulle elicità: `results_test/fix-helicity-audit-20261106/source-manifest.json` registra hash e inventari dei sorgenti; `verification.log` registra letture e controlli. Conservati come evidenza della ricerca e dei contenuti effettivamente disponibili. Ricerche aggiuntive: DOI 035207 con `supplemental`/`erratum`, `1004.5240 A3/2`, `Fix helicity amplitudes energy`, `1803.00727 data code coefficients`. Letti i riferimenti 2009 e 2013 sopra, testo e sorgenti 2010/2018. Nessun autore contattato.
