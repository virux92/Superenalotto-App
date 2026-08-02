from __future__ import annotations

from core.backtest import records_tuple
from core.experiments import StrategyProfile, run_experiment_suite
from core.metrics import MetricWeights
from core.orion import generate_orion_proposal
from services.draw_service import dataframe_to_history
from services.orion_service import build_orion_snapshot
from tests.helpers import synthetic_archive


def test_live_service_and_pure_pipeline_generate_same_primary() -> None:
    archive = synthetic_archive(120)
    history = dataframe_to_history(archive)
    pure = generate_orion_proposal(history)
    live = build_orion_snapshot(archive)
    assert pure["primary"] == live["primary"]
    assert pure["candidate_pool"] == live["candidate_pool"]


def test_experiment_uses_same_pipeline_for_last_target() -> None:
    archive = synthetic_archive(70)
    profile = StrategyProfile("Test", 0.50, 0.20, 0.30)
    result = run_experiment_suite(
        records_tuple(archive),
        [profile],
        40,
        1,
        12,
        150,
        390,
        5,
        2,
        77,
    )
    chronological = archive.sort_values("data")
    training = chronological.iloc[:-1]
    expected = generate_orion_proposal(
        dataframe_to_history(training),
        metric_weights=MetricWeights(0.50, 0.20, 0.30),
    )["primary"]
    observed = tuple(int(value.strip()) for value in result["details"][0]["Pronostico"].split(","))
    assert observed == expected
