from __future__ import annotations

import math
from typing import Any

BASELINE_MODEL_VERSION = "baseline-logistic-v1"


class BaselineModelService:
    """
    Interpretable baseline for trial success probability.

    This is intentionally simple: it gives the project a transparent benchmark
    before heavier ML models are introduced.
    """

    COEFFICIENTS = {
        "intercept": -0.4,
        "phase_score": 0.28,
        "has_results": 0.35,
        "data_completeness_ratio": 0.55,
        "event_date_quality": 0.4,
        "public_sponsor_mapping": 0.25,
        "industry_sponsor": 0.12,
    }

    def _coerce_float(self, value: Any, default: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def _sigmoid(self, value: float) -> float:
        return 1 / (1 + math.exp(-value))

    def _build_features(
        self,
        trial: dict[str, Any],
        sponsor_mapping: dict[str, Any] | None = None,
    ) -> tuple[dict[str, float], list[str]]:
        warnings: list[str] = []
        phase_score = self._coerce_float(trial.get("phase_score"), default=0.0)
        if phase_score == 0.0 and not trial.get("phase_score"):
            warnings.append("phase_score_missing")

        data_completeness_ratio = trial.get("data_completeness_ratio")
        if data_completeness_ratio is None:
            completeness_score = self._coerce_float(trial.get("data_completeness_score"), default=0.0)
            data_completeness_ratio = completeness_score / 9 if completeness_score else 0.0
            if not completeness_score:
                warnings.append("data_completeness_missing")

        event_date_quality_score = self._coerce_float(trial.get("event_date_quality_score"), default=0.0)
        if not event_date_quality_score:
            warnings.append("event_date_quality_missing")

        sponsor_class = str(trial.get("sponsor_class") or "").strip().lower()
        mapped_ticker = (sponsor_mapping or {}).get("ticker") or trial.get("mapped_ticker")

        return (
            {
                "phase_score": max(0.0, min(4.0, phase_score)) / 4,
                "has_results": 1.0 if trial.get("has_results") else 0.0,
                "data_completeness_ratio": max(0.0, min(1.0, self._coerce_float(data_completeness_ratio))),
                "event_date_quality": max(0.0, min(100.0, event_date_quality_score)) / 100,
                "public_sponsor_mapping": 1.0 if mapped_ticker else 0.0,
                "industry_sponsor": 1.0 if sponsor_class == "industry" else 0.0,
            },
            warnings,
        )

    def score_trial(
        self,
        trial: dict[str, Any],
        sponsor_mapping: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        features, warnings = self._build_features(trial, sponsor_mapping=sponsor_mapping)
        contributions = {
            name: round(features[name] * self.COEFFICIENTS[name], 6)
            for name in features
        }
        logit = self.COEFFICIENTS["intercept"] + sum(contributions.values())
        probability = round(self._sigmoid(logit), 4)
        if probability >= 0.65:
            probability_tier = "favorable"
        elif probability >= 0.45:
            probability_tier = "balanced"
        else:
            probability_tier = "elevated_risk"

        return {
            "status": "available",
            "model_name": "interpretable_baseline_success_probability",
            "model_version": BASELINE_MODEL_VERSION,
            "success_probability": probability,
            "probability_percent": round(probability * 100, 2),
            "probability_tier": probability_tier,
            "features": features,
            "contributions": contributions,
            "intercept": self.COEFFICIENTS["intercept"],
            "logit": round(logit, 6),
            "warnings": warnings,
        }
