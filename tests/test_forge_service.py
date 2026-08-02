from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

from services import forge_service
from tests.helpers import synthetic_archive



@pytest.fixture(autouse=True)
def _fast_nested_validation(monkeypatch):
    def fake_validation(_records, profiles, **_kwargs):
        output = []
        for index, profile in enumerate(profiles):
            selected = index == 0
            metrics = {
                "Profilo": profile.name,
                "Test sviluppo": 40,
                "Media sviluppo": 0.40,
                "Delta vs champion sviluppo": 0.0,
                "2+ sviluppo": 1,
                "3+ sviluppo": 0,
                "Test holdout": 40 if selected else 0,
                "Media holdout": 0.40 if selected else 0.0,
                "Delta vs champion holdout": 0.0,
                "IC95 delta holdout min": -0.10,
                "IC95 delta holdout max": 0.10,
                "2+ holdout": 1 if selected else 0,
                "3+ holdout": 0,
                "2+ champion holdout": 1 if selected else 0,
            }
            output.append(
                {"profile": profile, "metrics": metrics, "selected": selected}
            )
        return {"records": output}

    monkeypatch.setattr(
        forge_service, "run_nested_orion_validation", fake_validation
    )


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
        existing = module.predictions.get(record["prediction_key"])
        activated = existing is None or existing.get("status") == "void"
        if activated:
            module.predictions[record["prediction_key"]] = {
                **dict(record),
                **{f"n{i}": sorted(record["numbers"])[i - 1] for i in range(1, 7)},
                "status": "pending",
                "target_year": None,
                "target_contest": None,
                "target_date": None,
                "hits": None,
            }
        return {
            "prediction_key": record["prediction_key"],
            "inserted": activated,
        }

    def fetch_pending_forge_predictions(version: str):
        return [
            dict(value)
            for value in module.predictions.values()
            if value["status"] == "pending"
            and value["forge_version"] == version
        ]

    def void_obsolete_pending_forge_predictions(
        *,
        forge_version: str,
        source_year: int,
        source_contest: int,
        keep_prediction_keys,
    ):
        changed = []
        for value in module.predictions.values():
            if (
                value["status"] == "pending"
                and value["forge_version"] == forge_version
                and int(value["source_year"]) == int(source_year)
                and int(value["source_contest"]) == int(source_contest)
                and value["prediction_key"] not in set(keep_prediction_keys)
            ):
                value["status"] = "void"
                changed.append(dict(value))
        return changed

    def evaluate_forge_prediction(prediction_key: str, **fields):
        module.predictions[prediction_key].update(fields, status="evaluated")
        return {"prediction_key": prediction_key}

    def fetch_evaluated_forge_predictions(version: str):
        return [
            dict(value)
            for value in module.predictions.values()
            if value["status"] == "evaluated"
            and value["forge_version"] == version
        ]

    module.fetch_forge_experiments_v2 = fetch_forge_experiments_v2
    module.save_forge_experiment_v2 = save_forge_experiment_v2
    module.fetch_forge_state = fetch_forge_state
    module.save_forge_state = save_forge_state
    module.save_forge_prediction = save_forge_prediction
    module.fetch_pending_forge_predictions = fetch_pending_forge_predictions
    module.void_obsolete_pending_forge_predictions = (
        void_obsolete_pending_forge_predictions
    )
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


def test_archive_edit_voids_obsolete_pair_and_revert_reactivates_original(
    monkeypatch, tmp_path: Path
) -> None:
    fake_database = _fake_database_module()
    monkeypatch.setitem(sys.modules, "database", fake_database)
    registry = tmp_path / ".forge_registry_v2.json"
    monkeypatch.setattr(forge_service, "REGISTRY_FILE", registry)

    original = synthetic_archive(90)
    first = forge_service.build_forge_snapshot(original)
    original_signature = first["archive_signature"]
    assert first["predictions_saved_now"] in (1, 2)

    edited = original.copy()
    edited.loc[10, "n1"] = 1 if int(edited.loc[10, "n1"]) != 1 else 2
    row_numbers = sorted(
        {int(edited.loc[10, f"n{i}"]) for i in range(1, 7)}
    )
    while len(row_numbers) < 6:
        candidate = max(row_numbers) + 1
        if candidate <= 90:
            row_numbers.append(candidate)
    for index, number in enumerate(sorted(row_numbers[:6]), start=1):
        edited.loc[10, f"n{index}"] = number

    second = forge_service.build_forge_snapshot(edited)
    assert second["archive_signature"] != original_signature
    assert second["predictions_voided_now"] in (1, 2)
    assert sum(
        value["status"] == "pending"
        for value in fake_database.predictions.values()
    ) in (1, 2)

    third = forge_service.build_forge_snapshot(original)
    assert third["archive_signature"] == original_signature
    assert third["predictions_voided_now"] in (1, 2)
    assert third["predictions_saved_now"] in (1, 2)
    active = [
        value
        for value in fake_database.predictions.values()
        if value["status"] == "pending"
    ]
    assert active
    assert {value["archive_signature"] for value in active} == {original_signature}


def test_prospective_minimum_is_never_below_hardened_default(
    monkeypatch, tmp_path: Path
) -> None:
    fake_database = _fake_database_module()
    monkeypatch.setitem(sys.modules, "database", fake_database)
    monkeypatch.setattr(
        forge_service, "REGISTRY_FILE", tmp_path / ".forge_registry_v2.json"
    )

    archive = synthetic_archive(90)
    forge_service.build_forge_snapshot(archive)
    fake_database.state["prospective_minimum"] = 30

    snapshot = forge_service.build_forge_snapshot(archive)
    assert snapshot["prospective"]["minimum"] >= 100
    assert fake_database.state["prospective_minimum"] >= 100
