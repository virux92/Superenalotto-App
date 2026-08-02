from __future__ import annotations

import hashlib
import json
from pathlib import Path
from statistics import mean
from typing import Any, Iterable, Mapping

import pandas as pd

from core.backtest import records_tuple
from core.experiments import paired_bootstrap_ci, run_nested_orion_validation
from core.forge import (
    FORGE_VERSION,
    PROSPECTIVE_MINIMUM,
    ForgeModel,
    build_candidate_models,
    choose_shadow_challenger,
    default_champion_record,
    evaluate_validation_record,
    experiment_key,
    weights_from_record,
)
from core.orion import DEFAULT_POLICY, generate_orion_proposal
from services.draw_service import dataframe_to_history

REGISTRY_FILE = Path(__file__).resolve().parents[1] / ".forge_registry_v2.json"


def main_numbers_signature(archive: pd.DataFrame) -> str:
    """Firma soltanto i dati usati dal motore dei sei numeri.

    Jolly e SuperStar non invalidano più inutilmente tutti i backtest FORGE.
    """
    columns = ["data", "anno", "concorso", "n1", "n2", "n3", "n4", "n5", "n6"]
    canonical = archive.sort_values(["data", "anno", "concorso"])[columns].copy()
    canonical["data"] = pd.to_datetime(canonical["data"]).dt.strftime("%Y-%m-%d")
    payload = canonical.to_csv(index=False, lineterminator="\n").encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _read_local_registry() -> dict[str, dict[str, Any]]:
    if not REGISTRY_FILE.exists():
        return {}
    try:
        payload = json.loads(REGISTRY_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_local_registry(records: Mapping[str, Mapping[str, Any]]) -> None:
    temporary = REGISTRY_FILE.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(records, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    temporary.replace(REGISTRY_FILE)


def _load_database_context(
    archive_signature: str,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any] | None, str | None]:
    try:
        from database import fetch_forge_experiments_v2, fetch_forge_state

        rows = fetch_forge_experiments_v2(archive_signature, FORGE_VERSION)
        state = fetch_forge_state()
    except Exception as exc:  # diagnostica restituita all'interfaccia
        return {}, None, f"{type(exc).__name__}: {exc}"
    return {str(row["experiment_key"]): dict(row) for row in rows}, (
        None if state is None else dict(state)
    ), None


def _save_database_experiment(record: Mapping[str, Any]) -> str | None:
    try:
        from database import save_forge_experiment_v2

        save_forge_experiment_v2(record)
    except Exception as exc:
        return f"{type(exc).__name__}: {exc}"
    return None


def _save_database_state(record: Mapping[str, Any]) -> str | None:
    try:
        from database import save_forge_state

        save_forge_state(record)
    except Exception as exc:
        return f"{type(exc).__name__}: {exc}"
    return None


def _evaluate_pending_predictions(archive: pd.DataFrame) -> tuple[int, str | None]:
    try:
        from database import evaluate_forge_prediction, fetch_pending_forge_predictions

        pending = fetch_pending_forge_predictions()
    except Exception as exc:
        return 0, f"{type(exc).__name__}: {exc}"

    chronological = archive.sort_values(["data", "anno", "concorso"]).copy()
    evaluated = 0
    try:
        for prediction in pending:
            source_year = int(prediction["source_year"])
            source_contest = int(prediction["source_contest"])
            future = chronological.loc[
                (chronological["anno"] > source_year)
                | (
                    (chronological["anno"] == source_year)
                    & (chronological["concorso"] > source_contest)
                )
            ]
            if future.empty:
                continue
            target = future.iloc[0]
            predicted = {
                int(prediction[f"n{index}"]) for index in range(1, 7)
            }
            extracted = {int(target[f"n{index}"]) for index in range(1, 7)}
            evaluate_forge_prediction(
                str(prediction["prediction_key"]),
                target_year=int(target["anno"]),
                target_contest=int(target["concorso"]),
                target_date=pd.Timestamp(target["data"]).date(),
                hits=len(predicted & extracted),
            )
            evaluated += 1
    except Exception as exc:
        return evaluated, f"{type(exc).__name__}: {exc}"
    return evaluated, None


def _paired_prospective_results(
    champion_model_id: str,
    challenger_model_id: str,
) -> tuple[list[dict[str, Any]], str | None]:
    try:
        from database import fetch_evaluated_forge_predictions

        rows = fetch_evaluated_forge_predictions()
    except Exception as exc:
        return [], f"{type(exc).__name__}: {exc}"

    grouped: dict[str, dict[str, dict[str, Any]]] = {}
    for row in rows:
        signature = str(row["archive_signature"])
        role = str(row["role"])
        model_id = str(row["model_id"])
        if role == "champion" and model_id != champion_model_id:
            continue
        if role == "challenger" and model_id != challenger_model_id:
            continue
        grouped.setdefault(signature, {})[role] = dict(row)

    pairs = []
    for signature, values in grouped.items():
        if "champion" not in values or "challenger" not in values:
            continue
        champion = values["champion"]
        challenger = values["challenger"]
        pairs.append(
            {
                "archive_signature": signature,
                "champion_hits": int(champion["hits"]),
                "challenger_hits": int(challenger["hits"]),
                "difference": int(challenger["hits"]) - int(champion["hits"]),
                "target_date": challenger.get("target_date"),
            }
        )
    pairs.sort(key=lambda row: str(row.get("target_date", "")))
    return pairs, None


def _prospective_assessment(
    champion: Mapping[str, Any],
    challenger: Mapping[str, Any] | None,
    minimum: int,
) -> tuple[dict[str, Any], str | None]:
    if not challenger:
        return {
            "count": 0,
            "minimum": int(minimum),
            "decision": "waiting_challenger",
        }, None

    pairs, error = _paired_prospective_results(
        str(champion["model_id"]), str(challenger["model_id"])
    )
    if error:
        return {
            "count": 0,
            "minimum": int(minimum),
            "decision": "persistence_error",
        }, error

    differences = [float(row["difference"]) for row in pairs]
    ci_min, ci_max = paired_bootstrap_ci(differences, seed=2740)
    champion_hits = [int(row["champion_hits"]) for row in pairs]
    challenger_hits = [int(row["challenger_hits"]) for row in pairs]
    count = len(pairs)
    average_delta = mean(differences) if differences else 0.0
    decision = "collecting"
    if count >= int(minimum):
        if (
            average_delta > 0.0
            and ci_min > 0.0
            and sum(value >= 2 for value in challenger_hits)
            >= sum(value >= 2 for value in champion_hits)
        ):
            decision = "promote"
        elif count >= max(60, int(minimum) * 2) and (
            ci_max < 0.0 or average_delta <= -0.10
        ):
            decision = "reject"
        else:
            decision = "continue_shadow"

    return {
        "count": count,
        "minimum": int(minimum),
        "decision": decision,
        "average_delta": average_delta,
        "ci_min": ci_min,
        "ci_max": ci_max,
        "champion_mean": mean(champion_hits) if champion_hits else 0.0,
        "challenger_mean": mean(challenger_hits) if challenger_hits else 0.0,
        "champion_2_plus": sum(value >= 2 for value in champion_hits),
        "challenger_2_plus": sum(value >= 2 for value in challenger_hits),
    }, None


def _prediction_key(
    archive_signature: str,
    role: str,
    model_id: str,
) -> str:
    material = f"{FORGE_VERSION}:{archive_signature}:{role}:{model_id}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _save_current_predictions(
    archive: pd.DataFrame,
    archive_signature: str,
    champion: Mapping[str, Any],
    challenger: Mapping[str, Any] | None,
) -> tuple[int, str | None]:
    try:
        from database import save_forge_prediction
    except Exception as exc:
        return 0, f"{type(exc).__name__}: {exc}"

    history = dataframe_to_history(archive)
    latest = archive.sort_values(["data", "anno", "concorso"]).iloc[-1]
    models: list[tuple[str, Mapping[str, Any]]] = [("champion", champion)]
    if challenger:
        models.append(("challenger", challenger))

    saved = 0
    try:
        for role, model in models:
            proposal = generate_orion_proposal(
                history,
                metric_weights=weights_from_record(model),
                policy=DEFAULT_POLICY,
            )
            save_forge_prediction(
                {
                    "prediction_key": _prediction_key(
                        archive_signature, role, str(model["model_id"])
                    ),
                    "archive_signature": archive_signature,
                    "forge_version": FORGE_VERSION,
                    "source_year": int(latest["anno"]),
                    "source_contest": int(latest["concorso"]),
                    "source_date": pd.Timestamp(latest["data"]).date(),
                    "role": role,
                    "model_id": str(model["model_id"]),
                    "model_config": model.get("configuration", {}),
                    "numbers": tuple(proposal["primary"]),
                }
            )
            saved += 1
    except Exception as exc:
        return saved, f"{type(exc).__name__}: {exc}"
    return saved, None


def _records_for_current_archive(
    known: Mapping[str, Mapping[str, Any]],
    archive_signature: str,
) -> list[dict[str, Any]]:
    return [
        dict(record)
        for record in known.values()
        if record.get("archive_signature") == archive_signature
        and record.get("forge_version") == FORGE_VERSION
    ]


def build_forge_snapshot(archive: pd.DataFrame) -> dict[str, Any]:
    """Esegue FORGE 2 in modalità champion/challenger persistente.

    Il backtest retrospettivo sceglie soltanto un challenger da osservare. La
    promozione del modello live può avvenire esclusivamente dopo un campione di
    previsioni prospettiche registrate su Supabase prima delle estrazioni.
    """
    archive_signature = main_numbers_signature(archive)
    models = build_candidate_models(len(archive))
    model_by_label = {model.label: model for model in models}

    local_records = _read_local_registry()
    database_records, database_state, persistence_error = _load_database_context(
        archive_signature
    )
    persistence_ok = persistence_error is None

    known: dict[str, dict[str, Any]] = {
        key: dict(value)
        for key, value in local_records.items()
        if value.get("archive_signature") == archive_signature
        and value.get("forge_version") == FORGE_VERSION
    }
    known.update(database_records)

    expected_keys = {experiment_key(model, archive_signature) for model in models}
    missing_keys = expected_keys - set(known)
    executed = 0
    failed = 0
    save_errors: list[str] = []

    if models and missing_keys:
        try:
            suite = run_nested_orion_validation(
                records_tuple(archive),
                [model.as_strategy_profile() for model in models],
                development_limit=40,
                holdout_limit=40,
                random_seed=20260726,
            )
            for item in suite["records"]:
                profile = item["profile"]
                model = model_by_label[profile.name]
                key = experiment_key(model, archive_signature)
                record = evaluate_validation_record(
                    model,
                    item["metrics"],
                    selected_for_holdout=bool(item["selected"]),
                )
                record.update(
                    {
                        "experiment_key": key,
                        "archive_signature": archive_signature,
                        "forge_version": FORGE_VERSION,
                        "reason": None,
                    }
                )
                known[key] = record
                local_records[key] = record
                executed += 1
                if persistence_ok:
                    error = _save_database_experiment(record)
                    if error:
                        save_errors.append(error)
                    else:
                        database_records[key] = record
        except Exception as exc:
            for model in models:
                key = experiment_key(model, archive_signature)
                record = {
                    "experiment_key": key,
                    "archive_signature": archive_signature,
                    "forge_version": FORGE_VERSION,
                    "model_id": model.model_id,
                    "label": model.label,
                    "status": "failed",
                    "quality": None,
                    "configuration": model.configuration,
                    "metrics": {},
                    "checks": {},
                    "reason": f"{type(exc).__name__}: {exc}",
                }
                known[key] = record
                local_records[key] = record
                failed += 1
                if persistence_ok:
                    error = _save_database_experiment(record)
                    if error:
                        save_errors.append(error)
                    else:
                        database_records[key] = record

    try:
        _write_local_registry(local_records)
    except OSError as exc:
        save_errors.append(f"Cache locale: {type(exc).__name__}: {exc}")

    # Se un salvataggio Supabase era fallito in una sessione precedente ma la
    # cache locale è sopravvissuta, ritenta la sincronizzazione. Il database
    # resta la memoria autorevole e non dipende dal filesystem di Streamlit.
    if persistence_ok:
        for key, record in list(known.items()):
            if (
                record.get("archive_signature") == archive_signature
                and record.get("forge_version") == FORGE_VERSION
                and key not in database_records
            ):
                error = _save_database_experiment(record)
                if error:
                    save_errors.append(error)
                else:
                    database_records[key] = dict(record)

    current_records = _records_for_current_archive(known, archive_signature)
    default_champion = default_champion_record()
    champion = default_champion
    challenger: dict[str, Any] | None = None
    mode = "shadow"
    prospective_minimum = PROSPECTIVE_MINIMUM

    if persistence_ok and database_state:
        champion_payload = database_state.get("champion_model")
        if isinstance(champion_payload, dict) and champion_payload.get("model_id"):
            champion = dict(champion_payload)
        challenger_payload = database_state.get("challenger_model")
        if isinstance(challenger_payload, dict) and challenger_payload.get("model_id"):
            challenger = dict(challenger_payload)
        mode = str(database_state.get("mode", "shadow"))
        prospective_minimum = int(
            database_state.get("prospective_minimum", PROSPECTIVE_MINIMUM)
        )

    excluded = {str(champion.get("model_id", "ORION-BALANCED"))}
    if challenger is None:
        challenger = choose_shadow_challenger(
            current_records,
            excluded_model_ids=excluded,
        )

    evaluated_now = 0
    predictions_saved = 0
    prospective: dict[str, Any] = {
        "count": 0,
        "minimum": prospective_minimum,
        "decision": "persistence_unavailable" if not persistence_ok else "collecting",
    }

    if persistence_ok:
        evaluated_now, evaluation_error = _evaluate_pending_predictions(archive)
        if evaluation_error:
            save_errors.append(evaluation_error)
        prospective, assessment_error = _prospective_assessment(
            champion,
            challenger,
            prospective_minimum,
        )
        if assessment_error:
            save_errors.append(assessment_error)

        if challenger and prospective.get("decision") == "promote":
            promoted = dict(challenger)
            promoted["status"] = "promoted"
            champion = promoted
            challenger = choose_shadow_challenger(
                current_records,
                excluded_model_ids={str(champion["model_id"])},
            )
            mode = "promoted"
        elif challenger and prospective.get("decision") == "reject":
            rejected_id = str(challenger["model_id"])
            challenger = choose_shadow_challenger(
                current_records,
                excluded_model_ids={str(champion["model_id"]), rejected_id},
            )
            mode = "shadow"
        else:
            mode = "shadow" if str(champion["model_id"]) == "ORION-BALANCED" else "promoted"

        state_error = _save_database_state(
            {
                "mode": mode,
                "champion_model": champion,
                "challenger_model": challenger,
                "prospective_minimum": prospective_minimum,
                "note": "Promozione consentita solo da risultati prospettici appaiati.",
            }
        )
        if state_error:
            save_errors.append(state_error)

        predictions_saved, prediction_error = _save_current_predictions(
            archive,
            archive_signature,
            champion,
            challenger,
        )
        if prediction_error:
            save_errors.append(prediction_error)

    if save_errors:
        persistence_error = "; ".join(dict.fromkeys(save_errors))
        persistence_ok = False

    state = mode if persistence_ok else "fallback"
    return {
        "engine": "FORGE",
        "version": FORGE_VERSION,
        "archive_signature": archive_signature,
        "state": state,
        "active_model": champion,
        "challenger_model": challenger,
        "candidate_count": len(models),
        "shadow_count": sum(row.get("status") == "shadow" for row in current_records),
        "non_validated_count": sum(
            row.get("status") == "non_validated" for row in current_records
        ),
        "rejected_count": sum(row.get("status") == "rejected" for row in current_records),
        "failed_count": sum(row.get("status") == "failed" for row in current_records),
        "executed_now": executed,
        "failed_now": failed,
        "skipped_known": max(0, len(models) - executed - failed),
        "registry": "Supabase" if persistence_ok else "cache locale non persistente",
        "persistence_ok": persistence_ok,
        "persistence_error": persistence_error,
        "evaluated_predictions_now": evaluated_now,
        "predictions_saved_now": predictions_saved,
        "prospective": prospective,
    }
