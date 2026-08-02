from __future__ import annotations

from core.orion import calculate_orion_state
from services.draw_service import dataframe_to_history
from services.orion_service import build_orion_snapshot
from tests.helpers import synthetic_archive


def test_orion_uses_multiple_available_memories() -> None:
    history = dataframe_to_history(synthetic_archive(220))
    state = calculate_orion_state(history)
    assert len(state["memories"]) == 5
    assert set(state["score"]) == set(range(1, 91))
    assert 0 <= state["stability"] <= 1


def test_orion_snapshot_is_deterministic() -> None:
    dataframe = synthetic_archive(220)
    first = build_orion_snapshot(dataframe)
    second = build_orion_snapshot(dataframe)
    assert first["primary"] == second["primary"]
    assert first["signature"] == second["signature"]
    assert len(first["primary"]) == 6
