# Sezioni d’urto — stato del 21 ottobre 2026

Campagna nativa da100.000 eventi completata;630 candidati MC finali.
Prima estrazione2002_uv1 produce11–39μb contro circa1–3.5μb di Ajaka:
**risultato diagnostico, accettanza e fondo non validati**. Confronto, contabilità,
limiti e verifica PID nel [report nativo](2026-10-21-native-cross-section-diagnostic.md).
Prove successive sui dati1998_uv, come richiesto dall’utente; estrazione finale
su tutti i periodi con risposte corrispondenti. Incertezze complete restano TODO.

## Paper e figure

PDF spostato senza modificarne i byte in
`docs/papers/Ajaka_2008_EtaPi0_Photoproduction_PRL100_052003.pdf`.
SHA256 `7fdf85fe56fa8b0e232d070269e3e58d4d7ca542dcd9ac2287291abaa6b4f1cb`.

Digitalizzazione vettoriale riproducibile: Fig.2 contiene 12 punti Ajaka,
9 barre d’errore recuperabili; le altre tre sono mancanti, non zero.
Fig.3 contiene 300 punti sperimentali e 60 curve nei 15 pannelli.
Valori negativi pubblicati conservati. Errori Fig.3 non pubblicati.
PDF/PNG riprodotti in `results/ajaka-digitization-20261021/`;
CSV, manifest, script e provenienza in `08_observable_extraction/references/`.

La caption specifica Eγ=1.1,1.2,1.3,1.4,1.5 GeV. Mancano **bordi/larghezze**
delle cinque finestre, non le energie nominali. L’overlay ora le accetta
esplicitamente e dichiara che le finestre locali possono differire.

## Resa netta reale

Campione UV esattamente coerente col flusso valido: **100641 candidati**,
**93807.947 ±356.738** eventi di segnale; errore statistico condizionato
al modello. Sette periodi; 2001_uv escluso per esposizioni complete mancanti.
Rese totali e tre proiezioni differenziali con covarianza congiunta tra periodi.
Firme e conteggi verificati contro la selezione canonica Stage08.

Tutti gli otto fit UV convergono, ma devianza/ndf=1.47–2.18 e test di
adeguatezza falliti. Output `provisional_model_inadequate`; fondo fisico
con picchi e correlazioni massa/cinematica non ancora calibrato.
VIS non identificabile: diagnostica salvata, nessuna resa inventata.
Celle differenziali vuote hanno varianza zero: richiedono binning supportato
o inferenza appropriata prima del GLS, non un pavimento artificiale.

[Dettagli delle rese](2026-10-21-net-yields.md), risultati in
`results/cross-section-net-yields-20261021/extracted/`.

## Normalizzazione provvisoria e integrazione

Istruzione utente applicata in
`config/cross_sections/ajaka_provisional_normalization.json`:
LH₂ lungo12cm per tutti i periodi; densità nominale GEANT0.071g/cm³,
non dichiarata come misura di Ajaka; n_p=5.090445787963568×10²³cm⁻².
BR=0.3938×0.98823=0.389164974 per η e π⁰ forzati in due fotoni.
Flusso assunto assoluto e già corretto come richiesto.

Quattro configurazioni integrate in
`results/cross-section-inputs-20261021/campaigns/`: riferimenti reali,
rese reali, correlazioni condivise, bersaglio e BR espliciti. Percorsi delle
risposte MC ancora mancanti indicati come `pending_responses`, nessun valore
sostitutivo. Test integrazione numerico riproduce errore totale356.7384 e
legge tutti i12+300 punti Ajaka.

Stage08 valida ordine/firme della covarianza congiunta e uguaglianza dei
blocchi marginali; rifiuta rese dichiarate condivise se la configurazione
le tratta indipendenti. Stato di qualità del fondo propagato nell’audit.

## Accettanza del segnale

[Rapporto della catena GEANT3](2026-10-21-signal-acceptance.md).
Canale38 dedicato, GENBOD non pesato, verità completa prima delle perdite,
LAGDIG e PREAN ricompilati. Corrente prova tecnica usa periodo26/run4300:
configurazione storicamente di deuterio con bersaglio simulato H₂, quindi
non assegnabile come accettanza a un periodo protonico.

Rilevata perdita dei fotoni già negli hit GEANT e blocco riproducibile
intorno all’evento653. Il campione strumentato da1000 eventi attraversa
pipeline e BDT con46 selezionati, ma il build pulito non riproduce tale
comportamento. I suoi valori sono diagnostici, non efficienze fisiche.

Implementata alternativa fisicamente definita: decadimenti isotropi prompt
η/π⁰→γγ prima del trasporto GEANT, con verità delle madri e dei2000 decadimenti
conservata. Controlli di conservazione e massa nulla dei fotoni passano.
Controllo periodo26:1000→996; **primo profilo protonico21:1000→117**,
quindi successo non trasferito alla configurazione richiesta. Conversione
h70 del profilo21:114 eventi con un cluster BGO,3 con due; nessun candidato
finale nella pipeline corrente. Risposta rifiutata per accettanza nulla.
Causa di trasporto ancora non isolata, `transport_validated=false`.

Runtime conserva ora copia immutabile delle risorse: un replay precedente
aveva completato gli eventi ma falliva perché uno script montato dal repository
veniva modificato durante l’esecuzione. Campione segnato fallito; nessuna
riqualificazione silenziosa. Nessun container di simulazione lasciato attivo.

## Configurazioni dei periodi dopo «fai tu»

Associazioni ricavate dai sorgenti storici e verificate sui1289 run del
manifest:1998_uv→09,1999_uv→10,2000_uv1→14,2000_fuv→15,
2000_uv2→17,2002_uv1→21,2002_uv2→22. Primo profilo:2002_uv1,
run3629,base21. Nessuna assegnazione di periodo26/deuterio ai dati protonici.

`resources/geant3/proton_periods_provisional.json` conserva hash ed evidenze.
OLD_CYL resta assunzione esplicita ricavata dalla convenzione degli eseguibili;
geometria planare e soglie vengono dai relativi header e basi. Scelta trigger
solo-BGO rimane provvisoria. Primo profilo ora eseguibile:2002_uv1/run3629/base21/OLD_CYL.
Gli altri sei restano configurazioni dichiarative, non produzioni eseguite.

## Attività da completare

- [ ] Associare lunghezza, densità, incertezze del bersaglio ai periodi;
      sostituire l’assunzione comune autorizzata quando disponibili.
- [ ] Validare configurazione camere, calibrazioni e trigger per periodi protonici;
      produrre risposta su dominio energetico/angolare completo, indipendente dal training.
- [ ] Migliorare/validare separazione segnale-fondo; risolvere VIS se incluso.
- [ ] Definire celle differenziali con supporto ed effetti delle migrazioni.
- [ ] Recuperare larghezze originali delle finestre Fig.3 oppure mantenere
      esplicita la differenza nel confronto.
- [ ] **Incertezze complete rinviate per istruzione utente:** fondo, bersaglio,
      flusso, polarizzazione, energia, BR e modello di produzione/accettanza.
      Statistica delle rese e del MC resta necessaria e non è rimossa.

## Verifiche di questo aggiornamento

Suite complete eseguite separatamente: **Stage03 92 + Stage08 310 = 402 test passati**;
un warning preesistente di legenda vuota in Stage08. Ruff passa sui moduli/test nuovi delle rese e dell’integrazione.
Revisione indipendente: corretto rifiuto delle rese con covarianza condivisa
se configurate impropriamente come indipendenti; regressione prima fallita,
poi passata. Covarianza reale congiunta896×896 validata e somma verificata.
Riproduzioni Fig.2 e Fig.3 controllate visivamente, inclusi tutti i15 pannelli.
Revisione launcher MC: aggiunti rifiuto dell’energia vera diversa da quella
richiesta e verifica del numero di eventi ricevuti da PREAN contro LAGDIG,
entrambi con regressioni prima fallite e poi passate.

## Verifiche precedenti (prima di questo aggiornamento)

## Evidenze di verifica

Test eseguiti separatamente per evitare collisione di namespace `tests` fra
stage nella raccolta congiunta:

```sh
python3 -m pytest 03_mc_simulation/tests -q
MPLCONFIGDIR=/tmp/graal-matplotlib XDG_CACHE_HOME=/tmp/graal-cache \
  python3 -m pytest 08_observable_extraction/tests -q
```

**81 + 281 = 362 test passati**, di cui 47 nuovi. Un warning preesistente
su legenda vuota in `compare_gate.py`; nessun fallimento nelle due suite.
La prima raccolta con entrambi gli stage nello stesso processo falliva
su import relativo `tests.test_systematics`: nessuna modifica al test runner.
Ruff passa sui nuovi moduli e test. Nessuna campagna fisica completa eseguita.

Revisione indipendente scientifica/codice completata. Un rilievo sostanziale
corretto e riprodotto con test prima fallito, poi passato: eventi esclusi
per esposizione mancante erano riportati solo a stderr. Ora audit persistente
conserva conteggi e coppie run/strip; questi run non vengono etichettati come
semplicemente privi di candidati. Controlli di selezione restano nel lettore
comune, con parametro opzionale di audit.

Demo Asimov tramite CLI pubblico, accettanza azimutale variabile, migrazioni,
flusso orizzontale dimezzato e ampiezza polarizzata non nulla:

- Attesi: σ=0.5 μb, ampiezza polarizzata=0.12 μb.
- Estratti: 0.4999999999999997 μb e 0.11999999999999987 μb.
- Errore noto sintetico su σ: 0.06779575471198888 μb;
  χ²≈1.74×10⁻²⁹, essendo rese Asimov costruite dal modello.
- Artefatti finali:
  `results/cross-section-closure-20261021/final/cross_sections.root`,
  `results/cross-section-closure-20261021/final/cross_sections.pdf`.
- Configurazione/input, aspettative e script riproducibile nella directory
  superiore. I conteggi grezzi della fixture sono supporto del test; rese
  nette sintetiche non costituiscono un modello validato del fondo.
- ROOT riaperto e valori/audit verificati; PDF renderizzato e controllato,
  con dicitura visibile **Synthetic closure**.

Prova GEANT3 finale:
`results/cross-section-geant3-smoke-fixed-20261021/run.json` e `simulation.log`.
Due record generati più terminatore `-1`, log: due eventi GG, zero errati,
chiusura regolare. Prima prova individuava `FLUKAAF.DAT` mancante nel percorso:
Fortran usciva con codice zero. Correzione: `CERN_ROOT` esplicito e controllo
della terminazione normale; regressione dedicata impedisce falso successo.

## Provenienza del lavoro

Checkout `codex/dalitz-completion`, nessun commit/push/merge. Modifiche
preesistenti conservate. Il blocco precedente documenta le prove della prima
implementazione; lo stato corrente è descritto nelle sezioni iniziali.
