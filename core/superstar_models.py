from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from core.metrics import calculate_superstar_ranking, min_max_scale
from core.model_contracts import SuperStarForecast, stable_identifier


@dataclass(frozen=True)
class SuperStarModelSpec:
    label: str
    family: str
    parameters: Mapping[str, Any] = field(default_factory=dict)
    eligible_for_promotion: bool = True

    @property
    def configuration(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "family": self.family,
            "parameters": dict(self.parameters),
            "eligible_for_promotion": self.eligible_for_promotion,
        }

    @property
    def model_id(self) -> str:
        if self.family == "legacy_orion":
            return "SUPERSTAR-LEGACY-V1"
        return stable_identifier("SUPERSTAR", self.configuration)


SUPERSTAR_CHAMPION = SuperStarModelSpec(
    "SuperStar ORION protetto", "legacy_orion"
)
SUPERSTAR_CHALLENGERS: tuple[SuperStarModelSpec, ...] = (
    SuperStarModelSpec("Bayes storico SuperStar", "bayes", {"alpha": 1.0}),
    SuperStarModelSpec("Frequenza mobile 30", "rolling", {"window": 30, "alpha": 1.0}),
    SuperStarModelSpec("Multi-EMA SuperStar", "multi_ema", {"half_lives": (8, 24, 72)}),
    SuperStarModelSpec(
        "Controllo uniforme deterministico",
        "uniform_hash",
        {},
        eligible_for_promotion=False,
    ),
)


def _signature(history: list[dict[str, Any]]) -> str:
    material = json.dumps(
        [
            {
                "date": str(draw.get("date", "")),
                "year": draw.get("year"),
                "contest": draw.get("contest"),
                "superstar": int(draw["superstar"]),
            }
            for draw in history
        ],
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _ranking(scores: dict[int, float], history: list[dict[str, Any]]) -> tuple[tuple[int, float, int, int], ...]:
    frequency = {number: 0 for number in range(1, 91)}
    delay = {number: len(history) for number in range(1, 91)}
    for position, draw in enumerate(history):
        number = int(draw["superstar"])
        frequency[number] += 1
        if delay[number] == len(history):
            delay[number] = position
    return tuple(
        sorted(
            (
                (number, float(scores[number]), frequency[number], delay[number])
                for number in range(1, 91)
            ),
            key=lambda item: (item[1], item[2], item[3], item[0]),
            reverse=True,
        )
    )


def generate_superstar_forecast(
    history: list[dict[str, Any]], spec: SuperStarModelSpec
) -> SuperStarForecast:
    if not history:
        raise ValueError("Storico SuperStar vuoto.")
    if spec.family == "legacy_orion":
        ranking = tuple(calculate_superstar_ranking(history))
    elif spec.family == "uniform_hash":
        signature = _signature(history)
        scores = {
            number: int(
                hashlib.sha256(
                    f"{spec.model_id}:{signature}:{number}".encode("utf-8")
                ).hexdigest()[:16],
                16,
            )
            / float(0xFFFFFFFFFFFFFFFF)
            for number in range(1, 91)
        }
        ranking = _ranking(scores, history)
    else:
        sample = history
        if spec.family == "rolling":
            sample = history[: max(6, int(spec.parameters.get("window", 30)))]
        scores = {number: 0.0 for number in range(1, 91)}
        if spec.family in ("bayes", "rolling"):
            alpha = float(spec.parameters.get("alpha", 1.0))
            for draw in sample:
                scores[int(draw["superstar"])] += 1.0
            scores = {
                number: (value + alpha / 90.0) / (len(sample) + alpha)
                for number, value in scores.items()
            }
        elif spec.family == "multi_ema":
            half_lives = tuple(
                float(value) for value in spec.parameters.get("half_lives", (8, 24, 72))
            )
            for half_life in half_lives:
                decay = math.log(2.0) / max(1.0, half_life)
                normalizer = 0.0
                local = {number: 0.0 for number in range(1, 91)}
                for age, draw in enumerate(history):
                    weight = math.exp(-decay * age)
                    normalizer += weight
                    local[int(draw["superstar"])] += weight
                for number in local:
                    scores[number] += local[number] / normalizer
        else:
            raise ValueError(f"Famiglia SuperStar sconosciuta: {spec.family}")
        ranking = _ranking(min_max_scale(scores), history)
    return SuperStarForecast(
        model_id=spec.model_id,
        predicted=int(ranking[0][0]),
        ranking=ranking,
        metadata={"family": spec.family, "configuration": spec.configuration},
    )


def assign_distinct_superstars(
    ranking: Sequence[tuple[int, float, int, int]], line_count: int
) -> list[int]:
    """Assegna un SuperStar diverso a ogni schedina finche' possibile."""
    if line_count < 0:
        raise ValueError("Il numero di schedine non può essere negativo.")
    ordered = list(dict.fromkeys(int(item[0]) for item in ranking))
    if not ordered and line_count:
        raise ValueError("Ranking SuperStar vuoto.")
    return [ordered[index % len(ordered)] for index in range(line_count)]
