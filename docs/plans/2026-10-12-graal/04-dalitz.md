# 4 — Dalitz: completare quanto già esiste

> Completato il 13 ottobre 2026. [Relazione e verifiche](../../research/2026-10-13-dalitz.md).

**Obiettivo:** analisi Dalitz leggibile e riproducibile, con masse, selezioni e normalizzazioni esplicite.

**Architettura:** estendere `plots/dalitz.py` e adapter esistenti; nessuna seconda pipeline cinematica. **Stack:** PyROOT, NumPy. **Spec:** [README](README.md), [audit](00-stato-verificato.md).

## Già fatto

M(pη) contro M(pπ0), varianti protone misurato/implicito, masse mesoni, M(η) contro M(π0), confronti χ²/BDT, PDF e `istogrammi.root` già implementati. Test Dalitz inclusi nei 108 passati. Attuali TH1/TH2 usano conteggi unitari, senza correzione d'accettanza. Non rifare questi prodotti.

## Invarianti e dipendenze

Nuova baseline senza 6C; stessi tagli per confronti χ²/BDT salvo gate. Masse comuni: mp=0.938272, mη=0.547862, mπ0=0.134977 GeV. Separare M in GeV da M² in GeV². Protone implicito è missing mass e non misura indipendente del rinculo. Nessuna selezione automatica degli eventi fuori bordo: prima diagnosticarli come risoluzione/ricostruzione.

## File candidati

`plots/dalitz.py`, `plots/core/kinematics.py`, `plots/core/reconstruction_data.py`, `scripts/plot_campaign.py`; test `plots/tests/test_dalitz.py`, `test_kinematics.py`, `test_reconstruction_data.py`, `tests/test_plot_campaign.py`. Relazione e dizionario istogrammi in `docs/research/` e dentro ROOT.

## Passi e metodo

- [x] Inventariare ROOT/PDF già prodotti; verificare assi, contenuti, overflow e selezione di provenienza. Se soddisfano requisito, documentare e fermare estensione corrispondente.
- [x] Produrre dalla nuova baseline raw le viste già disponibili. Salvare campione, profilo, periodo se disponibile, intervallo energia, tagli, conteggi, masse e unità in oggetti ROOT leggibili.
- [x] Aggiungere vista canonica `s_peta=M²(pη)` contro `s_ppi0=M²(pπ0)` se utile per confronto di densità/letteratura, mantenendo vista M già esistente. Nessuna trasformazione di densità senza Jacobiano/bordi espliciti.
- [x] Per energia fissata, verificare `s_peta+s_ppi0+s_etapi0 = W²+mp²+mη²+mπ0²` su eventi on-shell di test. Per raw con masse ricostruite e non-conservazione, mostrare residuo invece di imporre identità. In bin energetico finito, inviluppo cinematico non equivale a unico bordo a W medio.
- [x] Conservare istogrammi di yield; aggiungere confronti a area unitaria solo con etichetta distinta. Eventuale normalizzazione a flusso resta yield normalizzato, non sezione d'urto senza target, efficienza e accettanza. Correzione d'accettanza richiede MC indipendente e celle con supporto adeguato: proposta separata, non automatica.
- [x] Test conteggi inclusi under/overflow, assi/masse e lettura ROOT; controllo visivo PDF su raw senza fit. Ripetere con campione vuoto e dominio cinematico limite.

```bash
python3 -m pytest -q plots/tests/test_dalitz.py plots/tests/test_kinematics.py \
  plots/tests/test_reconstruction_data.py tests/test_plot_campaign.py
```

**Consegna:** riuso verificato dei plot, ROOT auto-documentato e relazione su popolazioni/normalizzazione. Nessuna nuova interpretazione risonante o misura di sezione d'urto dal solo colore del Dalitz. Il taglio sulle masse dei due mesoni appartiene al punto 10.
