from __future__ import annotations

import random
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from core.analytics import archive_analytics
from core.backtest import records_tuple, run_walk_forward_backtest as engine_backtest
from core.combinations import (
    combination_features,
    euro,
    generate_base_variant_system,
    generate_integral_system,
    generate_reduced_system,
    rank_candidate_sestine,
    system_cost,
)
from core.metrics import calculate_metrics, calculate_superstar_ranking
from database import (
    delete_recommendation,
    fetch_draws,
    fetch_recommendations,
    save_recommendation,
)
from services.archive_service import archive_snapshot, load_primary_archive
from services.draw_service import dataframe_to_history
from services.recommendation_service import (
    build_monitoring_tables,
    suggest_next_target,
)

APP_TITLE = "SuperEnalotto — Analisi statistica e sistemi"
DATA_FILE = Path(__file__).with_name("estrazioni.csv")

st.set_page_config(page_title=APP_TITLE, page_icon="🎰", layout="wide")


@st.cache_data(show_spinner=False)
def rank_candidate_sestine_cached(
    score_items: tuple[tuple[int, float], ...],
    top_pool_size: int,
    limit: int,
    minimum_sum: int,
    maximum_sum: int,
    maximum_low_numbers: int,
    minimum_decades: int,
) -> list[tuple[float, tuple[int, ...]]]:
    return rank_candidate_sestine(
        dict(score_items),
        top_pool_size,
        limit,
        minimum_sum,
        maximum_sum,
        maximum_low_numbers,
        minimum_decades,
    )


@st.cache_data(show_spinner=False)
def run_walk_forward_backtest_cached(
    raw_records: tuple[tuple[Any, ...], ...],
    window_size: int,
    test_limit: int,
    pool_size: int,
    minimum_sum: int,
    maximum_sum: int,
    maximum_low_numbers: int,
    minimum_decades: int,
    random_seed: int,
) -> dict[str, Any]:
    return engine_backtest(
        raw_records,
        window_size,
        test_limit,
        pool_size,
        minimum_sum,
        maximum_sum,
        maximum_low_numbers,
        minimum_decades,
        random_seed,
    )


@st.cache_data(show_spinner=False)
def archive_analytics_cached(
    raw_records: tuple[tuple[Any, ...], ...], association_limit: int
) -> dict[str, Any]:
    dataframe = pd.DataFrame(
        raw_records,
        columns=[
            "data", "anno", "concorso", "n1", "n2", "n3", "n4", "n5", "n6", "jolly", "superstar"
        ],
    )
    dataframe["data"] = pd.to_datetime(dataframe["data"])
    dataframe["jolly"] = pd.to_numeric(dataframe["jolly"]).mask(lambda values: values.eq(0)).astype("Int64")
    return archive_analytics(dataframe_to_history(dataframe), association_limit)


def initialize_state() -> None:
    if "single_result" not in st.session_state:
        st.session_state.single_result = None
    if "backtest_result" not in st.session_state:
        st.session_state.backtest_result = None


def render_sidebar(archive: pd.DataFrame) -> int:
    st.sidebar.header("Archivio estrazioni")
    st.sidebar.metric("Estrazioni disponibili", f"{len(archive):,}".replace(",", "."))
    st.sidebar.caption(
        f"Dal {archive['data'].min():%d/%m/%Y} al {archive['data'].max():%d/%m/%Y}"
    )

    window_options = [50, 100, 200, 500, len(archive)]
    window_options = sorted(
        set(option for option in window_options if option <= len(archive))
    )
    return int(
        st.sidebar.selectbox(
            "Finestra statistica attiva",
            window_options,
            index=window_options.index(100) if 100 in window_options else 0,
            format_func=lambda value: (
                f"Tutto l'archivio ({value})"
                if value == len(archive)
                else f"Ultime {value}"
            ),
        )
    )

def render_single_tab(
    scores: dict[int, float],
    score_items: tuple[tuple[int, float], ...],
    superstar_ranking: list[tuple[int, float, int, int]],
    archive: pd.DataFrame,
    database_available: bool,
) -> None:
    st.subheader("Sestina elaborata sulla finestra attiva")
    filter_columns = st.columns(5)
    pool_size = filter_columns[0].slider("Pool top", 15, 25, 25)
    minimum_sum = filter_columns[1].number_input("Somma minima", 100, 400, 200, 5)
    maximum_sum = filter_columns[2].number_input("Somma massima", 120, 500, 340, 5)
    maximum_low = filter_columns[3].number_input("Max numeri ≤31", 0, 6, 4, 1)
    minimum_decades = filter_columns[4].number_input("Min decine", 2, 6, 4, 1)

    button_columns = st.columns(2)
    generate_main = button_columns[0].button(
        "Calcola principale", type="primary", use_container_width=True
    )
    generate_alternative = button_columns[1].button(
        "Alternativa tra le migliori", use_container_width=True
    )

    if minimum_sum >= maximum_sum:
        st.error("La somma minima deve essere inferiore alla massima.")
    elif generate_main or generate_alternative:
        candidates = rank_candidate_sestine_cached(
            score_items,
            int(pool_size),
            250,
            int(minimum_sum),
            int(maximum_sum),
            int(maximum_low),
            int(minimum_decades),
        )
        if not candidates:
            st.error("Nessuna sestina rispetta i filtri.")
        else:
            previous = (
                tuple(st.session_state.single_result["combo"])
                if st.session_state.single_result
                else None
            )
            if generate_alternative:
                alternatives = [
                    item for item in candidates[:100] if item[1] != previous
                ]
                quality, combo = random.SystemRandom().choice(
                    alternatives or candidates[:100]
                )
            else:
                quality, combo = candidates[0]

            st.session_state.single_result = {
                "combo": combo,
                "quality": quality,
                "features": combination_features(combo),
                "superstar": superstar_ranking[0][0],
            }

    result = st.session_state.single_result
    if result:
        number_columns = st.columns(6)
        for index, number in enumerate(result["combo"], start=1):
            number_columns[index - 1].metric(f"N{index}", number)

        detail_columns = st.columns(4)
        detail_columns[0].metric("SuperStar statistico", result["superstar"])
        detail_columns[1].metric("Somma", result["features"]["sum"])
        even = result["features"]["even"]
        detail_columns[2].metric("Pari / dispari", f"{even} / {6-even}")
        detail_columns[3].metric("Decine", result["features"]["decades"])
        st.caption(
            "La sestina è una selezione statistica riproducibile; non modifica "
            "la probabilità matematica della singola combinazione."
        )

        with st.expander("Salva e monitora questa schedina", expanded=False):
            if not database_available:
                st.warning(
                    "Il salvataggio richiede Supabase. In questo momento l'app sta usando "
                    "il CSV di emergenza."
                )
            else:
                default_year, default_contest = suggest_next_target(archive)
                with st.form("save_generated_recommendation"):
                    save_columns = st.columns(4)
                    name = save_columns[0].text_input(
                        "Nome",
                        value=f"Sestina consigliata {pd.Timestamp.now():%d/%m/%Y}",
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
                        "Concorsi da monitorare", min_value=1, max_value=100,
                        value=5, step=1,
                    )
                    notes = st.text_input(
                        "Note facoltative",
                        placeholder="Esempio: giocata per 5 concorsi consecutivi",
                    )
                    save_submitted = st.form_submit_button(
                        "Salva schedina nel database", type="primary",
                        use_container_width=True,
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
                            source="generatore_app",
                            notes=notes,
                        )
                    except Exception as exc:
                        st.error(str(exc))
                    else:
                        st.success(
                            f"Schedina #{saved['id']} salvata. I risultati verranno "
                            "calcolati automaticamente quando inserirai le estrazioni."
                        )


def render_systems_tab(
    scores: dict[int, float], superstar_ranking: list[tuple[int, float, int, int]]
) -> None:
    st.subheader("Generatore sistemi")
    with_superstar = st.checkbox("Costo con SuperStar", value=True)
    system_type = st.selectbox(
        "Tipologia", ["Integrale", "Basi e varianti", "Ridotto diversificato"]
    )

    if system_type == "Integrale":
        integral_pool = st.radio("Numeri", [7, 8, 9], horizontal=True)
        if st.button("Genera integrale", type="primary"):
            pool, lines = generate_integral_system(scores, int(integral_pool))
            st.write("**Pool:** " + ", ".join(map(str, pool)))
            st.metric("Combinazioni", len(lines))
            st.metric("Costo", euro(system_cost(len(lines), with_superstar)))
            system_dataframe = pd.DataFrame(
                lines, columns=[f"N{index}" for index in range(1, 7)]
            )
            if with_superstar:
                system_dataframe["SuperStar"] = superstar_ranking[0][0]
            st.dataframe(system_dataframe, use_container_width=True, hide_index=True)
            st.download_button(
                "Scarica sistema CSV",
                system_dataframe.to_csv(index=False).encode("utf-8-sig"),
                f"sistema_integrale_{integral_pool}.csv",
                "text/csv",
            )

    elif system_type == "Basi e varianti":
        setting_columns = st.columns(2)
        base_count = setting_columns[0].slider("Basi fisse", 1, 3, 2)
        required_variants = 6 - base_count
        variant_count = setting_columns[1].slider(
            "Varianti", required_variants, 10, max(6, required_variants)
        )
        if st.button("Genera basi e varianti", type="primary"):
            bases, variants, lines = generate_base_variant_system(
                scores, int(base_count), int(variant_count)
            )
            st.write("**Basi:** " + ", ".join(map(str, bases)))
            st.write("**Varianti:** " + ", ".join(map(str, variants)))
            st.metric("Combinazioni", len(lines))
            st.metric("Costo", euro(system_cost(len(lines), with_superstar)))
            system_dataframe = pd.DataFrame(
                lines, columns=[f"N{index}" for index in range(1, 7)]
            )
            if with_superstar:
                system_dataframe["SuperStar"] = superstar_ranking[0][0]
            st.dataframe(system_dataframe, use_container_width=True, hide_index=True)
            st.download_button(
                "Scarica sistema CSV",
                system_dataframe.to_csv(index=False).encode("utf-8-sig"),
                "sistema_basi_varianti.csv",
                "text/csv",
            )

    else:
        setting_columns = st.columns(2)
        reduced_pool = setting_columns[0].slider("Pool", 10, 15, 12)
        maximum_lines = setting_columns[1].slider("Sestine", 4, 20, 8)
        if st.button("Genera ridotto", type="primary"):
            pool, lines, coverage = generate_reduced_system(
                scores, int(reduced_pool), int(maximum_lines)
            )
            st.write("**Pool:** " + ", ".join(map(str, pool)))
            result_columns = st.columns(3)
            result_columns[0].metric("Combinazioni", len(lines))
            result_columns[1].metric(
                "Costo", euro(system_cost(len(lines), with_superstar))
            )
            result_columns[2].metric("Copertura coppie", f"{coverage:.1%}")
            system_dataframe = pd.DataFrame(
                lines, columns=[f"N{index}" for index in range(1, 7)]
            )
            if with_superstar:
                system_dataframe["SuperStar"] = superstar_ranking[0][0]
            st.dataframe(system_dataframe, use_container_width=True, hide_index=True)
            st.download_button(
                "Scarica sistema CSV",
                system_dataframe.to_csv(index=False).encode("utf-8-sig"),
                "sistema_ridotto.csv",
                "text/csv",
            )


def render_statistics_tab(
    active_dataframe: pd.DataFrame,
    metrics: dict[str, dict[int, float]],
    scores: dict[int, float],
    superstar_ranking: list[tuple[int, float, int, int]],
) -> None:
    ranking_tab, structure_tab, association_tab, stability_tab = st.tabs(
        ["Ranking numeri", "Struttura estrazioni", "Coppie e terzine", "Stabilità annuale"]
    )

    analytics = archive_analytics_cached(records_tuple(active_dataframe), 100)

    with ranking_tab:
        stats_dataframe = pd.DataFrame(
            {
                "Numero": range(1, 91),
                "Frequenza": [
                    int(metrics["frequency"][number]) for number in range(1, 91)
                ],
                "Ritardo": [
                    int(metrics["delay"][number]) for number in range(1, 91)
                ],
                "Recenza": [
                    round(metrics["recency"][number], 4) for number in range(1, 91)
                ],
                "Score": [round(scores[number], 4) for number in range(1, 91)],
            }
        ).sort_values(["Score", "Numero"], ascending=[False, True])
        st.dataframe(stats_dataframe, use_container_width=True, hide_index=True, height=520)

        st.subheader("Ranking SuperStar")
        superstar_dataframe = pd.DataFrame(
            [
                {
                    "Numero": number,
                    "Score": round(score, 4),
                    "Frequenza": frequency,
                    "Ritardo": delay,
                }
                for number, score, frequency, delay in superstar_ranking[:20]
            ]
        )
        st.dataframe(superstar_dataframe, use_container_width=True, hide_index=True)

    with structure_tab:
        st.caption(
            "Analisi descrittiva della finestra attiva. Gli scostamenti storici "
            "non costituiscono una previsione delle estrazioni future."
        )
        summary_dataframe = pd.DataFrame(analytics["structure_summary"])
        st.dataframe(summary_dataframe, use_container_width=True, hide_index=True)

        decade_dataframe = pd.DataFrame(analytics["decades"])
        st.subheader("Distribuzione per decine")
        st.bar_chart(decade_dataframe.set_index("Decina")["Presenze"])
        st.dataframe(decade_dataframe, use_container_width=True, hide_index=True)

        st.subheader("Ripetizioni rispetto all'estrazione precedente")
        overlap_dataframe = pd.DataFrame(analytics["overlaps"])
        st.dataframe(overlap_dataframe, use_container_width=True, hide_index=True)

        with st.expander("Dettaglio strutturale delle estrazioni"):
            structure_dataframe = pd.DataFrame(analytics["structure_rows"])
            structure_dataframe["Entropia decine"] = structure_dataframe[
                "Entropia decine"
            ].round(4)
            st.dataframe(
                structure_dataframe.sort_values(["Anno", "Concorso"], ascending=False),
                use_container_width=True,
                hide_index=True,
                height=520,
            )

    with association_tab:
        association_limit = st.slider("Associazioni da mostrare", 10, 100, 30, 10)
        st.caption(
            "Le coppie e le terzine sono ordinate per presenze nella finestra. "
            "L'atteso casuale si riferisce a una specifica associazione fissata in anticipo; "
            "la selezione delle più frequenti è retrospettiva."
        )
        pairs = pd.DataFrame(analytics["pairs"]).head(association_limit)
        triplets = pd.DataFrame(analytics["triplets"]).head(association_limit)
        pair_column, triplet_column = st.columns(2)
        with pair_column:
            st.subheader("Coppie più presenti")
            st.dataframe(pairs, use_container_width=True, hide_index=True, height=520)
        with triplet_column:
            st.subheader("Terzine più presenti")
            st.dataframe(triplets, use_container_width=True, hide_index=True, height=520)

    with stability_tab:
        stability_dataframe = pd.DataFrame(analytics["annual_stability"])
        display_mode = st.radio(
            "Ordinamento",
            ["Più stabili", "Più variabili", "Numero"],
            horizontal=True,
        )
        if display_mode == "Più stabili":
            stability_dataframe = stability_dataframe.sort_values(
                ["Stabilità", "Numero"], ascending=[False, True]
            )
        elif display_mode == "Più variabili":
            stability_dataframe = stability_dataframe.sort_values(
                ["CV", "Numero"], ascending=[False, True]
            )
        else:
            stability_dataframe = stability_dataframe.sort_values("Numero")
        st.caption(
            "Il tasso annuale è la quota di estrazioni dell'anno in cui il numero è comparso. "
            "CV basso indica maggiore uniformità storica, non maggiore probabilità futura."
        )
        st.dataframe(
            stability_dataframe,
            use_container_width=True,
            hide_index=True,
            height=600,
        )


def render_backtest_tab(archive: pd.DataFrame) -> None:
    st.subheader("Backtest walk-forward sull'archivio")
    st.write(
        "Ogni estrazione viene simulata usando soltanto le estrazioni precedenti "
        "contenute nella finestra mobile selezionata."
    )

    backtest_columns = st.columns(5)
    backtest_window = backtest_columns[0].selectbox("Finestra", [50, 100, 200], index=1)
    backtest_pool = backtest_columns[1].selectbox(
        "Pool algoritmo", [15, 16, 17, 18], index=0
    )
    test_choice = backtest_columns[2].selectbox(
        "Numero test", ["Ultimi 100", "Ultimi 300", "Tutti"], index=1
    )
    test_limit = {"Ultimi 100": 100, "Ultimi 300": 300, "Tutti": 0}[test_choice]
    minimum_decades_backtest = backtest_columns[3].selectbox(
        "Min decine", [3, 4], index=0
    )
    random_seed = backtest_columns[4].number_input(
        "Seed casuale", min_value=0, value=20260726, step=1
    )

    st.caption(
        "Filtri backtest: somma 190–350, massimo 4 numeri fino a 31. "
        "Il benchmark casuale è deterministico e riproducibile tramite il seed."
    )

    if st.button("Esegui backtest", type="primary"):
        with st.spinner("Calcolo storico in corso..."):
            st.session_state.backtest_result = run_walk_forward_backtest_cached(
                records_tuple(archive),
                int(backtest_window),
                int(test_limit),
                int(backtest_pool),
                190,
                350,
                4,
                int(minimum_decades_backtest),
                int(random_seed),
            )

    backtest = st.session_state.backtest_result
    if backtest:
        top_metrics = st.columns(3)
        top_metrics[0].metric("Test eseguiti", backtest["test_count"])
        top_metrics[1].metric("Seed benchmark", backtest["random_seed"])
        top_metrics[2].metric(
            "2+ casuali teorici attesi", f"{backtest['random_expected_2_plus']:.2f}"
        )

        summary_dataframe = pd.DataFrame(backtest["summary"])
        numeric_columns = [
            "Media punti", "Deviazione", "IC95% minimo", "IC95% massimo"
        ]
        summary_dataframe[numeric_columns] = summary_dataframe[numeric_columns].round(4)
        st.dataframe(summary_dataframe, use_container_width=True, hide_index=True)

        st.caption(
            "Riferimento teorico casuale: media 0,400 punti per sestina. "
            "L'intervallo di confidenza descrive l'incertezza della media osservata."
        )

        with st.expander("Stabilità annuale del backtest"):
            annual_dataframe = pd.DataFrame(backtest["annual_summary"])
            annual_dataframe["Media punti"] = annual_dataframe["Media punti"].round(4)
            st.dataframe(annual_dataframe, use_container_width=True, hide_index=True)

        detail_dataframe = pd.DataFrame(backtest["details"])
        st.dataframe(
            detail_dataframe.tail(300),
            use_container_width=True,
            hide_index=True,
            height=520,
        )
        st.download_button(
            "Scarica dettaglio backtest",
            detail_dataframe.to_csv(index=False).encode("utf-8-sig"),
            "backtest_superenalotto.csv",
            "text/csv",
        )


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
            extra_columns = st.columns(2)
            has_superstar = extra_columns[0].checkbox(
                "SuperStar giocato", value=False, key="manual_has_superstar"
            )
            superstar = extra_columns[1].number_input(
                "SuperStar", min_value=1, max_value=90, value=1, step=1,
                disabled=not has_superstar, key="manual_ticket_superstar",
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


def render_archive_tab(archive: pd.DataFrame) -> None:
    st.subheader("Archivio completo")
    year_options = ["Tutti"] + sorted(archive["anno"].unique().tolist(), reverse=True)
    selected_year = st.selectbox("Anno", year_options)

    display_archive = archive.copy()
    if selected_year != "Tutti":
        display_archive = display_archive[display_archive["anno"] == int(selected_year)]

    display_archive = display_archive.sort_values("data", ascending=False)
    display_archive["data"] = display_archive["data"].dt.strftime("%d/%m/%Y")
    display_archive["jolly"] = display_archive["jolly"].astype("Int64")
    st.dataframe(display_archive, use_container_width=True, hide_index=True, height=600)


def main() -> None:
    try:
        repository_archive, archive_source, database_error = load_primary_archive(
            str(DATA_FILE), fetch_draws
        )
    except (FileNotFoundError, ValueError, pd.errors.ParserError) as exc:
        st.error(str(exc))
        st.stop()

    initialize_state()
    archive = repository_archive
    window_size = render_sidebar(archive)
    active_dataframe = archive.sort_values("data", ascending=False).head(window_size)
    history = dataframe_to_history(active_dataframe)
    metrics = calculate_metrics(history)
    scores = metrics["score"]
    superstar_ranking = calculate_superstar_ranking(history)
    score_items = tuple(sorted(scores.items()))
    snapshot = archive_snapshot(archive)

    st.title("🎰 SuperEnalotto — Analizzatore statistico")
    st.caption(
        "Archivio persistente, analisi descrittiva e backtest walk-forward. "
        "Il sistema misura il passato: non rende prevedibile un'estrazione casuale."
    )
    st.caption(f"Fonte dati attiva: **{archive_source}**")
    if database_error and archive_source != "Supabase":
        st.warning(
            "Supabase non era disponibile: l'app sta usando il CSV di sicurezza. "
            f"Dettaglio: {database_error}"
        )

    metric_columns = st.columns(4)
    metric_columns[0].metric("Archivio totale", f"{len(archive):,}".replace(",", "."))
    metric_columns[1].metric("Finestra attiva", len(history))
    metric_columns[2].metric(
        "Anni presenti", f"{archive['anno'].min()}–{archive['anno'].max()}"
    )
    metric_columns[3].metric("Jolly mancanti", snapshot["missing_jolly"])
    st.caption(
        f"Snapshot archivio: `{snapshot['sha256'][:16]}` · "
        f"{snapshot['date_min']:%d/%m/%Y}–{snapshot['date_max']:%d/%m/%Y}"
    )

    database_available = archive_source == "Supabase" and database_error is None
    single_tab, systems_tab, monitored_tab, stats_tab, backtest_tab, archive_tab = st.tabs(
        [
            "Sestina singola",
            "Sistemi",
            "Schedine monitorate",
            "Statistiche",
            "Backtest",
            "Archivio",
        ]
    )
    with single_tab:
        render_single_tab(
            scores, score_items, superstar_ranking, archive, database_available
        )
    with systems_tab:
        render_systems_tab(scores, superstar_ranking)
    with monitored_tab:
        render_monitored_tickets_tab(archive, database_available)
    with stats_tab:
        render_statistics_tab(active_dataframe, metrics, scores, superstar_ranking)
    with backtest_tab:
        render_backtest_tab(archive)
    with archive_tab:
        render_archive_tab(archive)


if __name__ == "__main__":
    main()
