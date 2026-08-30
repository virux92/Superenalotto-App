from __future__ import annotations

from typing import Any, Mapping

import pandas as pd

from core.forge import default_champion_record, model_spec_from_record, weights_from_record
from core.metrics import calculate_superstar_ranking
from core.number_models import generate_number_forecast
from core.orion import DEFAULT_POLICY, generate_orion_proposal, orion_signature
from services.draw_service import dataframe_to_history


def build_orion_snapshot(
    archive: pd.DataFrame,
    forge: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    history = dataframe_to_history(archive)
    active_model = (
        forge.get("active_model") if forge else default_champion_record()
    ) or default_champion_record()
    state = generate_orion_proposal(
        history,
        metric_weights=weights_from_record(active_model),
        policy=DEFAULT_POLICY,
    )
    if str(active_model.get("model_id")) != "ORION-BALANCED":
        forecast = generate_number_forecast(history, model_spec_from_record(active_model))
        state["score"] = dict(forecast.scores)
        state["primary"] = tuple(forecast.numbers)
        state["candidates"] = list(forecast.metadata.get("candidates", ()))
        state["engine"] = str(forecast.family).upper()
    superstar_lab = forge.get("superstar_lab", {}) if forge else {}
    state["superstar_ranking"] = superstar_lab.get("ranking") or calculate_superstar_ranking(history)
    state["superstar_model"] = superstar_lab.get("active_model")
    state["forge_state"] = forge.get("state", "fallback") if forge else "fallback"
    state["active_model"] = active_model
    state["challenger_model"] = forge.get("challenger_model") if forge else None
    state["model_id"] = str(active_model.get("model_id", "ORION-BALANCED"))
    state["signature"] = orion_signature(state)
    return state
