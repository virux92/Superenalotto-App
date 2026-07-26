# SuperEnalotto — Analisi statistica e sistemi

Versione **2.3.0**.

## Architettura

- `app.py`: interfaccia principale;
- `core/`: metriche, analisi, combinazioni, backtest ed esperimenti;
- `services/`: caricamento e validazione archivio;
- `pages/10_Laboratorio.py`: confronto sperimentale delle strategie;
- `pages/99_Amministrazione_Database.py`: gestione Supabase e backup;
- `tests/`: controlli automatici del motore.

La fonte principale è Supabase, con fallback sul CSV del repository.

Il software analizza dati storici e confronta euristiche. Non può prevedere
estrazioni casuali né modificare le probabilità matematiche del gioco.
