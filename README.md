# ORION — SuperEnalotto Quant Engine

Versione **2.7.5**.

ORION è un motore statistico multi-memoria con interfaccia Streamlit. FORGE 2 lavora dietro le quinte in modalità **champion/challenger**: il profilo bilanciato resta attivo, mentre un challenger viene osservato senza influenzare le schedine live finché non supera una verifica prospettica su estrazioni future.

## Cosa cambia nella 2.7.5

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

Il file `.forge_registry_v2.json` è soltanto una cache locale. Su Streamlit Cloud può sparire al reboot e non viene usato come memoria autorevole.

## Stati

- `shadow`: challenger osservato, champion invariato;
- `promoted`: un challenger ha superato i criteri prospettici ed è diventato champion;
- `fallback`: Supabase non è disponibile o non salva; resta attivo il profilo bilanciato protetto;
- `non_validated`, `rejected`, `failed`: stati degli esperimenti, non modelli live.

## Limite fondamentale

Il SuperEnalotto è un processo casuale. ORION organizza euristiche e controlla in modo onesto se producono risultati diversi dal champion; non crea probabilità aggiuntiva e non promette capacità predittive.
