# Sezioni d'urto per generazione e risposta GEANT4: fonti

Verifica mirata: **27 ottobre 2026**. Ambito: i nove canali neutri di
`00_common/physics/channels.py`, su protone libero, nel fascio
`Eγ ≈ 0.9313–1.5 GeV` (energia del fotone nel laboratorio). Questo inventario
supporta il piano di efficienze e fondo residuo; non costituisce una nuova
parametrizzazione né una validazione della simulazione. La sezione LAGGEN sotto
documenta anche gli originali locali resi disponibili nella stessa giornata.

## Cinque fonti sperimentali da riconciliare con le tabelle locali

| Fonte primaria | Contenuto verificato e copertura utile | Limiti della lettura |
| --- | --- | --- |
| **Ajaka et al., PRL 100 (2008) 052003**, [record degli autori](https://art.torvergata.it/handle/2108/34799), [DOI](https://doi.org/10.1103/PhysRevLett.100.052003) | `γp → pηπ0`: GRAAL ha pubblicato sezioni totali, differenziali e asimmetria del fascio dalla soglia a 1.5 GeV. Copre quindi il segnale nell'intervallo richiesto. | Letto l'abstract nel repository istituzionale; PDF non letto. Variabili differenziali, frame, unità, bin e convenzione BR devono essere verificati sul PDF/tabella prima dell'importazione. L'esistenza della misura è accertata; qui non se ne importa alcun valore. |
| **Kashevarov et al., PRC 85 (2012) 064610**, [articolo APS](https://journals.aps.org/prc/abstract/10.1103/PhysRevC.85.064610) | `γp → pπ0π0`: totali e differenziali da soglia a 1.4 GeV con CB/TAPS a MAMI. È una fonte candidata per `pi0pi0`. | Letto l'abstract: dettagli di distribuzioni, BR e unità ancora da verificare. Il tratto 1.4–1.5 GeV richiede un'altra tabella o una scelta esplicita di modello; non è coperto dall'intervallo dichiarato nell'abstract. |
| **Starostin et al., arXiv:1101.3744**, [testo e Table I](https://arxiv.org/pdf/1101.3744) | `γp → p3π0` diretto, con fondo `η → 3π0` sottratto. Table I: σ totale in μb, energie tabulate fino a 1434 MeV; per esempio `1.808 ± 0.019 μb` a `1255 ± 6 MeV` (errore su σ solo statistico). §III stima il sistematico al 15%. Fig. 6: differenziale nell'angolo del protone di rinculo nel CM; sono discusse anche distribuzioni di massa/Dalitz. | Non è una densità esclusiva completa. Non riclassificare il contributo η come parte del canale diretto. Unità precise della differenziale e trattamento BR dei π0 da verificare prima di importare. L'estensione 1.434–1.5 GeV richiede una scelta documentata. |
| **Junkersfeld et al., EPJ A 31 (2007) 365–372**, [arXiv:0704.0710, §§3.2–3.3 e tabelle](https://arxiv.org/html/0704.0710v1) | `γp → pπ0ω` da soglia a 3 GeV. Table 3: primo bin **1383–1817 MeV**, σ totale `0.49 ± 0.13 μb`. Tables 1–2: `dσ/dΩ` in μb/sr rispetto a `cos θω` e `cos θπ0` nel CM; è presente anche `dσ/dt`. Il totale include extrapolazioni nelle zone di bassa accettanza. | Il primo bin attraversa il limite superiore GRAAL: `0.49 μb` non è una misura puntuale a 1.60 GeV né la media del solo tratto GRAAL. Verificare esplicitamente la correzione BR dell'intera catena `ω → π0γ`, `π0 → γγ` prima di usare una tabella. |
| **Crede et al., PRC 80 (2009) 055202**, [arXiv:0909.1248, §§IV–V](https://arxiv.org/html/0909.1248v2) | `γp → pη` e `γp → pη′`: totali e `dσ/dΩ` rispetto all'angolo del mesone nel CM. Intervallo complessivo dichiarato `Eγ = 0.85–2.55 GeV`; per η′ vale la propria soglia. §IV divide per le BR della catena osservata: le sezioni pubblicate sono di **produzione**, non già moltiplicate per il decadimento neutro. `ΔΩ = 2π Δcos θCM`. Fonte per `eta_via_3pi0` e `etaprime`. | L'intervallo complessivo non garantisce da solo ogni bin vicino alla soglia η′ (~1.447 GeV). Verificare bordi effettivi e unità di ciascuna tabella numerica. Le BR usate dall'articolo sono storiche: conservarle nella provenienza, senza confonderle con la convenzione scelta per nuovi decadimenti. |

**Correzione bibliografica da pianificare:** il registry associa il canale
`3pi0` sia ad arXiv:1101.3744 sia a «Kashevarov, PRC 85, 064610».
Sono lavori differenti: il primo è Starostin/3π0, il secondo Kashevarov/2π0.
Il valore `1.808 μb` è effettivamente nella Table I del primo. Questa nota non
modifica i valori storici o il codice.

## Applicazione ai nove canali

| Canali del registry | Decisione da preparare |
| --- | --- |
| `eta_pi0` | La misura Ajaka può fornire una proposta di generazione o una forma da confrontare per l'efficienza. Lasciare libera la normalizzazione del segnale estratto e verificare la dipendenza dell'efficienza dalla forma proposta; non usarla come vincolo circolare sull'estrazione. |
| `eta_pi0_via_3pi0` | Stessa produzione di `eta_pi0`, altro decadimento. La normalizzazione relativa usa il rapporto delle BR delle catene e le rispettive efficienze; non una seconda sezione di produzione indipendente. |
| `pi0pi0`, `3pi0`, `omega_pi0` | Collegare le tabelle della reazione esatta sopra, distinguendo la normalizzazione totale dalle forme differenziali e dai decadimenti. |
| `etaprime`, `eta_via_3pi0` | Usare rispettivamente la produzione η′ e η; applicare una sola volta le BR delle catene simulate. Separare η′ risonante dagli eventuali contributi diretti allo stesso stato stabile. |
| `eta_2pi0`, `4pi0` | Nessuna misura dedicata è stata verificata in questa ricerca limitata. Questo **non dimostra assenza di misure**. Verificare prima `laggen` e le sue referenze; gli attuali numeri del registry restano stime, non acquisiscono lo status di dati sperimentali. Una scelta di modello richiede fonte, dominio e variazioni dichiarati. |

## Modelli esterni: domini da rispettare

| Modello / fonte primaria | Uso pertinente e limite |
| --- | --- |
| **MAID2007**, [Drechsel, Kamalov, Tiator](https://arxiv.org/abs/0710.0306) | Modello di produzione di **un pione** sul nucleone; l'abstract descrive 13 risonanze sotto 2 GeV. Questa lettura non certifica il limite numerico di una specifica interfaccia. Non trasferire il modello a ηπ0 o a 2/3/4π0. Nessuno dei nove canali è singolo π0. |
| **EtaMAID2018**, [Tiator et al., §IV.2](https://arxiv.org/html/1807.04525v2) | Produzione di **un η o un η′** su p/n. Il lavoro analizza i quattro canali fino a `W = 4.5 GeV` (`Eγ ≈ 10 GeV`); non confondere W con Eγ. Candidato per `eta_via_3pi0` e `etaprime` nel dominio pertinente; non descrive direttamente ηπ0 o η2π0. |
| **Two-Pion MAID**, [interfaccia ufficiale](https://maid.kph.uni-mainz.de/twopion/), [Fix–Arenhövel, EPJ A 25 (2005) 115](https://arxiv.org/abs/nucl-th/0503042) | Totali e differenziali esclusive a cinque variabili per **due pioni** sul nucleone. Il paper studia dalla soglia a `Eγ = 1.5 GeV` e segnala sottostima di π0π0 vicino alla soglia. La parte sul deuterone usa impulso + rescattering NN, trascurando πN e ππ: non equivale a prendere due volte il protone libero. Non è un modello ηπ0, 3π0 o 4π0. |
| **SAID**, [servizio GWU e istruzioni](https://gwdac.phys.gwu.edu/), [fit pionico 2012](https://doi.org/10.1103/PhysRevC.85.025201) | Il portale distingue produzione pionica, η e η′. Il fit pionico citato copre fino a `Eγ = 2.7 GeV`; non estendere tale limite automaticamente a ogni soluzione del portale. Le istruzioni richiedono energie in MeV e avvertono sui limiti delle singole soluzioni. Non interpretare gli altri processi elencati, incluso πD elastico, come un generatore universale γD multimesonico. |

Una fonte di produzione sul nucleone libero non determina da sola una reazione
su deuterio: servono una scelta esplicita del nucleone colpito, moto di Fermi,
spettatore, stato finale coerente/incoerente e interazioni finali. Nessun
trasferimento automatico p → D è autorizzato da questo inventario.

## Contratto minimo prima di importare una tabella

Registrare reazione e target, Eγ(lab) oppure W con unità, bordi dei bin,
σ totale oppure densità differenziale con variabili/frame/Jacobiano, unità,
BR incluse o rimosse, errori e correlazioni disponibili, copertura reale e
regole per interpolazione/extrapolazione. Una proiezione 1D non determina tutte
le correlazioni di uno stato a molti corpi; i gradi di libertà non misurati
richiedono una scelta dichiarata e un confronto di efficienza/fondo residuo.

GENBOD resta una proposta valida di spazio delle fasi se i suoi pesi e quelli
della densità fisica vengono trattati coerentemente. Le sezioni totali fissano
i rate; le differenziali guidano la distribuzione cinematica. Verificare che
l'integrazione delle forme riproduca il totale e che BR, flusso e accettanza
entrino una sola volta. Questa è preparazione degli input di simulazione e non
riattiva lo stage 09 ritirato.

## Riscontro sugli originali LAGGEN locali

Lettura statica del **27 ottobre 2026**, sotto
`docs/reference/fortran/prog/{laggen,laggen_vale}/`. Nessun binario eseguito,
nessun originale o `.gitignore` modificato. I percorsi abbreviati sotto sono
relativi a queste due directory; le righe indicate valgono per `laggen` salvo
indicazione diversa. Questi sorgenti provano la presenza di una infrastruttura
di sezioni totali e differenziali, ma non provano che ogni tabella sia una misura
assoluta pubblicata né che copra i nove canali moderni.

| Confine | Riscontro concreto |
| --- | --- |
| **Totali incorporati** | `include/sigto.inc:4–5` dichiara `WR(251), SIGR(64,251)`. `src/blockdata.F:23–49` contiene la griglia `W = 1.00…3.50` a passo `0.01`; dal passaggio `EV_NUC:139` e `CHANNELEX:145` si identifica W come energia CM in GeV, non Eγ(lab). Le serie sono inizializzate nello stesso `blockdata.F`, per esempio 19 a riga381, 33 a766 e 35 a768. L'unità assoluta di SIGR non è dichiarata in questi include/reader: prima dell'importazione va riconciliata con le fonti originali. |
| **Uso delle totali** | `src/totalsect.F:302–315` somma SIGR dei canali scelti, costruisce l'istogramma10 e moltiplica lo spettro del fascio9/18. `src/channelex.F:145–146,207–214` interpola linearmente in W, normalizza alla somma e campiona il canale. Alcuni canali n sono ottenuti per uguaglianze/fattori dai p (`124–142`): non sono automaticamente misure neutroniche indipendenti. |
| **Differenziali esterne** | `src/gen_init.F:73–97` legge **`$INP_LAGGEN/channel.mat`** (oppure il percorso storico Condor `/home/gmandaglio/graal/data/inp_laggen/channel.mat`): 64 blocchi, 50 righe energetiche per blocco, 19 valori angolari per energia. Il formato è `20X,5G10.3` seguito da `7G10.3` (`122–124`); l'intestazione viene saltata. `include/xsect.inc:5` conferma `XSECT(64,50,0:18)`. Il reader non legge unità, bibliografia o BR. |
| **Frame, griglia e campionamento** | `src/gen_evt.F:37–65` interpreta le righe come `dσ/dΩ(W,θ)` nel CM, con `W_i = 0.950 + 0.050 i GeV`, `i=1…50`, e nodi `θ=0°,10°,…180°`. Interpola in W e θ, moltiplica per `sin θ`, quindi campiona θ/φ con accettazione-rifiuto (`80–148`), includendo i termini di polarizzazione configurati. Le unità assolute si cancellano in questa estrazione di forma: ciò non certifica la normalizzazione assoluta del file. La densità orienta la prima particella di produzione (`154–168`). |
| **GENBOD** | `src/ev_nuc.F:58` imposta `KGENEV=1`; a `271–277` chiama GENBOD per i canali multibody elencati, incluso35 (`pπ0π0`). Il secondo livello di decadimento usa ancora GENBOD (`405–407`). Per 15–18 e23–26 c'è inoltre un rifiuto in `exp(3t)` (`108,313–324`): non tutto il multibody è puro spazio delle fasi. |
| **Peso esposto ma non verificato end-to-end** | `include/genbod.inc:5–7` espone `WT` in `/GENOUT/`; `src/openntuple.F:51` lo registra nell'ntuple HBOOK, in entrambe le varianti. Nella ricerca testuale di tutti i `.F`/`.inc` delle due directory non appare un uso di WT per pesare o rifiutare l'evento, né un accumulo esplicito dei pesi di produzione e decadimento. Una nuova chiamata GENBOD riutilizza lo stesso `/GENOUT/`: la conservazione del peso complessivo va quindi auditata. Non è stato verificato l'uso di WT nei consumatori esterni a LAGGEN. |
| **Uscita ASCII specifica di laggen** | `src/ev_nuc.F:1065–1090` scrive sull'unità42 canale, codici particelle, Eγ, vertice e quadrimomenti, **senza WT**. Questo blocco manca in `laggen_vale`. L'esportazione HBOOK del peso non garantisce che il percorso ASCII lo conservi. |

### Differenze che impediscono una copia automatica delle tabelle

- In `laggen/src/channeldef.F:320,330`, i canali19/20 producono **`etap`**,
  mentre `totalsect.F:43–44` li chiama ηp/ηn. In `laggen_vale` le stesse righe
  producono invece **`eta`**. `rmass.F:63` identifica `etap` con massa circa
  `0.95777 GeV`. Il numero o l'etichetta di un canale non bastano a identificarne
  la fisica nello snapshot.
- `laggen/src/channeldef.F:513–540` disabilita i decadimenti interni del33
  (`JDEC=0`, BR commentate); `laggen_vale/src/channeldef.F:513–536` li attiva,
  con cinque BR storiche, compresa `.2085` per ηπ0π0. Queste BR sono scelte di
  decadimento, distinte dalla sezione di produzione.
- `blockdata.F:766` usa per il33 `90*0.,40*1.,121*0.`: una forma a gradino con
  plateau unitario non acquisisce la qualità di misura assoluta perché è in
  una tabella. La provenienza e l'eventuale intento di generazione vanno chiariti.
  Il35 è invece definito esplicitamente come pπ0π0
  (`channeldef.F:553–562`); il21 è **singolo ωp**, non ωπ0p (`338–363`).
  Non sono identificati canali dedicati pηπ0, p3π0 diretto, pη2π0, p4π0 o
  pωπ0 nel registro di queste due copie.
- Il ramo `GEN_EVT_3BODY` per54 in `ev_nuc.F:280–281` è preceduto da un IF
  che già include54 (`271–277`): il commento sulla θη secondo sezione d'urto
  non dimostra che quel ramo sia eseguito. Per il piano interessa preservare
  il metodo, poi verificarne il percorso effettivo.
- `src/montecarlo.F:75–106` estrae normalmente W dallo spettro pesato e lo
  converte a Eγ(lab); esistono anche energia fissa (`IBEAM=0`) e una proposta
  logaritmica separata (`IBEAM=3`, `54–70`). La card/configurazione scelta va
  quindi registrata: non attribuire a ogni esecuzione la stessa legge del fascio.

### Dati esterni ancora da localizzare e impronte

La ricerca dei nomi in `prog/` non ha trovato `channel.mat` né
`sigma_pi0.dat`. Quest'ultimo è letto da `src/gen_init_comp.F:12–28`
per le asimmetrie π0 (30 energie ×19 angoli), non è la tabella delle sezioni
totali. `src/profiles.F:27–36,39–130` richiede inoltre `$BEAM` e file
`gl{h,v}{351,514,300}.hist`; `profiles_services.F:16–47` ne legge gli
istogrammi HBOOK di profilo/spettro. Questi nomi non sono presenti nelle due
directory LAGGEN ispezionate. Sono dipendenze esterne dello snapshot, non prova
che i dati siano perduti.

È stato letto **solo l'elenco** delle 346 voci di `prog/laggen.zip`: non contiene
`channel.mat`, `sigma_pi0.dat` o i file `gl*.hist` richiesti; contiene
`laggen/hist.hist`, il cui contenuto non è stato interpretato. Nessuna estrazione.
Il Makefile (`src/Makefile:1,19–24`) e il log storico citano CERNLIB/GEANT3 e
librerie locali; il sorgente della routine GENBOD non è stato trovato nel corpus
`prog/` per nome. La semantica esatta della versione collegata resta da fissare
con la sua provenienza prima di certificare i pesi.

SHA-256 dei sorgenti chiave, conservati come impronta della lettura:

| File sotto `prog/` | SHA-256 |
| --- | --- |
| `laggen/src/gen_init.F` | `d9d2100ee3d44b63e27073bf415a3504442aa271bf7b58d988c7c7722623e80d` |
| `laggen/src/blockdata.F` | `a4579b98d9dcd69b834d10f75b8f0a6ec18ba0cd49431b2529b3078d3bdddf22` |
| `laggen/src/ev_nuc.F` | `57e6ebd45c6955f4afa952262734247be277a8a02c8b199f7d790a696d4410f1` |
| `laggen/src/channeldef.F` | `e5114b880debbcd39232937eb8e43a433a0626b42a4f9c730fbb9341c5c19c15` |
| `laggen_vale/src/channeldef.F` | `790f18ca238631411586724f65867cdb8067fb60a9ccc276793a4a340c6f22ff` |

`gen_init.F`, `gen_evt.F`, `blockdata.F`, `totalsect.F` e `channelex.F`
sono identici byte per byte nelle due copie controllate; le differenze di
`channeldef.F`, `ev_nuc.F` e `openntuple.F` sono state lette. Il passo utile
successivo è recuperare i datafile esterni e ricostruire per ciascuna reazione
la relazione tra totale, forma angolare, BR e peso GENBOD, prima di adattarli
alla generazione moderna.
