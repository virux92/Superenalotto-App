# ORION v2.7.2 — FORGE automatico

## Modifica funzionale

Il Laboratorio è stato eliminato dall’interfaccia. La grafica della v2.7.1 non è stata ridisegnata: il lavoro riguarda navigazione e motore interno.

## Menu

- Home
- Genera
- Schedine
- Archivio
- Impostazioni

## FORGE

FORGE opera automaticamente e senza parametri utente:

1. crea 18 modelli candidati su finestre e profili prefissati;
2. esegue backtest walk-forward senza look-ahead;
3. confronta ogni candidato con un benchmark casuale deterministico;
4. applica controlli di campione, non-dominanza e stabilità;
5. registra candidati validi, respinti e falliti;
6. non ripete esperimenti già conclusi sullo stesso snapshot dell’archivio;
7. promuove a ORION soltanto il migliore tra i candidati validi.

Quando nessun candidato supera i controlli, ORION non promuove un modello respinto: resta sul profilo bilanciato protetto.

## Persistenza

La tabella `forge_experiments` viene creata automaticamente su Supabase. Se il database non è disponibile, viene usato un registro locale di emergenza. Nessuna migrazione manuale è richiesta.

## Verifica

- compilazione Python completata;
- 25 test automatici superati;
- pipeline FORGE verificata sull’archivio reale;
- seconda esecuzione sullo stesso archivio: zero backtest ripetuti.
