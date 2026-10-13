# 3 — audit e ricostruzione sperimentale dei flussi mancanti

> Aggiornamento 13 ottobre 2026: stage `07_flux_studies` implementato come studio offline opt-in; osservabili rinumerati a 08. [Relazione e limiti](../../reports/2026-10-13-missing-flux.md). Nessun missing raw trovato nel dominio locale; validazione sperimentale sospesa per assenza dei metadati acquisizione. Il testo seguente conserva il piano scientifico originario.

**Obiettivo:** identificare assenze reali di POL1/POL2/BREM e confrontare ricostruzioni semplici con un metodo ML, senza sostituire misure.

**Architettura:** mantenere calibrazione corrente; aggiungere inventario e studio offline nello stadio 06, con artefatto sintetico distinto e opt-in. **Stack:** Python, ROOT/uproot, NumPy, scikit-learn già nel progetto. **Spec:** [vincoli](README.md), [inventario osservato](00-stato-verificato.md).

## Già fatto e invarianti

Adapter rileva triplette incomplete/duplicate e le scarta. Calibrazione completa energie strip mancanti, non flussi. Nel file grezzo locale tutti i 1.831 run P del manifest hanno triplette di chiavi: non sono stati identificati run con istogramma grezzo assente in questo universo. I 541 non completi nel calibrato richiedono diagnosi diversa.

Mai usare soltanto numero run per assumere vicinanza temporale o stabilità strumentale. Mai mescolare periodi, target, laser o configurazioni incompatibili. Distinguere missing histogram, missing strip calibration, duplicato, non-finito, zero valido/non valido e run non coperto. Contenuti misurati immutabili.

## Decisioni/input prima della ricostruzione

Identificativi Vinci e significato del gruppo; disponibilità run ±1 e log acquisizione; normalizzazione di flusso (tempo vivo, corrente, scalers e relativi errori); criteri quantitativi di adozione. Se mancano, produrre inventario e protocollo, senza stimare numeri fittizi. L'uso dei sintetici in Σ richiede una decisione successiva, non è automatico dopo training.

## File candidati

Riusare `06_calibration/run_manifest.py`, `strip_energy_flux.py`, `build_strip_energy_flux.py` e `07_observable_extraction/calibration/flux_v2.py`. Nuovi moduli circoscritti proposti: `06_calibration/audit_flux.py`, `06_calibration/study_missing_flux.py`; test `06_calibration/tests/test_flux_audit.py`, `test_missing_flux_study.py`. Output di studio sotto `results/<campagna>/missing_flux/`; relazione in `docs/research/`.

## Passi e metodo

- [ ] Catalogare per run/stato chiavi/cicli ROOT, 128 strip, assi, integrali, validità bin, copertura energia e motivo esclusione. Incrociare raw/calibrato/manifest/dati realmente acquisiti; non dedurre missing raw da assenza nel calibrato.
- [ ] Per Vinci, sovrapporre istogrammi r−1, r, r+1 quando esistono e sono compatibili; mostrare integrali assoluti e forme normalizzate separatamente. Se due vicini brackettano il run è interpolazione; con un solo lato è estrapolazione, con incertezza più debole. Nessun vicino compatibile → non ricostruibile con questo metodo.
- [ ] Baseline: vicino compatibile più prossimo; template medio/mediano robusto del periodo con normalizzazione da esposizione indipendente; interpolazione lineare fra due vicini. Senza normalizzazione indipendente, ricostruire soltanto forma e dichiarare integrale non identificato.
- [ ] ML candidato iniziale: regressione regolarizzata multi-output sui 128 bin o pochi coefficienti PCA della forma; predittori disponibili al momento del missing (flussi degli altri stati, esposizione, condizioni). Fit/scaling/PCA soltanto su train. Positività e incertezza di integrale/forma esplicite; un modello complesso è giustificato solo da miglioramento misurato.
- [ ] Validazione con masking di istogrammi realmente misurati: hold-out di run/blocchi contigui entro periodo, intero flusso o pattern di assenza realistico. Separare interpolazione offline (due lati disponibili) da previsione causale; escludere target mascherato da feature e tuning. Misurare bias integrale, errore per strip, forma, residui e copertura intervalli; confronto paired con baseline sugli stessi fold.
- [ ] Incertezza da residui out-of-fold e ricampionamento donor/modello, con covarianza tra strip e run sintetici che condividono donor. Verificare stabilità su bordi periodo, singolo donor, run anomalo e assenza multipla. ML non vincente → tenere metodo semplice o nessuna imputazione.
- [ ] Salvare ROOT/CSV separato con measured/synthetic, metodo, donor, split, seed, matrice d'incertezza, dominio e ragione. Riaprire originale e verificare immutato. Nessun aggiornamento silenzioso di `flux.root` o del calibrato.
- [ ] Solo se autorizzato nello step futuro: scenario measured-only contro measured+synthetic, propagazione dei nuisance comuni secondo punto 1, risultati per periodo secondo punto 2. Non dichiarare guadagno di precisione contando sintetici come misure indipendenti.

## Verifiche e chiusura

Test inventario con istogramma assente, ciclo duplicato, calibrazione assente ma raw presente, zero BREM valido; test fold senza leakage e nessun cambio hash degli originali. Validazione scientifica richiede curve su hold-out e copertura delle incertezze, non sola MSE di training. Consegna possibile anche negativa: “nessun missing raw nel dominio” oppure “nessun metodo validato”; entrambi evitano ricostruzioni inventate.
