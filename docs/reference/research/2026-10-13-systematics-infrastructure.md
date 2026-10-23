# Errori, correlazioni e sistematici — infrastruttura e diagnostica

13 ottobre 2026. Piano: `docs/plans/2026-10-12-graal/01-errori-sistematici.md`.
Base controllata: `f568c6b` (`cf2022f` introduce baseline senza 6C).
Graphify: grafo esistente di 2.480 nodi; query espansa sul vocabolario effettivo
`systematics covariance bootstrap background sigma figure polarization`.
Il grafo, precedente alla baseline, è stato usato come mappa; risultati
ricontrollati sui sorgenti e sui ROOT correnti.

**Esito iniziale:** piano non già applicato. Esistevano matrici nominate,
bootstrap nominale e somma totale; mancavano inventario di disponibilità,
identità esplicite delle matrici, propagazione congiunta e bootstrap appaiato.
L'utente ha poi specificato: «Completa infrastruttura e diagnostica; lascia
inferenza finale sospesa». Questo documento non certifica chiusura fisica del
piano originale.

## Artefatti controllati, senza rigenerarli

| ROOT sotto `results/baseline-no-fit-20261013/` | Byte | Punti | Max residuo `Ctot−Cstat−ΣCsyst` | Off-diagonali statistiche non nulle |
|---|---:|---:|---:|---:|
| `uv/beam_asymmetry/beam_asymmetry.root` | 4.403.134 | 382 | 4,163336342344337e−17 | 0 |
| `vis/beam_asymmetry/beam_asymmetry.root` | 169.236 | 64 | 2,6915318931952648e−17 | 0 |

SHA-256:

- UV: `7f0971637e6dfb6e9cbdb710fb1257d81fcc28b6d62bbf641ffbd9679db599bc`
- VIS: `3673c320e03ee1d2717696ce12ca173c092c1f673e87bed4cd9468ac735b317e`

Provenance di entrambi: `raw_vs_kinematic_fit=disabled`, `sample=raw_bdt`,
`estimator=both`, `phi_bins=12`, `phi_bin_divisor=0.9549`,
`phi_bin_correction=ratio_only_rounded`, `background=uncorrected`.
Il residuo fra diagonale statistica e `((stat_low+stat_high)/2)^2` è **zero**
in entrambi. Gli zeri fuori diagonale indicano correlazioni non quantificate.
Non identificano una misura d'indipendenza. Figura specifica indicata
originariamente dall'utente ancora da identificare.

Componenti presenti nei ROOT controllati:

- UV: scala polarizzazione, differenza stimatori, seno fallback.
- VIS: scala polarizzazione, differenza stimatori, molteplicità fotonica.
- Nessun `bootstrap_run`; nessuna sorgente raw/6C.

L'assenza storica di una matrice non distingue variazione nulla e non
calcolata. La nuova codifica risolve questa ambiguità per nuove estrazioni;
non inventa stati retroattivi per gli archivi.

## Tracciamento delle barre

Tutte le incertezze su Sigma e sui ratio sono adimensionali.

| Oggetto | Formula/sorgenti | Condizioni e correlazione assunta | Esclusioni/limiti |
|---|---|---|---|
| Ratio ROOT osservato | `R=(NV/FV−NH/FH)/(PH NV/FV+PV NH/FH)`; Jacobiano rispetto a conteggi Poisson | Flussi/polarizzazioni fissati; conteggi V/H indipendenti nel modello | Nessuna incertezza di calibrazione o correlazione tra proiezioni |
| Barre ratio Figure 4 | Errore del fit armonico diviso per 0,9549 a 12 bin phi | Statistica condizionata, stessi campioni/bin | Non sono `sqrt(diag(Ctot))` |
| Barre likelihood | Limiti da `ΔNLL=0,5` | Likelihood condizionale per run/strip; esposizioni fissate | Intervalli asimmetrici; nessuna correzione finite-bin |
| Barre dopo fondo, codice legacy | Jacobiano diagonale di `(obs−f bkg)/(1−f)` | Covarianze incrociate ignorate; errori di obs, bkg, f sommati | `f` non classificata; simmetrizzazione distrugge intervalli originali. Ora etichettato esplicitamente |
| `Cstat` legacy | Diagonale della media degli errori al quadrato; eventuale blocco bootstrap nominale | Se bootstrap attivo, off-diagonali bootstrap e `max` sulle diagonali | Proiezioni/campioni non coperti rimangono ignoti |
| `Csyst[k]` legacy | `Δk Δkᵀ` | Un nuisance comune per sorgente; somma assume indipendenza tra sorgenti | Portata fisica non validata; differenze appaiate possono contenere rumore |
| Banda Figure 4 nuova | `sqrt(Σ diag(Csyst[k]))` | Soltanto componenti materializzate | Parziale, provvisoria, distinta dalle barre |
| `Ctot` ROOT | `Cstat+ΣCsyst` | Solo modello numerico corrente | Non sostituisce intervalli di likelihood; nessuna significatività finale |

`background_template=corrected−uncorrected` resta nel modello legacy, ma è
segnalata esplicitamente come shift di correzione, non misura indipendente
dell'incertezza di `f`. Rimuoverla o riclassificarla nell'inferenza richiede
la scelta fisica sospesa dall'utente. Analogo limite per seno fallback (coefficiente
diagnostico) e differenze tra stimatori/tagli.

## Implementazione

- `core/systematics.py`: controllo simmetria/PSD/dimensione/valori finiti;
  differenze con blocco `CAB` esplicito; bootstrap per run appaiato su universo
  di esposizioni e strati espliciti. Conserva run a zero yield, molteplicità
  dei draw, valori mancanti, motivi di fallimento, rango, run effettivi e
  errore Monte Carlo approssimato sulla covarianza.
- `core/background.py`: API `correct_sigma_with_covariance` con `J Cin Jᵀ`,
  blocchi osservato/fondo/frazione, termini incrociati e frazioni condivise.
  Non sostituita automaticamente al modello fisico corrente.
- `beam_asymmetry.py`: inventario completo con shift firmato e maschera per
  punto; zero misurato distinto da indisponibilità; raw/6C ritirato dalle
  sorgenti operative. Opzione diagnostica appaiata separata da quella legacy;
  riesegue campioni/stimatori, fondo e frazioni, mantenendo MC fisso.
- `io/root_output.py`, `io/root_input.py`: chiavi campagna/selezione/profilo/
  periodo/campione/stimatore/coppia/bin energia/bin massa; stessa mappa su
  ogni asse di ogni matrice. Reader legacy esplicito; writer atomico con
  rifiuto di chiavi duplicate, matrici invalide e mancata chiusura.
  Replica e draw completi salvati in ROOT, fuori dalla covarianza pubblicata.
- `plotting/figure4.py`, `plotting/diagnostics.py`: etichette dell'errore,
  banda sistematica separata e inventario nel riepilogo PDF.
- `core/models.py`, `core/conditional_likelihood.py`: eccezione specifica
  per fit non stimabile, registrabile senza nascondere errori software.

Nessun nuovo default di produzione o modifica al launcher: bootstrap resta
spento. Nessuna nuova campagna fisica, training, ricostruzione o confronto 6C.
I file di input e i risultati delle campagne precedenti non sono modificati.

Per il comando diagnostico, schema ROOT, stati per ciascuna voce di
`REQUIRED_SYSTEMATICS` e limiti dei reader vedere
[wiki aggiornata](../../../wiki/08-observable-extraction.md).

## Prove

Ambiente: Python 3.14.6, NumPy 2.5.0, SciPy 1.18.0, ROOT 6.40.04.

Baseline iniziale: **36 passed** sui cinque file indicati dal piano.
Dopo implementazione e review: **155 passed in 35.00s**, intera suite Stage 07:

```bash
python3 -m pytest -q -p no:cacheprovider 07_observable_extraction/tests
```

Coperti: nuisance comune con segni opposti, differenza identica nulla,
confronti indipendenti con `CAB=0` fornito esplicitamente, PSD e chiusura,
permutazione delle chiavi, bin mancanti, run con esposizione e zero conteggi,
seed ripetibile, universo incompleto respinto, fit likelihood fallito,
roundtrip ROOT con repliche fallite, storia dei draw incompleta respinta,
lettura legacy e barre asimmetriche diverse dalla banda sistematica.

Quattro fixture VIS di `test_combine_profiles.py` erano create collassando
quattro righe energetiche sullo stesso indice, producendo chiavi duplicate.
Sono state corrette per usare una sola riga; i controlli originali su
profilo/binning/correzione restano verificati. Un nuovo toy CLI estrae anche
una replica composta soltanto dal run vuoto: resta fallita nel ROOT, come
richiesto, senza sostituirne seed o draw.

Review indipendente, sola lettura: individuati e corretti, con test prima
fallito e poi passato, (1) fallimenti dell'ottimizzatore non registrati e
(2) esclusione silenziosa di run selezionati da un manifest diagnostico
incompleto. Anche il controllo di completezza dei draw, inizialmente
classificato minore, è stato trattato come necessario per riproducibilità.
Nessuna re-review; verifica dei fix tramite regressioni e suite completa.
QA visiva su Figure 4 sintetica e riepilogo PDF: barre/bande distinte,
etichette e tabella di disponibilità leggibili.

## Toy riproducibile e precisione bootstrap

```bash
python3 docs/reference/research/2026-10-13-systematics-toy.py
```

Modello: 20 medie di run gaussiane indipendenti, Sigma vera 0,3, deviazione
standard tra run 0,1, esposizioni uguali; seed dati `20261013`. Campioni A/B
identici, stessi draw. Varianza condizionale esatta del bootstrap della media:
`0.0003432506364710461`. Rango congiunto **1**, run effettivi **20**;
`max(abs(A−B))=0` per tutti i conteggi/seed.

| Repliche | Seed | Varianza stimata | Errore Monte Carlo stimato | Scarto relativo dal valore condizionale |
|---:|---:|---:|---:|---:|
| 100 | 8 | 0,0003020314 | 0,0000438590 | −12,01% |
| 100 | 19 | 0,0003716432 | 0,0000433577 | +8,27% |
| 100 | 44 | 0,0002491995 | 0,0000346022 | −27,40% |
| 500 | 8 | 0,0003277671 | 0,0000194995 | −4,51% |
| 500 | 19 | 0,0003329555 | 0,0000212764 | −3,00% |
| 500 | 44 | 0,0002961895 | 0,0000185124 | −13,71% |
| 2000 | 8 | 0,0003437279 | 0,0000103057 | +0,14% |
| 2000 | 19 | 0,0003422854 | 0,0000110951 | −0,28% |
| 2000 | 44 | 0,0003274755 | 0,0000101254 | −4,60% |

Coverage della media ± una deviazione bootstrap su 120 toy indipendenti,
200 repliche ciascuno: **86/120 = 71,67%**, errore binomiale **4,11 punti
percentuali**. Bias medio **−0,0000790**, errore Monte Carlo sul bias
**0,0018453**. La precisione del toy è limitata: non dimostra copertura
esatta al 68,27%, assenza di bias detector o validità del modello di run.
Non è stato scelto un conteggio di repliche per produzione.

## Decisioni e limiti rimasti

1. Universo inclusivo di acquisizione da fornire esplicitamente: non si
   deduce dai run sopravvissuti alla selezione. Il codice impedisce omissioni
   dei run selezionati, ma non può identificare da solo tutti i run persi.
2. Bootstrap eventi/Poisson a esposizione fissa sospeso: mancano identità
   comuni garantite fra file e decisione sull'ensemble. Bootstrap per run
   disponibile come diagnostica di clustering; non automaticamente statistico.
3. Classificazione/covarianza di `f`, portata globale/per periodo delle
   sorgenti, dispersione run, precisione e politica sui bin non stimabili
   ancora da concordare. Intervalli corretti di likelihood non ricostruiti.
4. Niente sottrazione automatica del rumore statistico dalle variazioni di
   modello e taglio; i loro outer product legacy restano dichiarati provvisori.
5. MC fissato nelle repliche: incertezza da campione MC finito esclusa.
6. Sandbox impediva creazione worktree; modifiche applicate nel checkout
   corrente secondo fallback della skill. Nessun commit, merge o push.

Ruling operativo: conservare modello numerico legacy, salvo ritiro raw/6C
esplicitamente richiesto, evita decisioni fisiche implicite; costo del rinvio:
`Ctot` resta non certificata per inferenza. Decisioni sospese sono riportate
anche nei metadati dei nuovi ROOT, non soltanto in questa relazione.
