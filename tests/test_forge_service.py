from __future__ import annotations

import sys
import types
from pathlib import Path

from services import forge_service
from tests.helpers import synthetic_archive


def _fake_database_module() -> types.ModuleType:
    module = types.ModuleType("database")
    module.experiments = {}
    module.state = None
    module.predictions = {}

    def fetch_forge_experiments_v2(signature: str, version: str):
        return [
            value
            for value in module.experiments.values()
            if value["archive_signature"] == signature
            and value["forge_version"] == version
        ]

    def save_forge_experiment_v2(record):
        module.experiments[record["experiment_key"]] = dict(record)
        return {"experiment_key": record["experiment_key"]}

    def fetch_forge_state():
        return module.state

    def save_forge_state(record):
        module.state = {
            "mode": record["mode"],
            "champion_model": dict(record["champion_model"]),
            "challenger_model": (
                None
                if record.get("challenger_model") is None
                else dict(record["challenger_model"])
            ),
            "prospective_minimum": record["prospective_minimum"],
        }
        return {"mode": record["mode"]}

    def save_forge_prediction(record):
        inserted = record["prediction_key"] not in module.predictions
        module.predictions.setdefault(
            record["prediction_key"],
            {
                **dict(record),
                **{f"n{i}": sorted(record["numbers"])[i - 1] for i in range(1, 7)},
                "status": "pending",
            },
        )
        return {
            "prediction_key": record["prediction_key"],
            "inserted": inserted,
        }

    def fetch_pending_forge_predictions():
        return [
            dict(value)
            for value in module.predictions.values()
            if value["status"] == "pending"
        ]

    def evaluate_forge_prediction(prediction_key: str, **fields):
        module.predictions[prediction_key].update(fields, status="evaluated")
        return {"prediction_key": prediction_key}

    def fetch_evaluated_forge_predictions():
        return [
            dict(value)
            for value in module.predictions.values()
            if value["status"] == "evaluated"
        ]

    module.fetch_forge_experiments_v2 = fetch_forge_experiments_v2
    module.save_forge_experiment_v2 = save_forge_experiment_v2
    module.fetch_forge_state = fetch_forge_state
    module.save_forge_state = save_forge_state
    module.save_forge_prediction = save_forge_prediction
    module.fetch_pending_forge_predictions = fetch_pending_forge_predictions
    module.evaluate_forge_prediction = evaluate_forge_prediction
    module.fetch_evaluated_forge_predictions = fetch_evaluated_forge_predictions
    return module


def test_supabase_registry_survives_local_cache_loss(monkeypatch, tmp_path: Path) -> None:
    fake_database = _fake_database_module()
    monkeypatch.setitem(sys.modules, "database", fake_database)
    registry = tmp_path / ".forge_registry_v2.json"
    monkeypatch.setattr(forge_service, "REGISTRY_FILE", registry)

    archive = synthetic_archive(90)
    first = forge_service.build_forge_snapshot(archive)
    assert first["persistence_ok"] is True
    assert first["executed_now"] == 5
    assert first["active_model"]["model_id"] == "ORION-BALANCED"
    assert len(fake_database.experiments) == 5
    assert fake_database.state is not None
    assert len(fake_database.predictions) in (1, 2)

    registry.unlink(missing_ok=True)  # simula il filesystem perso al reboot
    second = forge_service.build_forge_snapshot(archive)
    assert second["persistence_ok"] is True
    assert second["executed_now"] == 0
    assert second["skipped_known"] == 5
    assert second["active_model"]["model_id"] == "ORION-BALANCED"
    assert second["predictions_saved_now"] == 0

    third = forge_service.build_forge_snapshot(synthetic_archive(91))
    assert third["persistence_ok"] is True
    assert third["evaluated_predictions_now"] == len(fake_database.predictions) - len(
        [value for value in fake_database.predictions.values() if value["status"] == "pending"]
    )
    assert third["prospective"]["count"] == 1


def test_historical_duplicate_records_do_not_pollute_current_counts(
    monkeypatch, tmp_path: Path
) -> None:
    fake_database = _fake_database_module()
    monkeypatch.setitem(sys.modules, "database", fake_database)
    registry = tmp_path / ".forge_registry_v2.json"
    monkeypatch.setattr(forge_service, "REGISTRY_FILE", registry)

    archive = synthetic_archive(90)
    first = forge_service.build_forge_snapshot(archive)
    assert first["candidate_count"] == 5
    assert (
        first["shadow_count"]
        + first["non_validated_count"]
        + first["rejected_count"]
        + first["failed_count"]
        == 5
    )

    # Simula i cinque record ridondanti creati da una vecchia patch che aveva
    # incluso la versione visibile dell'app nella configurazione del modello.
    for index in range(5):
        key = f"stale-{index}"
        fake_database.experiments[key] = {
            "experiment_key": key,
            "archive_signature": first["archive_signature"],
            "forge_version": first["version"],
            "model_id": f"ORION-STALE-{index}",
            "label": f"Storico {index}",
            "status": "shadow" if index == 0 else "non_validated",
            "quality": 999.0 if index == 0 else 0.0,
            "configuration": {},
            "metrics": {},
            "checks": {},
            "reason": None,
        }

    fake_database.state["challenger_model"] = {
        "model_id": "ORION-STALE-0",
        "status": "shadow",
        "configuration": {},
    }

    second = forge_service.build_forge_snapshot(archive)
    assert second["candidate_count"] == 5
    assert (
        second["shadow_count"]
        + second["non_validated_count"]
        + second["rejected_count"]
        + second["failed_count"]
        == 5
    )
    assert second["challenger_model"] is None or not str(
        second["challenger_model"]["model_id"]
    ).startswith("ORION-STALE")
    assert second["executed_now"] == 0
    assert second["skipped_known"] == 5
