from __future__ import annotations

from datetime import timedelta
import unittest

from services.draw_service import add_extraction, update_extraction
from tests.helpers import synthetic_archive


class DrawServiceTests(unittest.TestCase):
    def test_add_extraction_appends_next_contest(self) -> None:
        frame = synthetic_archive(30)
        draw_date = frame["data"].max().date() + timedelta(days=1)
        updated = add_extraction(
            frame,
            draw_date,
            31,
            [90, 10, 20, 30, 40, 50],
            60,
            70,
        )
        self.assertEqual(len(updated), 31)
        row = updated.iloc[-1]
        self.assertEqual(int(row["concorso"]), 31)
        self.assertEqual([int(row[f"n{i}"]) for i in range(1, 7)], [10, 20, 30, 40, 50, 90])

    def test_update_extraction_keeps_identity_and_normalizes_numbers(self) -> None:
        frame = synthetic_archive(30)
        original = frame.iloc[-1]
        updated = update_extraction(
            frame,
            int(original["anno"]),
            int(original["concorso"]),
            original["data"].date(),
            [66, 11, 22, 33, 44, 55],
            None,
            77,
        )
        row = updated.iloc[-1]
        self.assertEqual(int(row["anno"]), int(original["anno"]))
        self.assertEqual(int(row["concorso"]), int(original["concorso"]))
        self.assertEqual([int(row[f"n{i}"]) for i in range(1, 7)], [11, 22, 33, 44, 55, 66])
        self.assertTrue(row["jolly"] is None or str(row["jolly"]) == "<NA>")
        self.assertEqual(int(row["superstar"]), 77)

    def test_update_rejects_duplicate_date(self) -> None:
        frame = synthetic_archive(30)
        target = frame.iloc[-1]
        duplicate_date = frame.iloc[-2]["data"].date()
        with self.assertRaisesRegex(ValueError, "Esiste già"):
            update_extraction(
                frame,
                int(target["anno"]),
                int(target["concorso"]),
                duplicate_date,
                [1, 2, 3, 4, 5, 6],
                7,
                8,
            )


if __name__ == "__main__":
    unittest.main()
