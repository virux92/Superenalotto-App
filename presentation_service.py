from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import pandas as pd

from core.backtest import records_tuple
from core.experiments import run_experiment_suite
from core.forge import (
    ForgeModel,
    build_candidate_models,
    choose_active_model,
    evaluate_candidate,
    experiment_key,
)
from services.archive_service import archive_snapshot

REGISTRY_FILE = Path(__file__).resolve().parents[1] / ".forge_registry.json"


def _read_local_registry() -> dict[str, dict[str, Any]]:
    if not REGISTRY_FILE.exists():
        return {}
    try:
        payload = json.loads(REGISTRY_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_local_registry(records: dict[str, dict[str, Any]]) -> None:
    temporary = REGISTRY_FILE.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(records, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    temporary.replace(REGISTRY_FILE)


def _load_database_records(archive_signature: str) -> tuple[dict[str, dict[str, Any]], bool]:
    try:
        from database import fetch_forge_experiments

        rows = fetch_forge_experiments(archive_signature)
    except Exception:
        return {}, False
    return {str(row["experiment_key"]): dict(row) for row in rows}, True


def _save_database_record(record: dict[str, Any]) -> bool:
    try:
        from database import save_forge_experiment

        save_forge_experiment(record)
    except Exception:
        return False
    return True


def _group_unseen_models(
    models: tuple[ForgeModel, ...],
    known: dict[str, dict[str, Any]],
    archive_signature: str,
) -> dict[int, list[ForgeModel]]:
    grouped: dict[int, list[ForgeModel]] = defaultdict(list)
    for model in models:
        key = experiment_key(model, archive_signature)
        if key not in known:
            grouped[model.window_size].append(model)
    return grouped


def build_forge_snapshot(archive: pd.DataFrame) -> dict[str, Any]:
    """Esegue FORGE senza esporre parametri tecnici all'utente."""

    snapshot = archive_snapshot(archive)
    archive_signature = str(snapshot["sha256"])
    models = build_candidate_models(len(archive))

    local_records = _read_local_registry()
    database_records, database_registry = _load_database_records(archive_signature)
    known: dict[str, dict[str, Any]] = {
        key: value
        for key, value in local_records.items()
        if value.get("archive_signature") == archive_signature
    }
    known.update(database_records)

    structural_min = 150
    structural_max = 390
    low_max = 5
    decades_min = 3
    raw = records_tuple(archive)
    executed = 0
    failed = 0

    grouped = _group_unseen_models(models, known, archive_signature)
    for window_size, candidates in grouped.items():
        if not candidates:
            continue
        try:
            suite = run_experiment_suite(
                raw_records=raw,
                profiles=[model.as_strategy_profile() for model in candidates],
                window_size=int(window_size),
                test_limit=min(model.test_limit for model in candidates),
                pool_size=12,
                minimum_sum=structural_min,
                maximum_sum=structural_max,
                maximum_low_numbers=low_max,
                minimum_decades=decades_min,
                random_seed=20260726 + int(window_size),
            )
            summaries = {row["Profilo"]: row for row in suite["summary"]}
        except Exception as exc:
            for model in candidates:
                key = experiment_key(model, archive_signature)
                record = {
                    "experiment_key": key,
                    "archive_signature": archive_signature,
                    "model_id": model.model_id,
                    "status": "failed",
                    "quality": None,
                    "configuration": model.configuration,
                    "metrics": {},
                    "checks": {},
                    "reason": f"{type(exc).__name__}: {exc}",
                }
                known[key] = record
                local_records[key] = record
                _save_database_record(record)
                failed += 1
            continue

        for model in candidates:
            key = experiment_key(model, archive_signature)
            summary = summaries.get(model.model_id)
            if summary is None:
                record = {
                    "experiment_key": key,
                    "archive_signature": archive_signature,
                    "model_id": model.model_id,
                    "status": "failed",
                    "quality": None,
                    "configuration": model.configuration,
                    "metrics": {},
                    "checks": {},
                    "reason": "Risultato del backtest non disponibile.",
                }
                failed += 1
            else:
                record = evaluate_candidate(
                    model,
                    summary,
                    random_2_plus=int(suite["random_2_plus"]),
                )
                record.update(
                    {
                        "experiment_key": key,
                        "archive_signature": archive_signature,
                        "reason": None,
                    }
                )
                executed += 1
            known[key] = record
            local_records[key] = record
            _save_database_record(record)

    try:
        _write_local_registry(local_records)
    except OSError:
        pass

    current_records = [
        record
        for record in known.values()
        if record.get("archive_signature") == archive_signature
    ]
    active = choose_active_model(current_records)

    # Se nessun candidato supera il gate, FORGE non promuove un modello fallito:
    # ORION usa il profilo bilanciato incorporato e segnala lo stato protetto.
    state = "stable" if active else "protected"
    return {
        "engine": "FORGE",
        "archive_signature": archive_signature,
        "state": state,
        "active_model": active,
        "candidate_count": len(models),
        "valid_count": sum(row.get("status") == "valid" for row in current_records),
        "rejected_count": sum(row.get("status") == "rejected" for row in current_records),
        "failed_count": sum(row.get("status") == "failed" for row in current_records),
        "executed_now": executed,
        "failed_now": failed,
        "skipped_known": len(models) - sum(len(value) for value in grouped.values()),
        "registry": "Supabase + locale" if database_registry else "locale",
    }
