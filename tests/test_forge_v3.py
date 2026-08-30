from __future__ import annotations

from core.backtest import records_tuple
from core.forge import build_candidate_models
from core.number_models import generate_number_forecast
from core.orion import generate_orion_proposal
from core.portfolio_optimizer import optimize_ticket_portfolio
from core.superstar_models import (
    SUPERSTAR_CHALLENGERS,
    SUPERSTAR_CHAMPION,
    assign_distinct_superstars,
    generate_superstar_forecast,
)
from services.draw_service import dataframe_to_history
from services.superstar_forge_service import run_superstar_historical_validation
from tests.helpers import synthetic_archive


def test_new_number_families_do_not_modify_protected_orion_champion() -> None:
    archive = synthetic_archive(90)
    history = dataframe_to_history(archive)
    champion_before = generate_orion_proposal(history)

    models = build_candidate_models(len(history))
    forecasts = [
        generate_number_forecast(history, model.as_model_spec()) for model in models
    ]
    champion_after = generate_orion_proposal(history)

    assert champion_before["primary"] == champion_after["primary"]
    assert champion_before["score"] == champion_after["score"]
    assert {forecast.family for forecast in forecasts} == {
        "bayes_dirichlet",
        "multi_ema",
        "pair_shrink",
        "rolling_frequency",
        "uniform_hash",
    }
    assert all(len(set(forecast.numbers)) == 6 for forecast in forecasts)


def test_superstar_models_are_separate_and_lines_receive_distinct_values() -> None:
    history = dataframe_to_history(synthetic_archive(90))
    champion = generate_superstar_forecast(history, SUPERSTAR_CHAMPION)
    challengers = [
        generate_superstar_forecast(history, spec) for spec in SUPERSTAR_CHALLENGERS
    ]

    assigned = assign_distinct_superstars(champion.ranking, 15)
    assert len(assigned) == 15
    assert len(set(assigned)) == 15
    assert champion.model_id == "SUPERSTAR-LEGACY-V1"
    assert len({forecast.model_id for forecast in challengers}) == len(challengers)


def test_superstar_backtest_uses_walk_forward_history_and_never_promotes() -> None:
    archive = synthetic_archive(90)
    result = run_superstar_historical_validation(records_tuple(archive))

    assert result["history_count"] == 90
    assert result["development_count"] + result["holdout_count"] == 40
    assert sum(row["selected_for_holdout"] for row in result["records"]) == 1
    assert "decision" not in result  # il retrospettivo non decide promozioni
    assert result["uniform_exact_rate"] == 1 / 90


def test_ticket_optimizer_returns_unique_high_coverage_portfolio() -> None:
    history = dataframe_to_history(synthetic_archive(90))
    scores = generate_orion_proposal(history)["score"]
    pool, lines, metrics = optimize_ticket_portfolio(scores, 12, 8)

    assert len(pool) == 12
    assert len(lines) == 8
    assert len(set(lines)) == 8
    assert metrics["unique_lines"] == 8
    assert 0.0 <= metrics["pair_coverage"] <= 1.0
    assert metrics["maximum_overlap"] <= 5
