from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any

BAYESIAN_MODEL_VERSION = "bayesian-log-odds-v1"


@dataclass(frozen=True, slots=True)
class BayesianEvidence:
    name: str
    direction: str
    log_odds_delta: float
    weight: float
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class BayesianUpdateResult:
    prior_probability: float
    posterior_probability: float
    posterior_probability_percent: float
    probability_delta: float
    confidence_tier: str
    evidence: list[BayesianEvidence]
    warnings: list[str]
    model_version: str = BAYESIAN_MODEL_VERSION

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["evidence"] = [item.to_dict() for item in self.evidence]
        return payload


def clamp_probability(value: float, minimum: float = 0.01, maximum: float = 0.99) -> float:
    return max(minimum, min(maximum, value))


def probability_to_log_odds(probability: float) -> float:
    clamped = clamp_probability(probability)
    return math.log(clamped / (1 - clamped))


def log_odds_to_probability(log_odds: float) -> float:
    return 1 / (1 + math.exp(-log_odds))


def classify_confidence(evidence: list[BayesianEvidence], warnings: list[str]) -> str:
    total_weight = sum(abs(item.weight) for item in evidence)
    if warnings or total_weight < 1.0:
        return "low"
    if total_weight < 2.0:
        return "moderate"
    return "high"
