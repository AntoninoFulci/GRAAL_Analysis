# Ripartenza teorica: prima ricognizione su Ajaka

Data: 5 novembre 2026. Stato: obiettivo confermato, prima mappa delle fonti e dei meccanismi completata; ricetta numerica ancora da verificare. Nessuna nuova implementazione o validazione fisica.

## Obiettivo espresso

Ottenere curve teoriche da sovrapporre alle asimmetrie sperimentali GRAAL, procedendo lentamente: prima raccogliere le informazioni, poi decidere insieme, con spiegazioni semplici e una domanda alla volta. Il riferimento di lavoro è Ajaka et al. (2008), Figura 4. L'utente ha chiarito che vuole implementare correttamente il modello e ricalcolare le previsioni nei propri intervalli sperimentali, non limitarsi alle linee pubblicate. La correttezza di queste ultime è una domanda aperta, non un errore accertato.

È stato accettato il percorso graduale: fonti → ingredienti e lacune → verifica dei singoli pezzi → combinazione → controlli indipendenti → intervalli sperimentali. Il contratto numerico, i prodotti stage 08 e il primo benchmark non sono ancora concordati.

## Fonti individuate e controllo svolto

| Fonte | Ruolo | Verifica in questa ricognizione |
| --- | --- | --- |
| J. Ajaka et al., *Simultaneous Photoproduction of η and π⁰ Mesons on the Proton*, PRL **100**, 052003 (2008), [DOI](https://doi.org/10.1103/PhysRevLett.100.052003) | Definisce misure e curve da riprodurre | Testo del PDF locale; in particolare pp. 4–5, Figura 4 e riferimenti [11–12] |
| M. Döring, E. Oset, D. Strottman, *Chiral dynamics in the γp → π⁰ηp and γp → π⁰K⁰Σ⁺ reactions*, PRC **73**, 045209 (2006), [DOI](https://doi.org/10.1103/PhysRevC.73.045209) | Fonte principale del modello, riferimento [11] di Ajaka | Testo delle sezioni II, IV e passaggi di V; controllo visivo delle pagine 2, 10–12. Mappa strutturale, non validazione completa delle formule |
| M. Döring, E. Oset, D. Strottman, *Clues to the nature of the Δ*(1700) resonance from pion- and photon-induced reactions*, PLB **639**, 59–67 (2006), [DOI](https://doi.org/10.1016/j.physletb.2006.06.022) | Aggiornamento del modello, riferimento [12] di Ajaka | Testo delle sezioni 2–4; controllo visivo delle pagine stampate 62 e 65, inclusa Figura 5. Aggiornamento delle larghezze accertato; uso esatto nella Figura 4 di Ajaka da ricostruire |

I tre PDF sono in `docs/reference_papers/`. SHA-256 letti durante questa ricognizione:

```text
7fdf85fe56fa8b0e232d070269e3e58d4d7ca542dcd9ac2287291abaa6b4f1cb  Ajaka_2008_EtaPi0_Photoproduction_PRL100_052003.pdf
19a2fbce10ed8201a29bdfbcfb9f3690a280d943c1e83db01aa1b2057d20eccb  10.1103@PhysRevC.73.045209.pdf
c1def91b01ee5750aca4124ae2469178b204d99649075d7d4f4277facab9d430  10.1016@j.physletb.2006.06.022.pdf
```

## Cosa stabilisce direttamente Ajaka

- Reazione: γp → ηπ⁰p; osservabile della Figura 4: asimmetria di fascio Σ.
- Dodici pannelli: tre masse invarianti, M(pπ⁰), M(pη), M(ηπ⁰), per quattro intervalli di energia del fotone: 1.1–1.2, 1.2–1.3, 1.3–1.4, 1.4–1.5 GeV.
- Per ogni coppia, l'angolo azimutale φ è quello della somma dei suoi momenti. Asse z lungo il fotone, piano xz orizzontale.
- Per l'estrazione sperimentale: dieci intervalli di massa e dodici di φ; metodo basato sulla dipendenza cos(2φ).
- La didascalia attribuisce le curve al modello dei riferimenti [11–12]. Il testo di p. 1 precisa che queste previsioni per gli osservabili sono riportate qui per la prima volta.
- Il testo evidenzia il ruolo della Δ(1700), ma ciò non autorizza a identificare un suo singolo contributo con il calcolo completo.

Queste informazioni non stabiliscono da sole se le curve siano calcolate al centro dell'intervallo di energia o mediate, né quali pesi siano usati. Il testo estratto contiene simboli corrotti: prima di trascrivere equazioni occorrerà controllarle visivamente sul PDF.

## Materiale precedente: utile come indice, non come validazione

La [pagina dello stage 09](09-theory.md) documenta il ritiro del precedente tentativo e l'ultimo stato storico: 0/12 pannelli certificati. L'archivio rimane inattivo.

In [docs/reference/theory](../docs/reference/theory/index.md) sono conservati:

- Una digitalizzazione delle linee teoriche della Figura 4 (`ajaka2008_figure4_theory.csv` e relativo JSON). Il JSON dichiara lettura dai tracciati vettoriali del PDF e una tolleranza di lettura di 0.020 in Σ, non un'incertezza teorica. In questa ricognizione sono stati letti i metadati, senza ripetere il controllo grafico.
- Un inventario delle ampiezze e una mappa delle fonti del modello N*(1535). Citano ulteriori lavori di Inoue, Nacher, Sarkar e altri: dipendenze da ricontrollare sulle fonti, non parametri già accettati per la ripartenza.
- Note storiche su difficoltà di integrazione numerica e confronto con le curve. Non dimostrano che una nuova ricostruzione sia già corretta.

## Mappa verificata degli ingredienti

I riferimenti P73 e B639 indicano rispettivamente i due articoli di Döring sopra. I numeri delle pagine P73 sono quelli stampati dopo `045209-`; per B639 si usano le pagine 59–67. Le famiglie sotto sono un raggruppamento per studiare il modello, non una scelta dell'architettura software.

| Ingrediente | Significato semplice | Fonte e verifica | Cosa rimane da fissare |
| --- | --- | --- | --- |
| Cinematica a tre corpi | Quali energie e direzioni finali sono possibili | P73 p. 11, Eqs. (44)–(46), testo e immagine | Masse, unità, trasformazioni tra sistemi di riferimento e misura d'integrazione coerenti |
| Interazione forte a canali accoppiati | Le coppie di particelle possono interagire e trasformarsi; da qui emerge la N*(1535) | P73 p. 2, Eq. (1), Tab. I, Eqs. (4)–(6), testo e immagine | Ricostruzione del modello completo di Inoue, costanti e prescrizioni numeriche; nessun riuso automatico dei vecchi JSON |
| Produzione senza risonanze esplicite ai vertici iniziali | Il fotone si accoppia a mesoni e barioni, con emissione del π⁰ | P73 sezione IV A–B, Figg. 6–8, Eqs. (16)–(25); lettura testuale e riscontro delle descrizioni in Fig. 12, p. 11 | Segni, termini magnetici, fattori di forma e integrali; mantenere insieme i termini che gli autori associano per consistenza elettromagnetica |
| Risonanze esplicite nella produzione | Passaggi attraverso N*(1520), Δ*(1700), Δ(1232), inclusi i termini elettromagnetici associati | P73 IV C, Fig. 9, Eqs. (26)–(37); lettura testuale e Fig. 13, p. 12, controllata visivamente | Accoppiamenti al fotone, larghezze dipendenti dall'energia e convenzioni importate da Nacher |
| Δ*(1700) → ηΔ e KΣ*, seguiti da ulteriori interazioni | Altri percorsi arrivano allo stesso stato finale e interferiscono | P73 IV D, Fig. 10, Eqs. (38)–(42), pp. 10–11, testo e immagine | Accoppiamenti complessi, fasi relative, propagatori corretti per ogni canale e aggiornamenti B639 |
| Cascata senza interazione finale ηp | γp → Δ*(1700) → ηΔ(1232) → ηπ⁰p | P73 Fig. 11, Eqs. (43)–(44), p. 11, testo e immagine | Parametri coerenti con il resto del modello; questo singolo contributo non è il risultato completo |
| Somma coerente | Sommare le ampiezze prima di ricavare le probabilità, conservando le interferenze | P73 p. 12, testo e didascalia Fig. 14, controllo visivo | Un'unica convenzione per spin, fasi e normalizzazioni di tutti i contributi |
| Osservabile polarizzato e media sperimentale | Mantenere la dipendenza dalla polarizzazione e ottenere Σ negli intervalli richiesti | P73 ampiezze dipendenti dal vettore di polarizzazione; Ajaka p. 4 e Fig. 4 | Derivazione esplicita della proiezione osservabile, segno, pesi in energia e massa, selezione/accettanza pertinente allo stage 08 |

La P73 Eq. (5) scrive `T = [1 − VG]⁻¹ V`. È un sistema di interazioni ripetute tra i sei canali di Eq. (1): π⁰p, π⁺n, ηp, K⁺Σ⁰, K⁺Λ, K⁰Σ⁺. Sostituirlo direttamente con un picco N*(1535) di forma prefissata sarebbe una modifica del modello. La versione «ridotta» esclude sia lo scambio di mesoni vettori sia il contributo ππN; la versione «completa» li include (P73 pp. 3 e 12). Questa distinzione riguarda il sottosistema forte, non l'esistenza della cascata di Fig. 11.

Per arrivare a Σ non basta una tabella di sezioni d'urto non polarizzate: occorre conservare nelle ampiezze l'informazione sulla polarizzazione. I grafici non polarizzati restano controlli intermedi utili, ma non verificano da soli l'asimmetria.

## Dipendenze bibliografiche da chiudere

| Fonte | Perché serve | Stato al 5 novembre |
| --- | --- | --- |
| Inoue, Oset, Vicente Vacas, PRC **65**, 035204 (2002), [PDF](../docs/reference_papers/PhysRevC.65.035204.pdf) | Potenziale, funzioni di loop, costanti e contributo ππN per la N*(1535); P73 Ref. [8] | PDF disponibile. Letti passaggi su versione finale e parametri, Eq. (28) e seguito; verifica numerica e visiva completa ancora da fare |
| Nacher et al., NPA **695**, 295 (2001), [preprint v2](../docs/reference_papers/nucl-th-0012065.pdf) | Accoppiamenti elettromagnetici, risonanze, larghezze e fattori di forma; P73 Ref. [17] | Titolo/versione verificati; tabella A3 p. 30 controllata visivamente per gli ingredienti della Δ(1700). Vedi [scheda numerica](theory-delta1700-inputs.md); equivalenza completa al testo editoriale ancora da verificare |
| Sarkar, Oset, Vicente Vacas, NPA **750**, 294 (2005), [preprint v2](../docs/reference_papers/nucl-th-0407025.pdf) | Accoppiamenti Δ*(1700) → ηΔ e KΣ*; P73 Ref. [21] | Tabella 10 p. 15 controllata visivamente. Erratum NPA **780**, 90 (2006): DOI e pagina verificati con Crossref/INSPIRE, contenuto ancora non accessibile. Vedi [stato dell'erratum](theory-delta1700-inputs.md#erratum-identità-risolta-contenuto-aperto) |
| Butler, Savage, Springer, NPB **399**, 69 (1993), [preprint](../docs/reference_papers/9211247v1.pdf) | Convenzioni per i vertici con Δ e Σ*, adottate in P73 Eq. (38) | Rinvio verificato in P73; contenuto del preprint non riesaminato in questo passo |
| Döring, Oset, Vicente Vacas, PRC **70**, 045203 (2004), [PDF](../docs/reference_papers/PhysRevC.70.045203.pdf) | Riferimento al trattamento efficace del contributo ππN dopo P73 Eq. (5) | Rinvio verificato; non sostituire senza confronto il modello della regione N*(1535) con un'approssimazione di bassa energia |

## Primo problema concreto: distinguere le versioni del modello

**Fatto verificato:** B639 non è soltanto una discussione complementare. A p. 62 introduce per Δ*(1700) contributi ρN con pesi del 37% in onda s e del 5% in onda d, dichiarati come scelta dopo aggiustamento ai dati; la larghezza totale vicino alla risonanza è circa 300 MeV. La Eq. (13) modifica anche la dipendenza energetica del decadimento πN mediante un fattore di barriera.

A p. 65, Fig. 5 e testo, gli autori dichiarano una riduzione di circa il 30% delle sezioni d'urto γp → π⁰ηp e γp → π⁰K⁰Σ⁺ rispetto a P73, associata alla revisione della larghezza e all'introduzione del contributo ρN in onda d. Entrambi i passaggi sono stati controllati visivamente sul PDF editoriale.

**Conseguenza per noi:** prima di congelare i parametri occorre ricostruire un insieme coerente P73 + aggiornamenti B639 e stabilire il suo legame con il calcolo di Ajaka. I numeri citati sopra sono evidenza della modifica pubblicata, non parametri già approvati per una nuova implementazione.

**Non segue:** non è dimostrato un errore nelle curve di Ajaka e non segue una variazione del 30% di Σ. Una normalizzazione comune alle due polarizzazioni può cancellarsi nel rapporto; variazioni delle forme, dei pesi relativi e delle interferenze vanno invece calcolate.

Un'ulteriore ambiguità locale merita una nota per la futura trascrizione: a p. 11 P73 il testo dopo Eq. (42) estende letteralmente alle Eqs. (39)–(42) la sostituzione Δ → Σ*, mentre Fig. 10, Eq. (39) e il commento di p. 12 identificano il percorso ηΔ con Δ(1232). La lettura coerente è distinguere il percorso ηΔ da quelli con kaoni; va registrata come interpretazione della fonte e verificata, non applicata in silenzio come una correzione già certificata.

## Ricerca preliminare di codice e tabelle originali

Il 5 novembre sono state eseguite ricerche mirate per autori, DOI, codice e materiale supplementare. Sono state aperte la pagina APS di Ajaka e le schede arXiv [nucl-th/0510015](https://arxiv.org/abs/nucl-th/0510015) e [nucl-th/0602055](https://arxiv.org/abs/nucl-th/0602055). Le schede identificano le versioni v2 del 27 marzo e del 2 maggio 2006 e collegano PDF e sorgenti TeX. I sorgenti TeX sono materiale dell'articolo: il link non dimostra disponibilità del programma numerico.

In questa ricerca limitata non è stato individuato un codice numerico degli autori o un insieme di tabelle polarizzate utilizzabile per verificare la Figura 4. Questo non dimostra che non esistano. Nessun autore è stato contattato. La digitalizzazione locale resta distinta dalle tabelle numeriche originali.

**Risposta dell'utente, 5 novembre:** il gruppo non possiede codice, tabelle o note originali; considerarli perduti e indisponibili per il progetto. Si procede dalle fonti pubblicate, senza subordinare il lavoro al recupero di quel materiale e senza presumere che nessun autore possa averne conservato una copia.

## Prossimi passi, uno alla volta

1. Disponibilità privata chiarita: nessun materiale originale utilizzabile. Ricostruire dalle pubblicazioni; nessun contatto esterno richiesto o autorizzato.
2. Completare la [scheda della Δ*(1700)](theory-delta1700-inputs.md): primi accoppiamenti trascritti e aggiornamenti delle larghezze identificati; restano normalizzazioni, convenzioni e contenuto dell'erratum. Poi passare al sottosistema N*(1535) e ai restanti meccanismi.
3. Concordare convenzioni e primo benchmark dopo aver chiarito gli ingredienti. Possibili controlli sono le quantità forti di P73 Figg. 1/15 e i contributi separati di Figg. 12–14, con la versione dichiarata. Non sono ancora un piano di implementazione approvato.
4. Dichiarare prodotti stage 08, ricostruzione, manifest, flusso, intervalli e proiezione osservabile. Il rapporto tra quantità integrate non coincide in generale con la media dei rapporti. Rispettare la [correzione dei bin azimutali](finite-bin-correction.md) già applicata secondo l'estimatore, evitando duplicazioni.

Verifiche documentali e hash delle fonti sono registrati in `results_test/ajaka-source-audit-20261105/verification.log`. È conservato solo questo registro compatto; estrazioni di testo e immagini temporanee vengono rimosse dopo la lettura. La raccolta dei parametri non è completa; non è stato eseguito alcun calcolo scientifico del modello.
