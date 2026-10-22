# Estrazione delle sezioni d'urto

Implementazione condizionale per γp→pηπ⁰: σ(Eγ) in μb e dσ/dM in μb/MeV.
Non esiste ancora una misura assoluta dei dati correnti: manca una risposta
valida del segnale. Bersaglio assunto provvisoriamente come Ajaka per tutti
i periodi, su istruzione utente. Stato di ogni risultato:
`conditional`; nessuna normalizzazione al paper di Ajaka.

## Comandi

Ambiente Python del progetto con NumPy, PyROOT e matplotlib, package installato
in modalità editable come nella pipeline esistente:

```sh
# Conteggi selezionati e firme, prima di fornire target, MC e fondo:
python3 -m observable_extraction.cross_sections --config campaign.json --observations-only > observations.json

# Validazione completa e inferenza, senza pubblicare ROOT/PDF:
python3 -m observable_extraction.cross_sections --config campaign.json --audit-only

# Inferenza e pubblicazione atomica in directory nuova:
python3 -m observable_extraction.cross_sections --config campaign.json --output-dir results/campaign/cross_sections
```

`--audit-only` esige tutti gli input: input mancante/errato provoca errore.
`--observations-only` richiede griglia, manifest, flusso, ricostruzioni e periodi;
restituisce firme dei conteggi senza richiedere target/risposta/fondo/BR.
Percorsi relativi risolti rispetto al JSON che li contiene. Output esistenti
non vengono sovrascritti. Campi JSON duplicati e valori non finiti sono vietati.

## Configurazione

Esempio strutturale: `null` rende intenzionalmente impossibile l'inferenza
finché non vengono forniti input espliciti. La convenzione provvisoria autorizzata
è in `config/cross_sections/ajaka_provisional_normalization.json`: LH₂ 12 cm,
densità nominale GEANT 0.071 g/cm³, 5.0904458×10²³ protoni/cm². La densità non
è una misura riportata da Ajaka. BR esterna 0.3938×0.98823=0.389164974,
soltanto quando entrambi i decadimenti sono forzati. Errori di scala mancanti.

```json
{
  "schema_version": 1,
  "analysis_kind": "experimental",
  "grid": {
    "energy_edges_gev": [1.1, 1.2],
    "phi_edges_rad": [0, 0.7853981633974483, 1.5707963267948966, 2.356194490192345, 3.141592653589793, 3.9269908169872414, 4.71238898038469, 5.497787143782138, 6.283185307179586],
    "observable": "total",
    "mass_edges_gev": null
  },
  "branching": {"value": null, "relative_uncertainty": null, "source": "Da documentare: convenzione eta e pi0"},
  "flux_file": "flux.root",
  "run_manifest": "manifest.csv",
  "samples": [{
    "reconstructed": "reco.root",
    "tree": "reco",
    "profile": "uv",
    "period": "1999_uv",
    "response": "response.json",
    "target": {
      "areal_density_cm2": null,
      "relative_uncertainty": null,
      "source": "Associazione periodo/bersaglio da verificare",
      "correlation_group": "target_1999"
    },
    "flux_scale": {
      "relative_uncertainty": null,
      "source": "Flusso assunto assoluto e corretto su indicazione utente",
      "correlation_group": "flux_common"
    },
    "background": {"mode": "net_yields", "path": "background.json"}
  }]
}
```

Griglia: ordine celle **energia, massa eventuale, φ**, con φ più veloce.
Intervalli sinistra inclusa/destra esclusa, ultimo bordo incluso.
Osservabili differenziali: `p_pi0`, `p_eta`, `eta_pi0`, con `mass_edges_gev`.
Angolo φ riferito alla coppia scelta; per `total` viene usata ηπ⁰.
Ogni campione deve coprire l'intera griglia energetica. Per UV/VIS usare
intervallo comune validato. Griglie rettangolari con celle cinematicamente
impossibili sono rifiutate: scegliere intervalli supportati, eventualmente
un'energia alla volta. Non sono implementate celle di guardia indipendenti
nella normalizzazione: dominio delle migrazioni deve essere chiuso e validato.

La densità richiesta è **numero di protoni/cm²**, non g/cm²:
`n_p = rho * L * N_A / M_H`. Nessun default implicito della lunghezza nel codice;
la configurazione di campagna contiene esplicitamente l'assunzione autorizzata.
Gruppi di correlazione uguali condividono la stessa variazione di scala;
gruppi diversi sono trattati indipendenti. Incertezza `null` viene registrata
come mancante; non equivale a zero. `analysis_kind=synthetic_closure` serve
esclusivamente alle prove e permette risposta sintetica.

## Resa e fondo

Da `--observations-only` prendere `audit.samples[i].observation_signature` e
`raw_counts`. Per ogni campione, vettori ordinati **tutte le celle POL1, poi
 tutte le celle POL2**. File di resa:

```json
{
  "schema_version": 1,
  "source": "Metodo di fit/controllo, campione e versione",
  "observation_signature": "sha256 restituito dall'audit",
  "observed_counts": [],
  "net_yields": [],
  "covariance": []
}
```

Sostituire array vuoti con conteggi esatti, rese nette e matrice quadrata
completa positiva definita. La covarianza deve includere statistica della
resa, stima del fondo e loro correlazioni. Rese nette negative restano
ammesse. Il nuovo comando `python3 -m observable_extraction.signal_yields`
esegue fit bidimensionale delle masse entro la selezione effettiva; la formula
di correzione dell'asimmetria Σ non è una stima di resa assoluta.
I risultati del 21 ottobre sono `provisional_model_inadequate`: tutte le
prove di adeguatezza UV falliscono, VIS non identificabile. Questo stato
viene mantenuto nelle limitazioni del risultato downstream.

Con più campioni e rese nette, config richiede
`"background_cross_sample_covariance": "independent"` solo per controlli
indipendenti, oppure `"joint_background": {"path":"joint_covariance.json"}`.
Il fit di massa corrente condivide parametri tra periodi: usare sempre la
seconda opzione. Manifest con firme ordinate, `row_counts` e `covariance_npz`;
archivio NPZ con `diagonal`, `factors`, `kernel` ricostruisce
`diag(diagonal) + factors @ kernel @ factors.T`. La covarianza completa deve
essere PSD e i blocchi marginali devono coincidere con i file delle rese.
Il kernel da solo può essere indefinito. Celle vuote conservano varianza zero;
prima del GLS occorre scegliere bin con supporto, senza aggiungere varianze fittizie.

Solo per diagnostica esplicita:
`"background": {"mode":"none_diagnostic","reason":"motivazione"}`.
Usa rese grezze e varianza `max(N,1)`; registra `background_not_corrected`.
Non produce misura del segnale corretta dal fondo.

## Risposta del rivelatore

```sh
python3 -m mc_simulation.geant3 response \
  --generated generated.csv --selected selected.csv \
  --metadata response-metadata.json --output response.json
```

Entrambi i CSV: esattamente `event_id,cell`. Generato completo, ID univoci
non negativi, selezionato sottoinsieme univoco del generato. Perdite possono
essere assenti dal selezionato oppure avere `cell=-1`; restano al denominatore.
MC deve essere non pesato e indipendente dal training. Il selezionato deve
provenire da **LAGGEN/GEANT3 → LAGDIG → PREAN → conversione → pipeline dati**:
digitalizzazione, tagging, trigger e selezioni devono contribuire alla
risposta. Verità completa conservata prima delle perdite; verità dei soli
sopravvissuti in `.dig`/`.pol` non basta come denominatore. Nessun adattatore
automatico garantisce ancora l'identità fra ASCII LAGGEN e ricostruzione.

Metadati:

```json
{
  "schema_version": 1,
  "grid": {"energy_edges_gev": [], "phi_edges_rad": [], "observable":"total", "mass_edges_gev":null},
  "selection_signature": "audit.samples[i].selection_signature",
  "provenance": {
    "simulator": "GEANT3",
    "geometry": "Versione e configurazione per il periodo",
    "validation": "Riferimenti alle prove di trigger, selezione e closure",
    "independent_of_training": true,
    "generated_complete": true,
    "migration_domain": "closed",
    "decays": "forced_gamma_gamma"
  }
}
```

Sostituire griglia vuota con griglia esatta della campagna. Flag e descrizioni
sono dichiarazioni del produttore: non certificano da soli la simulazione.
Output aggiunge `generated`, `selected` (righe ricostruite, colonne vere),
`sample_id` e hash degli input. Stesso MC riusato fra periodi/stati resta
correlato; stesso ID con risposte diverse viene rifiutato perché manca la
covarianza congiunta fra le risposte.

`forced_gamma_gamma`: BR esterna include i decadimenti forzati e viene
applicata una sola volta. `inclusive`: decadimenti inclusi nel denominatore,
fattore esterno unitario. Simulazione solo con smearing è rifiutata.
Denominatori vuoti, accettanza nulla, selezionati in eccesso e matrici di
inferenza senza rango sufficiente provocano errore.

[Ambiente GEANT3 e prova tecnica](../../resources/geant3/README.md).

## Metodo e limiti

Fit GLS simultaneo di sezione non polarizzata e ampiezza cos(2φ), con
integrale esatto in ogni bin φ. POL1 verticale e POL2 orizzontale hanno
segni opposti; LAGGEN usa numerazione inversa e richiede mapping verificato.
Luminosità: `N_gamma * n_p * BR * 1e-30` in μb⁻¹.
σ(Eγ) non viene divisa per ΔEγ; dσ/dM viene divisa per ΔM in MeV.

Flusso misurato valido, esclusioni correnti e universo inclusivo dei run
restano comuni a dati/esposizione. Run senza candidati contribuiscono al
flusso. `event_selection` registra eventi eleggibili, perdite per esposizione
non valida e relative coppie run/strip. `zero_yield_runs` esclude run con
queste perdite, per non confonderle con assenza di candidati. Assegnazione energetica usa energia media dello strip del lettore
esistente, senza splitting fra bin: approssimazione registrata nei risultati.

Covarianze: resa, statistica MC multinomiale con perdite, scale correlate
bersaglio/flusso/BR note; propagazione al primo ordine. Non è un metodo di
intervalli Poisson a basse statistiche. Distribuzione di produzione dentro
le celle, buchi angolari nelle variabili non binate, calibrazione energetica
e polarizzazione richiedono validazione/variazioni ulteriori. Non sono
coperte dall'errore mostrato. Una griglia φ con quattro quadranti esatti
annulla l'integrale cos(2φ): usare griglia sensibile alla modulazione.

## Confronto Ajaka

Fig.2 e Fig.3 digitalizzate dai vettori del PDF originale, con provenienza:
12 punti Ajaka nella Fig.2, 300 punti e 60 curve nella Fig.3.
Errori non recuperabili restano mancanti, mai zero. Fig.2 include già la
sistematica dichiarata dal paper; non aggiungerla una seconda volta.
Fig.3 pubblica energie nominali 1.1, 1.2, 1.3, 1.4, 1.5 GeV; non pubblica
i bordi delle cinque finestre. `reference_nominal_energies_gev` consente overlay
esplicito con finestre locali, senza affermare identità dei bin sperimentali.
CSV `ajaka2008_figure4_digitized.csv` contiene Σ, non σ, e non è ammesso.
Riproduzioni: `results/ajaka-digitization-20261021/`.
Configurazioni integrate: `results/cross-section-inputs-20261021/campaigns/`;
i percorsi `pending_responses/` indicano input MC ancora mancanti. Non eseguono
inferenza usando efficienze inventate.
Ricerca e vincoli: [nota bibliografica](../research/2026-10-21-cross-section-target-ajaka.md).

Per punti Fig. 2 acquisiti/verificati, aggiungere `"reference":"ajaka.json"`
alla campagna. Manifest obbligatorio:

```json
{
  "schema_version":1, "observable":"total", "units":"ub", "energy_units":"GeV",
  "figure":2, "errors":"published_total_including_systematics", "energy_bins":"centers_only",
  "source":"https://doi.org/10.1103/PhysRevLett.100.052003",
  "label":"Ajaka 2008, Fig. 2",
  "extraction":"Metodo, versione sorgente, coordinate e verifica della digitalizzazione",
  "digitization_uncertainty_ub":0.01,
  "data":"ajaka-figure2.csv"
}
```

`0.01` è esempio di schema, non errore misurato: sostituire con stima verificata.
CSV: `energy_gev,sigma_ub,error_ub`, energie crescenti, valori finiti.
Overlay mostra barre pubblicate; incertezza di digitalizzazione resta separata
nei metadati. Fig. 2 include già sistematica ≈7%: non sommarla di nuovo.
Niente rescaling, rapporto o χ² automatico: bordi energetici e correlazioni
col campione corrente non sono noti. Confronto Fig. 3 rifiutato finché non
sono documentate le finestre energetiche originali.

## Prodotti

`cross_sections.root`: punti e unità, covarianza `known_total` e componenti,
conteggi grezzi/rese nette/covarianza della resa/design/parametri, risposte MC,
provenienza completa con configurazione, esposizioni, assunzioni e input hash.
`cross_sections.pdf`: grafico con dicitura condizionale (o synthetic closure)
e soli errori noti.

Demo locale: `results/cross-section-closure-20261021/`, aspettative Asimov
sintetiche σ=0.5 μb, ampiezza polarizzata=0.12 μb, accettanza non uniforme,
migrazioni e flussi H/V diversi. Non contiene risultati sperimentali.

### Data scope

User instruction: single-period data trials use1998_uv. Final extraction uses
all periods with corresponding validated responses. The completed2002_uv1
MC campaign is diagnostic and must not be relabeled1998_uv. Period09 uses
OLD_PLAN, data09.base and calib_1400.cal; period21 uses different settings.

Prepared1998 data check:

```sh
python -m observable_extraction.cross_sections \
  --config results/cross-section-inputs-20261021/campaigns/total_1998_uv_trial.json \
  --observations-only
```

It reports166 accepted runs and10487 observed candidates. The matched yield
contract gives9997.224±105.201 conditional events. This config retains a
pending period-specific response: it is not an acceptance-calibrated result.
The completed native comparison and its unresolved detector/background
limitations are documented in
[`2026-10-21-native-cross-section-diagnostic.md`](../reports/2026-10-21-native-cross-section-diagnostic.md).

### Native period21 campaign and direct harmonic inference

The current OrbStack execution fails the GTGAMA transport invariant. Build
and runtime are distinct: use native x86 execution with the mandatory probe.
The Docker source snapshot and corrective ledger are in
`resources/geant3/docker-upgrade/`; no updated image has been pushed.

After `h2root` conversion, apply the unchanged data pipeline while preserving
truth identities:

```sh
python -m mc_simulation.reconstruct_geant3 \
  --pilot results/cross-section-signal-acceptance-20261021/native-uniform-production-99900 \
  --converted results/cross-section-signal-acceptance-20261021/native-uniform-production-99900/converted.root \
  --output results/cross-section-signal-acceptance-20261021/native-uniform-production-99900/reconstruction
```

`matched_events.npz` contains every generated mother and only the uniquely
matched final candidates. Reconstruction of guard events below1.1GeV is not
silently removed from the generated denominator. The host analysis then uses
MC moments of selected `1` and `cos(2phi_true)` rather than assuming a constant
acceptance within coarse truth-phi bins. Reconstructed E/phi cells stay the
same as the net-yield fit. Truth0.95–1.1GeV is a fitted nuisance contribution,
with an independent cross section and polarized amplitude; Ajaka is never
used to set either coefficient. MC fluctuations are propagated jointly across
H/V, including correlations of the two moments.

MC reconstructed-strip masks are the same valid `(run, strip)` exposures used
by the data, restricted to the original observed1.1–1.5GeV domain. Each run's
mask is weighted by its own H/V truth-bin flux and polarized flux, including
guard flux. The representative detector run3629 is not used as the period's
exposure mask. Lost events remain zero contributions to the complete generated
denominator; the weighted moment covariance is shared across both states.

`reconstruction/validation.json` binds the exact native binary/card contract,
complete generated truth and forced two-photon decays, conversion and selected
archive hashes. The extractor rejects changed inputs, duplicate generated
truth or generator seeds, fixed-energy substitutions and wrong decay settings.
The frozen contract is `resources/geant3/native_campaign_contract.json`.

```sh
python -m observable_extraction.harmonic_cross_sections \
  --config results/cross-section-inputs-20261021/campaigns/total_2002_uv1_harmonic.json \
  --mc-dir results/cross-section-signal-acceptance-20261021/native-uniform-smoke-100/reconstruction \
  --mc-dir results/cross-section-signal-acceptance-20261021/native-uniform-production-99900/reconstruction \
  --output-dir results/cross-section-native-total-20261021
```

This is a conditional single-period result. Phase-space production, uniform
energy within truth bins, constant guard cross section, provisional detector
configuration, target normalization and the inadequate mass-background model
remain explicit limitations. Missing systematic uncertainties are not zero.
A singular fit, empty required support, or inconsistent identities must fail;
no acceptance floor, positivity clipping or normalization to the paper is
allowed. The three differential observables still require their own supported
response/fit domains; this total estimator does not validate them implicitly.
