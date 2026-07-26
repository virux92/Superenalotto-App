from __future__ import annotations

import unittest

from core.backtest import records_tuple
from core.experiments import DEFAULT_PROFILES, run_experiment_suite
from tests.helpers import synthetic_archive


class ExperimentTests(unittest.TestCase):
    def test_profiles_are_normalized(self) -> None:
        for profile in DEFAULT_PROFILES:
            self.assertAlmostEqual(
                profile.weights.frequency
                + profile.weights.delay
                + profile.weights.recency,
                1.0,
            )

    def test_suite_is_reproducible(self) -> None:
        records = records_tuple(synthetic_archive(70))
        arguments = dict(
            raw_records=records,
            profiles=DEFAULT_PROFILES[:3],
            window_size=40,
            test_limit=12,
            pool_size=12,
            minimum_sum=150,
            maximum_sum=390,
            maximum_low_numbers=5,
            minimum_decades=2,
            random_seed=77,
        )
        first = run_experiment_suite(**arguments)
        second = run_experiment_suite(**arguments)
        self.assertEqual(first["summary"], second["summary"])
        self.assertEqual(first["details"], second["details"])

    def test_expected_dimensions(self) -> None:
        records = records_tuple(synthetic_archive(70))
        result = run_experiment_suite(
            records,
            DEFAULT_PROFILES[:2],
            40,
            10,
            12,
            150,
            390,
            5,
            2,
            123,
        )
        self.assertEqual(result["test_count"], 10)
        self.assertEqual(len(result["summary"]), 2)
        self.assertEqual(len(result["details"]), 20)
        self.assertIn(result["best_profile"], result["profiles"])


if __name__ == "__main__":
    unittest.main()
