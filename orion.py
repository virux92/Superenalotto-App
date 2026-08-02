from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any, Iterable, Mapping

from core.experiments import StrategyProfile
from core.metrics import MetricWeights

FORGE_VERSION = "1.0.0"


@dataclass(frozen=True)
class ForgeModel:
    """Modello candidato generato e valutato automaticamente da FORGE."""

    label: str
    window_size: int
    frequency_weight: float
    delay_weight: float
    recency_weight: float
    pool_size: int = 12
    test_limit: int = 80

    @property
    def weights(self) -> MetricWeights:
        return MetricWeights(
            frequency=self.frequency_weight,
            delay=self.delay_weight,
            recency=self.recency_weight,
        ).normalized()

    @property
    def model_id(self) -> str:
        payload = json.dumps(self.configuration, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        numeric = int(digest[:12], 16) % 1_000_000
        return f"ORION-{numeric:06d}"

    @property
    def configuration(self) -> dict[str, Any]:
        normalized = self.weights
        return {
            "label": self.label,
            "window_size": int(self.window_size),
            "frequency_weight": round(normalized.frequency, 6),
            "delay_weight": round(normalized.delay, 6),
            "recency_weight": round(normalized.recency, 6),
            "pool_size": int(self.pool_size),
            "test_limit": int(self.test_limit),
        }

    def as_strategy_profile(self) -> StrategyProfile:
        normalized = self.weights
        return StrategyProfile(
            self.model_id,
            normalized.frequency,
            normalized.delay,
            normalized.recency,
        )


def build_candidate_models(history_size: int) -> tuple[ForgeModel, ...]:
    """Crea un portafoglio deterministico di modelli senza input utente."""

    if history_size < 60:
        windows = (max(30, history_size // 2),)
        test_limit = max(10, min(30, history_size - windows[0]))
    else:
        available = [80, 120, 200]
        windows = tuple(window for window in available if history_size > window + 20)
        if not windows:
            windows = (max(40, history_size // 2),)
        test_limit = min(80, max(20, history_size - max(windows)))

    profiles = (
        ("Bilanciato", 0.35, 0.25, 0.40),
        ("Frequenza controllata", 0.50, 0.20, 0.30),
        ("Recenza controllata", 0.25, 0.20, 0.55),
        ("Ritardo controllato", 0.25, 0.50, 0.25),
        ("Frequenza e recenza", 0.45, 0.10, 0.45),
        ("Ritardo e recenza", 0.15, 0.45, 0.40),
    )
    return tuple(
        ForgeModel(
            label=label,
            window_size=window,
            frequency_weight=frequency,
            delay_weight=delay,
            recency_weight=recency,
            pool_size=12,
            test_limit=test_limit,
        )
        for window in windows
        for label, frequency, delay, recency in profiles
    )


def experiment_key(model: ForgeModel, archive_signature: str) -> str:
    material = (
        f"{FORGE_VERSION}:{archive_signature}:{model.model_id}:"
        f"{model.window_size}:{model.test_limit}"
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def evaluate_candidate(
    model: ForgeModel,
    summary: Mapping[str, Any],
    *,
    random_2_plus: int,
) -> dict[str, Any]:
    """Applica criteri di robustezza operativa, non criteri di previsione."""

    test_count = max(1, int(summary.get("Test", 0)))
    delta = float(summary.get("Delta medio", 0.0))
    two_plus = int(summary.get("2+", 0))
    instability = float(summary.get("Instabilità annuale", 0.0))
    wins = int(summary.get("Vittorie vs casuale", 0))
    losses = int(summary.get("Sconfitte vs casuale", 0))

    # Il candidato viene considerato operativo se ha completato un campione
    # adeguato, non è nettamente dominato dal benchmark e non è instabile.
    minimum_two_plus = max(0, int(random_2_plus) - 2)
    checks = {
        "campione_adeguato": test_count >= 20,
        "non_dominato": delta >= -0.10,
        "eventi_2_plus": two_plus >= minimum_two_plus,
        "stabilita_annuale": instability <= 0.60,
        "confronto_bilanciato": losses <= wins + max(8, test_count // 4),
    }
    valid = all(checks.values())
    quality = (
        delta * 4.0
        + ((two_plus - int(random_2_plus)) / test_count) * 2.0
        + ((wins - losses) / test_count) * 0.35
        - instability * 0.50
    )

    return {
        "model_id": model.model_id,
        "label": model.label,
        "status": "valid" if valid else "rejected",
        "quality": round(float(quality), 8),
        "checks": checks,
        "configuration": model.configuration,
        "metrics": dict(summary),
    }


def choose_active_model(records: Iterable[Mapping[str, Any]]) -> dict[str, Any] | None:
    valid = [dict(record) for record in records if record.get("status") == "valid"]
    if not valid:
        return None
    valid.sort(
        key=lambda row: (
            float(row.get("quality", float("-inf"))),
            float(row.get("metrics", {}).get("Delta medio", float("-inf"))),
            int(row.get("metrics", {}).get("2+", 0)),
            -float(row.get("metrics", {}).get("Instabilità annuale", float("inf"))),
            str(row.get("model_id", "")),
        ),
        reverse=True,
    )
    return valid[0]


def weights_from_record(record: Mapping[str, Any] | None) -> MetricWeights:
    if not record:
        return MetricWeights()
    config = record.get("configuration", {})
    return MetricWeights(
        frequency=float(config.get("frequency_weight", 0.35)),
        delay=float(config.get("delay_weight", 0.25)),
        recency=float(config.get("recency_weight", 0.40)),
    ).normalized()
