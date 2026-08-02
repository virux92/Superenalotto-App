from __future__ import annotations

from core.backtest import records_tuple
from core.experiments import (
    DEFAULT_PROFILES,
    paired_bootstrap_ci,
    run_experiment_suite,
    run_nested_orion_validation,
)
from tests.helpers import synthetic_archive


def test_profiles_are_normalized() -> None:
    for profile in DEFAULT_PROFILES:
        assert round(
            profile.weights.frequency
            + profile.weights.delay
            + profile.weights.recency,
            8,
        ) == 1.0


def test_compatibility_suite_is_reproducible() -> None:
    records = records_tuple(synthetic_archive(70))
    arguments = dict(
        raw_records=records,
        profiles=DEFAULT_PROFILES[:2],
        window_size=40,
        test_limit=8,
        pool_size=12,
        minimum_sum=150,
        maximum_sum=390,
        maximum_low_numbers=5,
        minimum_decades=2,
        random_seed=77,
    )
    first = run_experiment_suite(**arguments)
    second = run_experiment_suite(**arguments)
    assert first["summary"] == second["summary"]
    assert first["details"] == second["details"]
    assert first["test_count"] == 8


def test_nested_validation_selects_on_development_and_has_holdout() -> None:
    records = records_tuple(synthetic_archive(90))
    result = run_nested_orion_validation(
        records,
        DEFAULT_PROFILES[1:4],
        development_limit=12,
        holdout_limit=12,
        random_seed=123,
    )
    assert result["development_count"] == 12
    assert result["holdout_count"] == 12
    selected = [row for row in result["records"] if row["selected"]]
    assert len(selected) == 1
    assert selected[0]["metrics"]["Test holdout"] == 12
    assert result["selected_profile"] in [profile.name for profile in DEFAULT_PROFILES]


def test_bootstrap_interval_is_deterministic() -> None:
    first = paired_bootstrap_ci([1, 0, -1, 1, 0], seed=9)
    second = paired_bootstrap_ci([1, 0, -1, 1, 0], seed=9)
    assert first == second
    assert first[0] <= first[1]
