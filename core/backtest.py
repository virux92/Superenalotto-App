from __future__ import annotations

import math
from typing import Any

import pandas as pd

from core.combinations import rank_candidate_sestine
from core.metrics import calculate_metrics


def random_hit_probabilities() -> dict[int, float]:
    denominator = math.comb(90, 6)
    return {hits: math.comb(6, hits) * math.comb(84, 6 - hits) / denominator for hits in range(7)}


def select_baseline_numbers(metrics: dict[str, dict[int, float]], strategy: str) -> tuple[int, ...]:
    if strategy == "frequenti":
        ranking = sorted(range(1, 91), key=lambda n: (metrics["frequency"][n], metrics["recency"][n], -n), reverse=True)
    elif strategy == "ritardatari":
        ranking = sorted(range(1, 91), key=lambda n: (metrics["delay"][n], -metrics["frequency"][n], -metrics["recency"][n], -n), reverse=True)
    else:
        raise ValueError("Strategia di confronto non riconosciuta.")
    return tuple(sorted(ranking[:6]))


def records_tuple(dataframe: pd.DataFrame) -> tuple[tuple[Any, ...], ...]:
    rows = []
    for row in dataframe.sort_values("data").itertuples(index=False):
        rows.append((pd.Timestamp(row.data).strftime("%Y-%m-%d"), int(row.anno), int(row.concorso), int(row.n1), int(row.n2), int(row.n3), int(row.n4), int(row.n5), int(row.n6), 0 if pd.isna(row.jolly) else int(row.jolly), int(row.superstar)))
    return tuple(rows)


def run_walk_forward_backtest(raw_records: tuple[tuple[Any, ...], ...], window_size: int, test_limit: int, pool_size: int, minimum_sum: int, maximum_sum: int, maximum_low_numbers: int, minimum_decades: int) -> dict[str, Any]:
    chronological = [{"date": pd.Timestamp(r[0]), "year": int(r[1]), "contest": int(r[2]), "numbers": [int(v) for v in r[3:9]], "jolly": None if int(r[9]) == 0 else int(r[9]), "superstar": int(r[10])} for r in raw_records]
    first_target = max(window_size, len(chronological) - test_limit) if test_limit > 0 else window_size
    details = []
    strategy_hits = {"Algoritmo": [], "Solo frequenti": [], "Solo ritardatari": []}
    for target_index in range(first_target, len(chronological)):
        history = list(reversed(chronological[target_index-window_size:target_index]))
        target = chronological[target_index]
        metrics = calculate_metrics(history)
        candidates = rank_candidate_sestine(metrics["score"], pool_size, 1, minimum_sum, maximum_sum, maximum_low_numbers, minimum_decades)
        algorithm = candidates[0][1] if candidates else tuple(sorted(sorted(metrics["score"], key=metrics["score"].get, reverse=True)[:6]))
        predictions = {"Algoritmo": algorithm, "Solo frequenti": select_baseline_numbers(metrics, "frequenti"), "Solo ritardatari": select_baseline_numbers(metrics, "ritardatari")}
        target_set = set(target["numbers"])
        hit_values = {}
        for strategy, prediction in predictions.items():
            hits = len(set(prediction) & target_set)
            strategy_hits[strategy].append(hits)
            hit_values[strategy] = hits
        details.append({"Data": target["date"].strftime("%d/%m/%Y"), "Concorso": f"{target['year']}/{target['contest']}", "Estratti": ", ".join(map(str, target["numbers"])), "Pronostico algoritmo": ", ".join(map(str, algorithm)), "Punti algoritmo": hit_values["Algoritmo"], "Punti frequenti": hit_values["Solo frequenti"], "Punti ritardatari": hit_values["Solo ritardatari"]})
    probabilities = random_hit_probabilities()
    summary = []
    for strategy, hits_list in strategy_hits.items():
        distribution = {hits: hits_list.count(hits) for hits in range(7)}
        summary.append({"Strategia": strategy, "Test": len(hits_list), "Media punti": sum(hits_list)/len(hits_list) if hits_list else 0.0, "2+": sum(h >= 2 for h in hits_list), "3+": sum(h >= 3 for h in hits_list), **{f"Punti {h}": distribution[h] for h in range(7)}})
    test_count = len(details)
    return {"details": details, "summary": summary, "test_count": test_count, "random_average": 0.4, "random_expected_2_plus": test_count * sum(p for h,p in probabilities.items() if h >= 2), "random_probabilities": probabilities}
