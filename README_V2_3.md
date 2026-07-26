# Versione 2.3 — Laboratorio sperimentale

Questa versione introduce una pagina separata per confrontare profili di scoring
mediante backtest walk-forward.

## Funzioni

- sei profili di pesi prefissati;
- confronto appaiato con una sestina casuale deterministica;
- intervalli di confidenza descrittivi;
- risultati annuali e dettaglio estrazione per estrazione;
- esportazione CSV;
- password opzionale tramite Streamlit Secrets.

## Password opzionale

Nei Secrets di Streamlit:

```toml
[admin]
lab_password = "scegli-una-password"
```

Il laboratorio è uno strumento di ricerca storica. Non dimostra capacità
predittiva e non altera le probabilità matematiche del SuperEnalotto.
