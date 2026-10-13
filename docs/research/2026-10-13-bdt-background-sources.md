# Audit mirato delle fonti dei fondi BDT

Data: 2026-10-13. Ambito: ancoraggi di `00_common/physics/channels.py`, decadimenti e possibili sovrapposizioni. Nessun parametro fisico o codice modificato. Le letture grafiche sotto servono a verificare la plausibilità; non costituiscono nuovi punti digitalizzati con errori sperimentali.

## Ancoraggi delle sezioni d'urto

| Canale | Registro attuale | Esito della verifica primaria |
|---|---|---|
| `3pi0` | 1.8 μb a 1.26 GeV | **Verificato come arrotondamento**: Kashevarov et al., Tab. I, **1.808 ± 0.019 μb a 1255 ± 6 MeV**; errore statistico, sistematico globale stimato 15% nel testo. La componente η→3π⁰ è sottratta. [Articolo, Tab. I e §III](https://arxiv.org/pdf/1101.3744) |
| `omega_pi0` | 0.49 μb a 1.60 GeV | **Valore verificato, interpretazione puntuale no**: Junkersfeld et al., Tab. 3, **0.49 ± 0.13 μb nel bin 1383–1817 MeV**; sistematici separati nelle figure. 1.600 GeV è il centro aritmetico di un bin molto largo, non una misura locale. [Articolo, Tab. 3](https://arxiv.org/pdf/0704.0710) |
| `eta_via_3pi0` | 0.65 μb = circa 2.0×0.327 a 1.03 GeV | **Non confermato; il 2.0 μb è incompatibile con il minimo mostrato**. A Eγ=1.03 GeV corrisponde W=1.6773 GeV; Fig. 7(b) mostra circa **2.8–3.0 μb** nella regione del minimo. Il range è una lettura grafica, non un intervallo di confidenza. Il picco di Fig. 6 è circa 16 μb. [McNicoll et al., Figg. 6–7](https://arxiv.org/pdf/1007.0777) |
| `etaprime` | 0.35 μb a 1.60 GeV | **Non confermato; incompatibile con Fig. 15**: Eγ=1.60 GeV implica W=1.9705 GeV; i punti vicini sono circa **0.8–0.9 μb**, lettura grafica. L'ascissa della figura è W, non Eγ. Nessun punto tabulato 0.35 μb a 1.60 GeV verificato. [Crede et al., Fig. 15](https://arxiv.org/pdf/0909.1248) |
| `pi0pi0` | 4.5 μb a 2.2 GeV, Sarantsev EPJA 25 (2005) 441 | **Citazione errata, numero non verificato**: il paper citato tratta decadimenti in ΛK⁺, Σ⁰K⁺ e Σ⁺K⁰. [Paper originale](https://www.cb.uni-bonn.de/fileadmin/user_upload/internal/Publication/Publication_EurPhysJA_25_2005_441_SarantsevAVEtAl.pdf). Thoma et al. PLB 659 (2008) 87 tratta davvero π⁰π⁰, ma i suoi dati coprono Eγ=0.4–1.3 GeV: non valida il punto a 2.2 GeV. [Thoma et al.](https://arxiv.org/pdf/0707.3592) |
| `eta_2pi0` | 0.3 μb a 1.90 GeV, «ceilinged by eta′», fattore 2–3 | **Stima non verificata**: nessuna misura esclusiva del continuo pηπ⁰π⁰ trovata nella ricerca mirata. La sezione totale η′ non dimostra un limite superiore al continuo. Il fattore 2–3 non ha una fonte verificata. |
| `4pi0` | 0.2 μb a 1.45 GeV, «upper bound» | **Limite non verificato**: scalarlo dalla sezione 3π⁰ non dimostra un limite superiore. Esistono misure di sottocanali che terminano in p4π⁰, descritte sotto; non è corretto estendere «nessuna misura» a ogni processo con questa topologia. |

Per confrontare grafici in W con energie del tagger è stato usato W²=mₚ²+2mₚEγ. Le sole figure non giustificano una sostituzione silenziosa degli ancoraggi: occorre acquisire punti e binning originali o dichiarare una digitalizzazione, mantenendo errori statistici e sistematici distinti. Un modello monotono di spazio delle fasi non riproduce il picco e la discesa misurati in η, né i due massimi documentati in π⁰π⁰.

## Branching ratio: confronto con PDG 2025

| Decadimento | Valore verificato | Fonte |
|---|---|---|
| η→3π⁰ | 0.3256 ± 0.0021 | [PDG η, p. 1](https://pdg.lbl.gov/2025/listings/rpp2025-list-eta.pdf) |
| η→γγ | 0.3936 ± 0.0018 | [PDG η, p. 1](https://pdg.lbl.gov/2025/listings/rpp2025-list-eta.pdf) |
| BR(η→3π⁰)/BR(η→γγ) | **0.827 ± 0.006**, fit PDG | [PDG η, p. 5](https://pdg.lbl.gov/2025/listings/rpp2025-list-eta.pdf) |
| η′→ηπ⁰π⁰ | 0.224 ± 0.005 | [PDG η′, p. 1](https://pdg.lbl.gov/2025/listings/rpp2025-list-eta-prime-958.pdf) |
| ω→π⁰γ | 0.0833 ± 0.0025 | [PDG ω, p. 3](https://pdg.lbl.gov/2025/listings/rpp2025-list-omega-782.pdf) |
| π⁰→γγ | 0.98823 ± 0.00034 | [PDG π⁰, p. 2](https://pdg.lbl.gov/2025/listings/rpp2025-list-pi-zero.pdf) |

I valori 0.327, 0.394 e 0.228 nel registro sono approssimazioni/valori precedenti, non i centrali di questa edizione. Usare il rapporto PDG evita di inventare un errore assumendo branching ratio indipendenti: provengono da un fit correlato.

**Convenzione da rendere esplicita:** se il generatore forza un decadimento, la normalizzazione al numero prodotto deve contenere il prodotto dei BR della catena una sola volta. Esempi: ωπ⁰→5γ richiede BR(ω→π⁰γ)×BR(π⁰→γγ)²; η′→ηπ⁰π⁰→6γ richiede BR(η′→ηπ⁰π⁰)×BR(η→γγ)×BR(π⁰→γγ)². Per il rapporto completo 8γ/4γ del segnale compare anche BR(π⁰→γγ)³, oltre al rapporto dei decadimenti η, salvo una convenzione esplicita che tratti tutti i π⁰→γγ con probabilità unitaria. Verificare dove i BR siano già applicati prima di modificarli.

## Sovrapposizioni e candidati

1. **3π⁰ diretto e η→3π⁰ sono separabili nella fonte scelta.** Kashevarov sottrae η→3π⁰; quindi usare quel totale e aggiungere il campione η non duplica intenzionalmente l'η. «Diretto» qui significa non proveniente dal decadimento η: non significa assenza di risonanze barioniche. La fonte segnala inoltre K⁰SΣ⁺→3π⁰p **non sottratto** sopra Eγ≈1.05 GeV. Aggiungere quel canale richiede una convenzione che eviti il doppio conteggio nella normalizzazione 3π⁰. [Kashevarov, §II–III](https://arxiv.org/pdf/1101.3744)

2. **ηπ⁰π⁰ inclusivo ed η′ non sono indipendenti.** La catena η′→ηπ⁰π⁰ è proprio quella usata per identificare η′ in Crede. Se `eta_2pi0` descrive l'inclusivo, include questo contributo; per sommarlo a `etaprime` va definito come continuo privo dell'η′ e normalizzato coerentemente. Nel trattamento usuale con risonanza stretta, il contributo η′ è σ(γη′p)×BR(η′→ηπ⁰π⁰): non un limite superiore al continuo. La ricerca svolta non stabilisce un intervallo numerico del continuo. [Crede, canale (3)](https://arxiv.org/pdf/0909.1248)

3. **4π⁰ inclusivo e ηπ⁰ con η→3π⁰ si sovrappongono.** Nanova et al. analizzano p4π⁰→p8γ, rimuovono esplicitamente pηπ⁰ e misurano K⁰π⁰Σ⁺ e K*⁰Σ⁺. Il primo ha soglia cinematica circa 1.300 GeV e quindi merita un audit nel dominio GRAAL; il paper contiene un bin 1400–1500 MeV. Il generatore di continuo `4pi0` deve indicare quali sottocanali esclude. Questa fonte non fornisce un bound 0.2 μb per il residuo non risonante. [Nanova et al., §3–6](https://arxiv.org/pdf/0803.2146)

4. **Esclusioni motivate dal solo conteggio dei fotoni.** Con perdita di fotoni, senza splitting, accidentali o identificazioni errate, γp→pω, ω→π⁰γ→3γ non può produrre quattro fotoni osservati. Lo stesso vale per pπ⁰→p2γ e pη→p2γ. Non escludere genericamente tutta la produzione ω: decadimenti rari o altre catene hanno molteplicità diverse. Per esempio PDG riporta ω→π⁰π⁰γ con BR=(6.7±1.1)×10⁻⁵, capace di dare cinque fotoni. [PDG ω, p. 4](https://pdg.lbl.gov/2025/listings/rpp2025-list-omega-782.pdf)

5. **η→3π⁰ non contiene una coppia γγ alla massa η.** Deduzione cinematica: due fotoni dello stesso π⁰ hanno massa mπ⁰; due fotoni da π⁰ diversi lasciano almeno il terzo π⁰ integro nel sistema complementare, quindi mγγ≤mη−mπ⁰≈0.413 GeV. Il commento del registro che attribuisce a questo campione un vero picco η nella coppia di fotoni è scorretto. Resta un fondo possibile dopo risoluzione, selezione e combinatoria, la cui importanza deve essere misurata dal MC; questa osservazione non ne giustifica la rimozione.

## Conseguenze operative

Conservare separati: quantità misurate, letture grafiche, modelli di forma e normalizzazioni ignote. Le stime 0.3 e 0.2 μb possono essere scenari dichiarati, ma non «upper bound» o misure. Non attribuire intervalli d'incertezza senza fonte. Prima di affermare trascurabile un canale servono flusso reale, soglia, catena di BR e accettanza dopo selezione; la sola molteplicità iniziale non determina il peso finale.
