# Aggiornamento v1.1 — Database First

Questa versione rende Supabase la fonte dati primaria dell'app.

- Se Supabase è raggiungibile e contiene estrazioni, l'app usa il database.
- Se Supabase non è disponibile, l'app continua a funzionare usando `estrazioni.csv`.
- La schermata principale mostra la fonte dati attiva.

## Installazione

Sostituire soltanto `app.py` nel repository GitHub e confermare il commit.
Dopo il redeploy, eseguire un reboot dell'app Streamlit.

## Verifica

Sotto il titolo deve comparire: `Fonte dati attiva: Supabase`.
