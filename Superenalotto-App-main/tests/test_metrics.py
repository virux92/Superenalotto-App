from __future__ import annotations

import unittest

from core.metrics import MetricWeights, calculate_metrics
from services.draw_service import dataframe_to_history
from tests.helpers import synthetic_archive


class MetricsTests(unittest.TestCase):
    def test_scores_are_bounded(self) -> None:
        history = dataframe_to_history(synthetic_archive(50))
        metrics = calculate_metrics(history)
        self.assertEqual(len(metrics["score"]), 90)
        self.assertTrue(all(0.0 <= value <= 1.0 for value in metrics["score"].values()))

    def test_weights_are_normalized(self) -> None:
        normalized = MetricWeights(2, 1, 1).normalized()
        self.assertAlmostEqual(normalized.frequency, 0.5)
        self.assertAlmostEqual(normalized.delay, 0.25)
        self.assertAlmostEqual(normalized.recency, 0.25)


if __name__ == "__main__":
    unittest.main()
