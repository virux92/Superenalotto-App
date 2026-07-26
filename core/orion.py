from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from statistics import mean, pstdev
from typing import Any

from core.combinations import combination_features
from core.metrics import calculate_metrics, min_max_scale


@dataclass(frozen=True)
class OrionMemory:
    name: str
    size: int | None
    weight: float


@dataclass(frozen=True)
class OrionPolicy:
    version: str = "1.0.0"
    memories: tuple[OrionMemory, ...] = (
        OrionMemory("Breve", 25, 0.10),
        OrionMemory("Operativa", 50, 0.20),
        OrionMemory("Intermedia", 100, 0.30),
        OrionMemory("Lunga", 200, 0.25),
        OrionMemory("Storica", None, 0.15),
    )
    minimum_history: int = 50
    candidate_pool: int = 25
    candidate_limit: int = 300


DEFAULT_POLICY = OrionPolicy()


def _available_memories(history_length: int, policy: OrionPolicy) -> list[OrionMemory]:
    memories = [
        memory
        for memory in policy.memories
        if memory.size is None or memory.size <= history_length
    ]
    if not memories:
        memories = [OrionMemory("Disponibile", history_length, 1.0)]
    total = sum(memory.weight for memory in memories)
    return [OrionMemory(m.name, m.size, m.weight / total) for m in memories]


def _structural_profile(history: list[dict[str, Any]]) -> dict[str, int]:
    features = [combination_features(tuple(sorted(draw["numbers"]))) for draw in history]
    sums = sorted(item["sum"] for item in features)
    if not sums:
        return {
            "minimum_sum": 200,
            "maximum_sum": 340,
            "maximum_low_numbers": 4,
            "minimum_decades": 4,
        }

    def percentile(values: list[int], fraction: float) -> int:
        index = min(len(values) - 1, max(0, round((len(values) - 1) * fraction)))
        return int(values[index])

    decade_values = sorted(item["decades"] for item in features)
    low_values = sorted(item["low"] for item in features)
    return {
        "minimum_sum": percentile(sums, 0.10),
        "maximum_sum": percentile(sums, 0.90),
        "maximum_low_numbers": max(3, percentile(low_values, 0.90)),
        "minimum_decades": max(3, percentile(decade_values, 0.20)),
    }


def calculate_orion_state(
    history: list[dict[str, Any]], policy: OrionPolicy = DEFAULT_POLICY
) -> dict[str, Any]:
    """Calcola il consenso multi-finestra di ORION senza parametri utente.

    Lo storico deve essere ordinato dal concorso più recente al più vecchio.
    Ogni memoria produce metriche indipendenti; il punteggio finale premia il
    consenso e penalizza l'instabilità tra finestre.
    """
    if len(history) < 6:
        raise ValueError("Servono almeno 6 estrazioni per inizializzare ORION.")

    memories = _available_memories(len(history), policy)
    memory_metrics: dict[str, dict[str, dict[int, float]]] = {}
    weighted_scores = {number: 0.0 for number in range(1, 91)}
    score_series = {number: [] for number in range(1, 91)}

    for memory in memories:
        sample = history if memory.size is None else history[: memory.size]
        metrics = calculate_metrics(sample)
        memory_metrics[memory.name] = metrics
        for number in range(1, 91):
            value = float(metrics["score"][number])
            weighted_scores[number] += memory.weight * value
            score_series[number].append(value)

    instability = {
        number: pstdev(values) if len(values) > 1 else 0.0
        for number, values in score_series.items()
    }
    instability_norm = min_max_scale(instability)
    consensus = {
        number: max(0.0, weighted_scores[number] * (1.0 - 0.18 * instability_norm[number]))
        for number in range(1, 91)
    }
    consensus = min_max_scale(consensus)

    agreement = {
        number: 1.0 - min(1.0, instability_norm[number])
        for number in range(1, 91)
    }
    overall_stability = mean(agreement.values()) if agreement else 0.0

    return {
        "engine": "ORION",
        "version": policy.version,
        "history_size": len(history),
        "status": "STABILE" if overall_stability >= 0.60 else "OSSERVAZIONE",
        "stability": overall_stability,
        "score": consensus,
        "agreement": agreement,
        "memory_metrics": memory_metrics,
        "memories": [asdict(memory) for memory in memories],
        "structural": _structural_profile(history),
        "candidate_pool": policy.candidate_pool,
        "candidate_limit": policy.candidate_limit,
    }


def orion_signature(state: dict[str, Any]) -> str:
    ranked = sorted(state["score"], key=state["score"].get, reverse=True)[:12]
    material = ":".join(map(str, ranked))
    checksum = sum((index + 1) * number for index, number in enumerate(ranked)) % 10000
    return f"OR-{state['version']}-{checksum:04d}"
