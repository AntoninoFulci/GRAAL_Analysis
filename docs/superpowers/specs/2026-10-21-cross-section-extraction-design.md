# Estrazione delle sezioni d'urto γp → pηπ⁰

Data: 21 ottobre 2026. **Disegno approvato dall'utente con «Sì»; implementazione autorizzata.**

## Obiettivo e decisioni già confermate

L'utente richiede l'estrazione delle sezioni d'urto e il confronto con Ajaka,
preceduti da una verifica degli ingredienti disponibili. Per il bersaglio si
devono cercare prima fonti di letteratura e chiedere soltanto ciò che resta
specifico dei nostri dati. L'utente conferma disponibilità della simulazione
originale GEANT3 tramite Docker Hub `afulci/ubuntu77`, con OrbStack su Mac.
L'ambiente e il suo contenuto devono essere verificati prima dell'integrazione.

Verifica completata per immagine `v2.8`, fissata a digest: presenti GEANT3,
CERNLIB, sorgenti e binari LAGGEN/LAGDIG, steering card e calibrazioni.
Container avviato su OrbStack; simulazione fisica non ancora eseguita.
Inventario e riferimento immutabile in [`resources/geant3`](../../../resources/geant3/README.md).

Aggiornamento utente: spessore del bersaglio dei nostri run non noto; cercarlo
nelle configurazioni e negli archivi sperimentali. Per il flusso l'utente
richiede **di assumere per ora che sia già assoluto e corretto**. Il primo
sviluppo userà questa assunzione esplicita, senza riapplicare monitor/tagging/
live time. Provenienza e incertezze restano da verificare prima di presentare
il risultato come misura assoluta validata; nessun errore viene assunto zero.

Proposta: primo risultato σ(Eγ) in μb e confronto con Fig. 2 di Ajaka;
successivamente dσ/dM delle tre coppie e confronto con Fig. 3, dopo recupero
delle finestre energetiche del paper. Priorità comprese nel disegno approvato.
Fig. 4 e relativi CSV esistenti
descrivono Σ, un'altra osservabile.

## Stato verificato nel repository

- `00_common/physics/cross_sections.py` modella pesi di fondo MC; non è
  estrattore di sezioni d'urto. Il registro vieta una σ di riferimento per il
  segnale, per evitare una normalizzazione circolare.
- `08_observable_extraction/` possiede lettori di eventi, flussi, stime del
  fondo e covarianze riutilizzabili. Il nuovo calcolo appartiene a questo
  livello; non va inserito nei pesi del training.
- Baseline corrente: BDT + pairing, senza fit cinematico 6C. Confronto con
  solo pairing deve usare la propria efficienza. Riferimento aggiornato:
  `docs/runbooks/full-pipeline.md`, non le vecchie descrizioni della baseline.
- `read_run_universe` legge conteggi inclusivi per run/stato, precedenti ai
  tagli di ricostruzione. Questi, oppure un manifesto esplicito verificato,
  devono definire l'esposizione, anche per run con zero candidati finali.
- `06_calibration/build_strip_energy_flux.py:write_calibrated_flux_root`
  calibra l'asse energetico e copia contenuti/errori degli istogrammi,
  troncando contenuti negativi a zero. Questo non certifica correzioni
  assolute monitor/tagging/live time già applicate all'input.
- `AJAKA_CROSS_SECTION` contiene 15 bin uniformi 0.95–1.50 GeV. Il paper
  documenta numero e intervallo, non uniformità: bordi locali da dichiarare.
- Generatore attuale applica smearing; adattatore MC→h85 conserva quattro
  fotoni e un protone per evento, con run/stato/strip fittizi. Non misura
  l'efficienza assoluta dell'apparato e non va usato a tale scopo.
- Recupero flussi: scansione conclusiva del 21 ottobre non seleziona alcuna
  politica. Baseline proposta usa solo flussi misurati validi, rispettando
  esclusioni correnti; nessuna adozione implicita dei flussi ricostruiti.

Il grafo `graphify-out` è stato consultato come orientamento; contiene ancora
percorsi anteriori alla rinumerazione. Le evidenze sopra sono verificate sui
sorgenti attuali, non dedotte dalla sola query.

## Bersaglio e confronto bibliografico

Evidenze e fonti nella [nota di ricerca](../../research/2026-10-21-cross-section-target-ajaka.md).
Ajaka usa LH₂ lungo **12 cm**. Altri campioni GRAAL usano 3 o 6 cm;
ρ≈0.07 g/cm³ a 18 K è indicazione di apparato, non calibrazione certificata
dei nostri periodi. Il codice richiederà densità areale di protoni e relativa
incertezza, con fonte e associazione ai periodi. Nessun default assoluto
ricavato combinando parametri approssimati di campioni diversi.

Ispezione del simulatore aggiunge un vincolo: `lagdata.F` assegna lunghezze
**11.1/6.12/3 cm**, mentre `lagmat.F` usa densità H₂ **0.071 g/cm³**.
La differenza fra 11.1 cm del codice e 12 cm descritti da Ajaka resta da
spiegare; non si può scegliere automaticamente uno dei due valori per i run.

Fig. 2 include già sistematica complessiva ≈7% nelle barre pubblicate.
Fig. 3 usa μb/MeV, sebbene l'ascissa massa sia in GeV. Il paper cita
BR(η→γγ)=0.3938: occorre dichiarare convenzione dei decadimenti della nuova
analisi, inclusa π⁰→γγ, e applicare ogni BR una sola volta.

## Catena proposta e invarianti

1. Congelare campagna, universo run inclusivo, esclusioni, modelli BDT,
   selezioni, configurazioni del bersaglio e stato delle correzioni di flusso.
   UV/VIS e periodi restano separati fino alla combinazione delle luminosità.
2. Produrre MC GEANT3 con identità evento conservata dal generato al
   ricostruito. Il denominatore include tutti gli eventi generati validi,
   anche quelli non rivelati; il numeratore attraversa trigger, selezione,
   pairing e BDT coerenti coi dati. Campione di efficienza indipendente dal
   training e dalla scelta della soglia BDT. Se GEANT3 non simula un effetto,
   documentare calibrazione esterna e incertezza, senza assumerlo unitario.
3. Estrarre rese di segnale con fondo e incertezze propri dei dati correnti.
   Riutilizzare geometria sideband e strumenti esistenti ove adeguati;
   correlazioni della resa non si ottengono copiando formula di correzione
   di Σ. Non adottare la percentuale di fondo pubblicata da Ajaka.
4. Costruire efficienza/risposta per energia e cinematica rilevante. Verificare
   migrazioni energetiche, dipendenza angolare e modello di produzione con
   closure. Un rapporto MC selezionato/generato per sola energia è utilizzabile
   soltanto se validato. Celle senza copertura non ricevono ε=1 né contributo
   implicitamente nullo a una quantità chiamata totale: distinguere misura
   fiduciale ed estrapolazione, con incertezza di modello.
5. Trattare separatamente stati POL1/POL2 fino alla correzione d'accettanza.
   Una somma grezza non elimina automaticamente modulazione polarizzata se
   esposizioni e accettanza differiscono. Correggere dipendenza azimutale e
   verificare integrazione su 2π; BREM resta inizialmente controllo separato.
6. Normalizzare con luminosità coerente e combinare periodi compatibili.
   Per un periodo e bin energetico, dopo correzione del fondo, accettanza,
   migrazioni e polarizzazione, la relazione di controllo è:

   `σ[μb] = N_corr / (Nγ × n_p × B × 10⁻³⁰)`.

   Qui `n_p = ρ L N_A / M_H` in cm⁻²; `B` include solo BR non già comprese
   nell'efficienza. La formula scalare richiede validità della media entro
   bin; usare risposta/integrazione coerenti quando variazioni entro bin sono
   rilevanti. Nessuna divisione per ΔEγ per σ(Eγ). Per dσ/dM, dividere per
   larghezza del bin di massa nell'unità dichiarata.
7. Scrivere ROOT con rese, esposizioni, efficienze, stato dei bin, covarianze
   e provenienza; grafici sotto `results/<campagna>/cross_sections/`.
   Scale comuni di bersaglio/flusso/BR restano correlate fra bin. Un errore
   sconosciuto non diventa zero e una resa netta negativa non viene troncata
   silenziosamente.
8. Acquisire tabella originale Ajaka oppure digitalizzare punti e barre con
   provenienza e incertezza. Nessuna riscalatura per far coincidere i risultati.
   Confrontare medie energetiche compatibili; non inventare bordi Fig. 3.
   Overlay prima di χ²: eventuale sovrapposizione dei campioni GRAAL e
   covarianze comuni impediscono di assumere indipendenza automaticamente.

## Architettura minima proposta

Un entry point per sezioni d'urto nello Stage 08, con nucleo numerico separato
da ROOT, riuso dei lettori/calibrazione e scrittore dedicato agli output.
Adattare ingresso GEANT3 nel livello che già prepara/seleziona MC, dopo aver
ispezionato formato reale. Nessun framework generico per simulatori, nuovo
servizio o dipendenza prevista. Congelare immagine Docker mediante digest;
risorse del progetto documentano ambiente e accesso, non contengono layer
Docker in Git. Schema dettagliato e comandi di produzione dipendono dal
contratto GEANT3 effettivamente disponibile.

Vincoli d'integrazione già individuati: `TARG 2 2` nella card generica è
deuterio, quindi va sostituito con configurazione fisica intenzionale;
polarizzazioni LAGGEN 1=orizzontale/2=verticale richiedono mapping rispetto
alla pipeline; wrapper storici usano `qsub`; output generato `outev.dat`
ha percorso fisso e impone isolamento delle esecuzioni. Identificare canale
γp→pηπ⁰ dai sorgenti, non da nomi di file ambigui o da decadimento η→π⁰γγ.

## Prove minime prima del risultato fisico

- Identità generato→ricostruito, conteggio perdite, selezioni e geometria.
- Closure con σ nota e fondo controllato, indipendente da Ajaka; includere
  luminosità H/V diverse, accettanza azimutale e variazioni del modello.
- Invarianza del risultato suddividendo un periodo; conservazione esposizione
  per run senza candidati; stesso insieme di run per resa ed esposizione.
- Controlli unità cm²/μb e GeV/MeV, BR contato una volta, efficienza nulla,
  migrazioni significative, bin senza supporto e propagazione covarianze.
- Prova integrata piccola con GEANT3 prima di produzione estesa.

## Questioni ancora aperte

1. Verificare immagine completa, sorgenti/librerie GRAAL, steering card,
   geometria/trigger e formato degli eventi generati e rivelati.
2. Associare a nostri periodi spessore del bersaglio e incertezza (utente non
   dispone del dato); accertare correzioni e incertezze dei flussi esistenti.
   Per iniziare, flusso già assoluto/corretto assunto su indicazione utente.
3. Definire trattamento pareti/accidentali con dati o controlli disponibili.
4. Recuperare dati e finestre energetiche Ajaka; verificare sovrapposizione
   temporale con campione corrente. Il confronto Fig. 3 quantitativo dipende
   da questi dettagli.

La disponibilità di un ambiente compilabile consente di iniziare integrazione
MC; da sola non dimostra validità della normalizzazione assoluta. Questo
documento non dichiara completata estrazione né autorizzata una nuova campagna.

Revisione di costruibilità indipendente eseguita il 21 ottobre: confermate
le quattro questioni aperte sopra; nessun ulteriore requisito bloccante
individuato. Il riferimento Docker verificato è documentato in
[`resources/geant3`](../../../resources/geant3/README.md).


Aggiornamento del contratto MC dopo chiarimento utente: catena necessaria
**LAGGEN/GEANT3 → LAGDIG (digitalizzazione) → PREAN → conversione e pipeline
corrente**. Verificata nei sorgenti lettura `.hit` da LAGDIG, scrittura `.dig`
con ADC/TDC, tagging/trigger, lettura `.dig` da PREAN in LSIMUL e scrittura
`.pol` per analisi. Conservare identità e denominatore prima di tutte le
perdite; verificare configurazioni per periodo e compatibilità dello schema
MC/dati dopo conversione. Dettagli e limiti degli identificativi nella
[risorsa GEANT3](../../../resources/geant3/README.md). Prova completa dei tre
programmi ancora da eseguire; nessuna efficienza fisica certificata.
