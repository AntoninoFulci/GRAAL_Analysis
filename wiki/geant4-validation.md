# Geant4: requisiti, benchmark e decisioni

Requisiti del 27 ottobre 2026; recupero degli input aggiornato il **3 novembre 2026**. Questa pagina registra requisiti approvati, riscontri di sorgente e dipendenze ancora aperte. Il [design](https://github.com/AntoninoFulci/GRAAL_Analysis/blob/main/docs/plans/2026-10-26-geant4-bdt-design.md) e il [piano esecutivo](https://github.com/AntoninoFulci/GRAAL_Analysis/blob/main/docs/plans/2026-10-26-geant4-bdt-execution.md) li traducono in lavoro verificabile. Il codice di trasporto corrente resta quello diagnostico descritto nello [stage 03](03-monte-carlo-simulation).

## Mandato scientifico

1. Determinare efficienze e migrazioni necessarie alla stima delle sezioni d'urto dei canali analizzati, includendo trigger, ricostruzione, PID, selezione e BDT quando applicato.
2. Stimare il fondo residuo dopo la stessa catena di analisi, con normalizzazioni e forme motivate da dati sperimentali oppure modelli dichiarati.
3. Riprodurre come benchmark obbligatorio le bande di identificazione delle particelle cariche: dE/dx contro energia BGO al centro e dE/dx contro TOF in avanti, con discriminazione pioni/protoni.
4. Studiare come obiettivo esplorativo la discriminazione fotoni/neutroni nel BGO. Timing e molteplicità dei cristalli possono sovrapporsi: nessuna separazione garantita a priori.

Il confronto sul training BDT rimane utile, ma l'adozione è guidata dalla qualità di efficienze, fondo e relativa incertezza. L'asimmetria resta un controllo di stabilità degli stimatori già esistenti; non è più l'unico risultato prioritario. Una mappa di accettanza validata per sezioni d'urto è un prodotto scientifico del progetto, distinto da una modifica degli stimatori dell'asimmetria.

## Geometria e target

Il responsabile conferma geometria e materiali ricavati dal Fortran come base del detector; non si riapre il ridisegno generale del rivelatore. Conservare quattro opzioni esplicite: idrogeno liquido o deuterio liquido, cella nominale di 6 cm o 12 cm. Ogni campagna dichiara una singola opzione e la corrispondenza con i run analizzati; non si mediano i quattro setup.

La densità richiesta è quella nominale del materiale puro liquido. Come riferimenti tabellati iniziali: [PDG, idrogeno liquido](https://pdg.lbl.gov/2021/AtomicNuclearProperties/HTML/hydrogen_liquid.html), 0.07080 g/cm³; [PDG, deuterio liquido](https://pdg.lbl.gov/2024/AtomicNuclearProperties/HTML/deuterium_liquid.html), 0.1638 g/cm³. Questi valori hanno una fonte/edizione e non sono una misura delle condizioni di esercizio. Il profilo conserva riferimento termodinamico e composizione isotopica; per LD₂ l'elemento è deuterio, non idrogeno naturale con sola densità cambiata.

Lo snapshot storico contiene lunghezza attiva 6.12 cm e densità 0.162 g/cm³. Nei sorgenti ora disponibili, `laggen/src/lagdata.F:299–305` assegna 6.12 cm alla variante corta e **11.1 cm** alla lunga. Mantenerli immutati e distinguere la misura attiva dalla denominazione nominale “6/12 cm”. La mappa nominale→attiva va confermata prima di fissare i nuovi solidi; `lagbers.F` mostra anche come finestre e supporti dipendono dalla lunghezza.

La scelta del materiale LD₂ non converte il generatore libero γp in un generatore nucleare. Per analisi su deuterio dichiarare reazione coerente, incoerente o quasi-libera, nucleone colpito, spettatore e trattamento di moto di Fermi, legame e interazioni finali. Questi input restano da definire prima di efficienze fisiche su D; trasporto di particelle singole è comunque possibile per benchmark detector.

## GENBOD e pesi

Decisione del responsabile: mantenere generazione GENBOD e usare i pesi prodotti dal generatore. Le sezioni d'urto totali/differenziali definiscono la distribuzione fisica dei canali; non sono contenute automaticamente nel peso di spazio delle fasi.

Riscontro locale: ROOT `TGenPhaseSpace` è basato su GENBOD/Raubold–Lynch (`math/physics/src/TGenPhaseSpace.cxx`, installazione ROOT 6.40.04). Il percorso attuale in `03_mc_simulation/generators/smearing.h::GenerateUnweighted` usa `Generate()` in accept–reject e salva eventi a peso unitario, con metadato `accept-reject-unweighted`. Non si possono recuperare pesi mancanti cambiando il manifest di file esistenti.

Nuovo percorso pesato: conservare per evento il peso nativo, la convenzione/normalizzazione, i pesi delle eventuali catene di decadimento e la densità di proposta. Applicare le dipendenze dinamiche come rapporto tra distribuzione desiderata e proposta, con normalizzazione coerente. Tenere distinguibili peso di fase, forma differenziale, flusso/beam, branching e normalizzazione assoluta. Se un effetto è già nella generazione o nell'unweighting, non applicarlo di nuovo. Il percorso unweighted rimane valido se il suo campionamento è correttamente dichiarato.

L'efficienza pesata nel bin di truth `b` è `ε_b = Σ(w_i I_pass,i) / Σ(w_i)`, dove entrambe le somme usano lo stesso insieme generato nel bin, inclusi eventi senza hit o falliti al trigger/selezione. Per migrazioni salvare `R_(r,b) = Σ(w_i I_reco_in_r_and_pass,i) / Σ_b(w_i)`, con definizione univoca di evento/candidato. Riportare somme dei pesi, quadrati, correlazioni e incertezze appropriate. Pesi di classe rinormalizzati per training non sostituiscono questi pesi fisici.

I fondi assoluti richiedono anche flusso calibrato/live time, nuclei bersaglio e sezioni d'urto/branching coerenti. Un campione generato con una sezione d'urto esterna del segnale può servire a proposta e studio dell'efficienza; non deve vincolare circolarmente la sezione d'urto che si vuole misurare. Forma e normalizzazione del modello entrano come assunzioni e incertezze esplicite.

I nove canali neutri correnti sono il primo catalogo di generazione, non una certificazione di fondo completo. Auditare cariche malidentificate, neutroni, processi nucleari/finestre e accidentali se compatibili con i dati: simulare, escludere con motivo oppure vincolare con controlli e incertezze. In assenza di questo audit si pubblica il fondo dei processi inclusi, non il fondo totale.

## Sezioni d'urto e sorgenti legacy

Ordine concordato: tabelle totali e differenziali in `laggen`, con verifica di unità, frame, variabile, BR inclusa, soglie e copertura; integrazione con misure primarie; modelli esterni identificati/versionati nei domini senza misure adeguate. La [ricerca di fonti](geant4-cross-section-sources) individua riferimenti e limiti, non costituisce già un import numerico verificato. Il modello a volume di fase saturato in `00_common/physics/cross_sections.py` rimane il riferimento software corrente: non è una tabella differenziale validata.

Il responsabile ha fornito l'archivio `docs/reference/fortran/prog/`: **39.939 file**, inclusi `laggen`, `laggen_vale`, `lagdig`, `prean` e configurazioni. La [mappa Fortran](legacy-fortran-map) distingue generazione, digitizzazione, ricostruzione e analisi, con inventario/hash completi nella campagna di evidenza. 57 dei 58 file confrontabili col manifest geometrico sono identici; differisce `laggen/pilot.h`. Non eseguire binari o scegliere la configurazione dalla sola presenza degli oggetti compilati.

Tabelle totali `SIGR` sono incorporate in `blockdata.F`; le differenziali vengono lette da `channel.mat` esterno, assente nell'inventario del 27 ottobre e recuperato il 3 novembre insieme a database/calibrazioni e profili del fascio. Disponibilità e limiti sono registrati sotto. `laggen` e `laggen_vale` differiscono nella definizione di canali/decadimenti, e il peso HBOOK non è conservato nell'uscita ASCII: dettagli e limiti sono nella [mappa delle sorgenti fisiche](geant4-cross-section-sources). La preanalisi ROOT attuale consuma già cluster; l'algoritmo frontier è disponibile in `prean`, quello ad automa cellulare dipende da `libclusC` da recuperare.

## Benchmark obbligatorio per cariche

| Regione | Assi ricostruiti | Riscontro nel codice preservato | Verifica richiesta |
| --- | --- | --- | --- |
| Centrale | `ECLUSC_TRACK`, `DEDX_TRACK` | `track_centr_classify.F`, selezione `CHECK_CUT_2D_BGO`; ROOT `Eclusc_track`, `Dedx_track` | Bande p/π, centroidi, larghezze, code e matrice di confusione con gli stessi tagli di periodo |
| Forward | `TOF_TRF`, `DE_TRF` | `track_forw_classify.F`, `CHECK_CUT_2D_FW`; ROOT `Tof_trf`, `De_trf` | Bande p/π, calibrazione tempi/cammino, risoluzione e PID dopo identica selezione |

Riprodurre l'osservabile strumentale: un deposito G4 o un dE/dx teorico non coincidono automaticamente con la variabile calibrata nei branch. Mappare scintillatore, correzione di cammino, quenching, saturazione, tempo zero e unità attraverso `prean`/calibrazioni. Usare PID vero solo per valutare la matrice di confusione MC, mai per selezionare al posto degli algoritmi osservati. Occorrono riferimenti dati indipendenti dal tuning e relativi fondi/incertezze.

Il quenching va calcolato prima di perdere la dipendenza dallo step, oppure richiede step energy/length/materiale salvati. In alternativa salvare energia visibile nello stepping con modello e parametri versionati. La somma dei depositi per cristallo da sola non è un input sufficiente per ricostruire la risposta non lineare π/p; questo requisito viene prima delle campagne utili al benchmark.

## Studio esplorativo fotoni/neutroni

Prima caratterizzare campioni γ e n singoli su griglie di energia, angolo e punto di ingresso comuni, poi topologie fisiche con controlli selezionati cinematicamente. Separare energia incidente da energia visibile, efficienza di rivelazione da efficienza di classificazione, e confrontare a energia visibile comparabile per evitare una separazione artificiale dovuta al campionamento. Le etichette truth restano fuori dalle feature del classificatore.

Studiare congiuntamente tempo rispetto al riferimento sperimentale, distribuzione dei tempi nel cluster se leggibile, molteplicità sopra soglia, frazione di energia nel cristallo più energetico, estensione e momenti della doccia. `PreAnalysis.h` conserva `Mclus`, `Emax`, `Sx1/Sy1/Sx2/Sy2`, tracciati in `prean`; OLD/NEW hanno convenzioni diverse. Il sorgente `TIME_BGO` trovato conserva TDC grezzi per 15 canali solo sui dati; non è un tempo calibrato per cluster e `lagdig/BGOD` non simula l'equivalente. Il primo tempo di deposito G4, tempi barrel e TOF forward non lo sostituiscono. Nessuna pulse-shape discrimination se waveform/informazione ottica non sono disponibili.

Misurare contaminazione neutronica a efficienza fotonica fissata e viceversa, per dominio e con intervalli; confrontare varianti dei modelli neutronici, soglie e risposta di scintillazione/quenching. Concludere anche “separazione insufficiente” se i dati lo indicano. Lo studio ha un gate proprio e non ritarda efficienze/fondo se non produce beneficio. I risultati di apparati con elettronica diversa non si trasferiscono automaticamente a GRAAL.

## Calcolo e decisioni ancora necessarie

Server designato: **trima**, disponibile senza vincolo di budget imposto dal responsabile. Confermato benchmark breve prima della statistica estesa. All'esecuzione rilevare ambiente, CPU/memoria/spazio e dipendenze; pianificare partizioni, seed, retry e merge verificabile. La disponibilità di risorse non elimina controlli di completezza o precisione statistica; nessun accesso o job è stato avviato sul server durante questo aggiornamento.

Restano da chiudere: scelta e convenzioni delle tabelle/card recuperate, validità delle calibrazioni e copertura dei periodi mancanti, libreria dell'automa se usato; mappa run → target/lunghezza; convenzione nominale/attiva e densità di riferimento; trigger e controlli cariche indipendenti; reazioni nucleari se si analizza D; osservabili, binning, precisione richiesta a efficienze/fondo e luminosità. La classificazione P/D è già nel catalogo run; non determina lunghezza attiva e configurazione completa. Sono dipendenze specifiche, non un riavvio delle scelte già approvate.

## Input da ricevere e procedura di ripresa

Il 27 ottobre gli input esterni erano da ricevere. Il **3 novembre** il responsabile ha fornito `docs/reference/fortran/prog/data/`: **31.115 percorsi di file**, 1.450.145.643 byte logici contando i target degli otto link interni risolti. Sono inclusi `.DS_Store`, copie/varianti e output storici: questo conteggio non identifica altrettanti input indipendenti. Inventario SHA-256, card, copertura nominale per run e audit riproducibile sono conservati in `results_test/geant4-input-recovery-20261103/` come evidenza locale della consegna. Originali e link rimangono al loro posto; nessun eseguibile legacy avviato. Il sottoalbero originale è escluso da Git; la documentazione non ne promette disponibilità remota.

| Input | Stato al 3 novembre | Prossima verifica |
| --- | --- | --- |
| `INP_LAGGEN/channel.mat`, card `laggen.dat` e relative fonti | Recuperati in `data/inp_laggen/`, incluse otto varianti `.mat` e `sigma_pi0.dat`; hash acquisiti | Associazione ID/reazione/variante, griglia energetica, unità/frame/BR e fonte fisica; vedere discrepanze sotto |
| Database e calibrazioni PREAN | Recuperati 29 `base/data*.base`, directory `calib_*`, `lincorr.dat`, `strip_geom.cal`, `strip_coinc.cal` e `barrel_adc.cal` | Validare contenuto e scelta per run, soglie, trigger, dead channels e tempo zero; la presenza del filename non certifica questi aspetti |
| Profili fascio HBOOK `gl*.hist` e configurazione `BEAM` | Presenti tutti i sei `gl{h,v}{300,351,514}.hist`, più `tag.hist`, in `data/simul_beam/`; card BEAM recuperate | Leggere istogrammi HBOOK e verificarne unità/supporto/normalizzazione; associare la card al periodo effettivo |
| `libclusC`/sorgente `COUNT_CLUSTER_CA`, se l'automa è quello usato | Non recuperati nell'audit; i due `clusc.inc` trovati sono include, non la libreria | Identificare algoritmo usato; frontier disponibile, senza equivalenza automatica con l'automa |
| Controlli cariche e metadati del setup effettivo | Nessun campione indipendente di validazione certificato dalla consegna; presenti anche output legacy in `out_*` | Identificare dati di controllo, purezza/fondo, separazione dal tuning e lunghezza attiva per run |

**Copertura dei filename:** confrontati i 2.711 run distinti del catalogo corrente. Tutti i 1.831 run su P hanno i file BGO `.cal/.ped`, tagger, barrel e wall. Le strip mancano nominalmente per sette run P: 3236, 3705, 3714, 3726, 4174, 4175, 4176. UV 1998 (179 run), UV 1999 (339) e VIS 1999 (110) hanno tutte e sei queste famiglie presenti. Per D, i 303 run dei periodi 2005_d1/2005_d2/2006_d non hanno i sei filename di calibrazione cercati; mancano anche `base/data30.base` e `data31.base`. Altri 12 run D hanno lacune strip, elencate nell'evidenza. Questo audit non ha risolto eventuali fallback o archivi compressi. Nella cartella `flux/` mancano i file dei run 1321, 1322, 1324 e dei 129 run 2006_d; ciò non cambia la politica né la disponibilità del flusso nell'analisi corrente.

**Tabelle da riconciliare:** `channel.mat` contiene 65 intestazioni; `gen_init.F` consuma solo i primi 64 blocchi. Il loro formato numerico è leggibile: 50 energie × 19 valori, 60.800 valori finiti non negativi. `channel_last.mat` contiene 64 blocchi; le altre varianti sono tabelle a 60 canali o frammenti, non sostituti completi per questo reader. Le etichette ECDM vanno da 1,05 a 3,50, mentre `gen_evt.F:37–50` associa l'indice 1 a W=1,00: discrepanza di 0,05 GeV da chiarire prima dell'importazione. Il reader salta le etichette. La card `laggen.dat` recuperata indica `TARG 2 2` (deuterio corto), non è un preset approvato per i run P. Nessuna di queste convenzioni viene corretta implicitamente.

Percorsi e hash sono ora registrati. Proseguire con riconciliazione delle tabelle e lettura delle calibrazioni dei primi periodi P completi, quindi congelare una configurazione esplicita con controlli indipendenti. Rieseguire i test del confine interessato, i benchmark fisici e il calcolo di efficienze/fondo prima di promozione. Il recupero degli input non aggiorna automaticamente risultati o certificazioni precedenti. Il [piano](https://github.com/AntoninoFulci/GRAAL_Analysis/blob/main/docs/plans/2026-10-26-geant4-bdt-execution.md) mantiene aperti i task fisici che ne dipendono.
