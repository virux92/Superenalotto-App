from __future__ import annotations

from core.forge import (
    ForgeModel,
    build_candidate_models,
    choose_active_model,
    evaluate_candidate,
    experiment_key,
    weights_from_record,
)


def test_candidate_portfolio_is_deterministic_and_unique() -> None:
    first = build_candidate_models(1169)
    second = build_candidate_models(1169)
    assert first == second
    assert len(first) == 18
    assert len({model.model_id for model in first}) == len(first)


def test_experiment_key_changes_with_archive() -> None:
    model = build_candidate_models(1169)[0]
    assert experiment_key(model, "archive-a") != experiment_key(model, "archive-b")


def test_only_valid_candidate_can_be_promoted() -> None:
    model = ForgeModel("Test", 100, 0.35, 0.25, 0.40)
    valid = evaluate_candidate(
        model,
        {
            "Test": 80,
            "Delta medio": 0.02,
            "2+": 12,
            "Instabilità annuale": 0.1,
            "Vittorie vs casuale": 30,
            "Sconfitte vs casuale": 25,
        },
        random_2_plus=11,
    )
    failed = dict(valid)
    failed["model_id"] = "ORION-FAILED"
    failed["status"] = "failed"
    failed["quality"] = 99.0
    active = choose_active_model([failed, valid])
    assert active is not None
    assert active["model_id"] == model.model_id
    weights = weights_from_record(active)
    assert round(weights.frequency + weights.delay + weights.recency, 8) == 1.0
