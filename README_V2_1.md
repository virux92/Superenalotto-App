# SuperEnalotto App v2.1 — Motore modulare

Questa versione separa la logica statistica e combinatoria dall'interfaccia Streamlit.

## Nuova struttura

- `core/metrics.py`: frequenza, ritardo, recency, score e ranking SuperStar.
- `core/combinations.py`: caratteristiche, filtri, ranking sestine e sistemi.
- `core/backtest.py`: backtest walk-forward e strategie baseline.
- `services/archive_service.py`: caricamento Supabase con fallback CSV.
- `app.py`: interfaccia e cache Streamlit.

Le formule e i risultati della v2.0 sono stati mantenuti invariati.
