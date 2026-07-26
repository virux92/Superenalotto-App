# Changelog

## v2.0.0 — Database First stabile

- Supabase resta la fonte primaria dell'archivio.
- Corretto il caricamento PostgreSQL eliminando `pandas.read_sql_query` su connessione psycopg diretta.
- Creato `services/archive_service.py` come unico punto di caricamento, normalizzazione e validazione.
- Aggiunto fallback automatico e diagnostico al CSV del repository.
- Aggiunta protezione contro eventuali righe d'intestazione lette come dati.
- Conservate le funzioni esistenti: statistiche, sestine, sistemi, backtest, archivio e amministrazione database.
