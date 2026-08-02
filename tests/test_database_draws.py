from __future__ import annotations

from datetime import timedelta
import importlib.util
import sys
import types
import unittest
from unittest.mock import patch

import pandas as pd

if importlib.util.find_spec("psycopg") is None:
    psycopg_stub = types.ModuleType("psycopg")
    psycopg_rows_stub = types.ModuleType("psycopg.rows")
    psycopg_rows_stub.dict_row = object()
    psycopg_stub.rows = psycopg_rows_stub
    sys.modules["psycopg"] = psycopg_stub
    sys.modules["psycopg.rows"] = psycopg_rows_stub

if importlib.util.find_spec("streamlit") is None:
    streamlit_stub = types.ModuleType("streamlit")

    def cache_resource(**_options):
        def decorator(function):
            return function
        return decorator

    streamlit_stub.cache_resource = cache_resource
    streamlit_stub.secrets = {}
    sys.modules["streamlit"] = streamlit_stub

import database
from services.draw_service import add_extraction
from tests.helpers import synthetic_archive


class DatabaseDrawValidationTests(unittest.TestCase):
    def test_upsert_validates_full_archive_before_writing(self) -> None:
        existing = synthetic_archive(30)
        updated = add_extraction(
            existing,
            existing["data"].max().date() + timedelta(days=1),
            31,
            [10, 20, 30, 40, 50, 60],
            70,
            80,
        )
        draw = updated.iloc[-1].to_dict()

        with patch.object(database, "fetch_draws", return_value=existing), patch.object(
            database,
            "_write_draw_records",
            return_value={"processed": 1},
        ) as writer:
            result = database.upsert_draw(draw, source="test")

        self.assertEqual(result, {"processed": 1})
        written = writer.call_args.args[0]
        self.assertEqual(len(written), 1)
        self.assertEqual(int(written.iloc[0]["concorso"]), 31)

    def test_upsert_rejects_jolly_equal_to_main_number(self) -> None:
        existing = synthetic_archive(30)
        draw = {
            "data": existing["data"].max() + pd.Timedelta(days=1),
            "anno": 2025,
            "concorso": 31,
            "n1": 10,
            "n2": 20,
            "n3": 30,
            "n4": 40,
            "n5": 50,
            "n6": 60,
            "jolly": 40,
            "superstar": 80,
        }

        with patch.object(database, "fetch_draws", return_value=existing), patch.object(
            database, "_write_draw_records"
        ) as writer:
            with self.assertRaisesRegex(ValueError, "Jolly duplicato"):
                database.upsert_draw(draw, source="test")

        writer.assert_not_called()

    def test_import_rejects_dates_out_of_sequence_before_writing(self) -> None:
        frame = synthetic_archive(10)
        start = frame["data"].min()
        frame["data"] = [
            start + pd.Timedelta(days=index * 3) for index in range(len(frame))
        ]
        frame.loc[5, "data"] = frame.loc[4, "data"] - pd.Timedelta(days=1)

        with patch.object(database, "_write_draw_records") as writer:
            with self.assertRaisesRegex(ValueError, "Date fuori sequenza"):
                database.import_draws(frame, source="test")

        writer.assert_not_called()


if __name__ == "__main__":
    unittest.main()
