from __future__ import annotations

import unittest

from core.analytics import archive_analytics, normalized_entropy
from services.draw_service import dataframe_to_history
from tests.helpers import synthetic_archive


class AnalyticsTests(unittest.TestCase):
    def test_entropy_bounds(self) -> None:
        self.assertEqual(normalized_entropy([6, 0, 0, 0, 0, 0, 0, 0, 0]), 0.0)
        self.assertAlmostEqual(normalized_entropy([1] * 9), 1.0, places=12)

    def test_analytics_dimensions(self) -> None:
        frame = synthetic_archive(40)
        analytics = archive_analytics(dataframe_to_history(frame), 20)
        self.assertEqual(len(analytics["structure_rows"]), 40)
        self.assertEqual(len(analytics["decades"]), 9)
        self.assertLessEqual(len(analytics["pairs"]), 20)
        self.assertLessEqual(len(analytics["triplets"]), 20)
        self.assertEqual(len(analytics["annual_stability"]), 90)


if __name__ == "__main__":
    unittest.main()
