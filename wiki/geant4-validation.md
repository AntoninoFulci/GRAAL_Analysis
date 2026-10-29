# Geant4: requisiti, benchmark e decisioni

Aggiornamento del 27 ottobre 2026, dopo le indicazioni del responsabile scientifico. Questa pagina registra requisiti approvati, riscontri di sorgente e dipendenze ancora aperte. Il [design](https://github.com/AntoninoFulci/GRAAL_Analysis/blob/main/docs/plans/2026-10-26-geant4-bdt-design.md) e il [piano esecutivo](https://github.com/AntoninoFulci/GRAAL_Analysis/blob/main/docs/plans/2026-10-26-geant4-bdt-execution.md) li traducono in lavoro verificabile. Il codice di trasporto corrente resta quello diagnostico descritto nello [stage 03](03-monte-carlo-simulation).

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

Tabelle totali `SIGR` sono incorporate in `blockdata.F`; le differenziali vengono lette da `channel.mat` esterno, non incluso nell'archivio inventariato. Anche database/calibrazioni e alcune librerie sono esterni. `laggen` e `laggen_vale` differiscono nella definizione di canali/decadimenti, e il peso HBOOK non è conservato nell'uscita ASCII: dettagli e limiti sono nella [mappa delle sorgenti fisiche](geant4-cross-section-sources). La preanalisi ROOT attuale consuma già cluster; l'algoritmo frontier è disponibile in `prean`, quello ad automa cellulare dipende da `libclusC` da recuperare.

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

Restano da chiudere: dati esterni `INP_LAGGEN/channel.mat` e card, database/calibrazioni PREAN e libreria dell'automa se usato; mappa run → target/lunghezza; convenzione nominale/attiva e densità di riferimento; trigger e controlli cariche indipendenti; reazioni nucleari se si analizza D; osservabili, binning, precisione richiesta a efficienze/fondo e luminosità. La posizione dei sorgenti `laggen`/`prean` è ora risolta. Sono dipendenze specifiche, non un riavvio delle scelte già approvate.

## Input da ricevere e procedura di ripresa

Il 27 ottobre il responsabile conferma di non avere al momento gli input esterni richiesti e di fornirli successivamente. Stato: **da ricevere dal responsabile**; non si continua a richiederli durante questa ricognizione. Gli originali `prog` già forniti restano disponibili e preservati.

| Input | Uso e verifica alla consegna | Lavoro possibile nel frattempo |
| --- | --- | --- |
| `INP_LAGGEN/channel.mat`, card `laggen.dat` e relative fonti | Hash/versione, associazione dei 64 ID alla variante giusta, griglie/frame/unità/BR, compatibilità con totali e dominio | Reader/contratto su fixture; audit `SIGR`, canali e pesi; fonti sperimentali/modelli |
| Database e calibrazioni PREAN, file run/pedestal/linearità e trigger | Mappa run/periodo, unità, soglie, dead channels, tempo zero e tagli; congelare tuning e controlli separati | Traccia sorgente delle variabili; porting frontier e test di convenzione, senza qualifica fisica |
| Profili fascio HBOOK `gl*.hist` e configurazione `BEAM` | Spettro/spot/stati, supporto e normalizzazione; confronto con input calibrati correnti | Definizione di sidecar beam/vertice, conservazione del quadrimpulso e provenienza |
| `libclusC`/sorgente `COUNT_CLUSTER_CA`, se l'automa è quello usato | Versione/ABI, algoritmo/parametri e confronto con eventi di riferimento | Analisi/porting frontier disponibile; nessuna equivalenza automatica con l'automa |
| Controlli cariche e metadati del setup effettivo | Purezza, bande e risoluzioni indipendenti dal tuning; LH₂/LD₂ e lunghezza attiva per run | Preparazione report benchmark e test strumentali su fixture |

Alla ricezione: registrare percorso e hash senza sovrascrivere sorgenti storici; validare schema/convenzioni, congelare una configurazione completa; rieseguire i test del confine interessato; rifare i benchmark fisici e ricalcolare efficienze/fondo prima di promozione. Il recupero degli input non aggiorna automaticamente risultati o certificazioni precedenti. Il [piano](https://github.com/AntoninoFulci/GRAAL_Analysis/blob/main/docs/plans/2026-10-26-geant4-bdt-execution.md) mantiene aperti i task fisici che ne dipendono.
