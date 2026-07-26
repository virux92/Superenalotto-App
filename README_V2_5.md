# v2.5 — Schedine monitorate

Questa versione aggiunge il monitoraggio persistente delle sestine consigliate o giocate.

## Funzioni

- Salvataggio di una sestina generata direttamente dalla scheda **Sestina singola**.
- Registrazione manuale di una schedina già giocata.
- Indicazione del concorso iniziale e del numero di concorsi consecutivi da monitorare.
- Confronto automatico con ogni nuova estrazione inserita in Supabase.
- Segnalazione per ogni concorso di numeri centrati, ambo, terno, 4, 5, 5+1 o 6.
- Controllo separato di Jolly e SuperStar.
- Riepilogo dei risultati e download CSV dello storico.

La tabella `public.schedine_monitorate` viene creata automaticamente al primo utilizzo. Non serve eseguire manualmente codice SQL su Supabase.

Una schedina registrata per cinque concorsi resta in stato **In corso** finché non sono presenti tutte e cinque le estrazioni. Per esempio, dopo due ambi consecutivi mostrerà due risultati da 2+ e tre concorsi ancora in attesa.
