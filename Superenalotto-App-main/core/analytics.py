from __future__ import annotations

import math
from collections import Counter, defaultdict
from itertools import combinations
from statistics import mean, median, pstdev
from typing import Any, Iterable

from core.combinations import combination_features


def normalized_entropy(counts: Iterable[int | float]) -> float:
    """Entropia di Shannon normalizzata tra 0 e 1."""
    values = [float(value) for value in counts if float(value) > 0]
    total = sum(values)
    if total <= 0 or len(values) <= 1:
        return 0.0
    probabilities = [value / total for value in values]
    entropy = -sum(probability * math.log(probability) for probability in probabilities)
    return entropy / math.log(9)


def decade_index(number: int) -> int:
    return (int(number) - 1) // 10


def draw_structure_rows(history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for draw in sorted(history, key=lambda item: item["date"]):
        combo = tuple(sorted(int(number) for number in draw["numbers"]))
        features = combination_features(combo)
        decade_counts = [0] * 9
        for number in combo:
            decade_counts[decade_index(number)] += 1
        rows.append(
            {
                "Data": draw["date"].strftime("%d/%m/%Y"),
                "Anno": int(draw["year"]),
                "Concorso": int(draw["contest"]),
                "Somma": features["sum"],
                "Pari": features["even"],
                "Dispari": 6 - features["even"],
                "Numeri ≤31": features["low"],
                "Decine": features["decades"],
                "Consecutivi": features["consecutive_pairs"],
                "Ampiezza": features["span"],
                "Entropia decine": normalized_entropy(decade_counts),
            }
        )
    return rows


def _describe(values: list[float]) -> dict[str, float]:
    if not values:
        return {"media": 0.0, "mediana": 0.0, "deviazione": 0.0, "minimo": 0.0, "massimo": 0.0}
    return {
        "media": mean(values),
        "mediana": median(values),
        "deviazione": pstdev(values),
        "minimo": min(values),
        "massimo": max(values),
    }


def structure_summary(history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = draw_structure_rows(history)
    mapping = {
        "Somma": "Somma",
        "Pari": "Numeri pari",
        "Numeri ≤31": "Numeri fino a 31",
        "Decine": "Decine rappresentate",
        "Consecutivi": "Coppie consecutive",
        "Ampiezza": "Ampiezza min-max",
        "Entropia decine": "Entropia delle decine",
    }
    summary: list[dict[str, Any]] = []
    for field, label in mapping.items():
        stats = _describe([float(row[field]) for row in rows])
        summary.append(
            {
                "Indicatore": label,
                "Media": round(stats["media"], 4),
                "Mediana": round(stats["mediana"], 4),
                "Deviazione": round(stats["deviazione"], 4),
                "Minimo": round(stats["minimo"], 4),
                "Massimo": round(stats["massimo"], 4),
            }
        )
    return summary


def decade_distribution(history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts = [0] * 9
    for draw in history:
        for number in draw["numbers"]:
            counts[decade_index(number)] += 1
    total = sum(counts)
    expected = total / 9 if total else 0.0
    rows = []
    for index, count in enumerate(counts):
        start = index * 10 + 1
        end = min(start + 9, 90)
        rows.append(
            {
                "Decina": f"{start}–{end}",
                "Presenze": count,
                "Quota %": round(100 * count / total, 3) if total else 0.0,
                "Atteso uniforme": round(expected, 2),
                "Scarto": round(count - expected, 2),
            }
        )
    return rows


def pair_frequency_rows(history: list[dict[str, Any]], limit: int = 50) -> list[dict[str, Any]]:
    counter: Counter[tuple[int, int]] = Counter()
    for draw in history:
        counter.update(combinations(sorted(draw["numbers"]), 2))
    expected = len(history) * math.comb(6, 2) / math.comb(90, 2) if history else 0.0
    return [
        {
            "Coppia": f"{pair[0]}–{pair[1]}",
            "N1": pair[0],
            "N2": pair[1],
            "Presenze": count,
            "Quota estrazioni %": round(100 * count / len(history), 3) if history else 0.0,
            "Atteso casuale": round(expected, 3),
            "Scarto dall'atteso": round(count - expected, 3),
        }
        for pair, count in counter.most_common(limit)
    ]


def triplet_frequency_rows(history: list[dict[str, Any]], limit: int = 50) -> list[dict[str, Any]]:
    counter: Counter[tuple[int, int, int]] = Counter()
    for draw in history:
        counter.update(combinations(sorted(draw["numbers"]), 3))
    expected = len(history) * math.comb(6, 3) / math.comb(90, 3) if history else 0.0
    return [
        {
            "Terzina": f"{triple[0]}–{triple[1]}–{triple[2]}",
            "N1": triple[0],
            "N2": triple[1],
            "N3": triple[2],
            "Presenze": count,
            "Quota estrazioni %": round(100 * count / len(history), 3) if history else 0.0,
            "Atteso casuale": round(expected, 4),
            "Scarto dall'atteso": round(count - expected, 4),
        }
        for triple, count in counter.most_common(limit)
    ]


def consecutive_draw_overlap(history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    chronological = sorted(history, key=lambda item: item["date"])
    distribution = Counter()
    details: list[dict[str, Any]] = []
    for previous, current in zip(chronological, chronological[1:]):
        repeated = sorted(set(previous["numbers"]) & set(current["numbers"]))
        distribution[len(repeated)] += 1
        details.append(
            {
                "Data": current["date"].strftime("%d/%m/%Y"),
                "Concorso": f"{current['year']}/{current['contest']}",
                "Ripetuti": len(repeated),
                "Numeri ripetuti": ", ".join(map(str, repeated)) if repeated else "—",
            }
        )
    return [
        {
            "Numeri ripetuti": overlap,
            "Passaggi": distribution.get(overlap, 0),
            "Quota %": round(100 * distribution.get(overlap, 0) / max(1, len(details)), 3),
        }
        for overlap in range(7)
    ]


def annual_number_stability(history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    draws_by_year: Counter[int] = Counter(int(draw["year"]) for draw in history)
    counts: dict[int, Counter[int]] = defaultdict(Counter)
    for draw in history:
        year = int(draw["year"])
        counts[year].update(int(number) for number in draw["numbers"])

    years = sorted(draws_by_year)
    rows: list[dict[str, Any]] = []
    for number in range(1, 91):
        rates = [counts[year][number] / draws_by_year[year] for year in years]
        average_rate = mean(rates) if rates else 0.0
        deviation = pstdev(rates) if rates else 0.0
        cv = deviation / average_rate if average_rate else 0.0
        row: dict[str, Any] = {
            "Numero": number,
            "Frequenza totale": sum(counts[year][number] for year in years),
            "Tasso medio annuo": round(average_rate, 5),
            "Deviazione annua": round(deviation, 5),
            "CV": round(cv, 4),
            "Stabilità": round(1 / (1 + cv), 4),
        }
        for year in years:
            row[str(year)] = round(100 * counts[year][number] / draws_by_year[year], 2)
        rows.append(row)
    return rows


def archive_analytics(history: list[dict[str, Any]], association_limit: int = 50) -> dict[str, Any]:
    if not history:
        raise ValueError("Storico vuoto.")
    return {
        "structure_rows": draw_structure_rows(history),
        "structure_summary": structure_summary(history),
        "decades": decade_distribution(history),
        "pairs": pair_frequency_rows(history, association_limit),
        "triplets": triplet_frequency_rows(history, association_limit),
        "overlaps": consecutive_draw_overlap(history),
        "annual_stability": annual_number_stability(history),
    }
