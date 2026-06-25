# Spiegazione del codice — studio BDT γ p → p η π⁰

Documentazione passo per passo per capire e presentare lo studio (pipeline completa: fondo MC + stage-1 BDT + stage-2 BDT).

## Ordine di lettura consigliato

1. [GUIDA.md](GUIDA.md) — visione d'insieme: problema fisico, come si usa, passo passo, risultati, mappa dei file. **Inizia qui.**
2. [01_physics.md](01_physics.md) — `physics.py`: matematica dei quadrivettori vettorizzata (massa invariante, angoli, asimmetria, β, χ², boost di Lorentz nel CM).
3. [02_build_features.md](02_build_features.md) — `build_features.py`: lettura MC segnale, mescolamento fotoni, 3 combinazioni, feature 67-dim, etichette y. **File centrale per stage-2.**
4. [03_train_bdt.md](03_train_bdt.md) — `train_bdt.py`: allenamento XGBoost multiclasse e grafici diagnostici (stage-2).
5. [04_evaluate_compare.md](04_evaluate_compare.md) — `evaluate_compare.py`: confronto BDT vs χ², spettri di massa, metriche.

### Moduli aggiuntivi (stage-1 e fondo)

- `photon_loss.py` — modello sigmoid P_loss(E,θ): spiegato in [GUIDA.md §Passo 0c](GUIDA.md).
- `build_background_features.py` — feature 24-dim per classificazione segnale/fondo: spiegato in [GUIDA.md §Passo 1](GUIDA.md).
- `train_bdt_stage1.py` — BDT binario stage-1: spiegato in [GUIDA.md §Passo 2](GUIDA.md).
- Generatori MC di fondo (`simulation/generate_*.C`): spiegati in [GUIDA.md §Passo 0b](GUIDA.md).

Ogni file `0X_*.md` spiega il rispettivo sorgente quasi linea per linea.
