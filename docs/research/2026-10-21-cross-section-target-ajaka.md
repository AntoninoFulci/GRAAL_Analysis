# Sezioni d'urto: Ajaka, bersaglio e flusso GRAAL

Verifica: **2026-10-21**, Europe/Rome. Ricerca mirata per progettare l'estrazione di γp→pηπ⁰; nessuna costante trasferita al codice. Integra [ricerca sperimentale precedente](2026-10-13-eta-pi0-experiments.md).

## Risultato operativo

Ajaka documenta **LH₂ lungo 12 cm**, ma non fornisce densità calibrata e relativa incertezza per il campione attuale. Letteratura GRAAL riporta **18 K, ρ≈0.07 g/cm³** e bersagli di diverse lunghezze. Questi numeri identificano configurazioni storiche: non certificano luminosità dei run presenti. Occorrono associazione run/configurazione, provenienza del flusso assoluto e accettanza del rivelatore prima di produrre σ assolute.

**Aggiornamento utente, stessa sessione:** spessore del bersaglio non conosciuto; autorizzato trattare provvisoriamente il flusso disponibile come **assoluto e già corretto**. L'implementazione può usare questa assunzione dichiarata senza applicare ulteriori fattori di monitor/tagging/live time. L'autorizzazione non equivale a verifica della calibrazione; la dipendenza resta da registrare nei risultati. Nessuna autorizzazione implicita ad assegnare 12 cm a tutti i periodi.

## A. Confronto con Ajaka 2008

J. Ajaka et al., *Simultaneous Photoproduction of η and π⁰ Mesons on the Proton*, PRL **100**, 052003 (2008), [DOI/editore](https://journals.aps.org/prl/abstract/10.1103/PhysRevLett.100.052003), [PDF APS](https://link.aps.org/pdf/10.1103/PhysRevLett.100.052003).

Letto PDF locale `docs/papers/Ajaka_2008_EtaPi0_Photoproduction_PRL100_052003.pdf`; testo completo estratto e pagine 3–4 controllate visivamente. Il PDF locale contiene evidenziazioni preesistenti. Provenienza/hash nella nota precedente; nessuna riscrittura del PDF.

| Elemento | Evidenza esatta e conseguenza |
|---|---|
| Bersaglio | P.1: idrogeno liquido, lunghezza 12 cm. Densità e incertezza specifica del bersaglio non riportate nel testo letto. |
| Fig.2, p.3 | σ totale in μb contro Eγ; punti pieni = Ajaka, cerchi vuoti = Nakabayashi Ref.16. Errori mostrati **includono** sistematica complessiva stimata ≈7% da flusso, accettanza e fondo. Non aggiungere un altro 7% alle barre digitalizzate. |
| Griglia d'accettanza, p.3 | Il testo dichiara **15 bin Eγ fra 0.95 e 1.5 GeV**, 14 bin θπ⁰ fra 0° e 168°, 12 bin θη fra 0° e 84°. Non elenca bordi energetici e **non dichiara uniformità**. Il preset locale `ajaka_cross_section = 15 bin uniformi 0.95–1.50 GeV` coincide con numero/intervallo, ma uniformità e bordi sono scelta locale, non binning originale certificato. |
| Correzione d'accettanza | LAGGEN/GEANT3, efficienza ε(Eγ,θπ⁰,θη), più estrapolazione nel buco θπ⁰≤12°. Non basta assegnare zero a celle ε=0 e chiamare totale la somma restante. |
| Decadimenti | P.3 cita esplicitamente BR(η→γγ)=0.3938. Il testo non esplicita separatamente trattamento di BR(π⁰→γγ); non dedurre che sia assente o incluso nell'efficienza corrente. |
| Fig.3, pp.3–4 | Tre distribuzioni **dσ/dIM in μb/MeV**, per IM(pπ⁰), IM(pη), IM(ηπ⁰); ascisse massa in GeV. Righe Eγ=1.1, 1.2, 1.3, 1.4, 1.5 GeV. Testo indica cinque intervalli energetici stretti ma non ne specifica bordi/larghezze. Aree normalizzate alla σ totale sperimentale alla stessa energia. |
| Fig.4, pp.4–5 | È Σ, non sezione d'urto. Quattro intervalli 1.1–1.2, 1.2–1.3, 1.3–1.4, 1.4–1.5 GeV, dieci bin massa e dodici φ. **Non trasferire** questo binning alla Fig.3. |

Non individuata tabella numerica originale Ajaka nelle fonti consultate; query dedicata HEPData senza risultato pertinente. Questo non prova assenza d'archivio. Non digitalizzati punti né inventati bordi/errori. Confronto quantitativo richiede dati originali o digitalizzazione dichiarata con incertezza; χ² richiede anche trattamento delle correlazioni di normalizzazione. Possibile sovrapposizione fra campione corrente e campione Ajaka: da verificare.

## B. Letteratura sul bersaglio e sul flusso

**B1.** O. Bartalini et al., *Measurement of π⁰ photoproduction on the proton from 550 to 1500 MeV at GRAAL*, EPJA **26**, 399–419 (2005), [DOI/editore](https://link.springer.com/article/10.1140/epja/i2005-10191-2). Testo primario consultato nella [copia caricata dal coautore P. Levi Sandri](https://www.researchgate.net/publication/227320283_Measurement_of_pphotoproduction_on_the_proton_from_550_to_1500_MeV_at_GRAAL); accesso editoriale integrale non disponibile.

- §§2.2.4–2.3: bersagli 3, 6, 12 cm; LH₂ a 18 K, ρ≈0.07 g/cm³. Monitor calibrato con SPACAL a basso rate: efficienza (2.68±0.03)%, comprensiva della conversione dei fotoni fra target e monitor.
- §§2.5,3.2–3.3: DAQ descritta con dead time trascurabile; trigger monitor prescalato 1000. Stessa selezione tagger per fisica e monitor. Eq.8: **F(i)=N_scal·N_mon*(i)/(N_mon·ε_mon)**; scaler conta coincidenze monitor–TAG, rapporto monitor selezionato/totale fornisce frazione energetica e selezione del picco temporale vero.
- §3.6.2: 2.3% globale combina monitor, densità e lunghezza, senza separare qui le componenti. È un altro campione/canale, non sistematica da adottare automaticamente.

**B2.** O. Bartalini et al., *Measurement of η photoproduction on the proton from threshold to 1500 MeV*, EPJA **33**, 169–184 (2007), [arXiv:0707.1385v1, PDF primario](https://arxiv.org/pdf/0707.1385), [DOI](https://doi.org/10.1140/epja/i2007-10439-9).

§2, p.2: bersaglio **6 cm** per quel campione, 18 K e densità approssimata precedente; cella diametro 4 cm, finestre Mylar 100 μm. §3.3, p.4: simulazione adattata ai periodi e alla posizione longitudinale del bersaglio; 2.3% globale da monitor, densità e lunghezza. §4: dati sotto 850 MeV riusano precedente misura con **3 cm**. Conferma concreta che lunghezza e accettanza dipendono dal periodo.

**B3.** F. Renard et al., *Differential cross section measurement of η photoproduction on the proton from threshold to 1100 MeV*, PLB **528**, 215–220 (2002), [PDF istituzionale ISS](https://publ.iss.it/ITA/Items/GetPDF?uuid=d285be6f-110f-45c3-a8c0-2dfd5bc50233), [DOI](https://doi.org/10.1016/S0370-2693(02)01196-6).

P.217: spessore areale **0.217±0.003 g/cm²**, contributo sistematico 1.5%; pareti misurate con target vuoto, 0.9%. Coincidenze tagger-monitor e ToF usate per correzione accidentali. Valore riferito al campione ηp storico; non è spessore del target Ajaka da 12 cm.

## C. Invarianti da preservare nell'implementazione

Raccomandazioni derivate, non ulteriori misure pubblicate:

1. Convertire densità **massica** in densità areale di protoni: `n_p = ρ·L·N_A/M_H` (equivalentemente `2ρ·L·N_A/M_H2`), unità cm⁻². Con i soli valori approssimati 0.07 g/cm³ e 12 cm: ρL≈0.84 g/cm², n_p≈5×10²³ cm⁻². Solo controllo d'ordine di grandezza, non calibrazione.
2. Per un periodo: `σ[μb] = N_corr / (Nγ · n_p · B · 10⁻³⁰ cm²/μb)`. `N_corr` include sottrazione fondo e correzione d'accettanza; `B` include soltanto decadimenti non già incorporati nell'efficienza. Per dσ/dM dividere inoltre per ΔM **in MeV** per confronto con Fig.3. σ(Eγ) mediata su bin usa flusso integrato: nessuna divisione extra per ΔEγ.
3. Se target/configurazione cambiano, conservare periodi e rispettive luminosità/efficienze. Sommare flussi assumendo un unico target è valido soltanto dopo verifica dell'identità della normalizzazione.
4. Non moltiplicare il flusso corrente per efficienza di tagging, inverso monitor, prescale o live time senza sapere quali fattori contenga già. Eq.8 documenta un metodo storico; non certifica contenuto dei file attuali.
5. Non identificare sistematica bersaglio, globale e bin-per-bin. Tenere scala comune separata; conservare eventuali correlazioni nel confronto.

## D. Informazioni che letteratura non risolve per i nostri run

- Quali periodi/run sono inclusi? Target 12 cm per tutti, o combinazione 3/6/12 cm? Disponibili misura calibrata `ρL`/`n_p`, incertezza, posizione e log di temperatura/pressione?
- File flussi contengono fotoni assoluti sul bersaglio oppure conteggi monitor/scaler? Quali correzioni sono già applicate: ε_monitor, tagging, selezione temporale, prescale, live time? Quale incertezza e correlazione H/V/energia?
- Disponibili campioni target vuoto e relative esposizioni? Disponibile MC completo del rivelatore per ciascuna configurazione, oltre al solo smearing? Quale trattamento dei decadimenti nel generatore?
- Disponibili tabelle originali Ajaka, bordi Fig.2/3, separazione statistica/sistematica e relazione del campione corrente con quello pubblicato?

Ricerca limitata a fonti direttamente utili. Esclusi risultati omonimi GRAAL di astronomia e software. Mancata disponibilità di dettagli qui non implica loro assenza negli archivi della collaborazione.

## E. Verifica mirata dell'associazione periodo → lunghezza

Controllo aggiuntivo, stessa data, limitato alle fonti sopra e a query mirate per 1998/1999/2002. Manifest P indicato dall'analisi corrente: `1998_uv`, `1999_uv`, `1999_vis`, `2000_fuv`, `2000_uv1`, `2000_uv2`, `2000_vis`, `2001_uv`, `2002_uv1`, `2002_uv2`, `2002_vis1`, `2002_vis2`, `2003_vis`.

**Nessuna associazione verificata fra questi identificatori e 3/6/12 cm.** B1 descrive nove periodi distribuiti su quattro anni con configurazioni diverse, senza tabella che associ anni/run e target. B2 associa 6 cm al proprio campione ηp e 3 cm alla misura precedente riusata sotto 850 MeV; non ai nomi del manifest. Ajaka associa 12 cm al campione pηπ⁰ pubblicato, senza identificare i periodi di questo manifest. Anno editoriale, lunghezza d'onda UV/vis e coincidenza del canale non consentono da soli il collegamento.

Passo utile successivo: recuperare geometrie/configurazioni del simulatore e run log, cercando una corrispondenza esplicita con questi periodi. Una costante di default nel simulatore documenterebbe soltanto quella configurazione MC, finché non collegata ai run reali. Nessun mapping numerico aggiunto.
