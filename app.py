from __future__ import annotations

import heapq
import math
import random
from datetime import date
from itertools import combinations
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st


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
def validate_number(value: Any, field_name: str, allow_empty: bool = False) -> int | None:
    if allow_empty and (value is None or pd.isna(value) or str(value).strip() == ""):
        return None

    if isinstance(value, bool):
        raise ValueError(f"{field_name} non valido.")

    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} deve essere un numero intero.") from exc

    if not NUMBER_MIN <= number <= NUMBER_MAX:
        raise ValueError(f"{field_name} deve essere compreso tra 1 e 90.")
    return number


def validate_archive_dataframe(raw_dataframe: pd.DataFrame) -> pd.DataFrame:
    dataframe = raw_dataframe.copy()
    dataframe.columns = [str(column).strip().lstrip("\ufeff").lower() for column in dataframe.columns]

    missing_columns = [column for column in REQUIRED_COLUMNS if column not in dataframe.columns]
    if missing_columns:
        raise ValueError("Colonne mancanti: " + ", ".join(missing_columns))

    dataframe = dataframe[REQUIRED_COLUMNS].copy()
    dataframe["data"] = pd.to_datetime(dataframe["data"], errors="raise")
    dataframe["anno"] = pd.to_numeric(dataframe["anno"], errors="raise").astype(int)
    dataframe["concorso"] = pd.to_numeric(dataframe["concorso"], errors="raise").astype(int)

    numeric_columns = [f"n{index}" for index in range(1, 7)] + ["superstar"]
    for column in numeric_columns:
        dataframe[column] = pd.to_numeric(dataframe[column], errors="raise").astype(int)

    dataframe["jolly"] = pd.to_numeric(dataframe["jolly"], errors="coerce").astype("Int64")

    if dataframe.empty:
        raise ValueError("L'archivio è vuoto.")

    duplicate_contests = dataframe.duplicated(subset=["anno", "concorso"], keep=False)
    if duplicate_contests.any():
        duplicated = dataframe.loc[duplicate_contests, ["anno", "concorso"]].head(5)
        details = ", ".join(
            f"{row.anno}/Conc.{row.concorso}" for row in duplicated.itertuples()
        )
        raise ValueError(f"Concorsi duplicati: {details}.")

    duplicate_dates = dataframe.duplicated(subset=["data"], keep=False)
    if duplicate_dates.any():
        dates = dataframe.loc[duplicate_dates, "data"].dt.strftime("%d/%m/%Y").head(5)
        raise ValueError("Date duplicate: " + ", ".join(dates))

    for row_number, row in enumerate(dataframe.itertuples(index=False), start=2):
        if row.data.year != row.anno:
            raise ValueError(
                f"Anno incoerente alla riga {row_number}: data {row.data:%d/%m/%Y}, "
                f"anno indicato {row.anno}."
            )

        numbers = [getattr(row, f"n{index}") for index in range(1, 7)]
        for index, number in enumerate(numbers, start=1):
            validate_number(number, f"N{index} alla riga {row_number}")

        if len(set(numbers)) != 6:
            raise ValueError(f"Numeri duplicati nella sestina alla riga {row_number}.")

        validate_number(row.superstar, f"SuperStar alla riga {row_number}")
        validate_number(row.jolly, f"Jolly alla riga {row_number}", allow_empty=True)

    for year, group in dataframe.groupby("anno"):
        contests = sorted(group["concorso"].tolist())
        expected = list(range(1, max(contests) + 1))
        if contests != expected:
            missing = sorted(set(expected) - set(contests))
            preview = ", ".join(map(str, missing[:10]))
            raise ValueError(
                f"Nel {year} mancano concorsi nella sequenza: {preview}"
                + ("..." if len(missing) > 10 else "")
            )

    return dataframe.sort_values(["data", "anno", "concorso"]).reset_index(drop=True)


def read_csv_flexible(file_or_path: Any) -> pd.DataFrame:
    try:
        dataframe = pd.read_csv(file_or_path, sep=None, engine="python")
    except UnicodeDecodeError:
        if hasattr(file_or_path, "seek"):
            file_or_path.seek(0)
        dataframe = pd.read_csv(file_or_path, sep=None, engine="python", encoding="latin-1")
    return validate_archive_dataframe(dataframe)


@st.cache_data(show_spinner=False)
def load_repository_archive(path_text: str) -> pd.DataFrame:
    path = Path(path_text)
    if not path.exists():
        raise FileNotFoundError(
            "File estrazioni.csv non trovato. Caricalo nella stessa cartella di app.py."
        )
    return read_csv_flexible(path)


def archive_to_csv_bytes(dataframe: pd.DataFrame) -> bytes:
    output = dataframe.copy()
    output["data"] = pd.to_datetime(output["data"]).dt.strftime("%Y-%m-%d")
    return output.to_csv(index=False).encode("utf-8-sig")


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


# -----------------------------------------------------------------------------
# METRICHE
# -----------------------------------------------------------------------------
def min_max_scale(values: dict[int, float]) -> dict[int, float]:
    minimum = min(values.values())
    maximum = max(values.values())
    if math.isclose(minimum, maximum):
        return {key: 0.5 for key in values}
    return {
        key: (value - minimum) / (maximum - minimum)
        for key, value in values.items()
    }


def calculate_metrics(history: list[dict[str, Any]]) -> dict[str, dict[int, float]]:
    if not history:
        raise ValueError("Storico vuoto.")

    draw_count = len(history)
    frequency = {number: 0.0 for number in range(1, 91)}
    delay = {number: float(draw_count) for number in range(1, 91)}
    recency = {number: 0.0 for number in range(1, 91)}

    for position, draw in enumerate(history, start=1):
        recency_weight = 1.0 / math.sqrt(position)
        for number in draw["numbers"]:
            frequency[number] += 1.0
            if delay[number] == float(draw_count):
                delay[number] = float(position - 1)
            recency[number] += recency_weight

    frequency_norm = min_max_scale(frequency)
    delay_norm = min_max_scale(delay)
    recency_norm = min_max_scale(recency)

    score = {
        number: (
            WEIGHT_FREQUENCY * frequency_norm[number]
            + WEIGHT_DELAY * delay_norm[number]
            + WEIGHT_RECENCY * recency_norm[number]
        )
        for number in range(1, 91)
    }

    return {
        "frequency": frequency,
        "delay": delay,
        "recency": recency,
        "score": score,
    }


def calculate_superstar_ranking(
    history: list[dict[str, Any]],
) -> list[tuple[int, float, int, int]]:
    draw_count = len(history)
    frequency = {number: 0.0 for number in range(1, 91)}
    delay = {number: float(draw_count) for number in range(1, 91)}
    recency = {number: 0.0 for number in range(1, 91)}

    for position, draw in enumerate(history, start=1):
        number = draw["superstar"]
        frequency[number] += 1.0
        if delay[number] == float(draw_count):
            delay[number] = float(position - 1)
        recency[number] += 1.0 / math.sqrt(position)

    frequency_norm = min_max_scale(frequency)
    delay_norm = min_max_scale(delay)
    recency_norm = min_max_scale(recency)

    ranking = []
    for number in range(1, 91):
        score = (
            0.40 * frequency_norm[number]
            + 0.25 * delay_norm[number]
            + 0.35 * recency_norm[number]
        )
        ranking.append((number, score, int(frequency[number]), int(delay[number])))

    return sorted(ranking, key=lambda item: (item[1], item[2], item[3]), reverse=True)


# -----------------------------------------------------------------------------
# COMBINAZIONI E SISTEMI
# -----------------------------------------------------------------------------
def combination_features(combo: tuple[int, ...]) -> dict[str, int]:
    even = sum(number % 2 == 0 for number in combo)
    low = sum(number <= 31 for number in combo)
    decades = len({(number - 1) // 10 for number in combo})
    consecutive_pairs = sum(b - a == 1 for a, b in zip(combo, combo[1:]))
    return {
        "sum": sum(combo),
        "even": even,
        "low": low,
        "decades": decades,
        "consecutive_pairs": consecutive_pairs,
        "span": combo[-1] - combo[0],
    }


def passes_structural_filters(
    combo: tuple[int, ...],
    minimum_sum: int,
    maximum_sum: int,
    maximum_low_numbers: int,
    minimum_decades: int,
) -> bool:
    features = combination_features(combo)
    return (
        minimum_sum <= features["sum"] <= maximum_sum
        and features["even"] in (2, 3, 4)
        and features["low"] <= maximum_low_numbers
        and features["decades"] >= minimum_decades
    )


def combination_quality(combo: tuple[int, ...], scores: dict[int, float]) -> float:
    features = combination_features(combo)
    base_score = sum(scores[number] for number in combo)
    parity_bonus = 0.06 if features["even"] == 3 else 0.02
    decades_bonus = features["decades"] * 0.015
    span_bonus = (features["span"] / 89.0) * 0.04
    consecutive_penalty = features["consecutive_pairs"] * 0.025
    return base_score + parity_bonus + decades_bonus + span_bonus - consecutive_penalty


def rank_candidate_sestine(
    scores: dict[int, float],
    top_pool_size: int,
    limit: int,
    minimum_sum: int,
    maximum_sum: int,
    maximum_low_numbers: int,
    minimum_decades: int,
) -> list[tuple[float, tuple[int, ...]]]:
    ranked_numbers = sorted(scores, key=scores.get, reverse=True)
    pool = ranked_numbers[:top_pool_size]
    heap: list[tuple[float, tuple[int, ...]]] = []

    for raw_combo in combinations(pool, 6):
        combo = tuple(sorted(raw_combo))
        if not passes_structural_filters(
            combo,
            minimum_sum,
            maximum_sum,
            maximum_low_numbers,
            minimum_decades,
        ):
            continue

        quality = combination_quality(combo, scores)
        item = (quality, combo)
        if len(heap) < limit:
            heapq.heappush(heap, item)
        elif item > heap[0]:
            heapq.heapreplace(heap, item)

    return sorted(heap, key=lambda item: (item[0], item[1]), reverse=True)


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


def system_cost(number_of_lines: int, with_superstar: bool) -> float:
    return number_of_lines * (
        COST_BASE + (COST_SUPERSTAR if with_superstar else 0.0)
    )


def euro(value: float) -> str:
    formatted = f"{value:,.2f}"
    return formatted.replace(",", "§").replace(".", ",").replace("§", ".") + " €"


def generate_integral_system(
    scores: dict[int, float], pool_size: int
) -> tuple[list[int], list[tuple[int, ...]]]:
    ranked_numbers = sorted(scores, key=scores.get, reverse=True)
    pool = sorted(ranked_numbers[:pool_size])
    return pool, list(combinations(pool, 6))


def generate_base_variant_system(
    scores: dict[int, float],
    base_count: int,
    variant_count: int,
) -> tuple[list[int], list[int], list[tuple[int, ...]]]:
    required_variants = 6 - base_count
    if variant_count < required_variants:
        raise ValueError(
            f"Con {base_count} basi servono almeno {required_variants} varianti."
        )

    ranked_numbers = sorted(scores, key=scores.get, reverse=True)
    bases = sorted(ranked_numbers[:base_count])
    variants = ranked_numbers[base_count : base_count + variant_count]
    lines = [
        tuple(sorted((*bases, *variant_combo)))
        for variant_combo in combinations(variants, required_variants)
    ]
    lines.sort(key=lambda combo: combination_quality(combo, scores), reverse=True)
    return bases, sorted(variants), lines


def generate_reduced_system(
    scores: dict[int, float],
    pool_size: int,
    maximum_lines: int,
) -> tuple[list[int], list[tuple[int, ...]], float]:
    ranked_numbers = sorted(scores, key=scores.get, reverse=True)
    pool = ranked_numbers[:pool_size]
    candidates: list[tuple[float, tuple[int, ...]]] = []

    for raw_combo in combinations(pool, 6):
        combo = tuple(sorted(raw_combo))
        if passes_structural_filters(combo, 200, 340, 4, 4):
            candidates.append((combination_quality(combo, scores), combo))

    if not candidates:
        candidates = [
            (combination_quality(tuple(sorted(combo)), scores), tuple(sorted(combo)))
            for combo in combinations(pool, 6)
        ]

    candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
    max_quality = candidates[0][0] or 1.0

    selected: list[tuple[int, ...]] = []
    covered_pairs: set[tuple[int, int]] = set()
    remaining = candidates.copy()

    while remaining and len(selected) < maximum_lines:
        best_index = 0
        best_objective = -math.inf

        for index, (quality, combo) in enumerate(remaining):
            combo_pairs = set(combinations(combo, 2))
            new_pair_ratio = len(combo_pairs - covered_pairs) / 15.0
            max_overlap = max(
                (len(set(combo) & set(chosen)) for chosen in selected),
                default=0,
            )
            diversity = 1.0 - max_overlap / 6.0
            normalized_quality = quality / max_quality
            objective = (
                0.55 * normalized_quality
                + 0.30 * new_pair_ratio
                + 0.15 * diversity
            )
            if objective > best_objective:
                best_objective = objective
                best_index = index

        _, chosen = remaining.pop(best_index)
        selected.append(chosen)
        covered_pairs.update(combinations(chosen, 2))

    possible_pairs = math.comb(pool_size, 2)
    coverage = len(covered_pairs) / possible_pairs if possible_pairs else 0.0
    return sorted(pool), selected, coverage


# -----------------------------------------------------------------------------
# BACKTEST WALK-FORWARD
# -----------------------------------------------------------------------------
def random_hit_probabilities() -> dict[int, float]:
    denominator = math.comb(90, 6)
    return {
        hits: math.comb(6, hits) * math.comb(84, 6 - hits) / denominator
        for hits in range(7)
    }


def select_baseline_numbers(
    metrics: dict[str, dict[int, float]],
    strategy: str,
) -> tuple[int, ...]:
    if strategy == "frequenti":
        ranking = sorted(
            range(1, 91),
            key=lambda number: (
                metrics["frequency"][number],
                metrics["recency"][number],
                -number,
            ),
            reverse=True,
        )
    elif strategy == "ritardatari":
        ranking = sorted(
            range(1, 91),
            key=lambda number: (
                metrics["delay"][number],
                -metrics["frequency"][number],
                -metrics["recency"][number],
                -number,
            ),
            reverse=True,
        )
    else:
        raise ValueError("Strategia di confronto non riconosciuta.")
    return tuple(sorted(ranking[:6]))


def records_tuple(dataframe: pd.DataFrame) -> tuple[tuple[Any, ...], ...]:
    ordered = dataframe.sort_values("data")
    rows = []
    for row in ordered.itertuples(index=False):
        rows.append(
            (
                pd.Timestamp(row.data).strftime("%Y-%m-%d"),
                int(row.anno),
                int(row.concorso),
                int(row.n1),
                int(row.n2),
                int(row.n3),
                int(row.n4),
                int(row.n5),
                int(row.n6),
                0 if pd.isna(row.jolly) else int(row.jolly),
                int(row.superstar),
            )
        )
    return tuple(rows)


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
    chronological = []
    for row in raw_records:
        chronological.append(
            {
                "date": pd.Timestamp(row[0]),
                "year": int(row[1]),
                "contest": int(row[2]),
                "numbers": [int(value) for value in row[3:9]],
                "jolly": None if int(row[9]) == 0 else int(row[9]),
                "superstar": int(row[10]),
            }
        )

    first_target = window_size
    if test_limit > 0:
        first_target = max(first_target, len(chronological) - test_limit)

    detail_rows = []
    strategy_hits = {
        "Algoritmo": [],
        "Solo frequenti": [],
        "Solo ritardatari": [],
    }

    for target_index in range(first_target, len(chronological)):
        training_chronological = chronological[
            target_index - window_size : target_index
        ]
        history = list(reversed(training_chronological))
        target = chronological[target_index]
        metrics = calculate_metrics(history)

        candidates = rank_candidate_sestine(
            metrics["score"],
            pool_size,
            1,
            minimum_sum,
            maximum_sum,
            maximum_low_numbers,
            minimum_decades,
        )
        if candidates:
            algorithm_prediction = candidates[0][1]
        else:
            ranking = sorted(metrics["score"], key=metrics["score"].get, reverse=True)
            algorithm_prediction = tuple(sorted(ranking[:6]))

        frequent_prediction = select_baseline_numbers(metrics, "frequenti")
        delay_prediction = select_baseline_numbers(metrics, "ritardatari")

        predictions = {
            "Algoritmo": algorithm_prediction,
            "Solo frequenti": frequent_prediction,
            "Solo ritardatari": delay_prediction,
        }

        hit_values = {}
        target_set = set(target["numbers"])
        for strategy, prediction in predictions.items():
            hits = len(set(prediction) & target_set)
            strategy_hits[strategy].append(hits)
            hit_values[strategy] = hits

        detail_rows.append(
            {
                "Data": target["date"].strftime("%d/%m/%Y"),
                "Concorso": f"{target['year']}/{target['contest']}",
                "Estratti": ", ".join(map(str, target["numbers"])),
                "Pronostico algoritmo": ", ".join(map(str, algorithm_prediction)),
                "Punti algoritmo": hit_values["Algoritmo"],
                "Punti frequenti": hit_values["Solo frequenti"],
                "Punti ritardatari": hit_values["Solo ritardatari"],
            }
        )

    probabilities = random_hit_probabilities()
    test_count = len(detail_rows)
    summary_rows = []

    for strategy, hits_list in strategy_hits.items():
        distribution = {hits: hits_list.count(hits) for hits in range(7)}
        summary_rows.append(
            {
                "Strategia": strategy,
                "Test": len(hits_list),
                "Media punti": (
                    sum(hits_list) / len(hits_list) if hits_list else 0.0
                ),
                "2+": sum(hits >= 2 for hits in hits_list),
                "3+": sum(hits >= 3 for hits in hits_list),
                **{f"Punti {hits}": distribution[hits] for hits in range(7)},
            }
        )

    random_2_plus_probability = sum(
        probability for hits, probability in probabilities.items() if hits >= 2
    )

    return {
        "details": detail_rows,
        "summary": summary_rows,
        "test_count": test_count,
        "random_average": 0.4,
        "random_expected_2_plus": test_count * random_2_plus_probability,
        "random_probabilities": probabilities,
    }


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
        repository_archive = load_repository_archive(str(DATA_FILE))
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
