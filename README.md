# SuperEnalotto — Analisi statistica e sistemi

Versione **2.5.1**.

## Architettura

- `app.py`: interfaccia principale di sola analisi e consultazione;
- `core/`: metriche, analisi, combinazioni, backtest ed esperimenti;
- `services/`: caricamento, validazione, operazioni sulle estrazioni e monitoraggio schedine;
- `pages/10_Laboratorio.py`: confronto sperimentale delle strategie;
- `pages/99_Amministrazione_Database.py`: gestione permanente di Supabase e backup;
- `tests/`: controlli automatici del motore.

La fonte principale è Supabase, con fallback sul CSV del repository. Le nuove
estrazioni si inseriscono soltanto nella pagina di amministrazione; GitHub resta
il contenitore del codice e il CSV è una copia di emergenza.

La scheda **Schedine monitorate** salva in Supabase le sestine consigliate o già
giocate e calcola automaticamente l’esito di ogni concorso, anche quando la stessa
schedina viene giocata per più estrazioni consecutive.

Il software analizza dati storici e confronta euristiche. Non può prevedere
estrazioni casuali né modificare le probabilità matematiche del gioco.
