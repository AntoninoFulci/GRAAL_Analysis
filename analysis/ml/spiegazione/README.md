# Spiegazione del codice — studio BDT photon pairing

Cartella di documentazione per capire e presentare lo studio
(γ p → p η π⁰, scelta della combinazione corretta dei 4 fotoni: BDT vs χ²).

## Ordine di lettura consigliato

1. [GUIDA.md](GUIDA.md) — visione d'insieme: a cosa serve, come si usa, cosa è
   stato fatto passo passo, risultati.
2. [01_physics.md](01_physics.md) — `physics.py`: matematica dei quadrivettori
   (massa invariante, angoli, asimmetria, β, χ²).
3. [02_build_features.md](02_build_features.md) — `build_features.py`: lettura
   MC, mescolamento, 3 combinazioni, 54 feature, etichette. **Il file centrale.**
4. [03_train_bdt.md](03_train_bdt.md) — `train_bdt.py`: allenamento XGBoost e
   grafici diagnostici.
5. [04_evaluate_compare.md](04_evaluate_compare.md) — `evaluate_compare.py`:
   confronto BDT vs χ², spettri di massa, metriche.

Ogni file `0X_*.md` spiega il rispettivo sorgente quasi linea per linea.
