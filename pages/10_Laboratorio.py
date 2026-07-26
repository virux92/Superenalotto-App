from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from core.backtest import records_tuple
from core.experiments import (
    DEFAULT_PROFILES,
    profiles_by_name,
    run_experiment_suite,
)
from database import fetch_draws
from services.archive_service import load_primary_archive

APP_ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = APP_ROOT / "estrazioni.csv"

st.set_page_config(
    page_title="Laboratorio — SuperEnalotto",
    page_icon="🧪",
    layout="wide",
)


def configured_password() -> str | None:
    try:
        admin_section = st.secrets.get("admin", {})
        value = admin_section.get("lab_password")
        return str(value) if value else None
    except Exception:
        return None


def require_optional_password() -> None:
    password = configured_password()
    if not password:
        return
    if st.session_state.get("laboratorio_autorizzato"):
        return

    st.title("🧪 Laboratorio sperimentale")
    entered = st.text_input("Password laboratorio", type="password")
    if st.button("Accedi", type="primary"):
        if entered == password:
            st.session_state["laboratorio_autorizzato"] = True
            st.rerun()
        else:
            st.error("Password non corretta.")
    st.stop()


@st.cache_data(show_spinner=False, ttl=300)
def load_archive() -> tuple[pd.DataFrame, str, str | None]:
    return load_primary_archive(str(DATA_FILE), fetch_draws)


@st.cache_data(show_spinner=False)
def run_cached(
    raw_records: tuple[tuple[Any, ...], ...],
    profile_names: tuple[str, ...],
    window_size: int,
    test_limit: int,
    pool_size: int,
    minimum_sum: int,
    maximum_sum: int,
    maximum_low_numbers: int,
    minimum_decades: int,
    random_seed: int,
) -> dict[str, Any]:
    profile_map = profiles_by_name()
    profiles = [profile_map[name] for name in profile_names]
    return run_experiment_suite(
        raw_records=raw_records,
        profiles=profiles,
        window_size=window_size,
        test_limit=test_limit,
        pool_size=pool_size,
        minimum_sum=minimum_sum,
        maximum_sum=maximum_sum,
        maximum_low_numbers=maximum_low_numbers,
        minimum_decades=minimum_decades,
        random_seed=random_seed,
    )


require_optional_password()

st.title("🧪 Laboratorio sperimentale")
st.caption("Confronto walk-forward di profili di scoring prefissati.")
st.warning(
    "I risultati descrivono esclusivamente il campione storico analizzato. "
    "Non dimostrano che un profilo possa prevedere estrazioni future né "
    "modificano le probabilità matematiche del gioco."
)

try:
    archive, source, database_error = load_archive()
except Exception as exc:
    st.error(f"Impossibile caricare l'archivio: {type(exc).__name__}: {exc}")
    st.stop()

source_columns = st.columns(3)
source_columns[0].metric("Fonte", source)
source_columns[1].metric("Estrazioni", f"{len(archive):,}".replace(",", "."))
source_columns[2].metric("Ultima", archive["data"].max().strftime("%d/%m/%Y"))
if database_error:
    st.info(f"Supabase non disponibile; usato il CSV. Dettaglio: {database_error}")

with st.form("laboratorio_configurazione"):
    st.subheader("Configurazione esperimento")
    profile_names = st.multiselect(
        "Profili da confrontare",
        options=[profile.name for profile in DEFAULT_PROFILES],
        default=[profile.name for profile in DEFAULT_PROFILES],
    )

    first_row = st.columns(4)
    window_size = first_row[0].slider(
        "Finestra storica", 50, min(500, len(archive) - 1), 200, 10
    )
    test_limit = first_row[1].slider(
        "Estrazioni di test", 20, min(300, len(archive) - window_size), 120, 10
    )
    pool_size = first_row[2].slider("Pool numeri", 12, 20, 15)
    random_seed = first_row[3].number_input(
        "Seed casuale", min_value=1, value=20260726, step=1
    )

    second_row = st.columns(4)
    minimum_sum = second_row[0].number_input(
        "Somma minima", min_value=100, max_value=400, value=200, step=5
    )
    maximum_sum = second_row[1].number_input(
        "Somma massima", min_value=120, max_value=500, value=340, step=5
    )
    maximum_low_numbers = second_row[2].number_input(
        "Max numeri ≤31", min_value=0, max_value=6, value=4, step=1
    )
    minimum_decades = second_row[3].number_input(
        "Min decine", min_value=2, max_value=6, value=4, step=1
    )

    submitted = st.form_submit_button(
        "Esegui confronto", type="primary", use_container_width=True
    )

if submitted:
    if not profile_names:
        st.error("Seleziona almeno un profilo.")
    elif minimum_sum >= maximum_sum:
        st.error("La somma minima deve essere inferiore alla massima.")
    else:
        with st.spinner("Backtest walk-forward in corso..."):
            try:
                result = run_cached(
                    records_tuple(archive),
                    tuple(profile_names),
                    int(window_size),
                    int(test_limit),
                    int(pool_size),
                    int(minimum_sum),
                    int(maximum_sum),
                    int(maximum_low_numbers),
                    int(minimum_decades),
                    int(random_seed),
                )
            except Exception as exc:
                st.error(f"Esperimento non completato: {type(exc).__name__}: {exc}")
            else:
                st.session_state["ultimo_esperimento"] = result

result = st.session_state.get("ultimo_esperimento")
if result:
    st.divider()
    st.subheader("Risultati")

    overview = st.columns(4)
    overview[0].metric("Test", result["test_count"])
    overview[1].metric("Migliore nel campione", result["best_profile"])
    overview[2].metric("Media casuale", f"{result['random_average']:.3f}")
    overview[3].metric("Casuale 2+", result["random_2_plus"])

    st.caption(
        "La dicitura “migliore nel campione” non è una previsione: indica soltanto "
        "il primo profilo nell'ordinamento dei test selezionati."
    )

    summary_frame = pd.DataFrame(result["summary"])
    preferred_order = [
        "Posizione campione",
        "Profilo",
        "Media punti",
        "Delta medio",
        "IC95% delta min",
        "IC95% delta max",
        "2+",
        "3+",
        "Vittorie vs casuale",
        "Pareggi vs casuale",
        "Sconfitte vs casuale",
        "Instabilità annuale",
        "Pesi frequenza",
        "Pesi ritardo",
        "Pesi recenza",
        "Test",
    ]
    summary_frame = summary_frame[
        [column for column in preferred_order if column in summary_frame.columns]
    ]
    st.dataframe(
        summary_frame.style.format(
            {
                "Media punti": "{:.3f}",
                "Delta medio": "{:+.3f}",
                "IC95% delta min": "{:+.3f}",
                "IC95% delta max": "{:+.3f}",
                "Instabilità annuale": "{:.3f}",
                "Pesi frequenza": "{:.2f}",
                "Pesi ritardo": "{:.2f}",
                "Pesi recenza": "{:.2f}",
            }
        ),
        use_container_width=True,
        hide_index=True,
    )

    annual_frame = pd.DataFrame(result["annual_summary"])
    details_frame = pd.DataFrame(result["details"])
    annual_tab, detail_tab, export_tab = st.tabs(
        ["Stabilità annuale", "Dettaglio test", "Esporta"]
    )

    with annual_tab:
        if annual_frame.empty:
            st.info("Nessun riepilogo annuale disponibile.")
        else:
            st.dataframe(
                annual_frame.style.format({"Media punti": "{:.3f}"}),
                use_container_width=True,
                hide_index=True,
            )

    with detail_tab:
        selected_detail_profiles = st.multiselect(
            "Filtra profili",
            options=result["profiles"],
            default=result["profiles"],
            key="profili_dettaglio_lab",
        )
        filtered = details_frame[
            details_frame["Profilo"].isin(selected_detail_profiles)
        ]
        st.dataframe(filtered, use_container_width=True, hide_index=True)

    with export_tab:
        st.download_button(
            "Scarica riepilogo CSV",
            data=summary_frame.to_csv(index=False).encode("utf-8-sig"),
            file_name="laboratorio_riepilogo.csv",
            mime="text/csv",
            use_container_width=True,
        )
        st.download_button(
            "Scarica dettaglio CSV",
            data=details_frame.to_csv(index=False).encode("utf-8-sig"),
            file_name="laboratorio_dettaglio.csv",
            mime="text/csv",
            use_container_width=True,
        )

st.divider()
with st.expander("Proteggere il laboratorio con password"):
    st.code(
        '[admin]\nlab_password = "scegli-una-password"',
        language="toml",
    )
    st.caption(
        "Aggiungi queste righe ai Secrets di Streamlit. Senza questa sezione, "
        "il laboratorio resta accessibile come le altre pagine."
    )
