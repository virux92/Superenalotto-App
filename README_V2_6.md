# Versione 2.6 — ORION Core

Questa versione introduce il primo nucleo automatico di ORION.

## Novità principali

- calcolo simultaneo su cinque memorie statistiche: 25, 50, 100, 200 estrazioni e archivio completo;
- fusione automatica dei punteggi delle diverse memorie;
- penalizzazione dei numeri con segnali instabili tra le finestre;
- determinazione automatica dei vincoli strutturali delle sestine dall'archivio;
- generazione principale deterministica e alternative tra i migliori candidati;
- firma del modello per identificare lo stato corrente del motore;
- eliminazione della finestra statistica manuale e dei filtri manuali dalla generazione singola;
- nessuna API esterna e nessun costo aggiuntivo.

## Filosofia

L'utente inserisce le estrazioni e richiede una sestina o un sistema. ORION gestisce internamente finestre, pesi e filtri. I moduli tecnici esistenti restano disponibili per controllo e sviluppo, ma non sono necessari per l'uso ordinario.

## Verifica

20 test automatici superati.
