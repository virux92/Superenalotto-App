# Changelog

## v2.0.0 — Database First stabile

- Supabase resta la fonte primaria dell'archivio.
- Corretto il caricamento PostgreSQL eliminando `pandas.read_sql_query` su connessione psycopg diretta.
- Creato `services/archive_service.py` come unico punto di caricamento, normalizzazione e validazione.
- Aggiunto fallback automatico e diagnostico al CSV del repository.
- Aggiunta protezione contro eventuali righe d'intestazione lette come dati.
- Conservate le funzioni esistenti: statistiche, sestine, sistemi, backtest, archivio e amministrazione database.

## v2.1 — Motore modulare
- Estratte metriche e ranking SuperStar in `core/metrics.py`.
- Estratti filtri, scoring e sistemi in `core/combinations.py`.
- Estratto il backtest walk-forward in `core/backtest.py`.
- `app.py` conserva la UI e usa il motore tramite import stabili.
- Nessuna modifica alle formule o al comportamento della v2.0.
