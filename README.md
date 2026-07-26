# SuperEnalotto — Analisi statistica e sistemi

Versione **2.4.0**.

## Architettura

- `app.py`: interfaccia principale di sola analisi e consultazione;
- `core/`: metriche, analisi, combinazioni, backtest ed esperimenti;
- `services/`: caricamento, validazione e operazioni sulle estrazioni;
- `pages/10_Laboratorio.py`: confronto sperimentale delle strategie;
- `pages/99_Amministrazione_Database.py`: gestione permanente di Supabase e backup;
- `tests/`: controlli automatici del motore.

La fonte principale è Supabase, con fallback sul CSV del repository. Le nuove
estrazioni si inseriscono soltanto nella pagina di amministrazione; GitHub resta
il contenitore del codice e il CSV è una copia di emergenza.

Il software analizza dati storici e confronta euristiche. Non può prevedere
estrazioni casuali né modificare le probabilità matematiche del gioco.
