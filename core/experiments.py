from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from statistics import mean, pstdev
from typing import Any, Iterable

import pandas as pd

from core.backtest import deterministic_random_line
from core.combinations import rank_candidate_sestine
from core.metrics import MetricWeights, calculate_metrics


@dataclass(frozen=True)
class StrategyProfile:
    """Configurazione immutabile di una strategia sperimentale."""

    name: str
    frequency_weight: float
    delay_weight: float
    recency_weight: float

    @property
    def weights(self) -> MetricWeights:
        return MetricWeights(
            frequency=self.frequency_weight,
            delay=self.delay_weight,
            recency=self.recency_weight,
        ).normalized()


DEFAULT_PROFILES: tuple[StrategyProfile, ...] = (
    StrategyProfile("Bilanciato", 0.35, 0.25, 0.40),
    StrategyProfile("Frequenza", 0.60, 0.15, 0.25),
    StrategyProfile("Recenza", 0.20, 0.15, 0.65),
    StrategyProfile("Ritardo", 0.20, 0.60, 0.20),
    StrategyProfile("Frequenza + recenza", 0.45, 0.10, 0.45),
    StrategyProfile("Ritardo + recenza", 0.15, 0.45, 0.40),
)


def profiles_by_name() -> dict[str, StrategyProfile]:
    return {profile.name: profile for profile in DEFAULT_PROFILES}


def _chronological_records(
    raw_records: tuple[tuple[Any, ...], ...],
) -> list[dict[str, Any]]:
    return [
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


def _fallback_prediction(scores: dict[int, float]) -> tuple[int, ...]:
    return tuple(sorted(sorted(scores, key=scores.get, reverse=True)[:6]))


def _confidence_interval(values: list[float]) -> tuple[float, float]:
    if not values:
        return 0.0, 0.0
    average = mean(values)
    deviation = pstdev(values)
    standard_error = deviation / math.sqrt(len(values))
    return average - 1.96 * standard_error, average + 1.96 * standard_error


def _annual_stability(years: dict[int, list[int]]) -> float:
    annual_averages = [mean(values) for values in years.values() if values]
    return pstdev(annual_averages) if len(annual_averages) > 1 else 0.0


def run_experiment_suite(
    raw_records: tuple[tuple[Any, ...], ...],
    profiles: Iterable[StrategyProfile],
    window_size: int,
    test_limit: int,
    pool_size: int,
    minimum_sum: int,
    maximum_sum: int,
    maximum_low_numbers: int,
    minimum_decades: int,
    random_seed: int = 20260726,
) -> dict[str, Any]:
    """Confronta profili prefissati con backtest walk-forward senza look-ahead.

    Ogni previsione usa esclusivamente le ``window_size`` estrazioni precedenti.
    Il confronto casuale è deterministico e condiviso tra tutti i profili,
    così il delta è appaiato estrazione per estrazione.
    """

    selected_profiles = tuple(profiles)
    if not selected_profiles:
        raise ValueError("Selezionare almeno un profilo sperimentale.")
    if len({profile.name for profile in selected_profiles}) != len(selected_profiles):
        raise ValueError("I nomi dei profili devono essere univoci.")
    if window_size < 10:
        raise ValueError("La finestra storica deve contenere almeno 10 estrazioni.")
    if test_limit < 1:
        raise ValueError("Il numero di test deve essere almeno 1.")
    if pool_size < 6:
        raise ValueError("Il pool deve contenere almeno 6 numeri.")
    if minimum_sum >= maximum_sum:
        raise ValueError("La somma minima deve essere inferiore alla massima.")

    chronological = _chronological_records(raw_records)
    if len(chronological) <= window_size:
        raise ValueError("Archivio insufficiente per la finestra storica scelta.")

    first_target = max(window_size, len(chronological) - test_limit)
    profile_hits: dict[str, list[int]] = {
        profile.name: [] for profile in selected_profiles
    }
    profile_excess: dict[str, list[int]] = {
        profile.name: [] for profile in selected_profiles
    }
    annual_hits: dict[str, dict[int, list[int]]] = defaultdict(
        lambda: defaultdict(list)
    )
    random_hits: list[int] = []
    details: list[dict[str, Any]] = []

    for target_index in range(first_target, len(chronological)):
        history = list(
            reversed(chronological[target_index - window_size : target_index])
        )
        target = chronological[target_index]
        target_set = set(target["numbers"])
        random_line = deterministic_random_line(target, random_seed)
        random_hit_count = len(set(random_line) & target_set)
        random_hits.append(random_hit_count)

        for profile in selected_profiles:
            metrics = calculate_metrics(history, profile.weights)
            candidates = rank_candidate_sestine(
                metrics["score"],
                pool_size,
                1,
                minimum_sum,
                maximum_sum,
                maximum_low_numbers,
                minimum_decades,
            )
            prediction = (
                candidates[0][1]
                if candidates
                else _fallback_prediction(metrics["score"])
            )
            hit_count = len(set(prediction) & target_set)
            excess = hit_count - random_hit_count
            profile_hits[profile.name].append(hit_count)
            profile_excess[profile.name].append(excess)
            annual_hits[profile.name][target["year"]].append(hit_count)

            details.append(
                {
                    "Data": target["date"].strftime("%d/%m/%Y"),
                    "Anno": target["year"],
                    "Concorso": f"{target['year']}/{target['contest']}",
                    "Profilo": profile.name,
                    "Pesi F/Rit/Rec": (
                        f"{profile.weights.frequency:.2f} / "
                        f"{profile.weights.delay:.2f} / "
                        f"{profile.weights.recency:.2f}"
                    ),
                    "Estratti": ", ".join(map(str, target["numbers"])),
                    "Pronostico": ", ".join(map(str, prediction)),
                    "Punti": hit_count,
                    "Pronostico casuale": ", ".join(map(str, random_line)),
                    "Punti casuale": random_hit_count,
                    "Delta": excess,
                }
            )

    random_average = mean(random_hits) if random_hits else 0.0
    summary: list[dict[str, Any]] = []
    annual_summary: list[dict[str, Any]] = []

    for profile in selected_profiles:
        hits = profile_hits[profile.name]
        excess_values = profile_excess[profile.name]
        hit_ci = _confidence_interval([float(value) for value in hits])
        excess_ci = _confidence_interval([float(value) for value in excess_values])
        years = annual_hits[profile.name]
        stability = _annual_stability(years)

        summary.append(
            {
                "Profilo": profile.name,
                "Pesi frequenza": profile.weights.frequency,
                "Pesi ritardo": profile.weights.delay,
                "Pesi recenza": profile.weights.recency,
                "Test": len(hits),
                "Media punti": mean(hits) if hits else 0.0,
                "IC95% punti min": max(0.0, hit_ci[0]),
                "IC95% punti max": min(6.0, hit_ci[1]),
                "Media casuale": random_average,
                "Delta medio": mean(excess_values) if excess_values else 0.0,
                "IC95% delta min": excess_ci[0],
                "IC95% delta max": excess_ci[1],
                "2+": sum(value >= 2 for value in hits),
                "3+": sum(value >= 3 for value in hits),
                "Vittorie vs casuale": sum(value > 0 for value in excess_values),
                "Pareggi vs casuale": sum(value == 0 for value in excess_values),
                "Sconfitte vs casuale": sum(value < 0 for value in excess_values),
                "Instabilità annuale": stability,
            }
        )

        for year, values in sorted(years.items()):
            annual_summary.append(
                {
                    "Profilo": profile.name,
                    "Anno": year,
                    "Test": len(values),
                    "Media punti": mean(values) if values else 0.0,
                    "2+": sum(value >= 2 for value in values),
                    "3+": sum(value >= 3 for value in values),
                }
            )

    summary.sort(
        key=lambda row: (
            row["Delta medio"],
            row["2+"],
            -row["Instabilità annuale"],
            row["Media punti"],
        ),
        reverse=True,
    )
    for rank, row in enumerate(summary, start=1):
        row["Posizione campione"] = rank

    return {
        "summary": summary,
        "annual_summary": annual_summary,
        "details": details,
        "best_profile": summary[0]["Profilo"] if summary else None,
        "test_count": len(random_hits),
        "window_size": window_size,
        "random_seed": random_seed,
        "random_average": random_average,
        "random_2_plus": sum(value >= 2 for value in random_hits),
        "random_3_plus": sum(value >= 3 for value in random_hits),
        "profiles": [profile.name for profile in selected_profiles],
    }
