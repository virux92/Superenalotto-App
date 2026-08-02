from __future__ import annotations

from statistics import mean
from typing import Any, Iterable, Mapping

from core.combinations import combination_features


def coherence_label(stability: float) -> str:
    value = float(stability)
    if value >= 0.67:
        return "Alta"
    if value >= 0.50:
        return "Media"
    return "Bassa"


def build_candidate_profile(
    combo: Iterable[int], state: Mapping[str, Any]
) -> dict[str, Any]:
    numbers = tuple(sorted(int(number) for number in combo))
    if len(numbers) != 6 or len(set(numbers)) != 6:
        raise ValueError("La proposta ORION deve contenere 6 numeri diversi.")

    score = state["score"]
    agreement = state["agreement"]
    structural = state["structural"]
    ranking = sorted(score, key=score.get, reverse=True)
    rank_positions = {number: position for position, number in enumerate(ranking, start=1)}
    features = combination_features(numbers)

    structural_checks = {
        "somma": structural["minimum_sum"] <= features["sum"] <= structural["maximum_sum"],
        "pari_dispari": features["even"] in (2, 3, 4),
        "numeri_bassi": features["low"] <= structural["maximum_low_numbers"],
        "decine": features["decades"] >= structural["minimum_decades"],
    }
    top_twelve = set(ranking[:12])

    return {
        "numbers": numbers,
        "features": features,
        "average_score": mean(float(score[number]) for number in numbers),
        "average_agreement": mean(float(agreement[number]) for number in numbers),
        "top_twelve_count": len(set(numbers).intersection(top_twelve)),
        "best_rank": min(rank_positions[number] for number in numbers),
        "worst_rank": max(rank_positions[number] for number in numbers),
        "structural_checks": structural_checks,
        "structural_ok": all(structural_checks.values()),
    }


def build_orion_brief(state: Mapping[str, Any]) -> dict[str, Any]:
    score = state["score"]
    agreement = state["agreement"]
    ranking = sorted(score, key=score.get, reverse=True)
    stable_ranking = sorted(
        score,
        key=lambda number: (float(score[number]) * float(agreement[number]), score[number]),
        reverse=True,
    )
    return {
        "coherence": coherence_label(float(state["stability"])),
        "top_numbers": ranking[:12],
        "stable_numbers": stable_ranking[:8],
        "memories": [memory["name"] for memory in state["memories"]],
    }
