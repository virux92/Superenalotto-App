from __future__ import annotations

from typing import Any

import pandas as pd

from core.combinations import rank_candidate_sestine
from core.metrics import calculate_superstar_ranking
from core.orion import DEFAULT_POLICY, calculate_orion_state, orion_signature
from services.draw_service import dataframe_to_history


def build_orion_snapshot(archive: pd.DataFrame) -> dict[str, Any]:
    history = dataframe_to_history(archive)
    state = calculate_orion_state(history, DEFAULT_POLICY)
    structural = state["structural"]
    candidates = rank_candidate_sestine(
        state["score"],
        state["candidate_pool"],
        state["candidate_limit"],
        structural["minimum_sum"],
        structural["maximum_sum"],
        structural["maximum_low_numbers"],
        structural["minimum_decades"],
    )
    if not candidates:
        fallback = tuple(sorted(sorted(state["score"], key=state["score"].get, reverse=True)[:6]))
        candidates = [(sum(state["score"][number] for number in fallback), fallback)]
    state["candidates"] = candidates
    state["primary"] = candidates[0][1]
    state["superstar_ranking"] = calculate_superstar_ranking(history)
    state["signature"] = orion_signature(state)
    return state
