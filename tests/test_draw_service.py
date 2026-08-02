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


    def test_add_extraction_rejects_skipped_contest(self) -> None:
        frame = synthetic_archive(30)
        draw_date = frame["data"].max().date() + timedelta(days=1)
        with self.assertRaisesRegex(ValueError, "prossimo concorso atteso"):
            add_extraction(
                frame,
                draw_date,
                32,
                [10, 20, 30, 40, 50, 60],
                70,
                80,
            )

    def test_add_extraction_rejects_duplicate_numbers(self) -> None:
        frame = synthetic_archive(30)
        draw_date = frame["data"].max().date() + timedelta(days=1)
        with self.assertRaisesRegex(ValueError, "tutti differenti"):
            add_extraction(
                frame,
                draw_date,
                31,
                [10, 10, 20, 30, 40, 50],
                60,
                70,
            )

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

    def test_add_extraction_rejects_jolly_in_sestina(self) -> None:
        frame = synthetic_archive(30)
        draw_date = frame["data"].max().date() + timedelta(days=1)
        with self.assertRaisesRegex(ValueError, "Jolly deve essere diverso"):
            add_extraction(
                frame,
                draw_date,
                31,
                [10, 20, 30, 40, 50, 60],
                40,
                80,
            )

    def test_add_extraction_rejects_date_not_after_latest(self) -> None:
        frame = synthetic_archive(30)
        with self.assertRaisesRegex(ValueError, "successiva all'ultima"):
            add_extraction(
                frame,
                frame["data"].min().date() - timedelta(days=1),
                31,
                [10, 20, 30, 40, 50, 60],
                70,
                80,
            )

    def test_update_rejects_date_before_previous_contest(self) -> None:
        frame = synthetic_archive(30)
        start = frame["data"].min()
        frame["data"] = [start + timedelta(days=index * 3) for index in range(len(frame))]
        target = frame.iloc[15]
        previous = frame.iloc[14]
        with self.assertRaisesRegex(ValueError, "successiva al concorso precedente"):
            update_extraction(
                frame,
                int(target["anno"]),
                int(target["concorso"]),
                previous["data"].date() - timedelta(days=1),
                [10, 20, 30, 40, 50, 60],
                70,
                80,
            )

    def test_update_rejects_date_after_next_contest(self) -> None:
        frame = synthetic_archive(30)
        start = frame["data"].min()
        frame["data"] = [start + timedelta(days=index * 3) for index in range(len(frame))]
        target = frame.iloc[15]
        following = frame.iloc[16]
        with self.assertRaisesRegex(ValueError, "precedente al concorso successivo"):
            update_extraction(
                frame,
                int(target["anno"]),
                int(target["concorso"]),
                following["data"].date() + timedelta(days=1),
                [10, 20, 30, 40, 50, 60],
                70,
                80,
            )

    def test_update_rejects_jolly_in_sestina(self) -> None:
        frame = synthetic_archive(30)
        target = frame.iloc[-1]
        with self.assertRaisesRegex(ValueError, "Jolly deve essere diverso"):
            update_extraction(
                frame,
                int(target["anno"]),
                int(target["concorso"]),
                target["data"].date(),
                [10, 20, 30, 40, 50, 60],
                50,
                80,
            )


if __name__ == "__main__":
    unittest.main()
