from __future__ import annotations

import copy
import heapq
import json
import math
import random
from itertools import combinations
from typing import Any

import pandas as pd
import streamlit as st


# -----------------------------------------------------------------------------
# CONFIGURAZIONE
# -----------------------------------------------------------------------------
APP_TITLE = "SuperEnalotto — Analisi statistica e sistemi"
MAX_HISTORY = 50
NUMBER_MIN = 1
NUMBER_MAX = 90
NUMBERS_PER_DRAW = 6
COST_BASE = 1.00
COST_SUPERSTAR = 0.50

# Pesi descrittivi. Non trasformano lo storico in una previsione affidabile.
WEIGHT_FREQUENCY = 0.35
WEIGHT_DELAY = 0.25
WEIGHT_RECENCY = 0.40

st.set_page_config(page_title=APP_TITLE, page_icon="🎰", layout="wide")


# -----------------------------------------------------------------------------
# DATASET INIZIALE: le 50 estrazioni fornite dall'utente
# Il file originale non conteneva i numeri Jolly storici.
# -----------------------------------------------------------------------------
REAL_50_EXTRACTIONS = [{'concorso': 'Conc. 118 (24/07)', 'numeri': [20, 40, 53, 61, 74, 79], 'superstar': 30},
 {'concorso': 'Conc. 117 (23/07)', 'numeri': [2, 12, 22, 34, 70, 74], 'superstar': 8},
 {'concorso': 'Conc. 116 (21/07)', 'numeri': [13, 14, 15, 29, 38, 63], 'superstar': 49},
 {'concorso': 'Conc. 115 (18/07)', 'numeri': [1, 28, 52, 62, 79, 86], 'superstar': 31},
 {'concorso': 'Conc. 114 (17/07)', 'numeri': [7, 34, 45, 64, 65, 76], 'superstar': 90},
 {'concorso': 'Conc. 113 (16/07)', 'numeri': [1, 15, 21, 46, 52, 67], 'superstar': 76},
 {'concorso': 'Conc. 112 (14/07)', 'numeri': [8, 44, 49, 80, 85, 88], 'superstar': 64},
 {'concorso': 'Conc. 111 (11/07)', 'numeri': [6, 7, 10, 47, 49, 61], 'superstar': 62},
 {'concorso': 'Conc. 110 (10/07)', 'numeri': [2, 3, 12, 28, 63, 82], 'superstar': 79},
 {'concorso': 'Conc. 109 (09/07)', 'numeri': [9, 17, 20, 31, 40, 79], 'superstar': 47},
 {'concorso': 'Conc. 108 (07/07)', 'numeri': [3, 16, 30, 53, 55, 79], 'superstar': 66},
 {'concorso': 'Conc. 107 (04/07)', 'numeri': [2, 37, 55, 62, 72, 76], 'superstar': 75},
 {'concorso': 'Conc. 106 (03/07)', 'numeri': [22, 26, 30, 40, 68, 86], 'superstar': 48},
 {'concorso': 'Conc. 105 (02/07)', 'numeri': [4, 17, 19, 23, 47, 59], 'superstar': 82},
 {'concorso': 'Conc. 104 (30/06)', 'numeri': [1, 7, 51, 64, 78, 83], 'superstar': 66},
 {'concorso': 'Conc. 103 (27/06)', 'numeri': [15, 19, 36, 47, 85, 90], 'superstar': 62},
 {'concorso': 'Conc. 102 (26/06)', 'numeri': [1, 22, 30, 45, 73, 76], 'superstar': 49},
 {'concorso': 'Conc. 101 (25/06)', 'numeri': [25, 27, 54, 72, 73, 76], 'superstar': 80},
 {'concorso': 'Conc. 100 (23/06)', 'numeri': [1, 12, 17, 27, 66, 84], 'superstar': 4},
 {'concorso': 'Conc. 99 (20/06)', 'numeri': [14, 59, 69, 71, 82, 89], 'superstar': 3},
 {'concorso': 'Conc. 98 (19/06)', 'numeri': [14, 18, 25, 69, 81, 89], 'superstar': 69},
 {'concorso': 'Conc. 97 (18/06)', 'numeri': [4, 26, 39, 43, 70, 87], 'superstar': 57},
 {'concorso': 'Conc. 96 (16/06)', 'numeri': [4, 28, 33, 35, 66, 80], 'superstar': 72},
 {'concorso': 'Conc. 95 (13/06)', 'numeri': [13, 23, 34, 68, 87, 90], 'superstar': 54},
 {'concorso': 'Conc. 94 (12/06)', 'numeri': [18, 24, 42, 68, 75, 83], 'superstar': 20},
 {'concorso': 'Conc. 93 (11/06)', 'numeri': [7, 21, 22, 40, 44, 87], 'superstar': 83},
 {'concorso': 'Conc. 92 (09/06)', 'numeri': [18, 36, 47, 55, 73, 80], 'superstar': 54},
 {'concorso': 'Conc. 91 (08/06)', 'numeri': [28, 33, 51, 59, 82, 87], 'superstar': 87},
 {'concorso': 'Conc. 90 (06/06)', 'numeri': [2, 7, 29, 68, 72, 89], 'superstar': 38},
 {'concorso': 'Conc. 89 (05/06)', 'numeri': [9, 25, 51, 63, 73, 89], 'superstar': 40},
 {'concorso': 'Conc. 88 (04/06)', 'numeri': [12, 33, 43, 55, 74, 75], 'superstar': 59},
 {'concorso': 'Conc. 87 (30/05)', 'numeri': [8, 13, 21, 39, 63, 71], 'superstar': 56},
 {'concorso': 'Conc. 86 (29/05)', 'numeri': [9, 42, 44, 46, 85, 90], 'superstar': 20},
 {'concorso': 'Conc. 85 (28/05)', 'numeri': [22, 33, 36, 74, 78, 86], 'superstar': 34},
 {'concorso': 'Conc. 84 (26/05)', 'numeri': [7, 10, 35, 41, 45, 61], 'superstar': 45},
 {'concorso': 'Conc. 83 (23/05)', 'numeri': [14, 29, 34, 57, 59, 69], 'superstar': 16},
 {'concorso': 'Conc. 82 (22/05)', 'numeri': [5, 17, 65, 71, 83, 87], 'superstar': 88},
 {'concorso': 'Conc. 81 (21/05)', 'numeri': [1, 38, 57, 58, 64, 81], 'superstar': 50},
 {'concorso': 'Conc. 80 (19/05)', 'numeri': [49, 57, 61, 73, 79, 86], 'superstar': 38},
 {'concorso': 'Conc. 79 (16/05)', 'numeri': [7, 12, 60, 69, 89, 90], 'superstar': 36},
 {'concorso': 'Conc. 78 (15/05)', 'numeri': [5, 13, 17, 28, 47, 68], 'superstar': 19},
 {'concorso': 'Conc. 77 (14/05)', 'numeri': [31, 56, 72, 74, 84, 85], 'superstar': 34},
 {'concorso': 'Conc. 76 (12/05)', 'numeri': [2, 28, 31, 57, 58, 59], 'superstar': 2},
 {'concorso': 'Conc. 75 (09/05)', 'numeri': [9, 27, 30, 42, 43, 62], 'superstar': 11},
 {'concorso': 'Conc. 74 (08/05)', 'numeri': [8, 16, 41, 47, 51, 90], 'superstar': 69},
 {'concorso': 'Conc. 73 (07/05)', 'numeri': [1, 34, 48, 66, 69, 73], 'superstar': 58},
 {'concorso': 'Conc. 72 (05/05)', 'numeri': [24, 34, 45, 55, 81, 87], 'superstar': 52},
 {'concorso': 'Conc. 71 (04/05)', 'numeri': [3, 14, 31, 46, 61, 63], 'superstar': 24},
 {'concorso': 'Conc. 70 (02/05)', 'numeri': [7, 58, 60, 79, 84, 86], 'superstar': 19},
 {'concorso': 'Conc. 69 (30/04)', 'numeri': [6, 7, 15, 44, 52, 58], 'superstar': 16}]


# -----------------------------------------------------------------------------
# UTILITÀ E VALIDAZIONE
# -----------------------------------------------------------------------------
def deep_copy_initial_history() -> list[dict[str, Any]]:
    history = copy.deepcopy(REAL_50_EXTRACTIONS)
    for draw in history:
        draw.setdefault("jolly", None)
    return history


def validate_number(value: Any, field_name: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field_name} non valido.")
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} deve essere un numero intero.") from exc
    if not NUMBER_MIN <= number <= NUMBER_MAX:
        raise ValueError(f"{field_name} deve essere compreso tra 1 e 90.")
    return number


def normalize_history(raw_history: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_history, list):
        raise ValueError("Il backup deve contenere una lista di estrazioni.")
    if not raw_history:
        raise ValueError("Il backup è vuoto.")

    normalized: list[dict[str, Any]] = []
    seen_contests: set[str] = set()

    for index, raw_draw in enumerate(raw_history, start=1):
        if not isinstance(raw_draw, dict):
            raise ValueError(f"Estrazione {index} non valida.")

        contest = str(raw_draw.get("concorso", "")).strip()
        if not contest:
            raise ValueError(f"Manca il nome del concorso alla riga {index}.")
        if contest in seen_contests:
            raise ValueError(f"Concorso duplicato nel backup: {contest}.")

        raw_numbers = raw_draw.get("numeri")
        if not isinstance(raw_numbers, (list, tuple)) or len(raw_numbers) != 6:
            raise ValueError(f"{contest} deve contenere esattamente 6 numeri.")

        numbers = sorted(validate_number(n, f"Numero di {contest}") for n in raw_numbers)
        if len(set(numbers)) != 6:
            raise ValueError(f"{contest} contiene numeri duplicati.")

        superstar = validate_number(raw_draw.get("superstar"), f"SuperStar di {contest}")
        raw_jolly = raw_draw.get("jolly")
        jolly = None if raw_jolly in (None, "") else validate_number(raw_jolly, f"Jolly di {contest}")

        normalized.append(
            {
                "concorso": contest,
                "numeri": numbers,
                "jolly": jolly,
                "superstar": superstar,
            }
        )
        seen_contests.add(contest)

    return normalized[:MAX_HISTORY]


def add_new_extraction(
    contest: str,
    numbers: list[int],
    superstar: int,
    jolly: int | None = None,
) -> None:
    contest = contest.strip()
    if not contest:
        raise ValueError("Inserisci il nome del concorso.")
    if any(draw["concorso"].casefold() == contest.casefold() for draw in st.session_state.history):
        raise ValueError("Esiste già un concorso con questo nome.")

    validated_numbers = sorted(validate_number(n, "Numero") for n in numbers)
    if len(set(validated_numbers)) != 6:
        raise ValueError("I sei numeri devono essere tutti diversi.")

    new_draw = {
        "concorso": contest,
        "numeri": validated_numbers,
        "jolly": None if jolly is None else validate_number(jolly, "Jolly"),
        "superstar": validate_number(superstar, "SuperStar"),
    }

    st.session_state.history.insert(0, new_draw)
    del st.session_state.history[MAX_HISTORY:]
    st.session_state.single_result = None
    st.session_state.backtest_result = None


def euro(value: float) -> str:
    formatted = f"{value:,.2f}"
    return formatted.replace(",", "§").replace(".", ",").replace("§", ".") + " €"


def system_cost(number_of_lines: int, with_superstar: bool) -> float:
    return number_of_lines * (COST_BASE + (COST_SUPERSTAR if with_superstar else 0.0))


def min_max_scale(values: dict[int, float]) -> dict[int, float]:
    minimum = min(values.values())
    maximum = max(values.values())
    if math.isclose(minimum, maximum):
        return {key: 0.5 for key in values}
    return {key: (value - minimum) / (maximum - minimum) for key, value in values.items()}


# -----------------------------------------------------------------------------
# METRICHE STATISTICHE DESCRITTIVE
# -----------------------------------------------------------------------------
def calculate_metrics(history: list[dict[str, Any]]) -> dict[str, dict[int, float]]:
    draw_count = len(history)
    frequency = {number: 0.0 for number in range(1, 91)}
    delay = {number: float(draw_count) for number in range(1, 91)}
    recency = {number: 0.0 for number in range(1, 91)}

    # history è ordinato dal più recente al più vecchio.
    for position, draw in enumerate(history, start=1):
        recency_weight = 1.0 / math.sqrt(position)
        for number in draw["numeri"]:
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
        "frequency_norm": frequency_norm,
        "delay_norm": delay_norm,
        "recency_norm": recency_norm,
        "score": score,
    }


def calculate_superstar_ranking(history: list[dict[str, Any]]) -> list[tuple[int, float, int, int]]:
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

    f_norm = min_max_scale(frequency)
    d_norm = min_max_scale(delay)
    r_norm = min_max_scale(recency)

    ranking = []
    for number in range(1, 91):
        score = 0.40 * f_norm[number] + 0.25 * d_norm[number] + 0.35 * r_norm[number]
        ranking.append((number, score, int(frequency[number]), int(delay[number])))

    return sorted(ranking, key=lambda item: (item[1], item[2], item[3]), reverse=True)


# -----------------------------------------------------------------------------
# GENERAZIONE DELLE COMBINAZIONI
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
    minimum_sum: int = 200,
    maximum_sum: int = 340,
    maximum_low_numbers: int = 4,
    minimum_decades: int = 4,
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
    top_pool_size: int = 25,
    limit: int = 250,
    minimum_sum: int = 200,
    maximum_sum: int = 340,
    maximum_low_numbers: int = 4,
    minimum_decades: int = 4,
) -> list[tuple[float, tuple[int, ...]]]:
    ranked_numbers = sorted(scores, key=scores.get, reverse=True)
    pool = ranked_numbers[:top_pool_size]
    heap: list[tuple[float, tuple[int, ...]]] = []

    for combo in combinations(pool, 6):
        sorted_combo = tuple(sorted(combo))
        if not passes_structural_filters(
            sorted_combo,
            minimum_sum,
            maximum_sum,
            maximum_low_numbers,
            minimum_decades,
        ):
            continue

        quality = combination_quality(sorted_combo, scores)
        item = (quality, sorted_combo)
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
        top_pool_size=top_pool_size,
        limit=limit,
        minimum_sum=minimum_sum,
        maximum_sum=maximum_sum,
        maximum_low_numbers=maximum_low_numbers,
        minimum_decades=minimum_decades,
    )


def create_single_result(
    candidates: list[tuple[float, tuple[int, ...]]],
    superstar_ranking: list[tuple[int, float, int, int]],
    alternative: bool = False,
    previous_combo: tuple[int, ...] | None = None,
) -> dict[str, Any]:
    if not candidates:
        raise ValueError("Nessuna sestina rispetta i filtri selezionati.")

    if alternative:
        alternative_candidates = [item for item in candidates[:100] if item[1] != previous_combo]
        quality, combo = random.SystemRandom().choice(alternative_candidates or candidates[:100])
    else:
        quality, combo = candidates[0]

    superstar, ss_score, ss_frequency, ss_delay = superstar_ranking[0]
    features = combination_features(combo)

    return {
        "combo": combo,
        "quality": quality,
        "superstar": superstar,
        "superstar_score": ss_score,
        "superstar_frequency": ss_frequency,
        "superstar_delay": ss_delay,
        "features": features,
        "alternative": alternative,
    }


def generate_integral_system(scores: dict[int, float], pool_size: int) -> tuple[list[int], list[tuple[int, ...]]]:
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

    generated = [tuple(sorted((*bases, *variant_combo))) for variant_combo in combinations(variants, required_variants)]
    filtered = [combo for combo in generated if passes_structural_filters(combo)]
    lines = filtered or generated
    lines.sort(key=lambda combo: combination_quality(combo, scores), reverse=True)

    return bases, sorted(variants), lines


def generate_reduced_smart_system(
    scores: dict[int, float],
    pool_size: int,
    maximum_lines: int,
) -> tuple[list[int], list[tuple[int, ...]], float]:
    ranked_numbers = sorted(scores, key=scores.get, reverse=True)
    pool = ranked_numbers[:pool_size]

    candidates: list[tuple[float, tuple[int, ...]]] = []
    for combo in combinations(pool, 6):
        sorted_combo = tuple(sorted(combo))
        if passes_structural_filters(sorted_combo):
            candidates.append((combination_quality(sorted_combo, scores), sorted_combo))

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
            max_overlap = max((len(set(combo) & set(chosen)) for chosen in selected), default=0)
            diversity = 1.0 - (max_overlap / 6.0)
            normalized_quality = quality / max_quality
            objective = 0.55 * normalized_quality + 0.30 * new_pair_ratio + 0.15 * diversity

            if objective > best_objective:
                best_objective = objective
                best_index = index

        _, chosen_combo = remaining.pop(best_index)
        selected.append(chosen_combo)
        covered_pairs.update(combinations(chosen_combo, 2))

    possible_pairs = math.comb(pool_size, 2)
    coverage = len(covered_pairs) / possible_pairs if possible_pairs else 0.0
    return sorted(pool), selected, coverage


# -----------------------------------------------------------------------------
# BACKTEST WALK-FORWARD
# -----------------------------------------------------------------------------
def run_walk_forward_backtest(history: list[dict[str, Any]], minimum_training_draws: int = 20) -> dict[str, Any]:
    chronological = list(reversed(history))
    rows: list[dict[str, Any]] = []

    for target_index in range(minimum_training_draws, len(chronological)):
        training_chronological = chronological[:target_index]
        training_newest_first = list(reversed(training_chronological))
        target = chronological[target_index]

        metrics = calculate_metrics(training_newest_first)
        candidates = rank_candidate_sestine(
            metrics["score"],
            top_pool_size=18,
            limit=1,
            minimum_sum=190,
            maximum_sum=350,
            maximum_low_numbers=4,
            minimum_decades=3,
        )
        if not candidates:
            continue

        prediction = candidates[0][1]
        hits = len(set(prediction) & set(target["numeri"]))
        rows.append(
            {
                "Concorso": target["concorso"],
                "Pronostico": ", ".join(map(str, prediction)),
                "Estratti": ", ".join(map(str, target["numeri"])),
                "Punti": hits,
            }
        )

    average_hits = sum(row["Punti"] for row in rows) / len(rows) if rows else 0.0
    wins_2_plus = sum(row["Punti"] >= 2 for row in rows)
    denominator = math.comb(90, 6)
    probability_2_plus = sum(
        math.comb(6, hits) * math.comb(84, 6 - hits) / denominator
        for hits in range(2, 7)
    )

    return {
        "rows": rows,
        "average_hits": average_hits,
        "wins_2_plus": wins_2_plus,
        "expected_average_hits": 0.4,
        "expected_2_plus": len(rows) * probability_2_plus,
    }


# -----------------------------------------------------------------------------
# STATO DELLA SESSIONE
# -----------------------------------------------------------------------------
if "history" not in st.session_state:
    st.session_state.history = deep_copy_initial_history()
if "single_result" not in st.session_state:
    st.session_state.single_result = None
if "backtest_result" not in st.session_state:
    st.session_state.backtest_result = None


# -----------------------------------------------------------------------------
# SIDEBAR: ARCHIVIO, IMPORTAZIONE ED ESPORTAZIONE
# -----------------------------------------------------------------------------
with st.sidebar:
    st.header("⚙️ Archivio estrazioni")
    st.caption(
        "L'app conserva al massimo 50 concorsi. Su Streamlit Community Cloud la sessione "
        "non è una memoria permanente: scarica il backup JSON dopo gli aggiornamenti."
    )

    with st.form("add_extraction_form", clear_on_submit=False):
        contest_name = st.text_input("Nome concorso", value="Conc. Nuovo")
        number_columns = st.columns(2)
        defaults = [10, 20, 30, 40, 50, 60]
        inserted_numbers = [
            number_columns[index % 2].number_input(
                f"{index + 1}° numero",
                min_value=1,
                max_value=90,
                value=defaults[index],
                step=1,
                key=f"new_number_{index}",
            )
            for index in range(6)
        ]
        include_jolly = st.checkbox("Inserisci anche il Jolly")
        jolly_value = (
            st.number_input("Jolly", min_value=1, max_value=90, value=1, step=1)
            if include_jolly
            else None
        )
        superstar_value = st.number_input("⭐ SuperStar", min_value=1, max_value=90, value=15, step=1)
        submitted = st.form_submit_button("Aggiungi estrazione", use_container_width=True)

        if submitted:
            try:
                add_new_extraction(
                    contest_name,
                    [int(number) for number in inserted_numbers],
                    int(superstar_value),
                    None if jolly_value is None else int(jolly_value),
                )
                st.success("Estrazione aggiunta. Il concorso più vecchio è stato rimosso se necessario.")
            except ValueError as exc:
                st.error(str(exc))

    st.divider()
    backup_bytes = json.dumps(
        st.session_state.history,
        ensure_ascii=False,
        indent=2,
    ).encode("utf-8")
    st.download_button(
        "⬇️ Scarica backup JSON",
        data=backup_bytes,
        file_name="storico_superenalotto.json",
        mime="application/json",
        use_container_width=True,
    )

    uploaded_backup = st.file_uploader("Carica un backup JSON", type=["json"])
    if st.button("Importa backup", use_container_width=True, disabled=uploaded_backup is None):
        try:
            assert uploaded_backup is not None
            imported = json.loads(uploaded_backup.getvalue().decode("utf-8"))
            st.session_state.history = normalize_history(imported)
            st.session_state.single_result = None
            st.session_state.backtest_result = None
            st.success("Backup importato correttamente.")
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError, AssertionError) as exc:
            st.error(f"Backup non valido: {exc}")

    if st.button("🔄 Ripristina le 50 estrazioni iniziali", use_container_width=True):
        st.session_state.history = deep_copy_initial_history()
        st.session_state.single_result = None
        st.session_state.backtest_result = None
        st.success("Archivio iniziale ripristinato.")


# -----------------------------------------------------------------------------
# CALCOLI CORRENTI
# -----------------------------------------------------------------------------
metrics = calculate_metrics(st.session_state.history)
scores = metrics["score"]
superstar_ranking = calculate_superstar_ranking(st.session_state.history)
score_items = tuple(sorted(scores.items()))


# -----------------------------------------------------------------------------
# INTERFACCIA PRINCIPALE
# -----------------------------------------------------------------------------
st.title("🎰 SuperEnalotto — Analizzatore statistico")
st.caption(
    "Analizza frequenza, ritardo e recenza degli ultimi 50 concorsi e costruisce "
    "combinazioni filtrate. Non è un sistema capace di prevedere un'estrazione casuale."
)

with st.expander("⚠️ Limite matematico da non ignorare", expanded=False):
    st.write(
        "Ogni specifica sestina ha la stessa probabilità di essere estratta: "
        "1 su 622.614.630. Frequenze, ritardi e filtri servono a organizzare la scelta, "
        "non a creare un vantaggio matematico dimostrato."
    )

single_tab, systems_tab, stats_tab, backtest_tab = st.tabs(
    [
        "🎯 Sestina singola",
        "🧩 Sistemi",
        "📊 Statistiche",
        "🧪 Backtest",
    ]
)


with single_tab:
    st.subheader("Sestina principale e alternative")

    filter_col1, filter_col2, filter_col3, filter_col4 = st.columns(4)
    minimum_sum = filter_col1.number_input("Somma minima", 150, 300, 200, 5)
    maximum_sum = filter_col2.number_input("Somma massima", 250, 450, 340, 5)
    maximum_low = filter_col3.number_input("Massimo numeri ≤31", 1, 6, 4, 1)
    minimum_decades = filter_col4.number_input("Minimo decine coperte", 2, 6, 4, 1)

    if minimum_sum >= maximum_sum:
        st.error("La somma minima deve essere inferiore alla somma massima.")
    else:
        button_col1, button_col2 = st.columns(2)
        generate_main = button_col1.button(
            "Calcola sestina principale",
            type="primary",
            use_container_width=True,
        )
        generate_alternative = button_col2.button(
            "Genera alternativa tra le migliori",
            use_container_width=True,
        )

        if generate_main or generate_alternative:
            with st.spinner("Valutazione delle combinazioni..."):
                candidates = rank_candidate_sestine_cached(
                    score_items,
                    25,
                    250,
                    int(minimum_sum),
                    int(maximum_sum),
                    int(maximum_low),
                    int(minimum_decades),
                )
                previous = (
                    tuple(st.session_state.single_result["combo"])
                    if st.session_state.single_result
                    else None
                )
                try:
                    st.session_state.single_result = create_single_result(
                        candidates,
                        superstar_ranking,
                        alternative=generate_alternative,
                        previous_combo=previous,
                    )
                except ValueError as exc:
                    st.error(str(exc))

    result = st.session_state.single_result
    if result:
        st.divider()
        st.markdown("### Combinazione elaborata")
        number_columns = st.columns(6)
        for index, number in enumerate(result["combo"]):
            number_columns[index].metric(f"N{index + 1}", str(number))

        details_col1, details_col2, details_col3, details_col4 = st.columns(4)
        details_col1.metric("⭐ SuperStar statistico", str(result["superstar"]))
        details_col2.metric("Somma", str(result["features"]["sum"]))
        even = result["features"]["even"]
        details_col3.metric("Pari / dispari", f"{even} / {6-even}")
        details_col4.metric("Decine coperte", str(result["features"]["decades"]))

        st.caption(
            "Il SuperStar indicato è il primo del ranking descrittivo separato. "
            "Non è statisticamente garantito come più probabile."
        )


with systems_tab:
    st.subheader("Generatore di sistemi")
    with_superstar = st.checkbox("Calcola il costo con SuperStar", value=True)

    system_type = st.selectbox(
        "Tipologia",
        [
            "Sistema integrale",
            "Sistema a basi e varianti",
            "Sistema ridotto diversificato",
        ],
    )

    if system_type == "Sistema integrale":
        pool_size = st.radio("Numeri nel sistema", [7, 8, 9], horizontal=True)
        if st.button("Genera sistema integrale", type="primary"):
            pool, lines = generate_integral_system(scores, int(pool_size))
            st.success(f"Generate {len(lines)} combinazioni integrali.")
            st.write("**Numeri selezionati:** " + ", ".join(map(str, pool)))
            st.metric("Costo totale", euro(system_cost(len(lines), with_superstar)))

            dataframe = pd.DataFrame(lines, columns=[f"N{index}" for index in range(1, 7)])
            if with_superstar:
                dataframe["SuperStar"] = superstar_ranking[0][0]
            st.dataframe(dataframe, use_container_width=True, hide_index=True)
            st.download_button(
                "Scarica CSV",
                data=dataframe.to_csv(index=False).encode("utf-8-sig"),
                file_name=f"sistema_integrale_{pool_size}_numeri.csv",
                mime="text/csv",
            )

    elif system_type == "Sistema a basi e varianti":
        base_col, variant_col = st.columns(2)
        base_count = base_col.slider("Basi fisse", 1, 3, 2)
        minimum_variants = 6 - base_count
        variant_count = variant_col.slider(
            "Varianti",
            minimum_variants,
            10,
            max(6, minimum_variants),
        )

        if st.button("Genera basi e varianti", type="primary"):
            try:
                bases, variants, lines = generate_base_variant_system(
                    scores,
                    int(base_count),
                    int(variant_count),
                )
                st.success(f"Generate {len(lines)} combinazioni.")
                st.write("**Basi:** " + ", ".join(map(str, bases)))
                st.write("**Varianti:** " + ", ".join(map(str, variants)))
                st.metric("Costo totale", euro(system_cost(len(lines), with_superstar)))

                dataframe = pd.DataFrame(lines, columns=[f"N{index}" for index in range(1, 7)])
                if with_superstar:
                    dataframe["SuperStar"] = superstar_ranking[0][0]
                st.dataframe(dataframe, use_container_width=True, hide_index=True)
                st.download_button(
                    "Scarica CSV",
                    data=dataframe.to_csv(index=False).encode("utf-8-sig"),
                    file_name="sistema_basi_varianti.csv",
                    mime="text/csv",
                )
            except ValueError as exc:
                st.error(str(exc))

    else:
        reduced_col1, reduced_col2 = st.columns(2)
        reduced_pool_size = reduced_col1.slider("Dimensione pool", 10, 15, 12)
        maximum_lines = reduced_col2.slider("Numero di sestine", 4, 20, 8)

        if st.button("Genera sistema ridotto diversificato", type="primary"):
            pool, lines, pair_coverage = generate_reduced_smart_system(
                scores,
                int(reduced_pool_size),
                int(maximum_lines),
            )
            st.success(f"Generate {len(lines)} combinazioni diversificate.")
            st.write("**Pool:** " + ", ".join(map(str, pool)))
            metric_col1, metric_col2 = st.columns(2)
            metric_col1.metric("Costo totale", euro(system_cost(len(lines), with_superstar)))
            metric_col2.metric("Copertura coppie del pool", f"{pair_coverage:.1%}")
            st.caption(
                "La copertura indica quante coppie diverse del pool compaiono almeno una volta. "
                "Non costituisce una garanzia di vincita."
            )

            dataframe = pd.DataFrame(lines, columns=[f"N{index}" for index in range(1, 7)])
            if with_superstar:
                dataframe["SuperStar"] = superstar_ranking[0][0]
            st.dataframe(dataframe, use_container_width=True, hide_index=True)
            st.download_button(
                "Scarica CSV",
                data=dataframe.to_csv(index=False).encode("utf-8-sig"),
                file_name="sistema_ridotto_diversificato.csv",
                mime="text/csv",
            )


with stats_tab:
    st.subheader("Ranking dei 90 numeri")
    stats_dataframe = pd.DataFrame(
        {
            "Numero": range(1, 91),
            "Frequenza": [int(metrics["frequency"][number]) for number in range(1, 91)],
            "Ritardo": [int(metrics["delay"][number]) for number in range(1, 91)],
            "Recenza": [round(metrics["recency"][number], 3) for number in range(1, 91)],
            "Score": [round(scores[number], 4) for number in range(1, 91)],
        }
    ).sort_values(["Score", "Numero"], ascending=[False, True])
    st.dataframe(stats_dataframe, use_container_width=True, hide_index=True, height=500)

    st.subheader("Ranking SuperStar")
    superstar_dataframe = pd.DataFrame(
        [
            {
                "SuperStar": number,
                "Frequenza": frequency,
                "Ritardo": delay_value,
                "Score": round(score, 4),
            }
            for number, score, frequency, delay_value in superstar_ranking[:15]
        ]
    )
    st.dataframe(superstar_dataframe, use_container_width=True, hide_index=True)

    st.subheader("Storico FIFO")
    history_dataframe = pd.DataFrame(
        [
            {
                "Posizione": index + 1,
                "Concorso": draw["concorso"],
                "Sestina": ", ".join(map(str, draw["numeri"])),
                "Jolly": draw.get("jolly") if draw.get("jolly") is not None else "—",
                "SuperStar": draw["superstar"],
            }
            for index, draw in enumerate(st.session_state.history)
        ]
    )
    st.dataframe(history_dataframe, use_container_width=True, hide_index=True, height=500)


with backtest_tab:
    st.subheader("Backtest walk-forward")
    st.write(
        "Per ogni concorso storico, il metodo usa soltanto le estrazioni precedenti e poi "
        "confronta la sestina elaborata con quella realmente uscita."
    )
    st.warning(
        "Con appena 50 estrazioni il campione è piccolo. Il backtest serve a smascherare "
        "metodi palesemente inconsistenti, non a dimostrare capacità predittiva."
    )

    if st.button("Esegui backtest", type="primary"):
        with st.spinner("Esecuzione del test storico..."):
            st.session_state.backtest_result = run_walk_forward_backtest(st.session_state.history)

    backtest = st.session_state.backtest_result
    if backtest:
        result_col1, result_col2, result_col3, result_col4 = st.columns(4)
        result_col1.metric("Concorsi testati", len(backtest["rows"]))
        result_col2.metric("Media punti", f"{backtest['average_hits']:.3f}")
        result_col3.metric("Media casuale teorica", f"{backtest['expected_average_hits']:.3f}")
        result_col4.metric("Risultati da 2+", backtest["wins_2_plus"])
        st.caption(
            f"Su questo numero di test, una sestina casuale produrrebbe in media "
            f"circa {backtest['expected_2_plus']:.2f} risultati da almeno 2 punti."
        )
        st.dataframe(pd.DataFrame(backtest["rows"]), use_container_width=True, hide_index=True)
