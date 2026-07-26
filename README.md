# ORION — SuperEnalotto Quant Engine

Versione **2.7.0**.

ORION è un motore statistico multi-memoria con interfaccia Streamlit. Analizza lo storico, fonde segnali provenienti da cinque finestre e costruisce automaticamente sestine e sistemi coerenti con la struttura dell’archivio.

## Uso ordinario

La home è progettata per l’utente finale: mostra subito la proposta ORION, una spiegazione sintetica, il SuperStar statistico e i comandi per salvare o generare un’alternativa. Finestre, pesi e filtri non vengono scaricati sull’utente.

## Architettura

- `app.py`: dashboard principale ORION;
- `core/`: metriche, consenso multi-memoria, combinazioni, analisi e backtest;
- `services/`: archivio, estrazioni, monitoraggio schedine e presentazione dei risultati;
- `ui/`: tema e componenti grafici Streamlit;
- `pages/10_Laboratorio.py`: confronto sperimentale delle strategie;
- `pages/99_Amministrazione_Database.py`: gestione permanente di Supabase e backup;
- `tests/`: controlli automatici del motore.

La fonte principale è Supabase, con fallback sul CSV del repository. Le estrazioni permanenti si inseriscono dalla pagina di amministrazione. Le schedine monitorate vengono confrontate automaticamente con i concorsi successivi.

Il software organizza dati storici ed euristiche. Non può prevedere estrazioni casuali e non modifica la probabilità matematica della singola sestina.
