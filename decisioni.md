Caveman disattivato. Puoi rispondere con `APPROVO TUTTI I DEFAULT` più eventuali eccezioni numerate.

## A. Flusso e polarizzazione — decisioni bloccanti

1. **Semantica di `BREM`**  
   Confermi che:

   - `runXXXX_POL1` = flusso degli eventi con `Polarization == 1`;
   - `runXXXX_POL2` = flusso degli eventi con `Polarization == 2`;
   - `runXXXX_BREM` = flusso degli eventi con `Polarization == 0`;
   - `BREM` non deve essere sottratto da `POL1` o `POL2`.

   **Default raccomandato:** sì, tre esposizioni indipendenti.

2. **Orientamento**  
   Confermi definitivamente:

   - `POL1` = polarizzazione orizzontale;
   - `POL2` = polarizzazione verticale;
   - questa associazione non cambia tra periodi/run.

   **Default:** associazione fissa per tutti i run.

3. **Corrispondenza strip**  
   Confermi che bin ROOT `i` dell’istogramma corrisponde direttamente a `Xstrip == i`, con strip 1–128?

   **Default:** sì.

4. **Contenuto istogrammi**  
   I valori sono già flussi fisici corretti per live time, dead time, efficienza del tagger e normalizzazione scaler, oppure sono conteggi grezzi?

   **Default provvisorio:** trattarli come flussi finali. Questo va confermato prima di pubblicare Σ.

5. **Errori del flusso**  
   Gli errori ROOT dei bin sono significativi? Devono entrare nell’incertezza di Σ?

   **Default:** leggerli e conservarli; se non documentati, non usarli come errori fisici e riportare incertezza di flusso separata.

6. **Run extra nel file di flusso**  
   `flux.root` contiene 307 run non presenti nel manifest, mentre tutti i run del manifest sono presenti. Cosa facciamo?

   **Default:** ignorare run extra con warning; manifest e campione eventi definiscono run utilizzabili.

7. **Run-quality mask**  
   Esiste lista di run/strip da escludere per problemi di acquisizione, polarizzazione, tagger o detector?

   **Default:** nessuna maschera aggiuntiva oltre QA automatica, finché non viene fornita.

8. **Polarizzazione del fascio \(P_\gamma(E)\)**  
   Usiamo funzione Compton già presente con:

   - energia elettroni 6027.6 MeV;
   - UV 351 nm;
   - VIS 514 nm.

   Oppure esiste calibrazione sperimentale run-by-run da usare?

   **Default:** funzione Compton esistente; 3% di incertezza relativa come nel paper.

9. **Offset angolare**  
   Consideriamo piani POL1/POL2 esattamente a \(0^\circ/90^\circ\), oppure esiste offset misurato rispetto all’asse \(x\)?

   **Default:** \(0^\circ/90^\circ\), con termine \(\sin 2\phi\) usato come controllo di offset.

## B. Campione dati

10. **Replica stretta del paper**  
    Per Fig. 4 usiamo solo:

    - bersaglio `P`;
    - fascio `UV`;
    - \(1.1 \le E_\gamma \le 1.5\) GeV;
    - `Polarization` 1 o 2.

    **Default raccomandato:** sì. VIS, deuterio e BREM esclusi dal risultato nominale.

11. **Dati BREM**  
    Gli eventi `Polarization == 0` non misurano Σ. Li usiamo solo per controllare distribuzione azimutale e accettanza?

    **Default:** sì, solo controllo/null test.

12. **Percorsi dati**  
    Nel workspace vedo solo `data/00_external/flux.root`; non vedo preanalysis, selected o reco. Dove saranno disponibili:

    - file `h80` inclusivi per calibrazione strip→energia;
    - file selected `h85`;
    - eventuale `results/reco/reco_eta_pi0_bdt.root`?

    Indica percorsi oppure conferma che verranno aggiunti più avanti.

13. **Manifest**  
    Il file corrente `config/run_manifest.csv` è autorevole per bersaglio e laser, oppure deve essere rigenerato dai dati reali?

    **Default:** usare manifest corrente dopo confronto con run realmente presenti.

14. **Esattamente quattro fotoni**  
    Paper richiede quattro particelle neutre. Ricostruzione attuale accetta `>=4` fotoni e usa solo primi quattro: possibile errore fisico.

    Scegli:

    - richiedere esattamente 4 fotoni;
    - cercare migliore combinazione di 4 tra tutti i fotoni;
    - mantenere primi quattro.

    **Default raccomandato:** esattamente 4 per replica del paper; migliore combinazione come estensione successiva. Eviterei “primi quattro”.

15. **Protone finale**  
    Manteniamo requisito esattamente un protone ricostruito?

    **Default:** sì.

16. **Soglia BDT**  
    Usiamo soglia versionata `0.275930` senza riottimizzazione sui dati?

    **Default:** sì. Variazioni di soglia solo come sistematica.

17. **Salvataggio score BDT**  
    Output attuale salva solo eventi accettati, non score. Aggiungiamo ramo `bdt_score` per controlli e variazioni offline?

    **Default raccomandato:** sì, ma richiede nuova ricostruzione.

## C. Cinematica

18. **Vettori raw o fitted**  
    Paper non usa nostro fit cinematico; inoltre provenance segnala covarianza detector `legacy-uncalibrated`.

    Scegli risultato nominale:

    - raw, più fedele al paper;
    - fitted, migliore risoluzione;
    - entrambi.

    **Default raccomandato:** raw nominale per prima replica; fitted come confronto/sistematica.

19. **Definizione di \(\phi\)**  
    Per ogni colonna calcoliamo:

    \[
    \phi_{p\pi^0}=\operatorname{atan2}[(p+\pi^0)_y,(p+\pi^0)_x]
    \]

    e analogamente per \(p\eta\) e \(\eta\pi^0\), nel sistema con \(z\) lungo fascio e \(x\) orizzontale.

    **Default:** sì. Boost lungo \(z\) non modifica azimut.

20. **Intervallo di \(\phi\)**  
    12 bin uniformi in \([0,2\pi)\), quindi 30° ciascuno?

    **Default raccomandato:** sì.

21. **Binning energetico**  
    Confermi bordi esatti:

    \[
    [1.1,1.2,1.3,1.4,1.5]\ {\rm GeV}
    \]

    con intervalli `[low, high)` e ultimo bordo incluso?

    **Default:** sì.

22. **Binning delle masse**  
    Paper specifica 10 bin ma non riporta bordi numerici. Possibili scelte:

    - inferire bordi dagli assi della figura;
    - usare limiti cinematici globali tra soglia e \(E_\gamma=1.5\);
    - usare bordi storici GRAAL, se li conosci;
    - digitalizzare Fig. 4 per ricostruire centri esatti.

    **Default raccomandato:** 10 bin uniformi tra soglia fisica della coppia e massimo cinematico globale; documentare che bordi sono ricostruiti, non esplicitati dal paper.

23. **Centro dei punti**  
    Usiamo centro geometrico del bin oppure media degli eventi nel bin?

    **Default:** centro geometrico, coerente con replica grafica; media come dato ausiliario.

## D. Estrazione statistica

24. **Metodo nominale**  
    Scegli:

    - rapporto binned e fit \(\cos2\phi\), più fedele al paper;
    - likelihood Poisson simultanea, più robusta;
    - entrambi.

    **Default raccomandato:** entrambi. Rapporto binned come benchmark; likelihood come risultato nominale solo dopo accordo tra metodi.

25. **Polarizzazione effettiva**  
    Per benchmark binned calcoliamo \(P_H\) e \(P_V\) medi, pesati col rispettivo flusso run/strip. Per likelihood manteniamo stratificazione run/strip o periodo.

    **Default:** sì.

26. **Modello del fit nominale**

    \[
    R(\phi)=\Sigma\cos 2\phi
    \]

    senza costante e senza fase libera?

    **Default:** sì.

27. **Fit diagnostico**  
    Eseguiamo anche:

    \[
    R(\phi)=c_0+c_2\cos2\phi+s_2\sin2\phi
    \]

    per controllare offset, falsa asimmetria e mancata cancellazione dell’accettanza?

    **Default raccomandato:** sì; non sostituisce fit nominale.

28. **Convenzione di segno**  
    Con POL1 orizzontale:

    \[
    R=\frac{y_V-y_H}{P_Hy_V+P_Vy_H}.
    \]

    Confermiamo segno tramite campione sintetico e confronto qualitativo col paper?

    **Default:** sì; test automatico obbligatorio.

29. **Bin a bassa statistica**  
    Come trattarli?

    **Default:** produrre punto solo se entrambe le polarizzazioni hanno flusso positivo e fit converge; altrimenti `invalid/low-stat`, senza inventare zero.

30. **Errori statistici**  
    Preferisci errore dal fit come paper, oppure intervallo di profile likelihood?

    **Default:** errore del fit per figura; profile likelihood nei dati tabellari e per bin problematici.

31. **Correlazioni**  
    Vuoi matrice di covarianza tra punti di massa?

    **Default:** sì per ciascuna colonna tramite bootstrap per run; correlazioni tra tre colonne documentate ma non necessarie per prima figura.

## E. Fondo e sistematiche

32. **Trattamento fondo nella prima iterazione**  
    Scegli:

    - nessuna correzione, solo risultato BDT-gated;
    - sideband sui valori raw;
    - fit di massa;
    - template MC/data-driven.

    **Default raccomandato:** prima estrazione senza correzione ma chiaramente etichettata; poi stima fondo e correzione prima del risultato fisico finale.

33. **Asimmetria del fondo**  
    Se fondo residuo non è nullo:

    \[
    \Sigma_{\rm sig}
    =
    \frac{\Sigma_{\rm obs}-f_{\rm bkg}\Sigma_{\rm bkg}}
         {1-f_{\rm bkg}}.
    \]

    Disponiamo di sideband o campioni di fondo utili?

    **Default:** stimare \(f_{\rm bkg}\) e \(\Sigma_{\rm bkg}\) dai raw masses/sideband, non assumere automaticamente \(\Sigma_{\rm bkg}=0\).

34. **Sistematiche minime**  
    Confermi questo set:

    - polarizzazione fascio, 3%;
    - normalizzazione flusso;
    - fondo residuo;
    - soglia BDT;
    - raw contro fitted;
    - binning massa/\(\phi\);
    - split per periodo/run;
    - offset angolare/\(\sin2\phi\);
    - scelta metodo statistico.

    **Default:** sì.

35. **Controlli di falsa asimmetria**  
    Eseguiamo:

    - split temporali;
    - split periodi;
    - randomizzazione POL1/POL2;
    - pseudo-asimmetria tra sottocampioni della stessa polarizzazione;
    - controllo BREM;
    - fit del termine \(\sin2\phi\).

    **Default raccomandato:** tutti.

36. **Accettanza MC**  
    Per Σ il rapporto H/V dovrebbe cancellare accettanza comune. Vuoi comunque correzione MC?

    **Default:** nessuna correzione MC nel primo risultato; MC usato per verificare che accettanza e gate non generino falsa modulazione.

## F. Output e implementazione

37. **Curve teoriche**  
    Vuoi:

    - solo punti sperimentali;
    - digitalizzazione curve del paper;
    - futura integrazione del modello teorico originale.

    **Default raccomandato:** solo punti sperimentali. Non digitalizzare curve come se fossero nuova previsione.

38. **Output richiesti**  
    Propongo:

    - PDF stile Fig. 4;
    - ROOT con istogrammi, grafici e fit;
    - CSV con ogni punto di Σ;
    - JSON QA/provenance;
    - figure diagnostiche \(R(\phi)\) e fit;
    - riepilogo sistematiche.

    **Default:** tutti.

39. **Posizione codice**  
    Creiamo `06_observable_extraction/`, come già previsto nella documentazione, lasciando rendering finale in `06_plots/`?

    **Default raccomandato:** sì.

40. **Compatibilità calibratore**  
    Modifichiamo schema corrente rimuovendo `pol1_net/pol2_net`, oppure introduciamo schema v2 mantenendo vecchi campi?

    **Default raccomandato:** schema v2 esplicito con `flux_pol1`, `flux_pol2`, `flux_brem`; niente campi “net” ambigui.

41. **Integrazione pipeline**  
    Prima comando standalone verificabile, poi integrazione in `run_pipeline.sh`?

    **Default raccomandato:** sì.

42. **Criterio di successo prima milestone**  
    Consideriamo milestone completata quando:

    - flusso passa QA;
    - campione P/UV è consistente;
    - test sintetici recuperano Σ iniettata;
    - rapporto e likelihood concordano;
    - viene prodotta Fig. 4 senza curve teoriche;
    - ogni punto possiede conteggi, flussi, \(P_\gamma\), errore e stato QA.

    **Default:** sì.