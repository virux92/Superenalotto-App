# SuperEnalotto Quantitative Research Engine

Applicazione personale Streamlit con archivio primario Supabase, analisi descrittiva, generazione di sestine e sistemi, e backtest walk-forward.

## Principio scientifico

Il software non promette di prevedere un'estrazione casuale. Frequenze, ritardi e associazioni descrivono lo storico; ogni configurazione deve essere confrontata con benchmark e dati fuori campione.

## Struttura

- `app.py`: interfaccia Streamlit.
- `core/`: metriche, analisi, combinazioni e backtest.
- `services/`: accesso archivio e operazioni sulle estrazioni.
- `database.py`: accesso PostgreSQL/Supabase.
- `pages/99_Amministrazione_Database.py`: diagnostica, importazione e backup.
- `tests/`: test automatici senza dipendenze aggiuntive.

## Test

```bash
python -m unittest discover -s tests -v
```
