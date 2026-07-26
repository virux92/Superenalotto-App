# Versione 2.4 — Gestione archivio centralizzata

La schermata principale è ora dedicata esclusivamente ad analisi, sistemi,
statistiche, backtest e consultazione.

## Modifiche principali

- rimossi dalla home l'inserimento temporaneo, l'importazione CSV e il download;
- eliminato l'archivio modificabile conservato in `st.session_state`;
- la home legge sempre la fonte primaria corrente;
- aggiunto in **Amministrazione Database** l'inserimento permanente di una nuova estrazione;
- aggiunta la correzione controllata di un concorso esistente;
- aggiunta l'eliminazione protetta della sola ultima estrazione;
- importazione massiva e backup riordinati in schede dedicate;
- differenza tra Supabase e CSV GitHub descritta come situazione normale;
- svuotamento automatico della cache dopo ogni scrittura.

## Regola operativa

- nuove estrazioni e correzioni: **Supabase / Amministrazione Database**;
- modifiche del programma: **GitHub**;
- `estrazioni.csv`: copia di emergenza, non archivio vivo.

Le operazioni di eliminazione richiedono una conferma testuale e sono limitate
all'ultima estrazione, così non si creano buchi nella sequenza annuale.
