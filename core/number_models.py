from __future__ import annotations

import hashlib
import heapq
import json
import math
from itertools import combinations
from typing import Any, Mapping

from core.combinations import combination_quality, passes_structural_filters
from core.metrics import min_max_scale
from core.model_contracts import ModelSpec, NumberForecast
from core.orion import DEFAULT_POLICY, calculate_orion_state, generate_orion_proposal


def _history_signature(history: list[dict[str, Any]]) -> str:
    payload = [
        {
            "date": str(draw.get("date", "")),
            "year": draw.get("year"),
            "contest": draw.get("contest"),
            "numbers": sorted(int(value) for value in draw["numbers"]),
        }
        for draw in history
    ]
    material = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _uniform_hash_scores(history: list[dict[str, Any]], model_id: str) -> dict[int, float]:
    signature = _history_signature(history)
    return {
        number: int(
            hashlib.sha256(f"{model_id}:{signature}:{number}".encode("utf-8")).hexdigest()[:16],
            16,
        )
        / float(0xFFFFFFFFFFFFFFFF)
        for number in range(1, 91)
    }


def _bayes_scores(history: list[dict[str, Any]], alpha: float) -> dict[int, float]:
    counts = {number: 0.0 for number in range(1, 91)}
    for draw in history:
        for number in draw["numbers"]:
            counts[int(number)] += 1.0
    denominator = len(history) + float(alpha)
    prior_inclusions = float(alpha) * (6.0 / 90.0)
    posterior = {
        number: (counts[number] + prior_inclusions) / denominator
        for number in range(1, 91)
    }
    return min_max_scale(posterior)


def _rolling_scores(history: list[dict[str, Any]], window: int, alpha: float) -> dict[int, float]:
    return _bayes_scores(history[: max(6, int(window))], alpha)


def _multi_ema_scores(
    history: list[dict[str, Any]], half_lives: tuple[float, ...]
) -> dict[int, float]:
    combined = {number: 0.0 for number in range(1, 91)}
    for half_life in half_lives:
        decay = math.log(2.0) / max(1.0, float(half_life))
        values = {number: 0.0 for number in range(1, 91)}
        normalizer = 0.0
        for age, draw in enumerate(history):
            weight = math.exp(-decay * age)
            normalizer += weight
            for number in draw["numbers"]:
                values[int(number)] += weight
        if normalizer:
            for number in values:
                combined[number] += values[number] / normalizer
    divisor = max(1, len(half_lives))
    return min_max_scale({number: value / divisor for number, value in combined.items()})


def _pair_scores(
    history: list[dict[str, Any]], *, window: int, shrinkage: float
) -> dict[tuple[int, int], float]:
    sample = history[: max(6, int(window))]
    counts = {pair: 0.0 for pair in combinations(range(1, 91), 2)}
    for draw in sample:
        for pair in combinations(sorted(int(value) for value in draw["numbers"]), 2):
            counts[pair] += 1.0
    # Una coppia casuale compare con probabilita' C(6,2)/C(90,2).
    prior = 15.0 / 4005.0
    denominator = len(sample) + float(shrinkage)
    posterior = {
        pair: (value + float(shrinkage) * prior) / denominator
        for pair, value in counts.items()
    }
    return min_max_scale(posterior)


def _rank_from_scores(
    history: list[dict[str, Any]],
    scores: dict[int, float],
    *,
    pair_scores: Mapping[tuple[int, int], float] | None = None,
    pair_weight: float = 0.0,
) -> tuple[tuple[int, ...], list[tuple[float, tuple[int, ...]]], dict[str, Any]]:
    base_state = calculate_orion_state(history, DEFAULT_POLICY)
    structural = base_state["structural"]
    pool = sorted(scores, key=scores.get, reverse=True)[: DEFAULT_POLICY.candidate_pool]
    heap: list[tuple[float, tuple[int, ...]]] = []
    for raw in combinations(pool, 6):
        combo = tuple(sorted(raw))
        if not passes_structural_filters(
            combo,
            structural["minimum_sum"],
            structural["maximum_sum"],
            structural["maximum_low_numbers"],
            structural["minimum_decades"],
        ):
            continue
        quality = combination_quality(combo, scores)
        if pair_scores:
            quality += float(pair_weight) * sum(
                pair_scores[pair] for pair in combinations(combo, 2)
            ) / 15.0
        item = (quality, combo)
        if len(heap) < DEFAULT_POLICY.candidate_limit:
            heapq.heappush(heap, item)
        elif item > heap[0]:
            heapq.heapreplace(heap, item)
    ranked = sorted(heap, key=lambda item: (item[0], item[1]), reverse=True)
    if not ranked:
        fallback = tuple(sorted(sorted(scores, key=scores.get, reverse=True)[:6]))
        ranked = [(sum(scores[number] for number in fallback), fallback)]
    return ranked[0][1], ranked, structural


def generate_number_forecast(
    history: list[dict[str, Any]], spec: ModelSpec
) -> NumberForecast:
    """Genera una previsione target-free secondo il contratto FORGE v3."""
    if len(history) < DEFAULT_POLICY.minimum_history:
        raise ValueError("Storico insufficiente per un modello FORGE v3.")

    family = spec.family
    parameters = dict(spec.parameters)
    if family == "orion_champion":
        proposal = generate_orion_proposal(history, policy=DEFAULT_POLICY)
        return NumberForecast(
            spec.model_id,
            family,
            tuple(proposal["primary"]),
            proposal["score"],
            {"structural": proposal["structural"]},
        )
    if family == "uniform_hash":
        scores = _uniform_hash_scores(history, spec.model_id)
    elif family == "bayes_dirichlet":
        scores = _bayes_scores(history, float(parameters.get("alpha", 1.0)))
    elif family == "rolling_frequency":
        scores = _rolling_scores(
            history,
            int(parameters.get("window", 90)),
            float(parameters.get("alpha", 1.0)),
        )
    elif family == "multi_ema":
        scores = _multi_ema_scores(
            history,
            tuple(float(value) for value in parameters.get("half_lives", (12, 40, 120))),
        )
    elif family == "pair_shrink":
        scores = _bayes_scores(history, float(parameters.get("alpha", 1.0)))
        pairs = _pair_scores(
            history,
            window=int(parameters.get("window", 200)),
            shrinkage=float(parameters.get("shrinkage", 20.0)),
        )
        numbers, ranked, structural = _rank_from_scores(
            history,
            scores,
            pair_scores=pairs,
            pair_weight=float(parameters.get("pair_weight", 0.18)),
        )
        return NumberForecast(
            spec.model_id,
            family,
            numbers,
            scores,
            {"candidates": ranked, "structural": structural},
        )
    else:
        raise ValueError(f"Famiglia FORGE sconosciuta: {family}")

    numbers, ranked, structural = _rank_from_scores(history, scores)
    return NumberForecast(
        spec.model_id,
        family,
        numbers,
        scores,
        {"candidates": ranked, "structural": structural},
    )
