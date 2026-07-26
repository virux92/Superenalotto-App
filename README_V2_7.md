# Versione 2.7 — ORION User Experience

La v2.7 trasforma ORION da motore tecnico con interfaccia tradizionale a prodotto pensato per l’utente finale.

## Obiettivo

L’utente non deve comportarsi da statistico. ORION continua a usare il motore multi-memoria introdotto nella v2.6, ma decide autonomamente finestre, pesi, filtri strutturali e candidati. L’interfaccia espone soltanto le scelte che hanno un’utilità pratica.

## Novità principali

- nuova dashboard moderna con identità visiva ORION;
- proposta principale mostrata automaticamente all’apertura;
- sestina e SuperStar visualizzati tramite sfere numeriche;
- alternative ordinate e riproducibili, senza estrazione casuale dall’elenco dei candidati;
- spiegazione leggibile dei motivi della selezione;
- indicatore di coerenza tra memorie chiaramente distinto dalla probabilità di vincita;
- numeri sotto osservazione e ultima estrazione nella stessa schermata;
- salvataggio e monitoraggio della schedina mantenuti senza modifiche allo schema dati;
- sistemi semplificati in tre profili: Compatto, Equilibrato e Integrale 7 numeri;
- impostazioni tecniche disponibili soltanto nella modalità Personalizzato;
- statistiche, backtest e archivio spostati nella sezione separata “Dati e verifica”;
- nessuna nuova dipendenza esterna.

## Architettura aggiunta

- `services/presentation_service.py`: traduce lo stato ORION in informazioni adatte alla UI;
- `ui/orion_ui.py`: tema visuale e componenti grafici riutilizzabili;
- `tests/test_presentation_service.py`: controlli sui profili delle sestine e sulle etichette di coerenza.

## Compatibilità

- archivio Supabase invariato;
- fallback CSV invariato;
- tabella delle schedine monitorate invariata;
- pagine Laboratorio e Amministrazione Database mantenute;
- nessuna migrazione SQL richiesta.

## Verifica

22 test automatici superati.
