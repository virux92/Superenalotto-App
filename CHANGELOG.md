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

## v2.2 — Statistiche avanzate e validazione
- Creato `core/analytics.py` con strutture, decine, entropia, coppie, terzine, ripetizioni e stabilità annuale.
- Estratte le operazioni sulle estrazioni in `services/draw_service.py`.
- Aggiunto hash SHA-256 canonico dell'archivio e confronto Supabase/CSV.
- Aggiunto benchmark casuale deterministico e riproducibile al backtest.
- Aggiunte deviazione standard, intervallo di confidenza e stabilità annuale.
- Aggiunta suite di test automatici per archivio, metriche, analytics e assenza di future leakage.

## 2.3.0
- Aggiunto il Laboratorio sperimentale in una pagina dedicata.
- Introdotti sei profili di scoring confrontabili con backtest walk-forward.
- Aggiunto confronto appaiato con baseline casuale deterministica.
- Aggiunti intervalli descrittivi, stabilità annuale ed esportazione CSV.
- Aggiunta protezione opzionale del laboratorio tramite Streamlit Secrets.
- Aggiunti test automatici per il motore degli esperimenti.
