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
from services.archive_service import (
    archive_snapshot,
    archive_to_csv_bytes,
    normalize_archive_dataframe,
    read_csv_flexible,
)

st.set_page_config(page_title="Amministrazione database", page_icon="🗄️", layout="wide")
st.title("🗄️ Amministrazione database")
st.caption("Connessione, importazione controllata, integrità e backup dell'archivio Supabase.")

repository_csv = Path(__file__).resolve().parents[1] / "estrazioni.csv"

with st.expander("Istruzioni", expanded=True):
    st.markdown(
        """
        1. La URI PostgreSQL deve restare nei **Secrets** di Streamlit sotto `[database].url`.
        2. Verifica connessione e integrità dell'archivio.
        3. L'importazione usa un upsert: una seconda esecuzione non crea duplicati.
        4. Scarica periodicamente un backup esterno.
        """
    )

if st.button("Verifica connessione e archivio", type="primary", use_container_width=True):
    try:
        status = database_health()
        database_frame = normalize_archive_dataframe(fetch_draws())
        database_snapshot = archive_snapshot(database_frame)
        repository_frame = read_csv_flexible(repository_csv)
        repository_snapshot = archive_snapshot(repository_frame)
    except DatabaseConfigurationError as exc:
        st.error(str(exc))
    except Exception as exc:
        st.exception(exc)
    else:
        st.success("Connessione Supabase riuscita e archivio valido.")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Database", str(status["database"]))
        col2.metric("Tabelle pubbliche", int(status["table_count"]))
        col3.metric("Estrazioni presenti", database_snapshot["rows"])
        col4.metric("Jolly mancanti", database_snapshot["missing_jolly"])
        st.code(database_snapshot["sha256"], language=None)
        if database_snapshot["sha256"] == repository_snapshot["sha256"]:
            st.success("Supabase e CSV del repository hanno lo stesso hash.")
        else:
            st.warning(
                "Supabase e CSV del repository non sono identici. "
                "Può essere normale dopo un aggiornamento non ancora riportato nel repository."
            )
            comparison = pd.DataFrame(
                [
                    {
                        "Fonte": "Supabase",
                        "Righe": database_snapshot["rows"],
                        "Dal": database_snapshot["date_min"].strftime("%d/%m/%Y"),
                        "Al": database_snapshot["date_max"].strftime("%d/%m/%Y"),
                        "Jolly mancanti": database_snapshot["missing_jolly"],
                        "SHA256": database_snapshot["sha256"],
                    },
                    {
                        "Fonte": "CSV repository",
                        "Righe": repository_snapshot["rows"],
                        "Dal": repository_snapshot["date_min"].strftime("%d/%m/%Y"),
                        "Al": repository_snapshot["date_max"].strftime("%d/%m/%Y"),
                        "Jolly mancanti": repository_snapshot["missing_jolly"],
                        "SHA256": repository_snapshot["sha256"],
                    },
                ]
            )
            st.dataframe(comparison, use_container_width=True, hide_index=True)

st.divider()
st.subheader("Importazione archivio")

source_mode = st.radio(
    "Origine",
    ["CSV incluso nel repository", "Carica un CSV dal computer"],
    horizontal=True,
)
uploaded_file = None
if source_mode == "Carica un CSV dal computer":
    uploaded_file = st.file_uploader("Seleziona estrazioni.csv", type=["csv"])

try:
    if source_mode == "CSV incluso nel repository":
        preview_frame = read_csv_flexible(repository_csv)
    elif uploaded_file is not None:
        preview_frame = read_csv_flexible(uploaded_file)
        uploaded_file.seek(0)
    else:
        preview_frame = None
except Exception as exc:
    st.error(f"CSV non valido: {exc}")
    preview_frame = None

if preview_frame is not None:
    preview_snapshot = archive_snapshot(preview_frame)
    preview_columns = st.columns(4)
    preview_columns[0].metric("Righe da elaborare", preview_snapshot["rows"])
    preview_columns[1].metric("Dal", preview_snapshot["date_min"].strftime("%d/%m/%Y"))
    preview_columns[2].metric("Al", preview_snapshot["date_max"].strftime("%d/%m/%Y"))
    preview_columns[3].metric("Jolly mancanti", preview_snapshot["missing_jolly"])
    st.caption(f"SHA256: `{preview_snapshot['sha256']}`")
    st.dataframe(preview_frame.tail(5), use_container_width=True, hide_index=True)

confirm = st.checkbox("Confermo di voler importare o aggiornare l'archivio Supabase")
if st.button(
    "Importa in Supabase",
    disabled=not confirm or preview_frame is None,
    use_container_width=True,
):
    try:
        validated_frame = normalize_archive_dataframe(preview_frame)
        result = import_draws(validated_frame)
        database_frame = normalize_archive_dataframe(fetch_draws())
        database_snapshot = archive_snapshot(database_frame)
    except Exception as exc:
        st.exception(exc)
    else:
        st.success(
            f"Operazione completata: {result['processed']} righe elaborate; "
            f"{database_snapshot['rows']} estrazioni ora presenti nel database."
        )
        st.caption(f"Nuovo SHA256 Supabase: `{database_snapshot['sha256']}`")

st.divider()
st.subheader("Backup")

try:
    database_frame = normalize_archive_dataframe(fetch_draws())
    database_snapshot = archive_snapshot(database_frame)
except Exception as exc:
    st.info("Il backup sarà disponibile dopo aver configurato e collegato il database.")
    st.caption(str(exc))
else:
    backup_columns = st.columns(3)
    backup_columns[0].metric("Righe", database_snapshot["rows"])
    backup_columns[1].metric("Jolly mancanti", database_snapshot["missing_jolly"])
    backup_columns[2].metric("Hash", database_snapshot["sha256"][:12])

    st.download_button(
        "Scarica archivio CSV da Supabase",
        data=archive_to_csv_bytes(database_frame),
        file_name="backup_estrazioni_supabase.csv",
        mime="text/csv",
        use_container_width=True,
    )

    output = BytesIO()
    export_frame = database_frame.copy()
    export_frame["data"] = export_frame["data"].dt.strftime("%Y-%m-%d")
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        export_frame.to_excel(writer, sheet_name="Estrazioni", index=False)
    st.download_button(
        "Scarica archivio Excel da Supabase",
        data=output.getvalue(),
        file_name="backup_estrazioni_supabase.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )
