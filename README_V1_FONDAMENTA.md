# SuperEnalotto App — v1.0 Fondamenta

Questa versione mantiene l'app statistica esistente e aggiunge una pagina amministrativa per:

- verificare la connessione PostgreSQL Supabase;
- importare le 1.168 estrazioni dal CSV;
- aggiornare concorsi già presenti senza crearne duplicati;
- esportare l'archivio Supabase in CSV o Excel.

## Installazione su GitHub

Caricare tutti i file del pacchetto nel repository `Superenalotto-App`, mantenendo le cartelle `pages` e `.streamlit`.

## Secrets Streamlit

In Streamlit Community Cloud aprire **Manage app → Settings → Secrets** e inserire:

```toml
[database]
url = "LA_URI_SESSION_POOLER_DI_SUPABASE"
```

Non inserire mai la password in GitHub.

## Primo avvio

1. Attendere il redeploy automatico di Streamlit.
2. Aprire la pagina **Amministrazione Database**.
3. Premere **Verifica connessione**.
4. Controllare che risultino 12 tabelle e 0 estrazioni.
5. Spuntare la conferma e premere **Importa in Supabase**.
6. Controllare che risultino 1.168 estrazioni.
7. Scaricare un backup CSV di prova.

## Nota

Il file `estrazioni.csv` rimane nel repository come copia iniziale. Dopo l'importazione, Supabase sarà la memoria permanente. La successiva versione farà leggere l'archivio principale direttamente dal database, con fallback sul CSV.
