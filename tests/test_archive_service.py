from __future__ import annotations

import unittest

from services.archive_service import archive_sha256, normalize_archive_dataframe
from tests.helpers import synthetic_archive


class ArchiveServiceTests(unittest.TestCase):
    def test_normalization_and_hash_are_order_independent(self) -> None:
        frame = synthetic_archive(30)
        reversed_frame = frame.iloc[::-1].reset_index(drop=True)
        self.assertEqual(archive_sha256(frame), archive_sha256(reversed_frame))
        normalized = normalize_archive_dataframe(frame)
        self.assertEqual(len(normalized), 30)
        self.assertTrue(normalized["data"].is_monotonic_increasing)

    def test_unsorted_numbers_are_rejected(self) -> None:
        frame = synthetic_archive(10)
        frame.loc[0, ["n1", "n2"]] = frame.loc[0, ["n2", "n1"]].to_numpy()
        with self.assertRaisesRegex(ValueError, "ordine crescente"):
            normalize_archive_dataframe(frame)

    def test_jolly_equal_to_main_number_is_rejected(self) -> None:
        frame = synthetic_archive(10)
        frame.loc[0, "jolly"] = int(frame.loc[0, "n3"])
        with self.assertRaisesRegex(ValueError, "Jolly duplicato"):
            normalize_archive_dataframe(frame)

    def test_dates_out_of_contest_sequence_are_rejected(self) -> None:
        frame = synthetic_archive(10)
        pandas = __import__("pandas")
        start = frame["data"].min()
        frame["data"] = [start + pandas.Timedelta(days=index * 3) for index in range(len(frame))]
        frame.loc[5, "data"] = frame.loc[4, "data"] - pandas.Timedelta(days=1)
        with self.assertRaisesRegex(ValueError, "Date fuori sequenza"):
            normalize_archive_dataframe(frame)


if __name__ == "__main__":
    unittest.main()
