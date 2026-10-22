# Estrazione nativa e confronto Ajaka: risultato diagnostico

Campagna autorizzata da100.000 eventi completata su trima. Catena
LAGGEN→GEANT3→LAGDIG→PREAN→h2root→selezione/BDT corrente eseguita.
L’estrattore produce numeri e confronto Fig.2, ma **accettanza e modello
del fondo non sono validati**: questi valori non costituiscono ancora una
misura della sezione d’urto.

Nuova indicazione dell’utente: **prove sui dati1998_uv; estrazione finale su
tutti i periodi**. La campagna2002_uv1 già terminata resta diagnostica.
Non viene rietichettata1998: configurazioni delle camere planari, base e
calibrazione PID differiscono. Per1998 la mappatura provvisoria disponibile
è periodo09, run1321, OLD_CYL/OLD_PLAN, data09.base e calib_1400.cal.

## Prodotti e risultato numerico

[Confronto PDF](../../results/cross-section-native-total-20261021/cross_sections.pdf),
[ROOT](../../results/cross-section-native-total-20261021/cross_sections.root),
[risultato e audit JSON](../../results/cross-section-native-total-20261021/result.json),
[tabella CSV](../../results/cross-section-native-total-20261021/diagnostic_points.csv).
PDF renderizzato e controllato: titolo e legenda dichiarano risultato
diagnostico. Nessun riscalamento sui punti Ajaka.

| Eγ (GeV) | σ diagnostica (μb) | Errore condizionale (μb) |
|---|---:|---:|
|1.10–1.15|11.51|12.36|
|1.15–1.20|20.91|2.60|
|1.20–1.25|18.42|2.72|
|1.25–1.30|27.22|4.97|
|1.30–1.35|27.64|6.04|
|1.35–1.40|28.96|5.70|
|1.40–1.45|22.61|5.45|
|1.45–1.50|39.45|13.29|

Ajaka cresce circa da1 a3.5μb nell’intervallo coperto. Discrepanza grande;
non interpretata come effetto fisico. Nessun rapporto bin-a-bin o test
statistico contro il paper: bordi energetici e correlazioni non conosciuti.

Fit GLS su16.333 candidati osservati e14.822,20 rese nette condizionali:
χ²=2145,43 per110 gradi di libertà, con **sola covarianza delle rese**.
Aggiungendo covarianza MC della previsione al residuo post-fit si ottiene
337,64: controllo diagnostico, non nuovo fit e non p-value calibrato.
Rumore MC domina la varianza della previsione; errori riportati sono
propagazioni gaussiane al primo ordine. Numero di condizionamento35,61.

Regione vera0.95–1.1GeV trattata come contributo libero:19 eventi migrano
nella selezione. σ guard=21,85±75,20μb, scarsamente determinata. Regione
fra soglia fisica e0.95GeV non simulata: migrazione residua da quantificare.
Ultimo intervallo generato termina a1.4875GeV, limite del generatore.

## Contabilità e verifiche MC

| Passaggio | Smoke | Produzione | Totale |
|---|---:|---:|---:|
|Generati completi|100|99.900|100.000|
|LAGDIG/PREAN h70|100|99.585|99.685|
|Preselezione h85|75|73.455|73.530|
|Ricostruzione finale BDT|1|629|630|

Produzione: nessuna perdita tagging,315 perdite trigger, nessuna perdita
prima del digitizzatore. Conteggi h70 corrispondono al log PREAN/LAGDIG.
Identità complete fino99900;202 candidati selezionati hanno ID>65535.
Decadimenti forzati η/π⁰→γγ verificati:199.800 decadimenti nel lotto
principale, residuo massimo dei quadrimpulsi1.68×10⁻⁷GeV e massa quadrata
massima dei fotoni2.81×10⁻⁷GeV². Energia generata uniforme nel range richiesto.

Probe GTGAMA passato nativamente; tutte e tre le varianti diagnostiche
passano su trima. Libreria GEANT storica mantenuta: nessuna sostituzione
GTGAMA o hotpatch adottata. Vecchi fallimenti OrbStack restano documentati.

`native_validation.py` vincola card esatta, hash binari nativi, terminatori,
conteggi, decadimenti, truth completa e archivio ricostruito. Campioni
duplicati per truth o semi rifiutati. Manifest per campione in
`native-uniform-*/reconstruction/validation.json`.

## Perdita nell’identificazione del protone

Diagnostica riproducibile:
[script MC](../../results/cross-section-native-total-20261021/diagnostics/inspect_mc_pid.py),
[conteggi](../../results/cross-section-native-total-20261021/diagnostics/mc_pid.json).

Dopo preselezione, energia ricostruita1.1–1.5GeV e almeno quattro fotoni,
16.098 eventi MC restano disponibili. Solo1.637 hanno esattamente un protone;
14.409 ne hanno zero,51 ne hanno due e1 ne ha tre. Questo requisito conserva
circa10,2% dei candidati, prima del BDT. Efficienza condizionale per angolo
vero del protone:6,6% a0–10°,9,2% a10–20°,18,2% a20–30°.

Questo localizza una perdita importante nella regione in avanti; **non
dimostra ancora una calibrazione errata**. Servono confronto PID sui dati
1998_uv e configurazione MC corrispondente, più verifica di TOF/ΔE e modello
di produzione. Non si allargano i tagli né si moltiplica l’accettanza per
far coincidere Ajaka.

Diagnostica1998_uv eseguita su trima, risultati aggregati conservati in
`/data/graal/GRAAL_Analysis/results/cross-section-1998-pid-20261021/`.
Recupero locale del solo JSON aggregato completato dopo esplicita
autorizzazione dell’utente. Hash remoto e locale coincidono:
`c96a1083b36bd75bd6f196fd2f49f5d34938c6328a21796dd5e5e90d580d9bd7`.
Nessun evento o file ROOT sperimentale trasferito. Ricevuta:
[`data_1998_pid_receipt.json`](../../results/cross-section-native-total-20261021/diagnostics/data_1998_pid_receipt.json).
Lo script locale è `diagnostics/inspect_1998_pid.py`.

Aggregato prima del BDT e delle maschere di esposizione:416.461 eventi con
POL1/2, Eγ1.1–1.5GeV, almeno quattro fotoni e una traccia carica in avanti.
Di questi247.325 hanno esattamente un protone ricostruito (**59,39%**),
159.382 zero e9.754 più di uno. Somma dei tre conteggi verificata.
Istogramma80×100:369.834 eventi nei limiti disegnati,46.627 fuori;
le frazioni usano il campione completo.

[Diagnostica TOF–ΔE con tagli originali](../../results/cross-section-native-total-20261021/diagnostics/pid_1998_data_and_existing_mc.png)
mostra separatamente dati1998_uv e MC2002_uv1. La banda MC cade spesso sotto
il bordo inferiore del proprio taglio PID; questo motiva una verifica di
calibrazione, ma non ne dimostra la causa. Dati contengono fondo e MC solo
segnale; geometria, tagli e scala ΔE memorizzata differiscono fra periodi.
**59,39%/10,17% non è un rapporto di efficienze del segnale** e non giustifica
alcun riscalamento della sezione d’urto. Serve MC coerente con periodo09.

Input1998_uv locali già verificati:166 run con esposizione valida,
10.487 candidati osservati e9.997,224±105,201 rese nette condizionali.
Configurazione `results/cross-section-inputs-20261021/campaigns/total_1998_uv_trial.json`;
audit e riepilogo rese nella stessa directory. Stato del fondo ancora
`provisional_model_inadequate`; risposta periodo09 ancora da validare.

## Correzioni inferenza e lavoro residuo

- Risposta usa maschere `(run, strip)` identiche ai dati, pesate con flusso
  e flusso polarizzato di ciascun run. La maschera del run tecnico3629 non
  rappresenta da sola l’intero periodo.
- Momenti MC di1 e cos(2φ) integrati sugli eventi generati, perdite incluse;
  covarianza comune fra H/V. Revisione indipendente e test di derivate GLS.
- Bersaglio provvisorio12cm LH₂, densità0.071g/cm³; flusso assunto assoluto.
  BR=0.389164974 applicata una sola volta. Conferma per periodo e sistematiche
  complete restano TODO espliciti.
- Modello delle rese nette fallisce le prove di adeguatezza: da correggere.
- Risposte per1998_uv e altri periodi, più differenziali Fig.3, ancora da
  validare. Digitalizzazione/riproduzione Fig.2 e3 già disponibili.

Verifiche software:102 test Stage03 e314 Stage08 passati; un warning
preesistente sulla legenda. Modifiche Docker conservate nel
[registro aggiornamento](../runbooks/geant3-docker-upgrade.md).
Nessun commit, push Docker o ulteriore lotto oltre100.000 eventi.
Controlli mirati dopo aggiornamento diagnostico:32 test passati; ROOT riaperto
e PDF finale nuovamente renderizzato e controllato.
