from __future__ import annotations

import random
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from core.backtest import records_tuple, run_walk_forward_backtest
from core.combinations import (
    combination_features, combination_quality, euro, generate_base_variant_system,
    generate_integral_system, generate_reduced_system, rank_candidate_sestine, system_cost,
)
from core.metrics import calculate_metrics, calculate_superstar_ranking

from database import fetch_draws
from services.archive_service import (
    archive_to_csv_bytes,
    load_primary_archive,
    load_repository_archive,
    normalize_archive_dataframe as validate_archive_dataframe,
    read_csv_flexible,
    validate_number,
)


APP_TITLE = "SuperEnalotto — Analisi statistica e sistemi"
DATA_FILE = Path(__file__).with_name("estrazioni.csv")

NUMBER_MIN = 1
NUMBER_MAX = 90
NUMBERS_PER_DRAW = 6

COST_BASE = 1.00
COST_SUPERSTAR = 0.50

WEIGHT_FREQUENCY = 0.35
WEIGHT_DELAY = 0.25
WEIGHT_RECENCY = 0.40

REQUIRED_COLUMNS = [
    "data",
    "anno",
    "concorso",
    "n1",
    "n2",
    "n3",
    "n4",
    "n5",
    "n6",
    "jolly",
    "superstar",
]

st.set_page_config(page_title=APP_TITLE, page_icon="🎰", layout="wide")


# -----------------------------------------------------------------------------
# ARCHIVIO E VALIDAZIONE
# -----------------------------------------------------------------------------
def dataframe_to_history(dataframe: pd.DataFrame) -> list[dict[str, Any]]:
    newest_first = dataframe.sort_values("data", ascending=False)
    history: list[dict[str, Any]] = []

    for row in newest_first.itertuples(index=False):
        numbers = [int(getattr(row, f"n{index}")) for index in range(1, 7)]
        jolly = None if pd.isna(row.jolly) else int(row.jolly)
        history.append(
            {
                "date": pd.Timestamp(row.data),
                "year": int(row.anno),
                "contest": int(row.concorso),
                "label": f"{int(row.anno)} — Conc. {int(row.concorso)} ({pd.Timestamp(row.data):%d/%m})",
                "numbers": numbers,
                "jolly": jolly,
                "superstar": int(row.superstar),
            }
        )
    return history


def add_extraction(
    dataframe: pd.DataFrame,
    draw_date: date,
    contest: int,
    numbers: list[int],
    jolly: int | None,
    superstar: int,
) -> pd.DataFrame:
    year = draw_date.year
    if ((dataframe["anno"] == year) & (dataframe["concorso"] == contest)).any():
        raise ValueError(f"Il concorso {contest} del {year} è già presente.")

    timestamp = pd.Timestamp(draw_date)
    if (dataframe["data"] == timestamp).any():
        raise ValueError(f"Esiste già un'estrazione in data {draw_date:%d/%m/%Y}.")

    validated_numbers = [int(validate_number(number, f"N{index}")) for index, number in enumerate(numbers, start=1)]
    if len(set(validated_numbers)) != 6:
        raise ValueError("I sei numeri devono essere tutti differenti.")

    validated_jolly = validate_number(jolly, "Jolly", allow_empty=True)
    validated_superstar = int(validate_number(superstar, "SuperStar"))

    expected_next = (
        int(dataframe.loc[dataframe["anno"] == year, "concorso"].max()) + 1
        if (dataframe["anno"] == year).any()
        else 1
    )
    if contest != expected_next:
        raise ValueError(
            f"Per il {year} il prossimo concorso atteso è {expected_next}, non {contest}."
        )

    new_row = {
        "data": timestamp,
        "anno": year,
        "concorso": int(contest),
        **{f"n{index}": number for index, number in enumerate(sorted(validated_numbers), start=1)},
        "jolly": validated_jolly,
        "superstar": validated_superstar,
    }

    updated = pd.concat([dataframe, pd.DataFrame([new_row])], ignore_index=True)
    return validate_archive_dataframe(updated)


@st.cache_data(show_spinner=False)
def rank_candidate_sestine_cached(
    score_items: tuple[tuple[int, float], ...], top_pool_size: int, limit: int,
    minimum_sum: int, maximum_sum: int, maximum_low_numbers: int, minimum_decades: int,
) -> list[tuple[float, tuple[int, ...]]]:
    return rank_candidate_sestine(dict(score_items), top_pool_size, limit, minimum_sum, maximum_sum, maximum_low_numbers, minimum_decades)


_run_walk_forward_backtest = run_walk_forward_backtest


@st.cache_data(show_spinner=False)
def run_walk_forward_backtest(
    raw_records: tuple[tuple[Any, ...], ...],
    window_size: int,
    test_limit: int,
    pool_size: int,
    minimum_sum: int,
    maximum_sum: int,
    maximum_low_numbers: int,
    minimum_decades: int,
) -> dict[str, Any]:
    return _run_walk_forward_backtest(
        raw_records, window_size, test_limit, pool_size, minimum_sum, maximum_sum,
        maximum_low_numbers, minimum_decades,
    )


# -----------------------------------------------------------------------------
# INTERFACCIA
# -----------------------------------------------------------------------------
def initialize_state(repository_archive: pd.DataFrame) -> None:
    if "archive" not in st.session_state:
        st.session_state.archive = repository_archive.copy()
    if "single_result" not in st.session_state:
        st.session_state.single_result = None
    if "backtest_result" not in st.session_state:
        st.session_state.backtest_result = None


def render_sidebar(repository_archive: pd.DataFrame) -> int:
    st.sidebar.header("Archivio estrazioni")

    archive = st.session_state.archive
    st.sidebar.metric("Estrazioni caricate", f"{len(archive):,}".replace(",", "."))
    st.sidebar.caption(
        f"Dal {archive['data'].min():%d/%m/%Y} al {archive['data'].max():%d/%m/%Y}"
    )

    window_options = [50, 100, 200, 500, len(archive)]
    window_options = sorted(set(option for option in window_options if option <= len(archive)))
    window_size = st.sidebar.selectbox(
        "Finestra statistica attiva",
        window_options,
        index=window_options.index(100) if 100 in window_options else 0,
        format_func=lambda value: (
            f"Tutto l'archivio ({value})" if value == len(archive) else f"Ultime {value}"
        ),
    )

    with st.sidebar.expander("Aggiungi nuova estrazione"):
        latest_date = archive["data"].max().date()
        latest_year = latest_date.year
        latest_contest = int(
            archive.loc[archive["anno"] == latest_year, "concorso"].max()
        )

        with st.form("add_extraction_form"):
            draw_date = st.date_input("Data", value=latest_date)
            default_contest = latest_contest + 1 if draw_date.year == latest_year else 1
            contest = st.number_input(
                "Numero concorso",
                min_value=1,
                value=int(default_contest),
                step=1,
            )

            columns = st.columns(3)
            numbers = [
                columns[(index - 1) % 3].number_input(
                    f"N{index}",
                    min_value=1,
                    max_value=90,
                    value=index * 10,
                    step=1,
                    key=f"new_n{index}",
                )
                for index in range(1, 7)
            ]

            jolly_available = st.checkbox("Jolly disponibile", value=True)
            jolly = st.number_input(
                "Jolly",
                min_value=1,
                max_value=90,
                value=15,
                step=1,
                disabled=not jolly_available,
            )
            superstar = st.number_input(
                "SuperStar",
                min_value=1,
                max_value=90,
                value=30,
                step=1,
            )

            submitted = st.form_submit_button(
                "Aggiungi alla sessione",
                type="primary",
                use_container_width=True,
            )

        if submitted:
            try:
                st.session_state.archive = add_extraction(
                    archive,
                    draw_date,
                    int(contest),
                    [int(number) for number in numbers],
                    int(jolly) if jolly_available else None,
                    int(superstar),
                )
                st.session_state.single_result = None
                st.session_state.backtest_result = None
                st.success("Estrazione aggiunta. Scarica il CSV aggiornato.")
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))

    st.sidebar.download_button(
        "Scarica archivio CSV aggiornato",
        data=archive_to_csv_bytes(st.session_state.archive),
        file_name="estrazioni.csv",
        mime="text/csv",
        use_container_width=True,
    )

    with st.sidebar.expander("Importa o ripristina archivio"):
        uploaded = st.file_uploader("Carica estrazioni.csv", type=["csv"])
        if uploaded is not None and st.button("Importa CSV", use_container_width=True):
            try:
                st.session_state.archive = read_csv_flexible(uploaded)
                st.session_state.single_result = None
                st.session_state.backtest_result = None
                st.success("Archivio importato.")
                st.rerun()
            except (ValueError, UnicodeDecodeError, pd.errors.ParserError) as exc:
                st.error(str(exc))

        if st.button("Ripristina il CSV del repository", use_container_width=True):
            st.session_state.archive = repository_archive.copy()
            st.session_state.single_result = None
            st.session_state.backtest_result = None
            st.success("Archivio ripristinato.")
            st.rerun()

    st.sidebar.warning(
        "Su Streamlit Community Cloud le modifiche della sessione non riscrivono GitHub. "
        "Dopo un inserimento scarica estrazioni.csv e sostituiscilo nel repository."
    )
    return int(window_size)


def main() -> None:
    try:
        repository_archive, archive_source, database_error = load_primary_archive(str(DATA_FILE), fetch_draws)
    except (FileNotFoundError, ValueError, pd.errors.ParserError) as exc:
        st.error(str(exc))
        st.stop()

    initialize_state(repository_archive)
    window_size = render_sidebar(repository_archive)

    archive = st.session_state.archive
    active_dataframe = archive.sort_values("data", ascending=False).head(window_size)
    history = dataframe_to_history(active_dataframe)

    metrics = calculate_metrics(history)
    scores = metrics["score"]
    superstar_ranking = calculate_superstar_ranking(history)
    score_items = tuple(sorted(scores.items()))

    st.title("🎰 SuperEnalotto — Analizzatore statistico")
    st.caption(
        "Archivio storico completo, finestra mobile e backtest walk-forward. "
        "È un selettore statistico: non rende prevedibile un'estrazione casuale."
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
        "Anni presenti",
        f"{archive['anno'].min()}–{archive['anno'].max()}",
    )
    metric_columns[3].metric("Jolly mancanti", int(archive["jolly"].isna().sum()))

    single_tab, systems_tab, stats_tab, backtest_tab, archive_tab = st.tabs(
        [
            "Sestina singola",
            "Sistemi",
            "Statistiche",
            "Backtest",
            "Archivio",
        ]
    )

    with single_tab:
        st.subheader("Sestina elaborata sulla finestra attiva")

        filter_columns = st.columns(5)
        pool_size = filter_columns[0].slider("Pool top", 15, 25, 25)
        minimum_sum = filter_columns[1].number_input("Somma minima", 100, 400, 200, 5)
        maximum_sum = filter_columns[2].number_input("Somma massima", 120, 500, 340, 5)
        maximum_low = filter_columns[3].number_input("Max numeri ≤31", 0, 6, 4, 1)
        minimum_decades = filter_columns[4].number_input("Min decine", 2, 6, 4, 1)

        button_columns = st.columns(2)
        generate_main = button_columns[0].button(
            "Calcola principale",
            type="primary",
            use_container_width=True,
        )
        generate_alternative = button_columns[1].button(
            "Alternativa tra le migliori",
            use_container_width=True,
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

    with systems_tab:
        st.subheader("Generatore sistemi")
        with_superstar = st.checkbox("Costo con SuperStar", value=True)
        system_type = st.selectbox(
            "Tipologia",
            [
                "Integrale",
                "Basi e varianti",
                "Ridotto diversificato",
            ],
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
                "Varianti",
                required_variants,
                10,
                max(6, required_variants),
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

    with stats_tab:
        st.subheader("Ranking dei numeri")
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

    with backtest_tab:
        st.subheader("Backtest walk-forward sull'archivio")
        st.write(
            "Ogni estrazione viene simulata usando soltanto le estrazioni precedenti "
            "contenute nella finestra mobile selezionata."
        )

        backtest_columns = st.columns(4)
        backtest_window = backtest_columns[0].selectbox(
            "Finestra",
            [50, 100, 200],
            index=1,
        )
        backtest_pool = backtest_columns[1].selectbox(
            "Pool algoritmo",
            [15, 16, 17, 18],
            index=0,
        )
        test_choice = backtest_columns[2].selectbox(
            "Numero test",
            ["Ultimi 100", "Ultimi 300", "Tutti"],
            index=1,
        )
        test_limit = {
            "Ultimi 100": 100,
            "Ultimi 300": 300,
            "Tutti": 0,
        }[test_choice]
        minimum_decades_backtest = backtest_columns[3].selectbox(
            "Min decine",
            [3, 4],
            index=0,
        )

        st.caption(
            "Filtri backtest: somma 190–350, massimo 4 numeri fino a 31, "
            f"almeno {minimum_decades_backtest} decine."
        )

        if st.button("Esegui backtest", type="primary"):
            with st.spinner("Calcolo storico in corso..."):
                st.session_state.backtest_result = run_walk_forward_backtest(
                    records_tuple(archive),
                    int(backtest_window),
                    int(test_limit),
                    int(backtest_pool),
                    190,
                    350,
                    4,
                    int(minimum_decades_backtest),
                )

        backtest = st.session_state.backtest_result
        if backtest:
            st.metric("Test eseguiti", backtest["test_count"])
            summary_dataframe = pd.DataFrame(backtest["summary"])
            summary_dataframe["Media punti"] = summary_dataframe["Media punti"].round(4)
            st.dataframe(summary_dataframe, use_container_width=True, hide_index=True)

            st.caption(
                f"Riferimento casuale teorico: media 0,400 punti; su "
                f"{backtest['test_count']} test sono attesi circa "
                f"{backtest['random_expected_2_plus']:.2f} risultati da 2 o più."
            )

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

    with archive_tab:
        st.subheader("Archivio completo")
        year_options = ["Tutti"] + sorted(
            archive["anno"].unique().tolist(), reverse=True
        )
        selected_year = st.selectbox("Anno", year_options)

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


if __name__ == "__main__":
    main()
