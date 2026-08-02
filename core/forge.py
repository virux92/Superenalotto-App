from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from core.experiments import StrategyProfile
from core.metrics import DEFAULT_WEIGHTS, MetricWeights
from core.orion import DEFAULT_POLICY

FORGE_VERSION = "2.0.0"
PROSPECTIVE_MINIMUM = 100


@dataclass(frozen=True)
class ForgeModel:
    """Challenger deterministico valutato in shadow mode."""

    label: str
    frequency_weight: float
    delay_weight: float
    recency_weight: float

    @property
    def weights(self) -> MetricWeights:
        return MetricWeights(
            frequency=self.frequency_weight,
            delay=self.delay_weight,
            recency=self.recency_weight,
        ).normalized()

    @property
    def configuration(self) -> dict[str, Any]:
        normalized = self.weights
        return {
            "label": self.label,
            "frequency_weight": round(normalized.frequency, 6),
            "delay_weight": round(normalized.delay, 6),
            "recency_weight": round(normalized.recency, 6),
            "orion_policy_version": DEFAULT_POLICY.algorithm_version,
            "candidate_pool": DEFAULT_POLICY.candidate_pool,
            "candidate_limit": DEFAULT_POLICY.candidate_limit,
            "memories": [
                {"name": memory.name, "size": memory.size, "weight": memory.weight}
                for memory in DEFAULT_POLICY.memories
            ],
        }

    @property
    def model_id(self) -> str:
        payload = json.dumps(self.configuration, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        numeric = int(digest[:12], 16) % 1_000_000
        return f"ORION-{numeric:06d}"

    def as_strategy_profile(self) -> StrategyProfile:
        normalized = self.weights
        return StrategyProfile(
            self.label,
            normalized.frequency,
            normalized.delay,
            normalized.recency,
        )


def default_champion_record() -> dict[str, Any]:
    normalized = DEFAULT_WEIGHTS.normalized()
    return {
        "model_id": "ORION-BALANCED",
        "label": "Profilo bilanciato protetto",
        "status": "promoted",
        "configuration": {
            "label": "Profilo bilanciato protetto",
            "frequency_weight": normalized.frequency,
            "delay_weight": normalized.delay,
            "recency_weight": normalized.recency,
            "orion_policy_version": DEFAULT_POLICY.algorithm_version,
            "candidate_pool": DEFAULT_POLICY.candidate_pool,
            "candidate_limit": DEFAULT_POLICY.candidate_limit,
        },
        "metrics": {},
        "checks": {"default_champion": True},
        "quality": 0.0,
    }


def build_candidate_models(history_size: int) -> tuple[ForgeModel, ...]:
    """Crea challenger unici; nessuna finta moltiplicazione per finestre ignorate."""
    if history_size < DEFAULT_POLICY.minimum_history:
        return ()
    profiles = (
        ("Frequenza controllata", 0.50, 0.20, 0.30),
        ("Recenza controllata", 0.25, 0.20, 0.55),
        ("Ritardo controllato", 0.25, 0.50, 0.25),
        ("Frequenza e recenza", 0.45, 0.10, 0.45),
        ("Ritardo e recenza", 0.15, 0.45, 0.40),
    )
    return tuple(ForgeModel(*profile) for profile in profiles)


def experiment_key(model: ForgeModel, archive_signature: str) -> str:
    material = json.dumps(
        {
            "forge_version": FORGE_VERSION,
            "archive_signature": str(archive_signature),
            "model_id": model.model_id,
            "configuration": model.configuration,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def evaluate_validation_record(
    model: ForgeModel,
    metrics: Mapping[str, Any],
    *,
    selected_for_holdout: bool,
) -> dict[str, Any]:
    """Classifica il risultato retrospettivo senza fingere una promozione."""
    if not selected_for_holdout:
        return {
            "model_id": model.model_id,
            "label": model.label,
            "status": "non_validated",
            "quality": float(metrics.get("Delta vs champion sviluppo", 0.0)),
            "checks": {
                "selezionato_per_holdout": False,
                "promozione_consentita": False,
            },
            "configuration": model.configuration,
            "metrics": dict(metrics),
        }

    test_count = int(metrics.get("Test holdout", 0))
    delta = float(metrics.get("Delta vs champion holdout", 0.0))
    ci_min = float(metrics.get("IC95 delta holdout min", 0.0))
    ci_max = float(metrics.get("IC95 delta holdout max", 0.0))
    challenger_two_plus = int(metrics.get("2+ holdout", 0))
    champion_two_plus = int(metrics.get("2+ champion holdout", 0))

    # Il backtest può soltanto autorizzare la fase shadow. La promozione richiede
    # dati prospettici salvati prima delle estrazioni future.
    checks = {
        "campione_holdout_adeguato": test_count >= 20,
        "non_chiaramente_dominato": ci_max >= 0.0,
        "perdita_media_limitata": delta >= -0.05,
        "eventi_2_plus_non_collassati": challenger_two_plus >= max(0, champion_two_plus - 1),
        "promozione_consentita": False,
    }
    shadow = all(value for key, value in checks.items() if key != "promozione_consentita")
    quality = (
        delta * 5.0
        + (challenger_two_plus - champion_two_plus) / max(1, test_count)
        + ci_min * 0.25
    )
    return {
        "model_id": model.model_id,
        "label": model.label,
        "status": "shadow" if shadow else "rejected",
        "quality": round(quality, 8),
        "checks": checks,
        "configuration": model.configuration,
        "metrics": dict(metrics),
    }


def choose_shadow_challenger(
    records: Iterable[Mapping[str, Any]],
    *,
    excluded_model_ids: set[str] | None = None,
) -> dict[str, Any] | None:
    excluded = excluded_model_ids or set()
    eligible = [
        dict(record)
        for record in records
        if record.get("status") == "shadow"
        and str(record.get("model_id")) not in excluded
    ]
    if not eligible:
        return None
    eligible.sort(
        key=lambda row: (
            float(row.get("quality", float("-inf"))),
            float(row.get("metrics", {}).get("Delta vs champion holdout", float("-inf"))),
            float(row.get("metrics", {}).get("Delta vs champion sviluppo", float("-inf"))),
            str(row.get("model_id", "")),
        ),
        reverse=True,
    )
    return eligible[0]


def weights_from_record(record: Mapping[str, Any] | None) -> MetricWeights:
    if not record:
        return DEFAULT_WEIGHTS
    config = record.get("configuration", {})
    return MetricWeights(
        frequency=float(config.get("frequency_weight", DEFAULT_WEIGHTS.frequency)),
        delay=float(config.get("delay_weight", DEFAULT_WEIGHTS.delay)),
        recency=float(config.get("recency_weight", DEFAULT_WEIGHTS.recency)),
    ).normalized()
