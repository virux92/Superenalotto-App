# ORION — SuperEnalotto Quant Engine

Versione **2.7.6**.

ORION è un motore statistico multi-memoria con interfaccia Streamlit. FORGE 3 lavora dietro le quinte in modalità **champion/challenger**: ORION 2.7.4 resta il champion protetto, mentre famiglie algoritmiche differenti vengono osservate senza influenzare le schedine live finché non superano una verifica prospettica su estrazioni future.

## Cosa cambia nella 2.7.6

- FORGE confronta cinque famiglie per la sestina: Bayes-Dirichlet, multi-EMA, coppie con shrinkage, frequenza mobile e un controllo uniforme deterministico.
- Il backtest resta walk-forward con sviluppo e holdout; nessun risultato storico può promuovere un modello.
- ORION, pesi e scoring restano byte-per-byte invariati finché un challenger non supera almeno 100 confronti prospettici appaiati.
- Il SuperStar ha un ciclo champion/challenger e tabelle separate. Tutte le 1.168 estrazioni del CSV sono usate nel backtest storico; le osservazioni prospettiche richiedono comunque una previsione realmente congelata prima del target.
- Il portafoglio compatto usa CP-SAT, con fallback greedy deterministico, e mostra copertura e sovrapposizione.
- Nei sistemi ogni riga riceve un SuperStar distinto finché il ranking contiene valori disponibili; la proposta singola continua a mostrare il champion.
- La migrazione `FORGE_V3_SUPABASE.sql` è additiva, idempotente, protetta da RLS e recupera soltanto vecchie osservazioni SuperStar temporalmente valide.
- Sul live completo di 1.189 estrazioni, Multi-EMA sestina chiude l'holdout a +0,025 punti medi ma con IC95 −0,125/+0,175; Bayes SuperStar fa 2/100 come il champion. I dati non autorizzano alcuna promozione.
- Suite: 68 test superati.

## Correzioni precedenti (2.7.5.2)

- Le date future sono rifiutate sia dall'interfaccia sia da un trigger PostgreSQL, anche per scritture che non passano dall'app.
- Una previsione entra nel campione prospettico soltanto se `created_at` precede le ore 20:00 italiane del giorno target.
- Le previsioni tardive vengono messe a `void` al momento della valutazione; le righe storiche tardive sono escluse anche in lettura.
- La riattivazione di una previsione `void` azzera il vecchio timestamp e registra il nuovo istante reale.
- Le correzioni della sola data riallineano `source_date` e `target_date` senza invalidare previsioni che non dipendono numericamente dall'errore.
- Algoritmo ORION, pesi, scoring, champion/challenger, promozione e soglia prospettica minima di 100 restano invariati.

## Correzioni precedenti (2.7.5.1)

- Il SuperStar previsto viene congelato con ogni previsione FORGE e valutato separatamente, senza influire sul confronto champion/challenger.
- Le correzioni di sestina rivalutano i target gia' osservati e invalidano soltanto le previsioni future dipendenti dal dato errato.
- Le correzioni del solo Jolly non modificano FORGE; le correzioni del SuperStar aggiornano la metrica dedicata.
- Lo schema FORGE e' aggiornabile in modo idempotente anche se le colonne SuperStar esistono gia'.

## Correzioni precedenti (2.7.5)

- Rimosso il caching Streamlit dal ciclo FORGE che legge e scrive Supabase: valutazioni, invalidazioni e salvataggi vengono eseguiti a ogni ciclo reale dell'app.
- Le previsioni pendenti vengono filtrate per versione FORGE.
- È ammessa una sola previsione pendente per versione, concorso sorgente e ruolo.
- Snapshot alternativi dello stesso concorso vengono messi automaticamente a `void`; una firma già esistente può essere riattivata in sicurezza dopo il ripristino dell'archivio.
- Modifiche, cancellazioni o inserimenti retroattivi nell'archivio invalidano automaticamente le previsioni FORGE influenzate, anche se eseguiti direttamente nel database.
- La valutazione si blocca in presenza di ruoli duplicati o firme incoerenti, invece di gonfiare il campione prospettico.
- Il contatore `previsioni_valutate_ora` aumenta soltanto quando PostgreSQL aggiorna realmente una riga pendente.
- La soglia minima prospettica passa da 30 a **100 confronti appaiati**; il valore persistito viene rialzato automaticamente.
- Nessuna modifica allo scoring ORION, che resta versione algoritmica `2.7.4`.

## Correzioni precedenti

La serie 2.7.4.1–2.7.4.4 ha corretto il contatore delle previsioni, separato la versione applicativa da quella algoritmica, ripristinato la gestione delle estrazioni e rafforzato i controlli su Jolly, numeri e ordine cronologico.

## Menu utente

- **Home**
- **Genera**
- **Schedine**
- **Archivio**
- **Impostazioni**

La grafica della stable 2.7.3 è stata conservata. Non sono stati reintrodotti pesi, slider o comandi da Laboratorio.

## Persistenza FORGE

FORGE crea automaticamente, se mancanti:

- `forge_experiments_v2`: risultati retrospettivi versionati;
- `forge_state`: champion, challenger e modalità operativa;
- `forge_predictions`: proposte immutabili salvate prima delle estrazioni e successivamente valutate.
- `forge_superstar_experiments`: backtest versionati dei modelli SuperStar;
- `forge_superstar_state`: champion e challenger SuperStar indipendenti;
- `forge_superstar_predictions`: previsioni SuperStar prospettiche, congelate e valutate separatamente.

Il file `.forge_registry_v2.json` è soltanto una cache locale. Su Streamlit Cloud può sparire al reboot e non viene usato come memoria autorevole.

## Stati

- `shadow`: challenger osservato, champion invariato;
- `promoted`: un challenger ha superato i criteri prospettici ed è diventato champion;
- `fallback`: Supabase non è disponibile o non salva; resta attivo il profilo bilanciato protetto;
- `non_validated`, `rejected`, `failed`: stati degli esperimenti, non modelli live.

## Limite fondamentale

Il SuperEnalotto è un processo casuale. ORION organizza euristiche e controlla in modo onesto se producono risultati diversi dal champion; non crea probabilità aggiuntiva e non promette capacità predittive.
