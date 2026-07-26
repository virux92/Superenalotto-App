from __future__ import annotations

from datetime import timedelta
from io import BytesIO
from pathlib import Path

import pandas as pd
import streamlit as st

from database import (
    DatabaseConfigurationError,
    database_health,
    delete_draw,
    fetch_draws,
    import_draws,
    upsert_draw,
)
from services.archive_service import (
    archive_snapshot,
    archive_to_csv_bytes,
    normalize_archive_dataframe,
    read_csv_flexible,
)
from services.draw_service import add_extraction, update_extraction

st.set_page_config(page_title="Amministrazione database", page_icon="🗄️", layout="wide")
st.title("🗄️ Amministrazione database")
st.caption(
    "Gestione permanente dell'archivio Supabase: inserimento, correzione, importazione e backup."
)

repository_csv = Path(__file__).resolve().parents[1] / "estrazioni.csv"

flash_message = st.session_state.pop("admin_flash", None)
if flash_message:
    st.success(flash_message)

try:
    database_frame = normalize_archive_dataframe(fetch_draws())
    database_snapshot = archive_snapshot(database_frame)
    database_error: Exception | None = None
except Exception as exc:
    database_frame = None
    database_snapshot = None
    database_error = exc


def refresh_after_write(message: str) -> None:
    st.cache_data.clear()
    st.session_state["admin_flash"] = message
    st.rerun()


status_tab, add_tab, edit_tab, import_tab, backup_tab = st.tabs(
    ["Stato", "Nuova estrazione", "Correggi estrazione", "Importa", "Backup"]
)

with status_tab:
    st.subheader("Stato del database")
    if st.button("Verifica connessione e archivio", type="primary", use_container_width=True):
        try:
            status = database_health()
            current_frame = normalize_archive_dataframe(fetch_draws())
            current_snapshot = archive_snapshot(current_frame)
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
            col3.metric("Estrazioni presenti", current_snapshot["rows"])
            col4.metric("Jolly mancanti", current_snapshot["missing_jolly"])
            st.caption(f"SHA256 Supabase: `{current_snapshot['sha256']}`")

            if current_snapshot["sha256"] == repository_snapshot["sha256"]:
                st.success("Supabase e CSV di emergenza coincidono.")
            else:
                st.info(
                    "Supabase e CSV di emergenza non coincidono. È normale quando sono state "
                    "aggiunte nuove estrazioni al database: GitHub contiene il codice, mentre "
                    "Supabase contiene l'archivio aggiornato."
                )
                comparison = pd.DataFrame(
                    [
                        {
                            "Fonte": "Supabase (principale)",
                            "Righe": current_snapshot["rows"],
                            "Dal": current_snapshot["date_min"].strftime("%d/%m/%Y"),
                            "Al": current_snapshot["date_max"].strftime("%d/%m/%Y"),
                            "SHA256": current_snapshot["sha256"],
                        },
                        {
                            "Fonte": "CSV GitHub (emergenza)",
                            "Righe": repository_snapshot["rows"],
                            "Dal": repository_snapshot["date_min"].strftime("%d/%m/%Y"),
                            "Al": repository_snapshot["date_max"].strftime("%d/%m/%Y"),
                            "SHA256": repository_snapshot["sha256"],
                        },
                    ]
                )
                st.dataframe(comparison, use_container_width=True, hide_index=True)

    if database_frame is not None and database_snapshot is not None:
        cols = st.columns(4)
        cols[0].metric("Estrazioni", database_snapshot["rows"])
        cols[1].metric("Ultima data", database_snapshot["date_max"].strftime("%d/%m/%Y"))
        cols[2].metric("Ultimo concorso", int(database_frame.iloc[-1]["concorso"]))
        cols[3].metric("Jolly mancanti", database_snapshot["missing_jolly"])
    elif database_error is not None:
        st.error(f"Database non disponibile: {database_error}")

with add_tab:
    st.subheader("Inserisci una nuova estrazione")
    st.caption("Il salvataggio è permanente e modifica direttamente Supabase.")

    if database_frame is None:
        st.error("La funzione richiede una connessione attiva a Supabase.")
    else:
        latest = database_frame.sort_values(["data", "concorso"]).iloc[-1]
        suggested_date = pd.Timestamp(latest["data"]).date() + timedelta(days=1)
        suggested_contest = (
            int(latest["concorso"]) + 1
            if suggested_date.year == int(latest["anno"])
            else 1
        )

        with st.form("permanent_add_draw", clear_on_submit=False):
            first_row = st.columns(2)
            draw_date = first_row[0].date_input("Data", value=suggested_date)
            contest = first_row[1].number_input(
                "Numero concorso", min_value=1, value=suggested_contest, step=1
            )

            number_columns = st.columns(6)
            numbers = [
                number_columns[index - 1].number_input(
                    f"N{index}",
                    min_value=1,
                    max_value=90,
                    value=index,
                    step=1,
                    key=f"admin_add_n{index}",
                )
                for index in range(1, 7)
            ]

            extra_columns = st.columns(3)
            jolly_available = extra_columns[0].checkbox("Jolly disponibile", value=True)
            jolly = extra_columns[1].number_input(
                "Jolly",
                min_value=1,
                max_value=90,
                value=7,
                step=1,
                disabled=not jolly_available,
                key="admin_add_jolly",
            )
            superstar = extra_columns[2].number_input(
                "SuperStar",
                min_value=1,
                max_value=90,
                value=8,
                step=1,
                key="admin_add_superstar",
            )

            submitted = st.form_submit_button(
                "Salva estrazione in Supabase", type="primary", use_container_width=True
            )

        if submitted:
            try:
                validated_archive = add_extraction(
                    database_frame,
                    draw_date,
                    int(contest),
                    [int(number) for number in numbers],
                    int(jolly) if jolly_available else None,
                    int(superstar),
                )
                new_row = validated_archive.loc[
                    (validated_archive["anno"] == draw_date.year)
                    & (validated_archive["concorso"] == int(contest))
                ].iloc[0]
                upsert_draw(new_row.to_dict(), source="inserimento_manuale")
            except Exception as exc:
                st.error(str(exc))
            else:
                refresh_after_write(
                    f"Concorso {int(contest)} del {draw_date.year} salvato correttamente."
                )

with edit_tab:
    st.subheader("Correggi un'estrazione esistente")
    st.caption("Anno e numero del concorso restano invariati; puoi correggere data e valori estratti.")

    if database_frame is None:
        st.error("La funzione richiede una connessione attiva a Supabase.")
    else:
        year_options = sorted(database_frame["anno"].unique().tolist(), reverse=True)
        selected_year = st.selectbox("Anno", year_options, key="edit_year")
        year_frame = database_frame[database_frame["anno"] == int(selected_year)]
        contest_options = sorted(year_frame["concorso"].unique().tolist(), reverse=True)
        selected_contest = st.selectbox("Concorso", contest_options, key="edit_contest")
        selected = year_frame[year_frame["concorso"] == int(selected_contest)].iloc[0]

        with st.form(f"edit_draw_{selected_year}_{selected_contest}"):
            draw_date = st.date_input(
                "Data",
                value=pd.Timestamp(selected["data"]).date(),
                key=f"edit_date_{selected_year}_{selected_contest}",
            )
            number_columns = st.columns(6)
            numbers = [
                number_columns[index - 1].number_input(
                    f"N{index}",
                    min_value=1,
                    max_value=90,
                    value=int(selected[f"n{index}"]),
                    step=1,
                    key=f"edit_n{index}_{selected_year}_{selected_contest}",
                )
                for index in range(1, 7)
            ]

            selected_jolly_available = not pd.isna(selected["jolly"])
            extra_columns = st.columns(3)
            jolly_available = extra_columns[0].checkbox(
                "Jolly disponibile",
                value=selected_jolly_available,
                key=f"edit_jolly_available_{selected_year}_{selected_contest}",
            )
            jolly = extra_columns[1].number_input(
                "Jolly",
                min_value=1,
                max_value=90,
                value=int(selected["jolly"]) if selected_jolly_available else 1,
                step=1,
                disabled=not jolly_available,
                key=f"edit_jolly_{selected_year}_{selected_contest}",
            )
            superstar = extra_columns[2].number_input(
                "SuperStar",
                min_value=1,
                max_value=90,
                value=int(selected["superstar"]),
                step=1,
                key=f"edit_superstar_{selected_year}_{selected_contest}",
            )

            submitted_edit = st.form_submit_button(
                "Salva correzione", type="primary", use_container_width=True
            )

        if submitted_edit:
            try:
                corrected_archive = update_extraction(
                    database_frame,
                    int(selected_year),
                    int(selected_contest),
                    draw_date,
                    [int(number) for number in numbers],
                    int(jolly) if jolly_available else None,
                    int(superstar),
                )
                corrected_row = corrected_archive.loc[
                    (corrected_archive["anno"] == int(selected_year))
                    & (corrected_archive["concorso"] == int(selected_contest))
                ].iloc[0]
                upsert_draw(corrected_row.to_dict(), source="correzione_manuale")
            except Exception as exc:
                st.error(str(exc))
            else:
                refresh_after_write(
                    f"Concorso {int(selected_contest)} del {int(selected_year)} corretto."
                )

        st.divider()
        with st.expander("Zona pericolosa — elimina l'ultima estrazione"):
            latest = database_frame.sort_values(["data", "concorso"]).iloc[-1]
            latest_year = int(latest["anno"])
            latest_contest = int(latest["concorso"])
            st.warning(
                f"È eliminabile soltanto l'ultima estrazione: concorso {latest_contest} "
                f"del {latest_year}, data {pd.Timestamp(latest['data']):%d/%m/%Y}."
            )
            confirmation_text = f"ELIMINA {latest_contest}"
            typed_confirmation = st.text_input(
                f"Per confermare scrivi: {confirmation_text}", key="delete_confirmation"
            )
            if st.button(
                "Elimina definitivamente l'ultima estrazione",
                disabled=typed_confirmation.strip() != confirmation_text,
                use_container_width=True,
            ):
                try:
                    delete_draw(latest_year, latest_contest)
                except Exception as exc:
                    st.error(str(exc))
                else:
                    refresh_after_write(
                        f"Concorso {latest_contest} del {latest_year} eliminato dal database."
                    )

with import_tab:
    st.subheader("Importazione massiva")
    st.caption("Usa l'upsert: i concorsi esistenti vengono aggiornati e non duplicati.")

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
        st.dataframe(preview_frame.tail(5), use_container_width=True, hide_index=True)

    confirm_import = st.checkbox("Confermo l'importazione o l'aggiornamento massivo")
    if st.button(
        "Importa in Supabase",
        disabled=not confirm_import or preview_frame is None,
        use_container_width=True,
    ):
        try:
            validated_frame = normalize_archive_dataframe(preview_frame)
            result = import_draws(validated_frame, source="importazione_csv")
        except Exception as exc:
            st.exception(exc)
        else:
            refresh_after_write(
                f"Importazione completata: {result['processed']} righe elaborate."
            )

with backup_tab:
    st.subheader("Backup dell'archivio vivo")
    if database_frame is None or database_snapshot is None:
        st.info("Il backup sarà disponibile quando Supabase sarà raggiungibile.")
    else:
        backup_columns = st.columns(3)
        backup_columns[0].metric("Righe", database_snapshot["rows"])
        backup_columns[1].metric("Ultima data", database_snapshot["date_max"].strftime("%d/%m/%Y"))
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
