from __future__ import annotations

import unittest

from core.backtest import records_tuple, run_walk_forward_backtest
from tests.helpers import synthetic_archive


class BacktestTests(unittest.TestCase):
    def test_reproducibility_with_same_seed(self) -> None:
        records = records_tuple(synthetic_archive(80))
        arguments = (records, 50, 20, 15, 190, 350, 4, 3, 12345)
        first = run_walk_forward_backtest(*arguments)
        second = run_walk_forward_backtest(*arguments)
        self.assertEqual(first["details"], second["details"])
        self.assertEqual(first["summary"], second["summary"])

    def test_first_prediction_has_no_future_leakage(self) -> None:
        frame = synthetic_archive(80)
        original = run_walk_forward_backtest(
            records_tuple(frame), 50, 20, 15, 190, 350, 4, 3, 7
        )
        target_index = 60
        modified = frame.copy()
        replacement = [1, 2, 3, 4, 5, 6]
        for position, value in enumerate(replacement, 1):
            modified.loc[target_index, f"n{position}"] = value
        changed = run_walk_forward_backtest(
            records_tuple(modified), 50, 20, 15, 190, 350, 4, 3, 7
        )
        self.assertEqual(
            original["details"][0]["Pronostico algoritmo"],
            changed["details"][0]["Pronostico algoritmo"],
        )


if __name__ == "__main__":
    unittest.main()
