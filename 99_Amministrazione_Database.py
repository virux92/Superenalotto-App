from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pandas as pd
import streamlit as st

from database import (
    DatabaseConfigurationError,
    database_health,
    fetch_draws,
    import_draws,
)

st.set_page_config(page_title="Amministrazione database", page_icon="🗄️", layout="wide")
st.title("🗄️ Amministrazione database")
st.caption("Connessione, importazione iniziale e backup dell’archivio Supabase.")

with st.expander("Istruzioni", expanded=True):
    st.markdown(
        """
        1. Inserisci la URI PostgreSQL nei **Secrets** di Streamlit sotto `[database].url`.
        2. Verifica la connessione.
        3. Importa `estrazioni.csv` una sola volta. Le esecuzioni successive aggiornano gli stessi concorsi senza duplicarli.
        4. Scarica periodicamente un backup.
        """
    )

if st.button("Verifica connessione", type="primary", use_container_width=True):
    try:
        status = database_health()
    except DatabaseConfigurationError as exc:
        st.error(str(exc))
    except Exception as exc:
        st.exception(exc)
    else:
        st.success("Connessione Supabase riuscita.")
        col1, col2, col3 = st.columns(3)
        col1.metric("Database", str(status["database"]))
        col2.metric("Tabelle pubbliche", int(status["table_count"]))
        col3.metric("Estrazioni presenti", int(status["draw_count"]))

st.divider()
st.subheader("Importazione archivio")

repository_csv = Path(__file__).resolve().parents[1] / "estrazioni.csv"
source_mode = st.radio(
    "Origine",
    ["CSV incluso nel repository", "Carica un CSV dal computer"],
    horizontal=True,
)

uploaded_file = None
if source_mode == "Carica un CSV dal computer":
    uploaded_file = st.file_uploader("Seleziona estrazioni.csv", type=["csv"])

confirm = st.checkbox("Confermo di voler importare o aggiornare l’archivio Supabase")

if st.button("Importa in Supabase", disabled=not confirm, use_container_width=True):
    try:
        if source_mode == "CSV incluso nel repository":
            if not repository_csv.exists():
                raise FileNotFoundError("Il file estrazioni.csv non è presente nel repository.")
            dataframe = pd.read_csv(repository_csv, encoding="utf-8-sig")
        else:
            if uploaded_file is None:
                raise ValueError("Seleziona prima un file CSV.")
            dataframe = pd.read_csv(uploaded_file, encoding="utf-8-sig")

        result = import_draws(dataframe)
        status = database_health()
    except Exception as exc:
        st.exception(exc)
    else:
        st.success(
            f"Operazione completata: {result['processed']} righe elaborate; "
            f"{status['draw_count']} estrazioni ora presenti nel database."
        )

st.divider()
st.subheader("Backup")

try:
    database_frame = fetch_draws()
except Exception as exc:
    st.info("Il backup sarà disponibile dopo aver configurato e collegato il database.")
    st.caption(str(exc))
else:
    csv_bytes = database_frame.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        "Scarica archivio CSV da Supabase",
        data=csv_bytes,
        file_name="backup_estrazioni_supabase.csv",
        mime="text/csv",
        use_container_width=True,
    )

    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        database_frame.to_excel(writer, sheet_name="Estrazioni", index=False)
    st.download_button(
        "Scarica archivio Excel da Supabase",
        data=output.getvalue(),
        file_name="backup_estrazioni_supabase.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )
