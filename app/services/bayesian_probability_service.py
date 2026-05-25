from __future__ import annotations

from typing import Any

from app.models.bayesian import (
    BayesianEvidence,
    BayesianUpdateResult,
    clamp_probability,
    classify_confidence,
    log_odds_to_probability,
    probability_to_log_odds,
)


class BayesianProbabilityService:
    """
    Updates an interpretable baseline probability with auditable evidence.
    """

    def _coerce_float(self, value: Any, default: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def _phase_evidence(self, trial: dict[str, Any]) -> BayesianEvidence | None:
        phase_score = self._coerce_float(trial.get("phase_score"), default=-1.0)
        if phase_score < 0:
            return None
        delta = {0: -0.18, 1: -0.08, 2: 0.04, 3: 0.16, 4: 0.1}.get(int(phase_score), 0.0)
        return BayesianEvidence(
            name="phase_score",
            direction="positive" if delta >= 0 else "negative",
            log_odds_delta=delta,
            weight=0.35,
            rationale=f"Phase score {int(phase_score)} updates the prior using trial-stage maturity.",
        )

    def _event_date_quality_evidence(self, trial: dict[str, Any]) -> BayesianEvidence | None:
        tier = str(trial.get("event_date_quality_tier") or "").strip().lower()
        if not tier:
            return None
        delta_by_tier = {"high": 0.1, "moderate": 0.0, "low": -0.18, "unknown": -0.12}
        delta = delta_by_tier.get(tier, -0.08)
        return BayesianEvidence(
            name="event_date_quality",
            direction="positive" if delta >= 0 else "negative",
            log_odds_delta=delta,
            weight=0.3,
            rationale=f"Event-date quality tier '{tier}' affects trust in the catalyst timing.",
        )

    def _sponsor_mapping_evidence(self, sponsor_mapping: dict[str, Any] | None) -> BayesianEvidence | None:
        if not sponsor_mapping:
            return None
        confidence = self._coerce_float(sponsor_mapping.get("confidence"), default=0.0)
        ticker = sponsor_mapping.get("ticker")
        if not ticker:
            delta = -0.12
        elif confidence >= 0.9:
            delta = 0.08
        elif confidence >= 0.7:
            delta = 0.02
        else:
            delta = -0.08
        return BayesianEvidence(
            name="sponsor_mapping",
            direction="positive" if delta >= 0 else "negative",
            log_odds_delta=delta,
            weight=0.25,
            rationale="Sponsor-to-ticker confidence changes how much we trust market linkage.",
        )

    def _historical_analog_evidence(self, expected_reaction_context: dict[str, Any] | None) -> BayesianEvidence | None:
        profile = (expected_reaction_context or {}).get("profile") or {}
        if not profile:
            return None
        confidence_tier = str(profile.get("confidence_tier") or "unknown").strip().lower()
        expected_direction = str(profile.get("expected_direction") or "unknown").strip().lower()
        direction_delta = 0.1 if expected_direction == "positive" else -0.08 if expected_direction == "negative" else 0
        confidence_multiplier = {"high": 1.0, "moderate": 0.7, "thin": 0.35, "unknown": 0.25}.get(
            confidence_tier,
            0.4,
        )
        delta = round(direction_delta * confidence_multiplier, 6)
        return BayesianEvidence(
            name="historical_analog_reaction",
            direction="positive" if delta >= 0 else "negative",
            log_odds_delta=delta,
            weight=0.45 * confidence_multiplier,
            rationale="Historical analog direction updates probability with cohort-level support.",
        )

    def update_probability(
        self,
        baseline_probability: float,
        trial: dict[str, Any],
        sponsor_mapping: dict[str, Any] | None = None,
        expected_reaction_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        warnings: list[str] = []
        prior_probability = clamp_probability(baseline_probability)
        if baseline_probability != prior_probability:
            warnings.append("baseline_probability_was_clamped")

        evidence = [
            item
            for item in [
                self._phase_evidence(trial),
                self._event_date_quality_evidence(trial),
                self._sponsor_mapping_evidence(sponsor_mapping),
                self._historical_analog_evidence(expected_reaction_context),
            ]
            if item is not None
        ]
        if not evidence:
            warnings.append("no_bayesian_evidence_available")

        posterior_log_odds = probability_to_log_odds(prior_probability) + sum(
            item.log_odds_delta for item in evidence
        )
        posterior_probability = round(log_odds_to_probability(posterior_log_odds), 4)
        result = BayesianUpdateResult(
            prior_probability=round(prior_probability, 4),
            posterior_probability=posterior_probability,
            posterior_probability_percent=round(posterior_probability * 100, 2),
            probability_delta=round(posterior_probability - prior_probability, 4),
            confidence_tier=classify_confidence(evidence, warnings),
            evidence=evidence,
            warnings=warnings,
        )
        payload = result.to_dict()
        payload["status"] = "available"
        return payload
