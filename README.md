# ORION — SuperEnalotto Quant Engine

Versione **2.7.4.4**.

ORION è un motore statistico multi-memoria con interfaccia Streamlit. FORGE 2 lavora dietro le quinte in modalità **champion/challenger**: il profilo bilanciato resta attivo, mentre un challenger viene osservato senza influenzare le schedine live finché non supera una verifica prospettica su estrazioni future.

## Cosa cambia nella 2.7.4.4

- Il Jolly deve essere diverso da tutti i sei numeri principali; il SuperStar resta indipendente.
- Una nuova estrazione deve avere data strettamente successiva all'ultima presente.
- La data corretta di un concorso deve restare tra le date dei concorsi immediatamente precedente e successivo.
- Le stesse regole vengono applicate all'archivio caricato, agli import completi e agli upsert diretti verso Supabase.
- Gli archivi con date fuori sequenza o Jolly duplicato vengono rifiutati con un messaggio esplicito.
- Nessuna modifica all'algoritmo ORION (`2.7.4`), ai modelli FORGE o alle soglie prospettiche.

## Correzione precedente 2.7.4.3

- Ripristinata in **Archivio** la gestione permanente delle estrazioni.
- Aggiunti inserimento del prossimo concorso, correzione dei dati e cancellazione protetta dell'ultima estrazione.
- Ogni scrittura svuota le cache e ricalcola automaticamente ORION e FORGE sul nuovo archivio Supabase.
- La cancellazione dell'ultima estrazione è protetta sia nell'interfaccia sia nel livello database.
- Nessuna modifica all'algoritmo ORION (`2.7.4`).

## Correzione precedente 2.7.4.2

- Separata la versione visibile dell'app dalla versione dell'algoritmo ORION.
- Le patch applicative non generano più nuovi ID per gli stessi cinque modelli FORGE.
- I contatori mostrano soltanto i candidati della configurazione corrente, ignorando le righe storiche ridondanti già presenti in Supabase.
- Champion e challenger salvati vengono accettati soltanto se compatibili con i modelli correnti; eventuali riferimenti obsoleti vengono sostituiti senza cancellare lo storico.
- Nessuna migrazione SQL e nessuna cancellazione manuale delle tabelle.

## Correzione precedente 2.7.4.1

- Corretto `previsioni_salvate_ora`: conta soltanto le righe realmente inserite in Supabase e resta a zero dopo un reboot senza nuove previsioni.

- Il live e i backtest usano la stessa funzione pura `generate_orion_proposal`.
- Eliminato il proxy FORGE che testava un algoritmo diverso da quello realmente usato.
- Eliminata la moltiplicazione artificiale dei candidati per finestre ignorate: i challenger sono 5 configurazioni realmente distinte.
- Selezione retrospettiva su blocco di sviluppo e verifica su holdout successivo.
- Il backtest può autorizzare soltanto lo stato `shadow`; non può promuovere un modello.
- La promozione richiede almeno 30 confronti prospettici champion/challenger, salvati prima dell'estrazione.
- Esperimenti, stato operativo e previsioni sono persistenti su Supabase.
- Se Supabase non salva, FORGE lo dichiara e mantiene il champion bilanciato protetto.
- La firma dei backtest usa soltanto data, concorso e sei numeri principali: Jolly e SuperStar non causano ricalcoli inutili.
- Le proposte in sessione vengono invalidate quando cambia archivio o modello.
- Rimossi dall'app i vecchi pannelli manuali di statistiche e backtest non raggiungibili dal menu.

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

Il file `.forge_registry_v2.json` è soltanto una cache locale. Su Streamlit Cloud può sparire al reboot e non viene usato come memoria autorevole.

## Stati

- `shadow`: challenger osservato, champion invariato;
- `promoted`: un challenger ha superato i criteri prospettici ed è diventato champion;
- `fallback`: Supabase non è disponibile o non salva; resta attivo il profilo bilanciato protetto;
- `non_validated`, `rejected`, `failed`: stati degli esperimenti, non modelli live.

## Limite fondamentale

Il SuperEnalotto è un processo casuale. ORION organizza euristiche e controlla in modo onesto se producono risultati diversi dal champion; non crea probabilità aggiuntiva e non promette capacità predittive.
