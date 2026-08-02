# Changelog

## 2.7.4.2 — Versionamento algoritmico e contatori correnti

- Separata la versione dell'app (`2.7.4.2`) dalla versione algoritmica ORION (`2.7.4`).
- Gli ID dei cinque modelli e le chiavi degli esperimenti non cambiano più per una patch puramente applicativa.
- I riepiloghi `shadow`, `non_validati`, `respinti` e `falliti` contano soltanto le cinque chiavi attese dal ciclo corrente.
- I record storici ridondanti restano disponibili in Supabase ma non influenzano più selezione e contatori.
- Champion e challenger persistiti vengono riallineati ai modelli correnti; riferimenti obsoleti sono ignorati in sicurezza.
- Nessuna modifica a scoring, backtest, soglia prospettica o grafica.

## 2.7.4.1 — Contatore previsioni persistenti

- `save_forge_prediction` comunica ora se `ON CONFLICT DO NOTHING` ha inserito realmente una riga.
- `previsioni_salvate_ora` aumenta soltanto per nuovi record e resta a `0` dopo un reboot sullo stesso archivio.
- Aggiunto un test di regressione sulla perdita della cache locale e sul riavvio con Supabase persistente.
- Nessuna variazione agli algoritmi ORION/FORGE o alle soglie di promozione.

## 2.7.4 — Pipeline unica e FORGE shadow persistente

- Unificata la generazione live e di backtest in `generate_orion_proposal`.
- FORGE 2 valuta 5 challenger realmente distinti con sviluppo + holdout.
- Disattivata la promozione retrospettiva automatica: il backtest autorizza solo lo shadow.
- Aggiunto confronto prospettico champion/challenger con minimo 30 osservazioni appaiate.
- Aggiunte le tabelle automatiche `forge_experiments_v2`, `forge_state` e `forge_predictions`.
- Supabase è la memoria autorevole; il registro locale è solo cache esplicitamente non persistente.
- Aggiunta diagnostica visibile degli errori di persistenza.
- Separata la firma dei sei numeri da Jolly e SuperStar.
- Aggiunta invalidazione delle proposte di sessione al cambio di archivio/modello.
- Rimossi i pannelli manuali morti di statistiche e backtest dall'app.
- Allineate tutte le versioni a 2.7.4 e rimossa la dipendenza inutilizzata `openpyxl`.
- Suite: 32 test, inclusi pipeline live/backtest e persistenza simulata attraverso reboot.

## 2.7.3 — Ripristino sistemi utente

- Ripristinata la creazione dei sistemi nella pagina Genera.
- Aggiunte le sezioni Proposta singola e Sistema.
- Mantenuti soltanto tre profili semplici, senza parametri da analista.
- Ripristinata la visualizzazione del costo prima e dopo la generazione.
- Il Laboratorio resta escluso dall'interfaccia e FORGE continua a operare dietro le quinte.

# Changelog

## 2.7.2 — FORGE automatico e menu essenziale

- Mantenuta invariata l’identità grafica della v2.7.1.
- Eliminato il Laboratorio dall’interfaccia Streamlit.
- Ridotto il menu a Home, Genera, Schedine, Archivio e Impostazioni.
- Aggiunto FORGE per generazione automatica, backtest e confronto dei modelli candidati.
- Aggiunto un gate operativo che impedisce la promozione di candidati respinti o falliti.
- Aggiunto il registro `forge_experiments`, creato automaticamente su Supabase.
- Aggiunto fallback locale e riuso degli esperimenti già conclusi sullo stesso archivio.
- Collegato ORION ai pesi del modello validato e promosso da FORGE.
- Suite totale: 25 test.

## 2.7.1 — Correzione leggibilità sidebar

- Aumentato il contrasto dei tre riquadri riepilogativi nella barra laterale.
- Sostituito il fondo quasi bianco con pannelli scuri semitrasparenti.
- Ingranditi valori, etichette, didascalie e testo informativo della sidebar.
- Rafforzati bordi e separatori per mantenere la leggibilità su monitor ad alta risoluzione.

## 2.7.0 — ORION User Experience

- Ridisegnata la home con interfaccia moderna e orientata all’utente finale.
- Mostrata automaticamente la proposta principale ORION.
- Aggiunte sfere numeriche, pannello di coerenza e spiegazione della selezione.
- Rese deterministiche e sequenziali le alternative tra i migliori candidati.
- Introdotti profili di sistema semplici: Compatto, Equilibrato e Integrale 7 numeri.
- Spostati archivio, statistiche e backtest nella sezione “Dati e verifica”.
- Aggiunti `services/presentation_service.py` e `ui/orion_ui.py`.
- Aggiornata la versione del motore a ORION 2.7.0.
- Suite totale: 22 test.

## 2.5.1

- Corretto il campo SuperStar nel modulo di registrazione manuale delle schedine.
- Il checkbox ora abilita immediatamente il numero SuperStar, senza attendere l'invio del form.

## v2.0.0 — Database First stabile

- Supabase resta la fonte primaria dell'archivio.
- Corretto il caricamento PostgreSQL eliminando `pandas.read_sql_query` su connessione psycopg diretta.
- Creato `services/archive_service.py` come unico punto di caricamento, normalizzazione e validazione.
- Aggiunto fallback automatico e diagnostico al CSV del repository.
- Aggiunta protezione contro eventuali righe d'intestazione lette come dati.
- Conservate le funzioni esistenti: statistiche, sestine, sistemi, backtest, archivio e amministrazione database.

## v2.1 — Motore modulare
- Estratte metriche e ranking SuperStar in `core/metrics.py`.
- Estratti filtri, scoring e sistemi in `core/combinations.py`.
- Estratto il backtest walk-forward in `core/backtest.py`.
- `app.py` conserva la UI e usa il motore tramite import stabili.
- Nessuna modifica alle formule o al comportamento della v2.0.

## v2.2 — Statistiche avanzate e validazione
- Creato `core/analytics.py` con strutture, decine, entropia, coppie, terzine, ripetizioni e stabilità annuale.
- Estratte le operazioni sulle estrazioni in `services/draw_service.py`.
- Aggiunto hash SHA-256 canonico dell'archivio e confronto Supabase/CSV.
- Aggiunto benchmark casuale deterministico e riproducibile al backtest.
- Aggiunte deviazione standard, intervallo di confidenza e stabilità annuale.
- Aggiunta suite di test automatici per archivio, metriche, analytics e assenza di future leakage.

## 2.3.0
- Aggiunto il Laboratorio sperimentale in una pagina dedicata.
- Introdotti sei profili di scoring confrontabili con backtest walk-forward.
- Aggiunto confronto appaiato con baseline casuale deterministica.
- Aggiunti intervalli descrittivi, stabilità annuale ed esportazione CSV.
- Aggiunta protezione opzionale del laboratorio tramite Streamlit Secrets.
- Aggiunti test automatici per il motore degli esperimenti.

## 2.4.0
- Ripulita la barra laterale della home: rimossi inserimento temporaneo, import e download CSV.
- Rimossa la copia modificabile dell'archivio da `st.session_state`.
- Centralizzate tutte le scritture nella pagina Amministrazione Database.
- Aggiunti inserimento permanente, correzione e cancellazione protetta dell'ultima estrazione.
- Aggiunto svuotamento automatico della cache dopo ogni modifica a Supabase.
- Chiarita la distinzione tra archivio vivo Supabase e CSV di emergenza GitHub.
- Aggiunti test per inserimento e correzione delle estrazioni.

## v2.5.0 — Schedine monitorate

- Aggiunta tabella Supabase `schedine_monitorate`, creata automaticamente.
- Salvataggio persistente delle sestine generate.
- Registrazione manuale delle schedine già giocate.
- Monitoraggio della stessa schedina per più concorsi consecutivi.
- Calcolo automatico dell'esito per ciascuna estrazione.
- Segnalazione di ambo, terno, 4, 5, 5+1, 6, Jolly e SuperStar.
- Esportazione CSV dello storico risultati.
- Aggiunti test per due ambi consecutivi con la stessa schedina.

## 2.6.0 — ORION Core

- Introdotto il motore multi-memoria ORION 1.0.0.
- Aggiunte memorie Breve, Operativa, Intermedia, Lunga e Storica.
- Introdotti consenso multi-finestra e penalizzazione dell'instabilità.
- Resa automatica la selezione dei vincoli strutturali.
- Rimossi dalla generazione singola finestra, pesi e filtri manuali.
- Aggiunti firma modello e stato del motore nella dashboard.
- Aggiunti test dedicati; suite totale: 20 test.
