from __future__ import annotations

import math
from typing import Any

NUMBER_MIN = 1
NUMBER_MAX = 90
WEIGHT_FREQUENCY = 0.35
WEIGHT_DELAY = 0.25
WEIGHT_RECENCY = 0.40


def min_max_scale(values: dict[int, float]) -> dict[int, float]:
    minimum = min(values.values())
    maximum = max(values.values())
    if math.isclose(minimum, maximum):
        return {key: 0.5 for key in values}
    return {key: (value - minimum) / (maximum - minimum) for key, value in values.items()}


def calculate_metrics(history: list[dict[str, Any]]) -> dict[str, dict[int, float]]:
    if not history:
        raise ValueError("Storico vuoto.")

    draw_count = len(history)
    frequency = {number: 0.0 for number in range(NUMBER_MIN, NUMBER_MAX + 1)}
    delay = {number: float(draw_count) for number in range(NUMBER_MIN, NUMBER_MAX + 1)}
    recency = {number: 0.0 for number in range(NUMBER_MIN, NUMBER_MAX + 1)}

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
        for number in range(NUMBER_MIN, NUMBER_MAX + 1)
    }
    return {"frequency": frequency, "delay": delay, "recency": recency, "score": score}


def calculate_superstar_ranking(history: list[dict[str, Any]]) -> list[tuple[int, float, int, int]]:
    draw_count = len(history)
    frequency = {number: 0.0 for number in range(NUMBER_MIN, NUMBER_MAX + 1)}
    delay = {number: float(draw_count) for number in range(NUMBER_MIN, NUMBER_MAX + 1)}
    recency = {number: 0.0 for number in range(NUMBER_MIN, NUMBER_MAX + 1)}

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
    for number in range(NUMBER_MIN, NUMBER_MAX + 1):
        score = 0.40 * frequency_norm[number] + 0.25 * delay_norm[number] + 0.35 * recency_norm[number]
        ranking.append((number, score, int(frequency[number]), int(delay[number])))
    return sorted(ranking, key=lambda item: (item[1], item[2], item[3]), reverse=True)
