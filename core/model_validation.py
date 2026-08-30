from __future__ import annotations

from collections import defaultdict
from statistics import mean, pstdev
from typing import Any, Iterable, Sequence

import pandas as pd

from core.backtest import deterministic_random_line, random_hit_probabilities
from core.experiments import paired_bootstrap_ci
from core.model_contracts import ModelSpec
from core.number_models import generate_number_forecast
from core.orion import DEFAULT_POLICY, generate_orion_proposal


def _records(raw_records: tuple[tuple[Any, ...], ...]) -> list[dict[str, Any]]:
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


def _prediction(
    chronological: list[dict[str, Any]], target_index: int, model: ModelSpec | None
) -> tuple[int, ...]:
    history = list(reversed(chronological[:target_index]))
    if model is None:
        # Champion ORION: chiamata identica alla produzione, senza alcuna modifica.
        return tuple(generate_orion_proposal(history, policy=DEFAULT_POLICY)["primary"])
    return tuple(generate_number_forecast(history, model).numbers)


def _evaluate(
    chronological: list[dict[str, Any]],
    indices: Sequence[int],
    model: ModelSpec | None,
) -> dict[str, Any]:
    hits: list[int] = []
    years: dict[int, list[int]] = defaultdict(list)
    for target_index in indices:
        target = chronological[target_index]
        prediction = _prediction(chronological, target_index, model)
        hit_count = len(set(prediction) & set(target["numbers"]))
        hits.append(hit_count)
        years[int(target["year"])].append(hit_count)
    annual = [mean(values) for values in years.values() if values]
    return {
        "hits": hits,
        "test_count": len(hits),
        "mean_hits": mean(hits) if hits else 0.0,
        "two_plus": sum(value >= 2 for value in hits),
        "three_plus": sum(value >= 3 for value in hits),
        "annual_stability": pstdev(annual) if len(annual) > 1 else None,
    }


def _random_baseline(
    chronological: list[dict[str, Any]], indices: Sequence[int], seed: int
) -> dict[str, float]:
    simulation_means: list[float] = []
    for offset in range(32):
        values = []
        for target_index in indices:
            target = chronological[target_index]
            line = deterministic_random_line(target, seed + offset * 1009)
            values.append(len(set(line) & set(target["numbers"])))
        simulation_means.append(mean(values) if values else 0.0)
    simulation_means.sort()
    return {
        "mean": mean(simulation_means) if simulation_means else 0.4,
        "mean_ci_min": simulation_means[1] if simulation_means else 0.0,
        "mean_ci_max": simulation_means[-2] if simulation_means else 0.0,
    }


def run_nested_model_validation(
    raw_records: tuple[tuple[Any, ...], ...],
    models: Iterable[ModelSpec],
    *,
    development_limit: int = 40,
    holdout_limit: int = 40,
    random_seed: int = 20260726,
) -> dict[str, Any]:
    """Torneo walk-forward: selezione su sviluppo, verifica su holdout esterno."""
    candidates = tuple(models)
    if not candidates:
        raise ValueError("FORGE richiede almeno un challenger.")
    chronological = _records(raw_records)
    warmup = max(50, DEFAULT_POLICY.minimum_history)
    available = len(chronological) - warmup
    if available < 20:
        raise ValueError("Archivio insufficiente per la validazione FORGE v3.")
    total = min(int(development_limit) + int(holdout_limit), available)
    holdout_count = min(int(holdout_limit), max(10, total // 2))
    development_count = total - holdout_count
    if development_count < 10:
        development_count = 10
        holdout_count = total - development_count
    first = len(chronological) - total
    development_indices = list(range(first, first + development_count))
    holdout_indices = list(range(first + development_count, len(chronological)))

    champion_development = _evaluate(chronological, development_indices, None)
    development_rows: list[dict[str, Any]] = []
    for model in candidates:
        result = _evaluate(chronological, development_indices, model)
        differences = [
            candidate - champion
            for candidate, champion in zip(result["hits"], champion_development["hits"])
        ]
        ci_min, ci_max = paired_bootstrap_ci(
            differences, seed=random_seed + sum(map(ord, model.label))
        )
        development_rows.append(
            {
                "model": model,
                "Profilo": model.label,
                "Test sviluppo": result["test_count"],
                "Media sviluppo": result["mean_hits"],
                "Delta vs champion sviluppo": mean(differences) if differences else 0.0,
                "IC95 delta sviluppo min": ci_min,
                "IC95 delta sviluppo max": ci_max,
                "2+ sviluppo": result["two_plus"],
                "3+ sviluppo": result["three_plus"],
                "Instabilità annuale sviluppo": result["annual_stability"],
            }
        )
    promotable = [
        row for row in development_rows if row["model"].eligible_for_promotion
    ]
    promotable.sort(
        key=lambda row: (
            row["Delta vs champion sviluppo"],
            row["2+ sviluppo"],
            row["Media sviluppo"],
            row["Profilo"],
        ),
        reverse=True,
    )
    selected = promotable[0]["model"]
    champion_holdout = _evaluate(chronological, holdout_indices, None)
    challenger_holdout = _evaluate(chronological, holdout_indices, selected)
    differences = [
        candidate - champion
        for candidate, champion in zip(
            challenger_holdout["hits"], champion_holdout["hits"]
        )
    ]
    holdout_ci = paired_bootstrap_ci(differences, seed=random_seed + 274)

    records: list[dict[str, Any]] = []
    for row in development_rows:
        model = row.pop("model")
        metrics = dict(row)
        is_selected = model.model_id == selected.model_id
        metrics["Selezionato per holdout"] = is_selected
        if is_selected:
            metrics.update(
                {
                    "Test holdout": challenger_holdout["test_count"],
                    "Media holdout": challenger_holdout["mean_hits"],
                    "Media champion holdout": champion_holdout["mean_hits"],
                    "Delta vs champion holdout": mean(differences) if differences else 0.0,
                    "IC95 delta holdout min": holdout_ci[0],
                    "IC95 delta holdout max": holdout_ci[1],
                    "2+ holdout": challenger_holdout["two_plus"],
                    "2+ champion holdout": champion_holdout["two_plus"],
                    "3+ holdout": challenger_holdout["three_plus"],
                    "Instabilità annuale holdout": challenger_holdout["annual_stability"],
                }
            )
        records.append({"profile": model, "selected": is_selected, "metrics": metrics})

    return {
        "records": records,
        "selected_profile": selected.label,
        "development_count": development_count,
        "holdout_count": holdout_count,
        "champion_holdout": champion_holdout,
        "challenger_holdout": challenger_holdout,
        "random_baseline": _random_baseline(
            chronological, holdout_indices, random_seed
        ),
        "exact_random_probabilities": random_hit_probabilities(),
    }
