# Energia e binning — rapporto del 13 ottobre 2026

## Esito

Piano 08 non era implementato: bordi ancora nominali nei consumer. Usato
**graphify** per mappare dipendenze, poi verificati sorgenti correnti.
Implementato contratto comune `EnergyBinning`, separato dal fascio, con config
JSON e override CLI. Default storici invariati. Nessun commit/reset delle
modifiche dell'agente parallelo; lavorato sul checkout condiviso preservando
periodi/sistematici già presenti.

Chiarimento utente applicato: UV basso sul range VIS `[0.9313,1.10]` e ogni
bin nominale suddiviso al punto medio. Tre config versionate: nominale,
split, UV basso. I comandi sono nel [runbook](../runbooks/energy-binning.md).

## Implementazione e controlli

- Grid comune validata; CLI/config passano a spettro, feature builder,
  ricostruzioni, MC launcher, estrazione, periodi e bootstrap diagnostico.
- Target/laser/polarizzazione rimangono quelli del profilo. Endpoint storici
  oltre Compton conservati; esposizioni fuori dominio restano escluse.
- Cache MC/BDT includono comandi risolti e sorgenti comuni; canali chiusi non
  richiesti dal launcher; generatori mantengono la soglia sull'energia vera.
- Provenance di dataset/modello ammette domini espliciti, senza aggirare il
  controllo del gate. Segnale con peso positivo richiesto in ogni bin dello
  spettro prima di dichiarare un dominio continuo di training. Bin senza
  supporto bloccano il training; non inventano copertura.
- ROOT ricostruiti con dominio dichiarato più stretto vengono rifiutati anche
  tornando al nominale. Espansioni richiedono nuova provenance, inclusi
  sideband/template MC. Compatibilità legacy conservata nel nominale.
- ROOT di estrazione registra bordi effettivi e dichiarazione coerente;
  combiner e plot li consumano. Ajaka sovrapposto solo su intervalli identici.
- Inventario per periodo/bin: conteggi V/H/BREM, flussi, P efficace,
  fit/fallback/bordo, punti mancanti; efficienze ignote restano `null`.

## Campagne locali eseguite

Directory: `results/energy-binning-20261013/`. Input h85 UV locale:
5.341.787 eventi del 1998; VIS dalla baseline locale del 1999. Nessuna
campagna storica sovrascritta. Campioni nominali senza 6C riusati per split;
UV basso ricostruito nuovamente con pairing chi2 senza BDT.

UV basso: 3.803 eventi scritti, 3.707 selezionati con flussi validi, 96 esclusi
per esposizione assente/invalida. Non è un nuovo risultato BDT né una misura
on-shell sotto soglia. Soglia fisica circa 0.931311 GeV, bordo basso storico
0.9313 riguarda energia taggata. Nessun MC sotto soglia vera generato.

Conteggi qui riferiti al campione nominale dello studio: BDT per split,
raw per UV basso. N fit conta proiezioni di massa ed estimatori, non eventi
indipendenti. Inventari completi e bin mancanti in `periods/index.json`.

| Studio | Energia GeV | V | H | V+H | N fit | P efficace V/H |
|---|---|---:|---:|---:|---:|---|
| split/uv | 1.1–1.15 | 531 | 514 | 1045 | 32 | 0.8192/0.8192 |
| split/uv | 1.15–1.2 | 741 | 680 | 1421 | 34 | 0.8581/0.8580 |
| split/uv | 1.2–1.25 | 741 | 757 | 1498 | 36 | 0.8920/0.8920 |
| split/uv | 1.25–1.3 | 862 | 766 | 1628 | 38 | 0.9182/0.9183 |
| split/uv | 1.3–1.35 | 915 | 904 | 1819 | 42 | 0.9369/0.9369 |
| split/uv | 1.35–1.4 | 935 | 892 | 1827 | 46 | 0.9504/0.9504 |
| split/uv | 1.4–1.45 | 837 | 763 | 1600 | 48 | 0.9581/0.9581 |
| split/uv | 1.45–1.5 | 407 | 429 | 836 | 44 | 0.9609/0.9609 |
| split/vis | 0.9313–1.01565 | 295 | 330 | 625 | 22 | 0.9557/0.9557 |
| split/vis | 1.01565–1.1 | 1040 | 1017 | 2057 | 30 | 0.9769/0.9769 |
| uv-low/uv | 0.9313–1.1 | 1939 | 1768 | 3707 | 34 | 0.7073/0.7072 |

Disponibili soltanto periodi locali `1998_uv` e `1999_vis`; altri periodi
registrati `not_available`, mai trattati come yield zero. UV perde 8 run
con triplette POL1/POL2/BREM incomplete; restano visibili anche esclusioni
per polarizzazione fuori dominio. Flussi riusati dalla calibrazione esistente.

## Stabilità e ricomposizione

Unione dei sottobin ricostruita tramite eventi/esposizioni, poi nuovo fit sui
bordi nominali. Chiusura esatta su 4 confronti (UV/VIS, raw/BDT) quando si
mantiene ordine originale degli eventi: massimo |ΔΣ| = 0. Cambiando ordine
per raggruppamento si osservano scarti numerici fino a 3.91e-8; sono registrati,
non usati per rilassare la tolleranza del controllo. Anche chiusura per periodo
è esatta nei tre studi.

`stability.json` contiene 800 contrasti descrittivi figlio−padre sugli stessi
campioni, con intervalli energetici diversi. Per il BDT ratio, mediana del
rapporto errore figlio/padre: UV 1.4126 (160 punti confrontabili), VIS 1.2721
(26 punti). Mediana |ΔΣ|: UV 0.0673, VIS 0.0402. Non sono test di
significatività: gli errori delle differenze richiedono covarianza appaiata,
qui non valutata. Nessuna media semplice di Σ è usata per ricomporre i bin.

## Prove e review

396 test passati dopo fix (356 integrazione/domini + 40 CLI/feature builder).
Warning preesistenti ROOT sullo streamer TLorentzVector e legenda vuota nel test
`compare_gate`. Inclusi default, exact-edge, griglie invalide, round-trip
ROOT, discordanza provenance, domain guard, cache/launcher, periodi e figure.
Review indipendente ha individuato due difetti corretti con regressioni
RED→GREEN: bypass di copertura tornando al nominale e dominio training
esteso senza supporto MC. Aggiunto anche controllo sul template MC.

Verifica visiva PDF: UV 8 righe, VIS 2; pannelli leggibili. Composizione
UV/VIS genera 10 righe. Riferimento Ajaka non attribuito a sottobin diversi.

## Decisioni e limiti residui

- Checkout condiviso conservato per integrare i contratti non committati;
  nessuna modifica altrui annullata. Nessun commit o merge eseguito.
- Conservata coda nominale oltre endpoint Compton, con esclusioni a livello
  di esposizione; eliminarla cambierebbe baseline e confronto storico.
- Copertura training adottata conservativa: ogni bin dello spettro deve
  contenere segnale a peso positivo; può richiedere più MC/dati o dominio
  ridotto. Non sostituisce validazione BDT indipendente.
- UV basso BDT non eseguito: modello nominale/legacy non certifica dominio
  nuovo. MC nuovo e validazione fisica restano necessari. Efficienze e
  covarianze tra griglie restano non valutate; inferenza finale sospesa.
- Minor differito dalla review: etichette PDF ereditate arrotondano bordi
  non centesimali a quattro decimali (1.01565 mostrato 1.0156). Config, ROOT,
  selezione e tabella sopra conservano bordo esatto. Notazione inclusiva
  storica dei plot non cambia regola numerica `[low,high)`, ultimo incluso.

Artefatti riproducibili: `audit.json` (hash/config/comandi/canali),
`extraction-commands.json`, `check_stability.py`, `stability.json`, `tests.log`,
ROOT/PDF e indici per periodo nelle rispettive sottocartelle della campagna.
