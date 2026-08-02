# ORION v2.7.4 — rapporto di consolidamento

## Correzioni concluse

1. **Pipeline unica:** live e walk-forward chiamano `core.orion.generate_orion_proposal`.
2. **Shadow mode reale:** il modello retrospettivamente migliore non modifica ORION.
3. **Champion protetto:** `ORION-BALANCED` resta attivo fino a prova prospettica.
4. **Holdout:** il challenger viene scelto sullo sviluppo e misurato su un blocco successivo.
5. **Benchmark:** confronto principale appaiato contro il champion; baseline casuale simulata su più seed e riferimento ipergeometrico teorico.
6. **Persistenza:** esperimenti, champion/challenger e previsioni future sono salvati in Supabase.
7. **Reboot:** la perdita del file locale non azzera più lo stato quando Supabase è disponibile.
8. **Diagnostica:** gli errori di persistenza non sono più assorbiti in silenzio.
9. **Firma corretta:** la modifica di un Jolly non fa ripetere i backtest dei sei numeri.
10. **Pulizia:** rimossi i pannelli manuali morti dall'interfaccia e allineata la versione.

## Risultato sul CSV incluso

- 1.168 estrazioni.
- 5 challenger realmente distinti.
- Challenger selezionato retrospettivamente: `ORION-118955` — Frequenza e recenza.
- Sviluppo: delta medio vs champion `+0,025`.
- Holdout: delta medio vs champion `0,000`; intervallo bootstrap circa `[-0,075; +0,075]`.
- Decisione corretta: **shadow**, nessuna promozione.
- Champion live: `ORION-BALANCED`.

## Prestazioni di esecuzione

- Primo ciclo completo sul CSV incluso: circa 20 secondi nell'ambiente di verifica.
- Secondo ciclo sullo stesso archivio: pochi millisecondi grazie al registro.
- Un nuovo ciclo completo avviene quando cambia la firma dei sei numeri, normalmente dopo una nuova estrazione.

## Test

- Compilazione completa: superata.
- Test automatici: **32/32 superati**.
- Inclusi test che verificano:
  - identità tra pipeline live e pipeline di backtest;
  - impossibilità di promozione da solo backtest;
  - holdout separato dallo sviluppo;
  - ripristino da Supabase dopo perdita della cache locale simulata.

## Limiti rimasti

- Il SuperStar resta un'euristica separata e non è ancora sottoposto a un proprio FORGE prospettico.
- I sistemi Compatto/Equilibrato sono portafogli di sestine, non sistemi ridotti con garanzia combinatoria certificata.
- La promozione richiede dati futuri; per definizione non può essere verificata subito con lo storico già noto.
