from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from statistics import mean
from typing import Any, Mapping

import pandas as pd

from core.backtest import records_tuple
from core.experiments import paired_bootstrap_ci
from core.forge import PROSPECTIVE_MINIMUM
from core.superstar_models import (
    SUPERSTAR_CHALLENGERS,
    SUPERSTAR_CHAMPION,
    SuperStarModelSpec,
    generate_superstar_forecast,
)
from services.draw_service import dataframe_to_history

SUPERSTAR_FORGE_VERSION = "3.0.0"


def superstar_archive_signature(archive: pd.DataFrame) -> str:
    columns = ["data", "anno", "concorso", "superstar"]
    canonical = archive.sort_values(["data", "anno", "concorso"])[columns].copy()
    canonical["data"] = pd.to_datetime(canonical["data"]).dt.strftime("%Y-%m-%d")
    return hashlib.sha256(
        canonical.to_csv(index=False, lineterminator="\n").encode("utf-8")
    ).hexdigest()


def _chronological(raw_records: tuple[tuple[Any, ...], ...]) -> list[dict[str, Any]]:
    return [
        {
            "date": pd.Timestamp(row[0]),
            "year": int(row[1]),
            "contest": int(row[2]),
            "numbers": [int(value) for value in row[3:9]],
            "jolly": None if int(row[9]) == 0 else int(row[9]),
            "superstar": int(row[10]),
        }
        for row in raw_records
    ]


def _binomial_upper_tail(hits: int, count: int, probability: float = 1 / 90) -> float:
    if count <= 0:
        return 1.0
    # Ricorrenza stabile per la coda binomiale, senza dipendenze scientifiche.
    term = (1.0 - probability) ** count
    cumulative = term if hits > 0 else 0.0
    for successes in range(1, count + 1):
        term *= (count - successes + 1) / successes * probability / (1.0 - probability)
        if successes < hits:
            cumulative += term
    return max(0.0, min(1.0, 1.0 - cumulative))


def _walk_forward_hits(
    chronological: list[dict[str, Any]],
    indices: list[int],
    spec: SuperStarModelSpec,
) -> list[int]:
    hits = []
    for target_index in indices:
        history = list(reversed(chronological[:target_index]))
        predicted = generate_superstar_forecast(history, spec).predicted
        hits.append(int(predicted == int(chronological[target_index]["superstar"])))
    return hits


@lru_cache(maxsize=4)
def run_superstar_historical_validation(
    raw_records: tuple[tuple[Any, ...], ...],
) -> dict[str, Any]:
    """Backtest walk-forward su tutto lo storico, con holdout finale intatto."""
    chronological = _chronological(raw_records)
    warmup = 50
    available = len(chronological) - warmup
    if available < 40:
        raise ValueError("Archivio insufficiente per il laboratorio SuperStar.")
    holdout_count = min(100, max(20, available // 4))
    development_indices = list(range(warmup, len(chronological) - holdout_count))
    holdout_indices = list(range(len(chronological) - holdout_count, len(chronological)))

    champion_development = _walk_forward_hits(
        chronological, development_indices, SUPERSTAR_CHAMPION
    )
    development: list[dict[str, Any]] = []
    for spec in SUPERSTAR_CHALLENGERS:
        hits = _walk_forward_hits(chronological, development_indices, spec)
        development.append(
            {
                "spec": spec,
                "count": len(hits),
                "hits": sum(hits),
                "hit_rate": mean(hits) if hits else 0.0,
                "delta_vs_champion": (
                    mean([candidate - champion for candidate, champion in zip(hits, champion_development)])
                    if hits
                    else 0.0
                ),
            }
        )
    eligible = [row for row in development if row["spec"].eligible_for_promotion]
    eligible.sort(
        key=lambda row: (row["hits"], row["delta_vs_champion"], row["spec"].model_id),
        reverse=True,
    )
    selected_spec = eligible[0]["spec"]
    champion_holdout = _walk_forward_hits(
        chronological, holdout_indices, SUPERSTAR_CHAMPION
    )
    challenger_holdout = _walk_forward_hits(
        chronological, holdout_indices, selected_spec
    )
    differences = [
        challenger - champion
        for challenger, champion in zip(challenger_holdout, champion_holdout)
    ]
    ci_min, ci_max = paired_bootstrap_ci(differences, seed=9075)
    all_records = []
    for row in development:
        spec = row.pop("spec")
        record = {
            **row,
            "model_id": spec.model_id,
            "label": spec.label,
            "family": spec.family,
            "configuration": spec.configuration,
            "selected_for_holdout": spec.model_id == selected_spec.model_id,
        }
        if record["selected_for_holdout"]:
            record.update(
                {
                    "holdout_count": len(challenger_holdout),
                    "holdout_hits": sum(challenger_holdout),
                    "holdout_hit_rate": mean(challenger_holdout),
                    "champion_holdout_hits": sum(champion_holdout),
                    "champion_holdout_hit_rate": mean(champion_holdout),
                    "holdout_delta": mean(differences) if differences else 0.0,
                    "holdout_ci_min": ci_min,
                    "holdout_ci_max": ci_max,
                    "p_value_vs_uniform": _binomial_upper_tail(
                        sum(challenger_holdout), len(challenger_holdout)
                    ),
                }
            )
        all_records.append(record)
    return {
        "history_count": len(chronological),
        "development_count": len(development_indices),
        "holdout_count": len(holdout_indices),
        "selected_model": selected_spec.configuration | {"model_id": selected_spec.model_id},
        "records": all_records,
        "champion_holdout": {
            "count": len(champion_holdout),
            "hits": sum(champion_holdout),
            "hit_rate": mean(champion_holdout),
        },
        "uniform_exact_rate": 1 / 90,
    }


def _registered_before_target(created_at: object, target_date: object) -> bool:
    if created_at is None or target_date is None:
        return False
    registered = pd.Timestamp(created_at)
    if registered.tzinfo is None:
        registered = registered.tz_localize("UTC")
    cutoff = pd.Timestamp(
        f"{pd.Timestamp(target_date).date().isoformat()} 20:00:00",
        tz="Europe/Rome",
    )
    return bool(registered < cutoff)


def _prediction_key(signature: str, role: str, model_id: str) -> str:
    material = f"{SUPERSTAR_FORGE_VERSION}:{signature}:{role}:{model_id}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _model_from_payload(payload: Mapping[str, Any] | None) -> SuperStarModelSpec:
    if not payload:
        return SUPERSTAR_CHAMPION
    model_id = str(payload.get("model_id", ""))
    for spec in (SUPERSTAR_CHAMPION, *SUPERSTAR_CHALLENGERS):
        if spec.model_id == model_id:
            return spec
    return SUPERSTAR_CHAMPION


def _evaluate_pending(archive: pd.DataFrame) -> int:
    from database import (
        evaluate_forge_superstar_prediction,
        fetch_pending_forge_superstar_predictions,
    )

    pending = fetch_pending_forge_superstar_predictions(SUPERSTAR_FORGE_VERSION)
    chronological = archive.sort_values(["data", "anno", "concorso"])
    evaluated = 0
    for row in pending:
        future = chronological.loc[chronological["data"] > pd.Timestamp(row["source_date"])]
        if future.empty:
            continue
        target = future.iloc[0]
        saved = evaluate_forge_superstar_prediction(
            str(row["prediction_key"]),
            target_year=int(target["anno"]),
            target_contest=int(target["concorso"]),
            target_date=pd.Timestamp(target["data"]).date(),
            target_superstar=int(target["superstar"]),
            superstar_hit=int(row["predicted_superstar"]) == int(target["superstar"]),
        )
        evaluated += bool(saved)
    return evaluated


def _prospective(champion_id: str, challenger_id: str | None) -> dict[str, Any]:
    from database import fetch_evaluated_forge_superstar_predictions

    rows = fetch_evaluated_forge_superstar_predictions(SUPERSTAR_FORGE_VERSION)
    champion_rows = [
        row
        for row in rows
        if str(row.get("role")) == "champion"
        and str(row.get("model_id")) == champion_id
        and row.get("superstar_hit") is not None
        and _registered_before_target(row.get("created_at"), row.get("target_date"))
    ]
    champion_observations = {
        "champion_count": len(champion_rows),
        "champion_hits": sum(bool(row["superstar_hit"]) for row in champion_rows),
        "champion_hit_rate": (
            sum(bool(row["superstar_hit"]) for row in champion_rows) / len(champion_rows)
            if champion_rows
            else 0.0
        ),
    }
    if not challenger_id:
        return {
            "count": 0,
            "minimum": PROSPECTIVE_MINIMUM,
            "decision": "waiting_challenger",
            **champion_observations,
        }
    grouped: dict[tuple[int, int, int, int], dict[str, dict[str, Any]]] = {}
    for row in rows:
        if not _registered_before_target(row.get("created_at"), row.get("target_date")):
            continue
        role = str(row["role"])
        if role == "champion" and str(row["model_id"]) != champion_id:
            continue
        if role == "challenger" and str(row["model_id"]) != challenger_id:
            continue
        key = (
            int(row["source_year"]),
            int(row["source_contest"]),
            int(row["target_year"]),
            int(row["target_contest"]),
        )
        grouped.setdefault(key, {})[role] = dict(row)
    pairs = [value for value in grouped.values() if {"champion", "challenger"} <= value.keys()]
    differences = [
        int(pair["challenger"]["superstar_hit"]) - int(pair["champion"]["superstar_hit"])
        for pair in pairs
    ]
    ci_min, ci_max = paired_bootstrap_ci(differences, seed=3490)
    count = len(pairs)
    delta = mean(differences) if differences else 0.0
    decision = "collecting"
    if count >= PROSPECTIVE_MINIMUM and delta > 0 and ci_min > 0:
        decision = "promote"
    elif count >= PROSPECTIVE_MINIMUM * 2 and ci_max < 0:
        decision = "reject"
    return {
        "count": count,
        "minimum": PROSPECTIVE_MINIMUM,
        "decision": decision,
        "average_delta": delta,
        "ci_min": ci_min,
        "ci_max": ci_max,
        "paired_champion_hits": sum(bool(pair["champion"]["superstar_hit"]) for pair in pairs),
        "challenger_hits": sum(bool(pair["challenger"]["superstar_hit"]) for pair in pairs),
        **champion_observations,
    }


def build_superstar_forge_snapshot(archive: pd.DataFrame) -> dict[str, Any]:
    signature = superstar_archive_signature(archive)
    history = dataframe_to_history(archive)
    validation = run_superstar_historical_validation(records_tuple(archive))
    selected = _model_from_payload(validation["selected_model"])
    champion = SUPERSTAR_CHAMPION
    challenger: SuperStarModelSpec | None = selected
    persistence_error = None
    evaluated_now = saved_now = voided_now = 0
    prospective = {"count": 0, "minimum": PROSPECTIVE_MINIMUM, "decision": "persistence_unavailable"}
    try:
        from database import (
            fetch_forge_superstar_experiments,
            fetch_forge_superstar_state,
            save_forge_superstar_experiment,
            save_forge_superstar_prediction,
            save_forge_superstar_state,
            void_obsolete_pending_forge_superstar_predictions,
        )

        existing_experiment_keys = {
            str(row["experiment_key"])
            for row in fetch_forge_superstar_experiments(
                signature, SUPERSTAR_FORGE_VERSION
            )
        }
        for record in validation["records"]:
            experiment_key = hashlib.sha256(
                f"{signature}:{SUPERSTAR_FORGE_VERSION}:{record['model_id']}".encode("utf-8")
            ).hexdigest()
            if experiment_key in existing_experiment_keys:
                continue
            save_forge_superstar_experiment(
                {
                    "experiment_key": experiment_key,
                    "archive_signature": signature,
                    "forge_version": SUPERSTAR_FORGE_VERSION,
                    **record,
                }
            )
        state = fetch_forge_superstar_state()
        if state:
            champion = _model_from_payload(state.get("champion_model"))
            stored_challenger = _model_from_payload(state.get("challenger_model"))
            if stored_challenger.model_id != champion.model_id:
                challenger = stored_challenger
        evaluated_now = _evaluate_pending(archive)
        prospective = _prospective(
            champion.model_id, None if challenger is None else challenger.model_id
        )
        if challenger and prospective["decision"] == "promote":
            champion = challenger
            challenger = selected if selected.model_id != champion.model_id else None
        save_forge_superstar_state(
            {
                "mode": "promoted" if champion.model_id != SUPERSTAR_CHAMPION.model_id else "shadow",
                "champion_model": champion.configuration | {"model_id": champion.model_id},
                "challenger_model": (
                    None
                    if challenger is None
                    else challenger.configuration | {"model_id": challenger.model_id}
                ),
                "prospective_minimum": PROSPECTIVE_MINIMUM,
                "note": "Il backtest storico seleziona lo shadow; solo dati prospettici promuovono.",
            }
        )
        latest = archive.sort_values(["data", "anno", "concorso"]).iloc[-1]
        models = [("champion", champion)]
        if challenger:
            models.append(("challenger", challenger))
        keep = [_prediction_key(signature, role, spec.model_id) for role, spec in models]
        voided_now = len(
            void_obsolete_pending_forge_superstar_predictions(
                forge_version=SUPERSTAR_FORGE_VERSION,
                source_year=int(latest["anno"]),
                source_contest=int(latest["concorso"]),
                keep_prediction_keys=keep,
            )
        )
        for role, spec in models:
            forecast = generate_superstar_forecast(history, spec)
            saved = save_forge_superstar_prediction(
                {
                    "prediction_key": _prediction_key(signature, role, spec.model_id),
                    "archive_signature": signature,
                    "forge_version": SUPERSTAR_FORGE_VERSION,
                    "source_year": int(latest["anno"]),
                    "source_contest": int(latest["concorso"]),
                    "source_date": pd.Timestamp(latest["data"]).date(),
                    "role": role,
                    "model_id": spec.model_id,
                    "model_config": spec.configuration,
                    "predicted_superstar": forecast.predicted,
                }
            )
            saved_now += bool(saved.get("inserted"))
    except Exception as exc:
        persistence_error = f"{type(exc).__name__}: {exc}"

    active_forecast = generate_superstar_forecast(history, champion)
    return {
        "engine": "FORGE-SUPERSTAR",
        "version": SUPERSTAR_FORGE_VERSION,
        "archive_signature": signature,
        "active_model": champion.configuration | {"model_id": champion.model_id},
        "challenger_model": (
            None if challenger is None else challenger.configuration | {"model_id": challenger.model_id}
        ),
        "ranking": list(active_forecast.ranking),
        "predicted": active_forecast.predicted,
        "historical_validation": validation,
        "prospective": prospective,
        "persistence_ok": persistence_error is None,
        "persistence_error": persistence_error,
        "evaluated_now": evaluated_now,
        "saved_now": saved_now,
        "voided_now": voided_now,
    }
