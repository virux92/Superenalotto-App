from __future__ import annotations

import hashlib
import math
import random
from collections import defaultdict
from statistics import mean, pstdev
from typing import Any

import pandas as pd

from core.combinations import rank_candidate_sestine
from core.metrics import calculate_metrics


def random_hit_probabilities() -> dict[int, float]:
    denominator = math.comb(90, 6)
    return {
        hits: math.comb(6, hits) * math.comb(84, 6 - hits) / denominator
        for hits in range(7)
    }


def select_baseline_numbers(
    metrics: dict[str, dict[int, float]], strategy: str
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


def deterministic_random_line(target: dict[str, Any], seed: int) -> tuple[int, ...]:
    material = f"{seed}:{target['date']:%Y-%m-%d}:{target['year']}:{target['contest']}"
    digest = hashlib.sha256(material.encode("utf-8")).digest()
    local_seed = int.from_bytes(digest[:8], "big", signed=False)
    generator = random.Random(local_seed)
    return tuple(sorted(generator.sample(range(1, 91), 6)))


def records_tuple(dataframe: pd.DataFrame) -> tuple[tuple[Any, ...], ...]:
    rows = []
    for row in dataframe.sort_values("data").itertuples(index=False):
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


def _summary_row(strategy: str, hits_list: list[int]) -> dict[str, Any]:
    test_count = len(hits_list)
    average = mean(hits_list) if hits_list else 0.0
    deviation = pstdev(hits_list) if hits_list else 0.0
    standard_error = deviation / math.sqrt(test_count) if test_count else 0.0
    distribution = {hits: hits_list.count(hits) for hits in range(7)}
    return {
        "Strategia": strategy,
        "Test": test_count,
        "Media punti": average,
        "Deviazione": deviation,
        "IC95% minimo": max(0.0, average - 1.96 * standard_error),
        "IC95% massimo": min(6.0, average + 1.96 * standard_error),
        "2+": sum(hits >= 2 for hits in hits_list),
        "3+": sum(hits >= 3 for hits in hits_list),
        "4+": sum(hits >= 4 for hits in hits_list),
        **{f"Punti {hits}": distribution[hits] for hits in range(7)},
    }


def run_walk_forward_backtest(
    raw_records: tuple[tuple[Any, ...], ...],
    window_size: int,
    test_limit: int,
    pool_size: int,
    minimum_sum: int,
    maximum_sum: int,
    maximum_low_numbers: int,
    minimum_decades: int,
    random_seed: int = 20260726,
) -> dict[str, Any]:
    chronological = [
        {
            "date": pd.Timestamp(record[0]),
            "year": int(record[1]),
            "contest": int(record[2]),
            "numbers": [int(value) for value in record[3:9]],
            "jolly": None if int(record[9]) == 0 else int(record[9]),
            "superstar": int(record[10]),
        }
        for record in raw_records
    ]
    first_target = (
        max(window_size, len(chronological) - test_limit)
        if test_limit > 0
        else window_size
    )

    details: list[dict[str, Any]] = []
    strategy_hits: dict[str, list[int]] = {
        "Algoritmo": [],
        "Solo frequenti": [],
        "Solo ritardatari": [],
        "Casuale deterministico": [],
    }
    annual_hits: dict[str, dict[int, list[int]]] = defaultdict(lambda: defaultdict(list))

    for target_index in range(first_target, len(chronological)):
        history = list(
            reversed(chronological[target_index - window_size : target_index])
        )
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
        algorithm = (
            candidates[0][1]
            if candidates
            else tuple(
                sorted(
                    sorted(
                        metrics["score"],
                        key=metrics["score"].get,
                        reverse=True,
                    )[:6]
                )
            )
        )
        random_line = deterministic_random_line(target, random_seed)
        predictions = {
            "Algoritmo": algorithm,
            "Solo frequenti": select_baseline_numbers(metrics, "frequenti"),
            "Solo ritardatari": select_baseline_numbers(metrics, "ritardatari"),
            "Casuale deterministico": random_line,
        }
        target_set = set(target["numbers"])
        hit_values: dict[str, int] = {}
        for strategy, prediction in predictions.items():
            hits = len(set(prediction) & target_set)
            strategy_hits[strategy].append(hits)
            annual_hits[strategy][target["year"]].append(hits)
            hit_values[strategy] = hits

        details.append(
            {
                "Data": target["date"].strftime("%d/%m/%Y"),
                "Anno": target["year"],
                "Concorso": f"{target['year']}/{target['contest']}",
                "Estratti": ", ".join(map(str, target["numbers"])),
                "Pronostico algoritmo": ", ".join(map(str, algorithm)),
                "Punti algoritmo": hit_values["Algoritmo"],
                "Punti frequenti": hit_values["Solo frequenti"],
                "Punti ritardatari": hit_values["Solo ritardatari"],
                "Pronostico casuale": ", ".join(map(str, random_line)),
                "Punti casuale": hit_values["Casuale deterministico"],
            }
        )

    probabilities = random_hit_probabilities()
    summary = [
        _summary_row(strategy, hits_list)
        for strategy, hits_list in strategy_hits.items()
    ]
    annual_summary = []
    for strategy, years in annual_hits.items():
        for year, hits_list in sorted(years.items()):
            annual_summary.append(
                {
                    "Strategia": strategy,
                    "Anno": year,
                    "Test": len(hits_list),
                    "Media punti": mean(hits_list) if hits_list else 0.0,
                    "2+": sum(hits >= 2 for hits in hits_list),
                    "3+": sum(hits >= 3 for hits in hits_list),
                }
            )

    test_count = len(details)
    return {
        "details": details,
        "summary": summary,
        "annual_summary": annual_summary,
        "test_count": test_count,
        "random_seed": random_seed,
        "random_average": 0.4,
        "random_expected_2_plus": test_count
        * sum(probability for hits, probability in probabilities.items() if hits >= 2),
        "random_probabilities": probabilities,
    }
