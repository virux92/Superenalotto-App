from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Mapping


def stable_identifier(prefix: str, payload: Mapping[str, Any]) -> str:
    """Costruisce un ID semantico: cambia solo quando cambia il modello."""
    material = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:12].upper()
    return f"{prefix}-{digest}"


@dataclass(frozen=True)
class ModelSpec:
    """Contratto comune dei modelli sperimentali per la sestina."""

    label: str
    family: str
    parameters: Mapping[str, Any] = field(default_factory=dict)
    eligible_for_promotion: bool = True

    @property
    def name(self) -> str:
        return self.label

    @property
    def configuration(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "family": self.family,
            "parameters": dict(self.parameters),
            "eligible_for_promotion": self.eligible_for_promotion,
        }

    @property
    def model_id(self) -> str:
        return stable_identifier("FORGE", self.configuration)


@dataclass(frozen=True)
class NumberForecast:
    model_id: str
    family: str
    numbers: tuple[int, ...]
    scores: Mapping[int, float]
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SuperStarForecast:
    model_id: str
    predicted: int
    ranking: tuple[tuple[int, float, int, int], ...]
    metadata: Mapping[str, Any] = field(default_factory=dict)
