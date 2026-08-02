# ORION — SuperEnalotto Quant Engine

Versione **2.7.2**.

ORION è un motore statistico multi-memoria con interfaccia Streamlit. FORGE lavora dietro le quinte: genera modelli candidati, li sottopone a backtest walk-forward, registra gli esperimenti già conclusi e promuove a ORION soltanto i candidati che superano i controlli operativi.

## Menu utente

L’interfaccia espone soltanto cinque sezioni:

- **Home**
- **Genera**
- **Schedine**
- **Archivio**
- **Impostazioni**

Pesi, finestre statistiche, filtri tecnici e comandi del vecchio Laboratorio non sono più esposti.

## Architettura

- `app.py`: interfaccia principale e navigazione essenziale;
- `core/orion.py`: consenso multi-memoria e costruzione dello stato ORION;
- `core/forge.py`: definizione, identificazione, validazione e promozione dei modelli candidati;
- `services/forge_service.py`: esecuzione automatica dei backtest e registro degli esperimenti;
- `database.py`: archivio Supabase, schedine monitorate e registro persistente FORGE;
- `ui/`: tema e componenti grafici già introdotti nella v2.7;
- `tests/`: controlli automatici del motore.

La fonte principale è Supabase, con fallback sul CSV del repository. FORGE usa Supabase per ricordare gli esperimenti quando disponibile e un registro locale di emergenza negli altri casi.

Il software organizza dati storici ed euristiche. Non può prevedere estrazioni casuali e non modifica la probabilità matematica della singola sestina.
