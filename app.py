from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from core.backtest import records_tuple
from core.combinations import (
    euro,
    generate_base_variant_system,
    generate_integral_system,
    generate_reduced_system,
    system_cost,
)
from database import (
    delete_draw,
    delete_recommendation,
    fetch_draws,
    fetch_recommendations,
    save_recommendation,
    upsert_draw,
)
from services.archive_service import load_primary_archive
from services.draw_service import add_extraction, update_extraction
from services.recommendation_service import (
    build_monitoring_tables,
    suggest_next_target,
)
from services.forge_service import build_forge_snapshot
from services.orion_service import build_orion_snapshot
from services.presentation_service import build_candidate_profile, build_orion_brief
from ui.orion_ui import (
    apply_orion_theme,
    render_chips,
    render_coherence,
    render_hero,
    render_number_balls,
)

APP_TITLE = "ORION v2.7.5 — SuperEnalotto Quant Engine"
DATA_FILE = Path(__file__).with_name("estrazioni.csv")

st.set_page_config(page_title=APP_TITLE, page_icon="🌌", layout="wide")


def build_forge_snapshot_runtime(
    raw_records: tuple[tuple[Any, ...], ...],
) -> dict[str, Any]:
    dataframe = pd.DataFrame(
        raw_records,
        columns=[
            "data", "anno", "concorso", "n1", "n2", "n3", "n4", "n5", "n6", "jolly", "superstar"
        ],
    )
    dataframe["data"] = pd.to_datetime(dataframe["data"])
    dataframe["jolly"] = (
        pd.to_numeric(dataframe["jolly"])
        .mask(lambda values: values.eq(0))
        .astype("Int64")
    )
    return build_forge_snapshot(dataframe)


def initialize_state() -> None:
    if "single_result" not in st.session_state:
        st.session_state.single_result = None
    if "orion_candidate_index" not in st.session_state:
        st.session_state.orion_candidate_index = 0
    if "system_result" not in st.session_state:
        st.session_state.system_result = None


def invalidate_generated_state(signature: str) -> None:
    """Evita di mostrare proposte create con un archivio o modello precedente."""
    previous = st.session_state.get("orion_runtime_signature")
    if previous == signature:
        return
    st.session_state.single_result = None
    st.session_state.orion_candidate_index = 0
    st.session_state.system_result = None
    st.session_state.orion_runtime_signature = signature


def render_sidebar(
    archive: pd.DataFrame,
    orion: dict[str, Any],
    archive_source: str,
) -> str:
    latest = archive.sort_values(["data", "concorso"]).iloc[-1]
    brief = build_orion_brief(orion)

    st.sidebar.markdown("## ✦ ORION")
    st.sidebar.caption("Quant Engine · modalità automatica")
    navigation = st.sidebar.radio(
        "Navigazione",
        ["Home", "Genera", "Schedine", "Archivio", "Impostazioni"],
        key="orion_navigation",
        label_visibility="collapsed",
    )
    st.sidebar.divider()
    st.sidebar.metric("Archivio", f"{len(archive):,}".replace(",", "."))
    st.sidebar.metric("Ultimo concorso", f"{int(latest['concorso'])}/{int(latest['anno'])}")
    st.sidebar.metric("Coerenza", brief["coherence"])
    st.sidebar.caption(
        f"Dati: {archive_source} · aggiornati al {pd.Timestamp(latest['data']):%d/%m/%Y}"
    )
    st.sidebar.divider()
    st.sidebar.markdown(
        "ORION e FORGE lavorano automaticamente. L’utente vede soltanto le funzioni "
        "necessarie per generare, salvare e controllare le schedine."
    )
    st.sidebar.caption(
        "Il SuperEnalotto resta un gioco casuale. Il motore ordina dati e criteri; "
        "non crea probabilità aggiuntiva."
    )
    return str(navigation)


def render_single_tab(
    orion: dict[str, Any],
    archive: pd.DataFrame,
    database_available: bool,
) -> None:
    candidates = orion["candidates"]
    brief = build_orion_brief(orion)

    if st.session_state.single_result is None:
        quality, combo = candidates[0]
        st.session_state.orion_candidate_index = 0
        st.session_state.single_result = {
            "combo": combo,
            "quality": quality,
            "profile": build_candidate_profile(combo, orion),
            "superstar": orion["superstar_ranking"][0][0],
            "signature": orion["signature"],
        }

    title_column, action_column = st.columns([1.55, 1])
    with title_column:
        st.subheader("Il consiglio di ORION")
        st.caption(
            "La proposta principale è deterministica: a parità di archivio e modello, "
            "ORION restituisce la stessa sestina."
        )
    with action_column:
        action_columns = st.columns(2)
        reset_main = action_columns[0].button(
            "Proposta principale", type="primary", use_container_width=True
        )
        next_alternative = action_columns[1].button(
            "Altra proposta", use_container_width=True
        )

    if reset_main:
        st.session_state.orion_candidate_index = 0
    elif next_alternative:
        candidate_count = min(30, len(candidates))
        st.session_state.orion_candidate_index = (
            int(st.session_state.orion_candidate_index) + 1
        ) % candidate_count

    selected_index = int(st.session_state.orion_candidate_index)
    quality, combo = candidates[selected_index]
    current_combo = tuple(st.session_state.single_result["combo"])
    if combo != current_combo or reset_main or next_alternative:
        st.session_state.single_result = {
            "combo": combo,
            "quality": quality,
            "profile": build_candidate_profile(combo, orion),
            "superstar": orion["superstar_ranking"][0][0],
            "signature": orion["signature"],
        }

    result = st.session_state.single_result
    profile = result["profile"]
    proposal_label = (
        "Proposta principale"
        if selected_index == 0
        else f"Alternativa ORION #{selected_index}"
    )
    render_number_balls(
        result["combo"],
        int(result["superstar"]),
        label=proposal_label,
    )

    detail_columns = st.columns(4)
    detail_columns[0].metric("Somma", profile["features"]["sum"])
    even = profile["features"]["even"]
    detail_columns[1].metric("Pari / dispari", f"{even} / {6-even}")
    detail_columns[2].metric("Decine coperte", profile["features"]["decades"])
    detail_columns[3].metric("Numeri nella top 12", profile["top_twelve_count"])

    explanation_column, coherence_column = st.columns([1.5, 1])
    with explanation_column:
        st.markdown("#### Perché è stata scelta")
        structural_text = (
            "rispetta tutti i vincoli strutturali ricavati dall’archivio"
            if profile["structural_ok"]
            else "usa il miglior compromesso disponibile tra punteggio e struttura"
        )
        st.markdown(
            f"- **Consenso medio:** {profile['average_score']:.1%} sullo score normalizzato.\n"
            f"- **Accordo tra memorie:** {profile['average_agreement']:.1%}.\n"
            f"- **Struttura:** {structural_text}.\n"
            f"- **Posizionamento:** numeri compresi tra il {profile['best_rank']}° e il "
            f"{profile['worst_rank']}° posto del ranking corrente."
        )
    with coherence_column:
        render_coherence(float(orion["stability"]), brief["coherence"])

    with st.expander("Salva e monitora questa schedina", expanded=False):
        if not database_available:
            st.warning(
                "Il salvataggio persistente richiede Supabase. In questo momento "
                "l’app sta leggendo il CSV di emergenza."
            )
        else:
            default_year, default_contest = suggest_next_target(archive)
            with st.form("save_generated_recommendation"):
                save_columns = st.columns([1.4, 1, 1, 1])
                name = save_columns[0].text_input(
                    "Nome",
                    value=f"ORION {pd.Timestamp.now():%d/%m/%Y}",
                )
                start_year = save_columns[1].number_input(
                    "Anno iniziale", min_value=2020, max_value=2100,
                    value=int(default_year), step=1,
                )
                start_contest = save_columns[2].number_input(
                    "Concorso iniziale", min_value=1,
                    value=int(default_contest), step=1,
                )
                draw_count = save_columns[3].number_input(
                    "Concorsi", min_value=1, max_value=100,
                    value=5, step=1,
                )
                notes = st.text_input(
                    "Note facoltative",
                    placeholder="Esempio: stessa sestina per 5 concorsi",
                )
                save_submitted = st.form_submit_button(
                    "Salva nel monitoraggio", type="primary", use_container_width=True
                )
            if save_submitted:
                try:
                    saved = save_recommendation(
                        list(result["combo"]),
                        int(result["superstar"]),
                        int(start_year),
                        int(start_contest),
                        int(draw_count),
                        name=name,
                        source="orion_v2_7",
                        notes=notes,
                    )
                except Exception as exc:
                    st.error(str(exc))
                else:
                    st.success(
                        f"Schedina #{saved['id']} salvata. Gli esiti verranno aggiornati "
                        "quando saranno disponibili le nuove estrazioni."
                    )

    st.divider()
    watch_column, latest_column = st.columns(2)
    with watch_column:
        st.markdown("#### Numeri sotto osservazione")
        st.caption(
            "Sono i numeri con il consenso ORION più alto adesso. Non sono numeri “più probabili”."
        )
        render_chips([str(number) for number in brief["top_numbers"]])
        st.caption(
            "Memorie attive: " + " · ".join(brief["memories"])
        )
    with latest_column:
        latest = archive.sort_values(["data", "concorso"]).iloc[-1]
        latest_numbers = [int(latest[f"n{index}"]) for index in range(1, 7)]
        st.markdown("#### Ultima estrazione acquisita")
        st.caption(
            f"Concorso {int(latest['concorso'])}/{int(latest['anno'])} · "
            f"{pd.Timestamp(latest['data']):%d/%m/%Y} · Jolly "
            f"{('—' if pd.isna(latest['jolly']) else int(latest['jolly']))}"
        )
        render_number_balls(
            latest_numbers,
            int(latest["superstar"]),
            compact=True,
            label="Numeri estratti",
        )

    st.caption(
        "ORION applica criteri statistici allo storico, ma ogni sestina conserva la stessa "
        "probabilità matematica di qualunque altra sestina valida."
    )


def render_systems_tab(
    scores: dict[int, float], superstar_ranking: list[tuple[int, float, int, int]]
) -> None:
    st.subheader("Crea un sistema ORION")
    st.caption(
        "Scegli soltanto il livello di spesa. ORION seleziona automaticamente "
        "i numeri e costruisce le sestine."
    )

    profile_specs = {
        "Compatto · 8 sestine": {
            "lines": 8,
            "description": "Spesa contenuta e sestine diversificate.",
        },
        "Equilibrato · 15 sestine": {
            "lines": 15,
            "description": "Due numeri base e sei varianti combinate.",
        },
        "Integrale 7 numeri · 7 sestine": {
            "lines": 7,
            "description": "Tutte le sestine ottenibili da un gruppo di 7 numeri.",
        },
    }

    selection_column, option_column = st.columns([1.55, 1])
    with selection_column:
        system_profile = st.radio(
            "Tipo di sistema",
            list(profile_specs),
            key="orion_system_profile",
        )
        st.caption(str(profile_specs[system_profile]["description"]))
    with option_column:
        with_superstar = st.toggle(
            "Aggiungi SuperStar a tutte le sestine",
            value=True,
            key="orion_system_superstar",
        )
        line_count = int(profile_specs[system_profile]["lines"])
        st.metric("Costo previsto", euro(system_cost(line_count, with_superstar)))
        st.caption(
            f"{line_count} sestine · tariffa configurata: 1,00 € ciascuna"
            + (" + 0,50 € SuperStar" if with_superstar else "")
        )

    if st.button(
        "Genera sistema ORION",
        type="primary",
        use_container_width=True,
        key="generate_orion_system",
    ):
        coverage = None
        bases: list[int] = []
        variants: list[int] = []

        if system_profile == "Compatto · 8 sestine":
            pool, lines, coverage = generate_reduced_system(scores, 12, 8)
            method = "Compatto"
        elif system_profile == "Equilibrato · 15 sestine":
            bases, variants, lines = generate_base_variant_system(scores, 2, 6)
            pool = sorted([*bases, *variants])
            method = "Equilibrato"
        else:
            pool, lines = generate_integral_system(scores, 7)
            method = "Integrale 7 numeri"

        st.session_state.system_result = {
            "profile": system_profile,
            "method": method,
            "pool": pool,
            "bases": bases,
            "variants": variants,
            "lines": lines,
            "coverage": coverage,
            "with_superstar": with_superstar,
            "superstar": superstar_ranking[0][0],
        }

    result = st.session_state.system_result
    if not result:
        return

    lines = result["lines"]
    st.divider()
    st.markdown("#### Sistema generato")
    summary_columns = st.columns(4)
    summary_columns[0].metric("Profilo", result["method"])
    summary_columns[1].metric("Numeri usati", len(result["pool"]))
    summary_columns[2].metric("Sestine", len(lines))
    summary_columns[3].metric(
        "Costo totale", euro(system_cost(len(lines), result["with_superstar"]))
    )

    if result["bases"]:
        st.markdown("**Numeri base:** " + " · ".join(map(str, result["bases"])))
        st.markdown("**Numeri variabili:** " + " · ".join(map(str, result["variants"])))
    else:
        st.markdown("**Numeri scelti da ORION:**")
        render_chips([str(number) for number in result["pool"]])

    system_dataframe = pd.DataFrame(
        lines, columns=[f"N{index}" for index in range(1, 7)]
    )
    if result["with_superstar"]:
        system_dataframe["SuperStar"] = int(result["superstar"])
    st.dataframe(system_dataframe, use_container_width=True, hide_index=True, height=480)
    st.download_button(
        "Scarica sistema CSV",
        system_dataframe.to_csv(index=False).encode("utf-8-sig"),
        "sistema_orion_v2_7_4.csv",
        "text/csv",
        use_container_width=True,
    )
    st.caption(
        "Il costo mostrato dipende dal numero di sestine e dall’eventuale SuperStar. "
        "Più sestine aumentano la copertura acquistata, non la capacità di prevedere l’estrazione."
    )


def render_generate_view(
    orion: dict[str, Any],
    archive: pd.DataFrame,
    database_available: bool,
) -> None:
    render_hero(orion["version"], orion["status"], orion["signature"])
    proposal_tab, system_tab = st.tabs(["Proposta singola", "Sistema"])
    with proposal_tab:
        render_single_tab(orion, archive, database_available)
    with system_tab:
        render_systems_tab(orion["score"], orion["superstar_ranking"])





def render_monitored_tickets_tab(
    archive: pd.DataFrame, database_available: bool
) -> None:
    st.subheader("Schedine consigliate e risultati")
    st.caption(
        "Ogni schedina viene confrontata automaticamente con i concorsi indicati. "
        "Quando aggiungi una nuova estrazione a Supabase, il relativo esito compare qui."
    )

    if not database_available:
        st.warning(
            "Il monitoraggio persistente richiede Supabase. L'archivio è attualmente "
            "caricato dal CSV di emergenza."
        )
        return

    default_year, default_contest = suggest_next_target(archive)
    with st.expander("Registra una schedina già giocata", expanded=False):
        # Questo controllo resta fuori dal form: i widget contenuti in un form
        # aggiornano lo stato soltanto al submit. In questo modo la selezione
        # abilita immediatamente il campo numerico del SuperStar.
        has_superstar = st.checkbox(
            "SuperStar giocato",
            value=False,
            key="manual_has_superstar",
            help="Attiva il campo per indicare il numero SuperStar effettivamente giocato.",
        )

        with st.form("manual_recommendation"):
            identity_columns = st.columns(4)
            name = identity_columns[0].text_input(
                "Nome", value="Schedina giocata", key="manual_ticket_name"
            )
            start_year = identity_columns[1].number_input(
                "Anno iniziale", min_value=2020, max_value=2100,
                value=int(default_year), step=1, key="manual_start_year",
            )
            start_contest = identity_columns[2].number_input(
                "Concorso iniziale", min_value=1, value=int(default_contest),
                step=1, key="manual_start_contest",
            )
            draw_count = identity_columns[3].number_input(
                "Concorsi giocati", min_value=1, max_value=100, value=5,
                step=1, key="manual_draw_count",
            )

            number_columns = st.columns(6)
            numbers = [
                number_columns[index - 1].number_input(
                    f"N{index}", min_value=1, max_value=90, value=index,
                    step=1, key=f"manual_ticket_n{index}",
                )
                for index in range(1, 7)
            ]
            superstar = st.number_input(
                "Numero SuperStar",
                min_value=1,
                max_value=90,
                value=1,
                step=1,
                disabled=not has_superstar,
                key="manual_ticket_superstar",
                help=(
                    "Numero SuperStar associato alla schedina. "
                    "Il campo si abilita selezionando ‘SuperStar giocato’ sopra il modulo."
                ),
            )
            notes = st.text_input(
                "Note facoltative", key="manual_ticket_notes",
                placeholder="Esempio: stessa schedina per cinque concorsi",
            )
            submitted = st.form_submit_button(
                "Registra e monitora", type="primary", use_container_width=True
            )
        if submitted:
            try:
                saved = save_recommendation(
                    [int(number) for number in numbers],
                    int(superstar) if has_superstar else None,
                    int(start_year),
                    int(start_contest),
                    int(draw_count),
                    name=name,
                    source="inserimento_manuale",
                    notes=notes,
                )
            except Exception as exc:
                st.error(str(exc))
            else:
                st.session_state["ticket_flash"] = (
                    f"Schedina #{saved['id']} registrata correttamente."
                )
                st.rerun()

    flash = st.session_state.pop("ticket_flash", None)
    if flash:
        st.success(flash)

    try:
        recommendations = fetch_recommendations()
    except Exception as exc:
        st.error(f"Impossibile leggere le schedine monitorate: {exc}")
        return

    if recommendations.empty:
        st.info(
            "Non ci sono ancora schedine monitorate. Puoi salvare una sestina generata "
            "oppure registrare qui una schedina già giocata."
        )
        return

    summary, details = build_monitoring_tables(recommendations, archive)
    total_results = int(summary["Risultati 2+"].sum()) if not summary.empty else 0
    evaluated_draws = int(summary["Concorsi valutati"].sum()) if not summary.empty else 0
    pending_draws = int(summary["Concorsi in attesa"].sum()) if not summary.empty else 0
    metric_columns = st.columns(4)
    metric_columns[0].metric("Schedine monitorate", len(summary))
    metric_columns[1].metric("Concorsi valutati", evaluated_draws)
    metric_columns[2].metric("Risultati da 2 in su", total_results)
    metric_columns[3].metric("Concorsi in attesa", pending_draws)

    st.subheader("Riepilogo schedine")
    st.dataframe(summary, use_container_width=True, hide_index=True)

    st.subheader("Esito di ogni estrazione")
    if details.empty:
        st.info("I concorsi iniziali registrati non sono ancora presenti nell'archivio.")
    else:
        display_details = details.copy()
        display_details["Segnalazione"] = display_details.apply(
            lambda row: (
                f"✅ {row['Risultato']}"
                if int(row["Punti"]) >= 2
                else f"— {row['Risultato']}"
            ),
            axis=1,
        )
        display_details["Data"] = pd.to_datetime(display_details["Data"]).dt.strftime(
            "%d/%m/%Y"
        )
        preferred_columns = [
            "Segnalazione", "Nome", "Data", "Concorso", "Sestina giocata",
            "Numeri estratti", "Punti", "Numeri centrati", "Jolly centrato",
            "SuperStar centrato",
        ]
        st.dataframe(
            display_details[preferred_columns],
            use_container_width=True,
            hide_index=True,
            height=520,
        )
        st.download_button(
            "Scarica storico risultati CSV",
            details.to_csv(index=False).encode("utf-8-sig"),
            "storico_schedine_monitorate.csv",
            "text/csv",
        )

    with st.expander("Elimina una schedina dal monitoraggio"):
        ticket_options = {
            f"#{int(row.id)} — {row.nome} — {int(row.concorso_inizio)}/{int(row.anno_inizio)}": int(row.id)
            for row in recommendations.itertuples(index=False)
        }
        selected_label = st.selectbox(
            "Schedina", list(ticket_options), key="delete_ticket_selection"
        )
        selected_id = ticket_options[selected_label]
        confirmation = st.text_input(
            f"Per confermare scrivi ELIMINA {selected_id}",
            key="delete_ticket_confirmation",
        )
        if st.button(
            "Elimina schedina",
            disabled=confirmation.strip() != f"ELIMINA {selected_id}",
            key="delete_monitored_ticket",
        ):
            try:
                delete_recommendation(selected_id)
            except Exception as exc:
                st.error(str(exc))
            else:
                st.session_state["ticket_flash"] = (
                    f"Schedina #{selected_id} eliminata dal monitoraggio."
                )
                st.rerun()


def refresh_after_archive_write(message: str) -> None:
    """Svuota le cache dopo una scrittura e mostra l'esito al rerun successivo."""
    st.cache_data.clear()
    st.session_state["archive_flash"] = message
    st.rerun()


def render_draw_fields(prefix: str, values: list[int]) -> list[int]:
    columns = st.columns(6)
    return [
        int(
            columns[index - 1].number_input(
                f"N{index}",
                min_value=1,
                max_value=90,
                value=int(values[index - 1]),
                step=1,
                key=f"{prefix}_n{index}",
            )
        )
        for index in range(1, 7)
    ]


def render_archive_tab(archive: pd.DataFrame, database_available: bool) -> None:
    st.subheader("Archivio estrazioni")

    flash_message = st.session_state.pop("archive_flash", None)
    if flash_message:
        st.success(str(flash_message))

    archive_tab, add_tab, edit_tab = st.tabs(
        ["Archivio", "Nuova estrazione", "Correggi o elimina"]
    )

    with archive_tab:
        year_options = ["Tutti"] + sorted(
            archive["anno"].unique().tolist(), reverse=True
        )
        selected_year = st.selectbox("Anno", year_options, key="archive_year_filter")

        display_archive = archive.copy()
        if selected_year != "Tutti":
            display_archive = display_archive[
                display_archive["anno"] == int(selected_year)
            ]

        display_archive = display_archive.sort_values("data", ascending=False)
        display_archive["data"] = display_archive["data"].dt.strftime("%d/%m/%Y")
        display_archive["jolly"] = display_archive["jolly"].astype("Int64")
        st.dataframe(
            display_archive,
            use_container_width=True,
            hide_index=True,
            height=600,
        )

    with add_tab:
        st.markdown("#### Inserisci una nuova estrazione")
        st.caption(
            "Il salvataggio modifica direttamente l’archivio Supabase. "
            "Dopo il salvataggio ORION e FORGE vengono ricalcolati automaticamente."
        )

        if not database_available:
            st.warning(
                "L’inserimento richiede Supabase. L’app sta usando il CSV di emergenza, "
                "quindi il modulo è temporaneamente disattivato."
            )
        else:
            latest = archive.sort_values(["data", "concorso"]).iloc[-1]
            earliest_next = pd.Timestamp(latest["data"]).date() + timedelta(days=1)
            suggested_date = max(earliest_next, date.today())
            suggested_contest = (
                int(latest["concorso"]) + 1
                if suggested_date.year == int(latest["anno"])
                else 1
            )

            with st.form("add_draw_form", clear_on_submit=False):
                identity_columns = st.columns(2)
                draw_date = identity_columns[0].date_input(
                    "Data estrazione", value=suggested_date
                )
                contest = int(
                    identity_columns[1].number_input(
                        "Numero concorso",
                        min_value=1,
                        value=int(suggested_contest),
                        step=1,
                    )
                )

                st.caption("Inserisci i sei numeri; saranno salvati in ordine crescente.")
                numbers = render_draw_fields("add_draw", [1, 2, 3, 4, 5, 6])

                extra_columns = st.columns(3)
                jolly_available = extra_columns[0].checkbox(
                    "Jolly disponibile", value=True, key="add_jolly_available"
                )
                jolly = int(
                    extra_columns[1].number_input(
                        "Jolly",
                        min_value=1,
                        max_value=90,
                        value=7,
                        step=1,
                        disabled=not jolly_available,
                        key="add_jolly",
                    )
                )
                superstar = int(
                    extra_columns[2].number_input(
                        "SuperStar",
                        min_value=1,
                        max_value=90,
                        value=8,
                        step=1,
                        key="add_superstar",
                    )
                )

                submitted = st.form_submit_button(
                    "Salva estrazione", type="primary", use_container_width=True
                )

            if submitted:
                try:
                    validated_archive = add_extraction(
                        archive,
                        draw_date,
                        contest,
                        numbers,
                        jolly if jolly_available else None,
                        superstar,
                    )
                    new_row = validated_archive.loc[
                        (validated_archive["anno"] == draw_date.year)
                        & (validated_archive["concorso"] == contest)
                    ].iloc[0]
                    upsert_draw(new_row.to_dict(), source="inserimento_app_v2_7_5")
                except Exception as exc:
                    st.error(str(exc))
                else:
                    refresh_after_archive_write(
                        f"Concorso {contest} del {draw_date.year} salvato correttamente."
                    )

    with edit_tab:
        st.markdown("#### Correggi un’estrazione")
        st.caption(
            "Puoi correggere data, numeri, Jolly e SuperStar. "
            "Anno e numero del concorso restano invariati."
        )

        if not database_available:
            st.warning(
                "La modifica richiede Supabase. L’app sta usando il CSV di emergenza."
            )
        else:
            year_options = sorted(archive["anno"].unique().tolist(), reverse=True)
            selected_year = int(
                st.selectbox("Anno", year_options, key="edit_draw_year")
            )
            year_frame = archive[archive["anno"] == selected_year]
            contest_options = sorted(
                year_frame["concorso"].unique().tolist(), reverse=True
            )
            selected_contest = int(
                st.selectbox("Concorso", contest_options, key="edit_draw_contest")
            )
            selected = year_frame[
                year_frame["concorso"] == selected_contest
            ].iloc[0]

            with st.form(f"edit_draw_form_{selected_year}_{selected_contest}"):
                draw_date = st.date_input(
                    "Data estrazione",
                    value=pd.Timestamp(selected["data"]).date(),
                    key=f"edit_draw_date_{selected_year}_{selected_contest}",
                )
                current_numbers = [
                    int(selected[f"n{index}"]) for index in range(1, 7)
                ]
                numbers = render_draw_fields(
                    f"edit_draw_{selected_year}_{selected_contest}", current_numbers
                )

                selected_jolly_available = not pd.isna(selected["jolly"])
                extra_columns = st.columns(3)
                jolly_available = extra_columns[0].checkbox(
                    "Jolly disponibile",
                    value=selected_jolly_available,
                    key=f"edit_jolly_available_{selected_year}_{selected_contest}",
                )
                jolly = int(
                    extra_columns[1].number_input(
                        "Jolly",
                        min_value=1,
                        max_value=90,
                        value=(
                            int(selected["jolly"])
                            if selected_jolly_available
                            else 1
                        ),
                        step=1,
                        disabled=not jolly_available,
                        key=f"edit_jolly_{selected_year}_{selected_contest}",
                    )
                )
                superstar = int(
                    extra_columns[2].number_input(
                        "SuperStar",
                        min_value=1,
                        max_value=90,
                        value=int(selected["superstar"]),
                        step=1,
                        key=f"edit_superstar_{selected_year}_{selected_contest}",
                    )
                )

                submitted_edit = st.form_submit_button(
                    "Salva correzione", type="primary", use_container_width=True
                )

            if submitted_edit:
                try:
                    corrected_archive = update_extraction(
                        archive,
                        selected_year,
                        selected_contest,
                        draw_date,
                        numbers,
                        jolly if jolly_available else None,
                        superstar,
                    )
                    corrected_row = corrected_archive.loc[
                        (corrected_archive["anno"] == selected_year)
                        & (corrected_archive["concorso"] == selected_contest)
                    ].iloc[0]
                    upsert_draw(
                        corrected_row.to_dict(), source="correzione_app_v2_7_5"
                    )
                except Exception as exc:
                    st.error(str(exc))
                else:
                    refresh_after_archive_write(
                        f"Concorso {selected_contest} del {selected_year} corretto."
                    )

            st.divider()
            with st.expander("Zona pericolosa — elimina l’ultima estrazione"):
                latest = archive.sort_values(["data", "concorso"]).iloc[-1]
                latest_year = int(latest["anno"])
                latest_contest = int(latest["concorso"])
                st.warning(
                    f"È eliminabile soltanto l’ultima estrazione: concorso "
                    f"{latest_contest}/{latest_year} del "
                    f"{pd.Timestamp(latest['data']):%d/%m/%Y}. "
                    "Usa questa funzione soltanto per correggere un inserimento errato. "
                    "Non è un rollback delle valutazioni prospettiche FORGE."
                )
                confirmation_text = f"ELIMINA {latest_contest}"
                typed_confirmation = st.text_input(
                    f"Per confermare scrivi {confirmation_text}",
                    key="delete_latest_draw_confirmation",
                )
                if st.button(
                    "Elimina definitivamente l’ultima estrazione",
                    disabled=typed_confirmation.strip() != confirmation_text,
                    use_container_width=True,
                    key="delete_latest_draw_button",
                ):
                    try:
                        delete_draw(
                            latest_year,
                            latest_contest,
                            source="eliminazione_app_v2_7_5",
                        )
                    except Exception as exc:
                        st.error(str(exc))
                    else:
                        refresh_after_archive_write(
                            f"Concorso {latest_contest} del {latest_year} eliminato."
                        )


def render_home_view(
    archive: pd.DataFrame,
    orion: dict[str, Any],
    forge: dict[str, Any],
    archive_source: str,
    database_error: str | None,
) -> None:
    render_hero(orion["version"], orion["status"], orion["signature"])
    latest = archive.sort_values(["data", "concorso"]).iloc[-1]
    brief = build_orion_brief(orion)

    metric_columns = st.columns(4)
    metric_columns[0].metric(
        "Ultimo concorso", f"{int(latest['concorso'])}/{int(latest['anno'])}"
    )
    metric_columns[1].metric("Archivio", f"{len(archive):,}".replace(",", "."))
    metric_columns[2].metric(
        "Modello attivo", str(orion.get("model_id", "ORION-BALANCED"))
    )
    state_labels = {"shadow": "In osservazione", "promoted": "Promosso", "fallback": "Protetto"}
    metric_columns[3].metric("Stato", state_labels.get(str(forge.get("state")), "Non validato"))

    st.caption(
        f"Fonte dati: **{archive_source}** · archivio aggiornato al "
        f"{pd.Timestamp(latest['data']):%d/%m/%Y} · coerenza {brief['coherence'].lower()}."
    )
    if database_error and archive_source != "Supabase":
        st.warning("Supabase non è disponibile: ORION sta usando il CSV di sicurezza.")

    primary = tuple(orion["primary"])
    superstar = int(orion["superstar_ranking"][0][0])
    st.subheader("Ultima proposta ORION")
    render_number_balls(primary, superstar, label="Proposta principale")

    def open_generate() -> None:
        st.session_state["orion_navigation"] = "Genera"

    st.button(
        "Genera nuova proposta",
        type="primary",
        use_container_width=True,
        on_click=open_generate,
    )


def render_settings_view(
    archive: pd.DataFrame,
    forge: dict[str, Any],
    archive_source: str,
    database_error: str | None,
) -> None:
    st.subheader("Impostazioni")
    st.caption(
        "ORION è configurato per funzionare in automatico. Non ci sono pesi, finestre "
        "o filtri statistici da regolare manualmente."
    )

    active = forge.get("active_model") or {}
    challenger = forge.get("challenger_model") or {}
    state_labels = {"shadow": "Shadow", "promoted": "Promosso", "fallback": "Fallback"}
    columns = st.columns(4)
    columns[0].metric("Fonte dati", archive_source)
    columns[1].metric("FORGE", state_labels.get(str(forge.get("state")), "Non validato"))
    columns[2].metric("Challenger in ombra", int(forge.get("shadow_count", 0)))
    columns[3].metric("Champion", str(active.get("model_id", "ORION-BALANCED")))

    st.markdown("#### Automazione")
    st.markdown(
        "- Il backtest usa lo stesso identico pipeline della proposta live.\n"
        "- Il profilo bilanciato resta champion finché un challenger non supera dati futuri reali.\n"
        "- Le proposte champion/challenger vengono salvate prima dell’estrazione e valutate dopo.\n"
        "- Un buon risultato retrospettivo autorizza soltanto la modalità shadow, non la promozione."
    )
    if challenger:
        st.caption(f"Challenger osservato: {challenger.get('model_id')} · {challenger.get('label', '')}")

    st.markdown("#### Archivio")
    latest = archive.sort_values(["data", "concorso"]).iloc[-1]
    archive_count = f"{len(archive):,}".replace(",", ".")
    st.write(
        f"{archive_count} estrazioni disponibili, aggiornate al "
        f"{pd.Timestamp(latest['data']):%d/%m/%Y}."
    )
    if database_error:
        st.info("La connessione principale non è disponibile; il CSV locale resta operativo.")
    if not forge.get("persistence_ok", False):
        st.warning(
            "La memoria persistente di FORGE non è disponibile. Il champion resta protetto e "
            "i risultati locali possono sparire al reboot. Dettaglio nel riquadro tecnico."
        )

    with st.expander("Stato tecnico di FORGE", expanded=False):
        st.json(
            {
                "stato": forge.get("state"),
                "registro": forge.get("registry"),
                "persistenza_ok": forge.get("persistence_ok"),
                "errore_persistenza": forge.get("persistence_error"),
                "candidati": forge.get("candidate_count"),
                "shadow": forge.get("shadow_count"),
                "non_validati": forge.get("non_validated_count"),
                "respinti": forge.get("rejected_count"),
                "falliti": forge.get("failed_count"),
                "previsioni_valutate_ora": forge.get("evaluated_predictions_now"),
                "previsioni_annullate_ora": forge.get("predictions_voided_now"),
                "previsioni_salvate_ora": forge.get("predictions_saved_now"),
                "valutazione_prospettica": forge.get("prospective"),
                "esperimenti_saltati_perche_gia_noti": forge.get("skipped_known"),
            }
        )


def main() -> None:
    apply_orion_theme()
    try:
        repository_archive, archive_source, database_error = load_primary_archive(
            str(DATA_FILE), fetch_draws
        )
    except (FileNotFoundError, ValueError, pd.errors.ParserError) as exc:
        st.error(str(exc))
        st.stop()

    initialize_state()
    archive = repository_archive
    with st.spinner("FORGE verifica i modelli disponibili..."):
        forge = build_forge_snapshot_runtime(records_tuple(archive))
    orion = build_orion_snapshot(archive, forge)
    invalidate_generated_state(
        f"{forge.get('archive_signature')}:{orion.get('signature')}:{orion.get('model_id')}"
    )
    database_available = archive_source == "Supabase" and database_error is None

    navigation = render_sidebar(archive, orion, archive_source)
    if navigation == "Home":
        render_home_view(archive, orion, forge, archive_source, database_error)
    elif navigation == "Genera":
        render_generate_view(orion, archive, database_available)
    elif navigation == "Schedine":
        render_monitored_tickets_tab(archive, database_available)
    elif navigation == "Archivio":
        render_archive_tab(archive, database_available)
    else:
        render_settings_view(archive, forge, archive_source, database_error)


if __name__ == "__main__":
    main()
