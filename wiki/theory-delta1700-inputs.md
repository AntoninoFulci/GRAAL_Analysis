# Δ(1700): ingredienti recuperati e aggiornamento del modello

Ricognizione del 5 novembre 2026. Parte della [ripartenza teorica da Ajaka](theory-restart-ajaka.md). L'utente conferma che il gruppo non dispone più di codice, tabelle numeriche o note originali degli autori. Si ricostruisce dalle pubblicazioni; le formule e i numeri qui raccolti non costituiscono ancora un insieme di parametri validato o un'implementazione.

## Significato dei pezzi

La Δ(1700) è uno stato intermedio instabile. Per descriverlo servono informazioni diverse:

1. Come il fotone lo produce, conservando la dipendenza dalla polarizzazione.
2. Come contribuisce al variare dell'energia: massa e larghezza dipendente dall'energia.
3. Con quale intensità e fase si collega ai diversi stati intermedi successivi.

La larghezza è legata all'instabilità dello stato. Non basta conoscerne un numero nominale: i diversi modi di decadimento contribuiscono in maniera diversa al variare dell'energia. Gli accoppiamenti sono i coefficienti che regolano i collegamenti; quelli complessi contengono anche informazione di fase, necessaria alle interferenze.

## Fonti e versioni

- **P73:** Döring, Oset, Strottman, PRC **73**, 045209 (2006), [PDF editoriale](../docs/reference_papers/10.1103@PhysRevC.73.045209.pdf), Eqs. (30), (36)–(44), pp. 9–11.
- **B639:** stessi autori, PLB **639**, 59–67 (2006), [PDF editoriale](../docs/reference_papers/10.1016@j.physletb.2006.06.022.pdf), pp. 61–63 e 65, Eqs. (5)–(6), (12)–(13), Fig. 5. Aggiorna P73.
- **Nacher:** Nacher et al., NPA **695**, 295–327 (2001), [preprint nucl-th/0012065v2](../docs/reference_papers/nucl-th-0012065.pdf), pp. 16–17 e appendice A3, p. 30. Le pagine sono quelle del preprint; equivalenza completa alla versione editoriale non verificata.
- **Sarkar:** Sarkar, Oset, Vicente Vacas, NPA **750**, 294–323 (2005), [preprint nucl-th/0407025v2](../docs/reference_papers/nucl-th-0407025.pdf), sezione 4.3 e Tab. 10, p. 15. Erratum del 2006: metadati verificati, testo ancora non letto.

## Numeri recuperati: trascrizioni, non valori già approvati

| Ingrediente | Informazione della fonte | Localizzatore e controllo | Limite |
| --- | --- | --- | --- |
| Accoppiamenti al fotone | `g′₁ = −0.260 m⁻¹`, `g′₂ = 0.270 m⁻²` | Nacher A3, p. 30, tabella controllata visivamente; p. 17 attribuisce g′₁/g′₂ alla fotoeccitazione della Δ(1700) | Conservare la convenzione originale di m e ricostruire unità e normalizzazione nel collegamento con P73; non introdurre fattori di carica aggiuntivi senza derivazione |
| Canale ηΔ | `gη = 1.7 − 1.4 i` | Sarkar Tab. 10, colonna del polo `1827 − 108 i`, verificata visivamente; P73 p. 10 riporta lo stesso valore | Erratum non letto; fase globale/relativa da applicare secondo la convenzione di P73 |
| Canale KΣ* | `gK = 3.3 + 0.7 i` | Stessa colonna di Sarkar Tab. 10; P73 p. 10 | Come sopra; non sostituire il numero complesso con il suo modulo |
| Accoppiamento Δπ del modello dinamico | `gΔ = 0.5 + 0.8 i` | Sarkar Tab. 10 e P73 p. 10 | P73 lo discute per scegliere la fase; non va confuso automaticamente con i parametri s/d del decadimento empirico Δ*(1700) → Δπ |
| Decadimento Δ*(1700) → Δπ nella ricetta precedente | `f̃ = −1.325`, `g̃ = 0.146` | Nacher A3, p. 30, tabella controllata visivamente; P73 Eq. (37) rinvia a Nacher per le ampiezze s/d | L'inserimento coerente nell'aggiornamento B639 richiede ancora la verifica della larghezza risultante |
| Vecchio accoppiamento Δ*(1700) → ρN | `g′ρ = 2.60`; `fρ = 6.14` per ρ → ππ | Nacher A3 p. 30, controllata visivamente; P73 p. 10 usa la notazione `gρ = 2.6` per la Δ* | La notazione cambia tra fonti. B639 modifica i contributi ρN: questo vecchio valore non basta per la versione aggiornata |
| Larghezza nominale | `300 ± 100 MeV` | B639 p. 61, testo prima della Eq. (3), controllato visivamente | È il riferimento empirico adottato lì; B639 p. 62 descrive il totale del proprio modello come «circa 300 MeV» |
| Decadimento πN | Quota nominale `15 ± 5%`; Eq. (13) usa `Γ⁰πN = 0.15 × 300 MeV` | B639 pp. 61–62 | `45 MeV` è una conseguenza aritmetica della scelta centrale, non una nuova misura |
| Decadimento ρN aggiornato | `37%` in onda s, `5%` in onda d | B639 p. 62, testo; controllato visivamente nella ricognizione precedente | Gli autori dichiarano un aggiustamento ai dati. Sono scelte della versione pubblicata; non autorizzano un nuovo fit ai nostri dati |
| Fattore di barriera | `BW(x) = x² / sqrt(9 + 3x² + x⁴)`, `R = 0.4 fm` | B639 p. 61, Eqs. (5)–(6), controllo visivo | L'argomento x deve essere adimensionale; la conversione delle unità va resa esplicita |

La posizione del polo `1827 − 108 i` del modello dinamico di Sarkar non è automaticamente la massa da usare nel propagatore fenomenologico della Δ(1700). P73 importa gli accoppiamenti e costruisce il meccanismo di produzione secondo una prescrizione propria. Anche il numero `216 MeV` associato a quel polo (`2 × 108`) non va identificato con un'altra larghezza soltanto perché numericamente simile.

## Cosa cambia tra P73 e B639

P73 Eq. (36) usa il propagatore

\[
G_{\Delta^*}(W)=\frac{1}{W-M_{\Delta^*}+i\,\Gamma_{\Delta^*}(W)/2},
\]

con W energia del sistema pertinente al propagatore. P73 Eq. (37) descrive contributi πN, ρN e Δπ alla larghezza. B639 p. 62 mantiene la struttura di decadimento ρN/Δπ e introduce aggiornamenti espliciti:

- Per ρN separa contributi s e d. Il contributo d usa l'integrando ρN precedente moltiplicato al numeratore per `BW²(|q₁ − q₂| R)`; un accoppiamento viene regolato per ottenere il 5% dichiarato.
- Per πN, B639 Eq. (13) prescrive

\[
\Gamma_{\pi N}(W)=\Gamma^0_{\pi N}
\frac{k(W)\,BW^2(k(W)R)}{k_{\mathrm{on}}\,BW^2(k_{\mathrm{on}}R)}
\frac{M_{\Delta^*}}{W}.
\]

Qui `k_on = k(MΔ*)`; il prodotto kR è in unità naturali. Se k è in MeV e R in fm si usa kR/(ℏc). La formula precedente di P73 ha invece la dipendenza `k⁵/k_on⁵` per questo contributo. Le prescrizioni non sono intercambiabili.

B639 p. 65 dichiara una riduzione di circa il 30% delle sezioni d'urto rispetto a P73. Questo non stabilisce la variazione di Σ, né dimostra che conosciamo ogni dettaglio del calcolo delle curve di Ajaka.

**Ancora aperto:** ricostruire normalizzazione e funzione energetica di ciascun contributo, verificare il trattamento della Δπ e delle particelle instabili interne, controllare la somma delle larghezze. Non imporre un residuo Δπ del 43% sottraendo automaticamente 15% + 37% + 5% da 100%: il testo consultato non prescrive quella rinormalizzazione e descrive il totale soltanto come approssimativamente 300 MeV. Le masse e le convenzioni storiche devono essere ricostruite; un aggiornamento silenzioso ai valori PDG moderni cambierebbe il riferimento.

## Erratum: identità risolta, contenuto aperto

Crossref, tramite metadati depositati dall'editore, e INSPIRE concordano su:

- S. Sarkar, E. Oset, M. J. Vicente Vacas, *Erratum to: “Baryonic resonances from baryon decuplet-meson octet interaction” [Nucl. Phys. A 750 (2005) 294]*.
- Nuclear Physics A **780**, fascicoli 1–2, **pagina 90** (2006).
- DOI **[10.1016/j.nuclphysa.2006.09.019](https://doi.org/10.1016/j.nuclphysa.2006.09.019)**; PII `S0375947406006385`.

La scheda arXiv riporta invece `78–89`: per identificare l'erratum si adottano pagina e DOI confermati da Crossref/INSPIRE. Il preprint disponibile resta v2 del 4 gennaio 2005; la presenza di una data di composizione successiva non dimostra incorporazione dell'erratum del 2006.

Accesso al testo tentato il 5 novembre 2026: DOI e ScienceDirect tramite ricerca web non leggibili; ScienceDirect diretto risponde HTTP 403, endpoint testuale Elsevier indicato da Crossref risponde HTTP 400. Nessun testo dell'erratum ottenuto. Non è quindi noto se corregga gli accoppiamenti, altre formule o dettagli estranei al nostro canale. Nessuna correzione fisica è stata dedotta dai soli metadati.

## Prossimo controllo circoscritto

Confrontare riga per riga le formule delle larghezze di Nacher/P73 con B639 e preparare un elenco chiuso di scelte determinate dalle fonti e dettagli non determinati. Il recupero dell'erratum resta una verifica separata necessaria prima di certificare la catena bibliografica. Nessun parametro viene scelto per avvicinare una curva ai dati di Ajaka o ai nostri.

Evidenza: `results_test/ajaka-delta1700-audit-20261105/` conserva i piccoli record `erratum-metadata.json`, `erratum-access.json` e `verification.log`, necessari a documentare identità bibliografica, limiti d'accesso e controlli effettuati. Le immagini temporanee sono rimosse dopo l'ispezione. Gli originali e i registri storici del tentativo ritirato non sono modificati.
