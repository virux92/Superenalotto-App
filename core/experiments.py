from __future__ import annotations

import math
import random
from collections import defaultdict
from dataclasses import dataclass
from statistics import mean, pstdev
from typing import Any, Iterable, Sequence

import pandas as pd

from core.backtest import deterministic_random_line, random_hit_probabilities
from core.metrics import DEFAULT_WEIGHTS, MetricWeights
from core.orion import DEFAULT_POLICY, generate_orion_proposal


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
    StrategyProfile("Frequenza controllata", 0.50, 0.20, 0.30),
    StrategyProfile("Recenza controllata", 0.25, 0.20, 0.55),
    StrategyProfile("Ritardo controllato", 0.25, 0.50, 0.25),
    StrategyProfile("Frequenza e recenza", 0.45, 0.10, 0.45),
    StrategyProfile("Ritardo e recenza", 0.15, 0.45, 0.40),
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


def _confidence_interval(values: Sequence[float]) -> tuple[float, float]:
    if not values:
        return 0.0, 0.0
    average = mean(values)
    deviation = pstdev(values)
    standard_error = deviation / math.sqrt(len(values))
    return average - 1.96 * standard_error, average + 1.96 * standard_error


def paired_bootstrap_ci(
    differences: Sequence[float],
    *,
    seed: int = 274,
    repetitions: int = 2000,
) -> tuple[float, float]:
    """Intervallo bootstrap deterministico della differenza media appaiata."""
    values = [float(value) for value in differences]
    if not values:
        return 0.0, 0.0
    if len(values) == 1:
        return values[0], values[0]
    generator = random.Random(int(seed))
    sample_size = len(values)
    averages = []
    for _ in range(max(200, int(repetitions))):
        averages.append(
            sum(values[generator.randrange(sample_size)] for _ in range(sample_size))
            / sample_size
        )
    averages.sort()
    lower_index = max(0, round((len(averages) - 1) * 0.025))
    upper_index = min(len(averages) - 1, round((len(averages) - 1) * 0.975))
    return averages[lower_index], averages[upper_index]


def _annual_stability(years: dict[int, list[int]]) -> float | None:
    annual_averages = [mean(values) for values in years.values() if values]
    return pstdev(annual_averages) if len(annual_averages) > 1 else None


def _prediction_for_profile(
    chronological: list[dict[str, Any]],
    target_index: int,
    profile: StrategyProfile,
) -> tuple[int, ...]:
    # Stesso identico storico e stesso identico pipeline della produzione live.
    history = list(reversed(chronological[:target_index]))
    return tuple(
        generate_orion_proposal(
            history,
            metric_weights=profile.weights,
            policy=DEFAULT_POLICY,
        )["primary"]
    )


def _evaluate_profile_range(
    chronological: list[dict[str, Any]],
    target_indices: Sequence[int],
    profile: StrategyProfile,
) -> dict[str, Any]:
    hits: list[int] = []
    years: dict[int, list[int]] = defaultdict(list)
    details: list[dict[str, Any]] = []
    for target_index in target_indices:
        target = chronological[target_index]
        prediction = _prediction_for_profile(chronological, target_index, profile)
        hit_count = len(set(prediction) & set(target["numbers"]))
        hits.append(hit_count)
        years[target["year"]].append(hit_count)
        details.append(
            {
                "Data": target["date"].strftime("%d/%m/%Y"),
                "Anno": target["year"],
                "Concorso": f"{target['year']}/{target['contest']}",
                "Profilo": profile.name,
                "Pronostico": ", ".join(map(str, prediction)),
                "Estratti": ", ".join(map(str, target["numbers"])),
                "Punti": hit_count,
            }
        )
    ci = _confidence_interval([float(value) for value in hits])
    return {
        "hits": hits,
        "details": details,
        "test_count": len(hits),
        "mean_hits": mean(hits) if hits else 0.0,
        "ci_min": max(0.0, ci[0]),
        "ci_max": min(6.0, ci[1]),
        "two_plus": sum(value >= 2 for value in hits),
        "three_plus": sum(value >= 3 for value in hits),
        "annual_stability": _annual_stability(years),
    }


def _simulated_random_baseline(
    chronological: list[dict[str, Any]],
    target_indices: Sequence[int],
    *,
    seed: int,
    simulations: int = 64,
) -> dict[str, float]:
    simulation_means: list[float] = []
    simulation_two_plus: list[float] = []
    for offset in range(max(16, int(simulations))):
        hits = []
        for target_index in target_indices:
            target = chronological[target_index]
            line = deterministic_random_line(target, seed + offset * 1009)
            hits.append(len(set(line) & set(target["numbers"])))
        simulation_means.append(mean(hits) if hits else 0.0)
        simulation_two_plus.append(sum(value >= 2 for value in hits))
    simulation_means.sort()
    lower = simulation_means[round((len(simulation_means) - 1) * 0.025)]
    upper = simulation_means[round((len(simulation_means) - 1) * 0.975)]
    return {
        "mean": mean(simulation_means) if simulation_means else 0.4,
        "mean_ci_min": lower,
        "mean_ci_max": upper,
        "two_plus_mean": mean(simulation_two_plus) if simulation_two_plus else 0.0,
    }


def run_nested_orion_validation(
    raw_records: tuple[tuple[Any, ...], ...],
    profiles: Iterable[StrategyProfile],
    *,
    development_limit: int = 40,
    holdout_limit: int = 40,
    random_seed: int = 20260726,
) -> dict[str, Any]:
    """Seleziona sullo sviluppo e verifica su un holdout successivo.

    Tutte le previsioni vengono generate da ``generate_orion_proposal``: non
    esiste più un algoritmo proxy separato. Il challenger viene scelto usando
    esclusivamente il blocco di sviluppo; il blocco holdout resta esterno alla
    scelta e serve soltanto a decidere se il candidato può entrare in shadow.
    """
    candidates = tuple(profiles)
    if not candidates:
        raise ValueError("FORGE richiede almeno un modello challenger.")
    if len({profile.name for profile in candidates}) != len(candidates):
        raise ValueError("I nomi dei profili devono essere univoci.")

    chronological = _chronological_records(raw_records)
    minimum_warmup = max(25, DEFAULT_POLICY.minimum_history)
    requested = int(development_limit) + int(holdout_limit)
    available_tests = len(chronological) - minimum_warmup
    if available_tests < 20:
        raise ValueError("Archivio insufficiente per la validazione annidata di FORGE.")
    total_tests = min(requested, available_tests)
    holdout_count = min(int(holdout_limit), max(10, total_tests // 2))
    development_count = total_tests - holdout_count
    if development_count < 10:
        development_count = 10
        holdout_count = total_tests - development_count

    first_target = len(chronological) - total_tests
    development_indices = list(range(first_target, first_target + development_count))
    holdout_indices = list(range(first_target + development_count, len(chronological)))

    champion = StrategyProfile(
        "ORION-BALANCED",
        DEFAULT_WEIGHTS.frequency,
        DEFAULT_WEIGHTS.delay,
        DEFAULT_WEIGHTS.recency,
    )
    champion_development = _evaluate_profile_range(
        chronological, development_indices, champion
    )

    development_rows: list[dict[str, Any]] = []
    development_results: dict[str, dict[str, Any]] = {}
    for profile in candidates:
        result = _evaluate_profile_range(chronological, development_indices, profile)
        development_results[profile.name] = result
        differences = [
            candidate - baseline
            for candidate, baseline in zip(result["hits"], champion_development["hits"])
        ]
        delta_ci = paired_bootstrap_ci(
            differences,
            seed=random_seed + sum(map(ord, profile.name)),
        )
        development_rows.append(
            {
                "Profilo": profile.name,
                "Test sviluppo": result["test_count"],
                "Media sviluppo": result["mean_hits"],
                "Delta vs champion sviluppo": mean(differences) if differences else 0.0,
                "IC95 delta sviluppo min": delta_ci[0],
                "IC95 delta sviluppo max": delta_ci[1],
                "2+ sviluppo": result["two_plus"],
                "3+ sviluppo": result["three_plus"],
                "Instabilità annuale sviluppo": result["annual_stability"],
            }
        )

    development_rows.sort(
        key=lambda row: (
            row["Delta vs champion sviluppo"],
            row["2+ sviluppo"],
            row["Media sviluppo"],
            row["Profilo"],
        ),
        reverse=True,
    )
    selected_name = str(development_rows[0]["Profilo"])
    selected_profile = next(profile for profile in candidates if profile.name == selected_name)

    champion_holdout = _evaluate_profile_range(chronological, holdout_indices, champion)
    challenger_holdout = _evaluate_profile_range(
        chronological, holdout_indices, selected_profile
    )
    holdout_differences = [
        challenger - baseline
        for challenger, baseline in zip(
            challenger_holdout["hits"], champion_holdout["hits"]
        )
    ]
    holdout_delta_ci = paired_bootstrap_ci(
        holdout_differences,
        seed=random_seed + 274,
    )
    random_baseline = _simulated_random_baseline(
        chronological,
        holdout_indices,
        seed=random_seed,
    )
    probabilities = random_hit_probabilities()

    records: list[dict[str, Any]] = []
    rows_by_name = {str(row["Profilo"]): row for row in development_rows}
    for profile in candidates:
        development = rows_by_name[profile.name]
        metrics: dict[str, Any] = dict(development)
        selected = profile.name == selected_name
        if selected:
            metrics.update(
                {
                    "Selezionato per holdout": True,
                    "Test holdout": challenger_holdout["test_count"],
                    "Media holdout": challenger_holdout["mean_hits"],
                    "Media champion holdout": champion_holdout["mean_hits"],
                    "Delta vs champion holdout": (
                        mean(holdout_differences) if holdout_differences else 0.0
                    ),
                    "IC95 delta holdout min": holdout_delta_ci[0],
                    "IC95 delta holdout max": holdout_delta_ci[1],
                    "2+ holdout": challenger_holdout["two_plus"],
                    "2+ champion holdout": champion_holdout["two_plus"],
                    "3+ holdout": challenger_holdout["three_plus"],
                    "Instabilità annuale holdout": challenger_holdout[
                        "annual_stability"
                    ],
                }
            )
        else:
            metrics["Selezionato per holdout"] = False
        records.append(
            {
                "profile": profile,
                "selected": selected,
                "metrics": metrics,
            }
        )

    return {
        "records": records,
        "selected_profile": selected_name,
        "development_count": development_count,
        "holdout_count": holdout_count,
        "champion_holdout": champion_holdout,
        "challenger_holdout": challenger_holdout,
        "holdout_differences": holdout_differences,
        "holdout_delta_ci": holdout_delta_ci,
        "random_baseline": random_baseline,
        "theoretical_random_mean": 0.4,
        "theoretical_random_2_plus": holdout_count
        * sum(probability for hits, probability in probabilities.items() if hits >= 2),
        "details": champion_holdout["details"] + challenger_holdout["details"],
    }


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
    """Compatibilità con la vecchia API, ora basata sul pipeline ORION live.

    I parametri ``pool_size`` e filtri strutturali non vengono più applicati:
    la policy live è l'unica fonte di verità. ``window_size`` resta soltanto
    nella firma per non spezzare vecchi strumenti, ma lo storico usato è tutto
    quello disponibile prima di ciascun target, esattamente come nell'app.
    """
    del window_size, pool_size, minimum_sum, maximum_sum
    del maximum_low_numbers, minimum_decades

    selected_profiles = tuple(profiles)
    chronological = _chronological_records(raw_records)
    if not selected_profiles:
        raise ValueError("Selezionare almeno un profilo sperimentale.")
    if test_limit < 1:
        raise ValueError("Il numero di test deve essere almeno 1.")
    first_target = max(6, len(chronological) - int(test_limit))
    target_indices = list(range(first_target, len(chronological)))

    random_hits = []
    for target_index in target_indices:
        target = chronological[target_index]
        random_line = deterministic_random_line(target, random_seed)
        random_hits.append(len(set(random_line) & set(target["numbers"])))
    random_average = mean(random_hits) if random_hits else 0.0

    summary: list[dict[str, Any]] = []
    details: list[dict[str, Any]] = []
    annual_summary: list[dict[str, Any]] = []
    for profile in selected_profiles:
        result = _evaluate_profile_range(chronological, target_indices, profile)
        excess = [hit - baseline for hit, baseline in zip(result["hits"], random_hits)]
        delta_ci = _confidence_interval([float(value) for value in excess])
        summary.append(
            {
                "Profilo": profile.name,
                "Pesi frequenza": profile.weights.frequency,
                "Pesi ritardo": profile.weights.delay,
                "Pesi recenza": profile.weights.recency,
                "Test": result["test_count"],
                "Media punti": result["mean_hits"],
                "Media casuale": random_average,
                "Delta medio": mean(excess) if excess else 0.0,
                "IC95% delta min": delta_ci[0],
                "IC95% delta max": delta_ci[1],
                "2+": result["two_plus"],
                "3+": result["three_plus"],
                "Vittorie vs casuale": sum(value > 0 for value in excess),
                "Pareggi vs casuale": sum(value == 0 for value in excess),
                "Sconfitte vs casuale": sum(value < 0 for value in excess),
                "Instabilità annuale": result["annual_stability"],
            }
        )
        for row, random_hit in zip(result["details"], random_hits):
            details.append(
                {
                    **row,
                    "Punti casuale": random_hit,
                    "Delta": int(row["Punti"]) - random_hit,
                }
            )

    summary.sort(
        key=lambda row: (row["Delta medio"], row["2+"], row["Media punti"]),
        reverse=True,
    )
    for rank, row in enumerate(summary, start=1):
        row["Posizione campione"] = rank

    return {
        "summary": summary,
        "annual_summary": annual_summary,
        "details": details,
        "best_profile": summary[0]["Profilo"] if summary else None,
        "test_count": len(target_indices),
        "random_seed": random_seed,
        "random_average": random_average,
        "random_2_plus": sum(value >= 2 for value in random_hits),
        "random_3_plus": sum(value >= 3 for value in random_hits),
        "profiles": [profile.name for profile in selected_profiles],
    }
