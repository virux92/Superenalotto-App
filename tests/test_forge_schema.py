from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import types
from unittest.mock import patch


if "psycopg" not in sys.modules and importlib.util.find_spec("psycopg") is None:
    psycopg_stub = types.ModuleType("psycopg")
    psycopg_rows_stub = types.ModuleType("psycopg.rows")
    psycopg_rows_stub.dict_row = object()
    psycopg_stub.rows = psycopg_rows_stub
    sys.modules["psycopg"] = psycopg_stub
    sys.modules["psycopg.rows"] = psycopg_rows_stub

if "streamlit" not in sys.modules and importlib.util.find_spec("streamlit") is None:
    streamlit_stub = types.ModuleType("streamlit")

    def cache_resource(**_options):
        def decorator(function):
            return function

        return decorator

    streamlit_stub.cache_resource = cache_resource
    streamlit_stub.cache_data = cache_resource
    streamlit_stub.secrets = {}
    sys.modules["streamlit"] = streamlit_stub

import database


class _RecordingCursor:
    def __init__(self, statements: list[str]) -> None:
        self.statements = statements

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, statement, _parameters=None) -> None:
        self.statements.append(str(statement))


class _RecordingConnection:
    def __init__(self, statements: list[str]) -> None:
        self.statements = statements

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def cursor(self):
        return _RecordingCursor(self.statements)

    def commit(self) -> None:
        pass


class _ResultCursor(_RecordingCursor):
    def __init__(self, calls: list[tuple[str, object]], results: list[object]) -> None:
        super().__init__([])
        self.calls = calls
        self.results = results

    def execute(self, statement, parameters=None) -> None:
        self.calls.append((str(statement), parameters))

    def fetchone(self):
        return self.results.pop(0)


class _ResultConnection(_RecordingConnection):
    def __init__(self, calls: list[tuple[str, object]], results: list[object]) -> None:
        super().__init__([])
        self.calls = calls
        self.results = results

    def cursor(self):
        return _ResultCursor(self.calls, self.results)


def test_forge_setup_is_repeatable_and_contains_idempotent_superstar_upgrade() -> None:
    statements: list[str] = []
    setup = getattr(
        database.ensure_forge_v2_tables,
        "__wrapped__",
        database.ensure_forge_v2_tables,
    )
    with patch.object(
        database,
        "get_connection",
        side_effect=lambda: _RecordingConnection(statements),
    ):
        setup()
        first_run_count = len(statements)
        setup()

    assert first_run_count > 0
    assert len(statements) == first_run_count * 2
    first_run_sql = "\n".join(statements[:first_run_count]).lower()
    assert "add column if not exists predicted_superstar" in first_run_sql
    assert "add column if not exists target_superstar" in first_run_sql
    assert "add column if not exists superstar_hit" in first_run_sql
    assert "create or replace function public.invalidate_forge_predictions_on_draw_change" in first_run_sql
    assert (
        "public.invalidate_forge_predictions_on_draw_change()\n        from public, anon, authenticated"
        in first_run_sql
    )
    assert "drop trigger if exists trg_invalidate_forge_predictions" in first_run_sql


def test_install_sql_distinguishes_draw_change_types_and_preserves_evaluated_rows() -> None:
    sql_path = Path(__file__).resolve().parents[1] / "FORGE_V2_SUPABASE.sql"
    sql = sql_path.read_text(encoding="utf-8").lower()
    function_sql = sql.split(
        "create or replace function public.invalidate_forge_predictions_on_draw_change()",
        maxsplit=1,
    )[1]

    assert "predicted_superstar smallint null" in sql
    assert "target_superstar smallint null" in sql
    assert "superstar_hit boolean null" in sql
    assert "numbers_changed boolean" in function_sql
    assert "superstar_changed boolean" in function_sql
    assert "structure_changed boolean" in function_sql
    assert "if tg_op = 'insert'" in function_sql
    assert "elsif tg_op = 'delete'" in function_sql
    assert "if structure_changed then" in function_sql
    assert "old.jolly" not in function_sql
    assert "new.jolly" not in function_sql
    assert "where prediction.status = 'evaluated'" in function_sql
    assert "where status = 'pending'" in function_sql
    assert "source_date >= new.data_estrazione" in function_sql
    assert "target_superstar = new.superstar" in function_sql
    assert "superstar_hit = case" in function_sql
    assert (
        "revoke execute on function\n"
        "    public.invalidate_forge_predictions_on_draw_change()\n"
        "from public, anon, authenticated"
        in sql
    )

    statements: list[str] = []
    setup = getattr(
        database.ensure_forge_v2_tables,
        "__wrapped__",
        database.ensure_forge_v2_tables,
    )
    with patch.object(
        database,
        "get_connection",
        return_value=_RecordingConnection(statements),
    ):
        setup()
    database_function = next(
        statement
        for statement in statements
        if "invalidate_forge_predictions_on_draw_change" in statement
    )
    standalone_function = (
        "create or replace function public.invalidate_forge_predictions_on_draw_change()"
        + function_sql.split("revoke execute on function", maxsplit=1)[0]
    )
    def normalize(value: str) -> str:
        without_comments = "\n".join(
            line for line in value.splitlines() if not line.lstrip().startswith("--")
        )
        return " ".join(without_comments.lower().strip().rstrip(";").split())

    assert normalize(database_function) == normalize(standalone_function)


def test_prediction_insert_preserves_a_legacy_pending_unique_conflict() -> None:
    calls: list[tuple[str, object]] = []
    connection = _ResultConnection(calls, [None, None])
    record = {
        "prediction_key": "new-input-key",
        "archive_signature": "main-only-signature",
        "forge_version": "2.0.0",
        "source_year": 2026,
        "source_contest": 125,
        "source_date": "2026-08-07",
        "role": "champion",
        "model_id": "ORION-BALANCED",
        "model_config": {},
        "numbers": (1, 2, 3, 4, 5, 6),
        "predicted_superstar": 42,
    }

    with patch.object(database, "ensure_forge_v2_tables"), patch.object(
        database, "get_connection", return_value=connection
    ):
        result = database.save_forge_prediction(record)

    assert result == {"prediction_key": "new-input-key", "inserted": False}
    assert len(calls) == 2
    assert "and not exists" in calls[0][0].lower()
    assert "on conflict do nothing" in calls[1][0].lower()
    assert calls[1][1]["predicted_superstar"] == 42
