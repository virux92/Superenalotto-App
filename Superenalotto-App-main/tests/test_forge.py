from __future__ import annotations

from core.forge import (
    build_candidate_models,
    choose_shadow_challenger,
    default_champion_record,
    evaluate_validation_record,
    experiment_key,
    weights_from_record,
)


def test_candidate_portfolio_is_deterministic_unique_and_not_duplicated_by_window() -> None:
    first = build_candidate_models(1169)
    second = build_candidate_models(1169)
    assert first == second
    assert len(first) == 5
    assert len({model.model_id for model in first}) == len(first)
    assert all("window_size" not in model.configuration for model in first)


def test_experiment_key_changes_with_archive() -> None:
    model = build_candidate_models(1169)[0]
    assert experiment_key(model, "archive-a") != experiment_key(model, "archive-b")


def test_retro_validation_can_only_create_shadow_not_promote() -> None:
    model = build_candidate_models(1169)[0]
    record = evaluate_validation_record(
        model,
        {
            "Test holdout": 40,
            "Delta vs champion holdout": 0.05,
            "IC95 delta holdout min": -0.10,
            "IC95 delta holdout max": 0.20,
            "2+ holdout": 3,
            "2+ champion holdout": 3,
            "Delta vs champion sviluppo": 0.10,
        },
        selected_for_holdout=True,
    )
    assert record["status"] == "shadow"
    assert record["checks"]["promozione_consentita"] is False


def test_non_selected_candidate_is_not_validated() -> None:
    model = build_candidate_models(1169)[0]
    record = evaluate_validation_record(
        model,
        {"Delta vs champion sviluppo": 0.20},
        selected_for_holdout=False,
    )
    assert record["status"] == "non_validated"


def test_shadow_selector_ignores_rejected_and_champion() -> None:
    models = build_candidate_models(1169)
    records = [
        {
            "model_id": models[0].model_id,
            "status": "shadow",
            "quality": 0.1,
            "metrics": {"Delta vs champion holdout": 0.01},
        },
        {
            "model_id": models[1].model_id,
            "status": "rejected",
            "quality": 99.0,
            "metrics": {},
        },
    ]
    selected = choose_shadow_challenger(records)
    assert selected is not None
    assert selected["model_id"] == models[0].model_id


def test_default_champion_weights_are_normalized() -> None:
    champion = default_champion_record()
    weights = weights_from_record(champion)
    assert champion["model_id"] == "ORION-BALANCED"
    assert round(weights.frequency + weights.delay + weights.recency, 8) == 1.0
