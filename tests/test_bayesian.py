from __future__ import annotations

import unittest

from app.models.bayesian import (
    BAYESIAN_MODEL_VERSION,
    clamp_probability,
    log_odds_to_probability,
    probability_to_log_odds,
)
from app.services.bayesian_probability_service import BayesianProbabilityService


class BayesianModelTests(unittest.TestCase):
    def test_probability_log_odds_round_trip_is_stable(self) -> None:
        probability = 0.62

        recovered = log_odds_to_probability(probability_to_log_odds(probability))

        self.assertAlmostEqual(recovered, probability)

    def test_clamp_probability_keeps_posterior_math_stable(self) -> None:
        self.assertEqual(clamp_probability(0), 0.01)
        self.assertEqual(clamp_probability(1), 0.99)
        self.assertEqual(clamp_probability(0.55), 0.55)


class BayesianProbabilityServiceTests(unittest.TestCase):
    def test_update_probability_returns_auditable_positive_posterior(self) -> None:
        service = BayesianProbabilityService()

        result = service.update_probability(
            baseline_probability=0.58,
            trial={
                "phase_score": 3,
                "event_date_quality_tier": "high",
            },
            sponsor_mapping={"ticker": "PFE", "confidence": 0.96},
            expected_reaction_context={
                "profile": {
                    "expected_direction": "positive",
                    "confidence_tier": "moderate",
                }
            },
        )

        self.assertEqual(result["status"], "available")
        self.assertEqual(result["model_version"], BAYESIAN_MODEL_VERSION)
        self.assertGreater(result["posterior_probability"], result["prior_probability"])
        self.assertGreater(result["posterior_probability_percent"], 60)
        self.assertEqual(result["confidence_tier"], "moderate")
        self.assertEqual(
            [item["name"] for item in result["evidence"]],
            [
                "phase_score",
                "event_date_quality",
                "sponsor_mapping",
                "historical_analog_reaction",
            ],
        )
        self.assertEqual(result["warnings"], [])

    def test_update_probability_penalizes_weak_evidence(self) -> None:
        service = BayesianProbabilityService()

        result = service.update_probability(
            baseline_probability=0.58,
            trial={
                "phase_score": 1,
                "event_date_quality_tier": "low",
            },
            sponsor_mapping={"ticker": None, "confidence": 0.0},
            expected_reaction_context={
                "profile": {
                    "expected_direction": "negative",
                    "confidence_tier": "thin",
                }
            },
        )

        self.assertLess(result["posterior_probability"], result["prior_probability"])
        self.assertEqual(result["confidence_tier"], "moderate")
        self.assertTrue(all("rationale" in item for item in result["evidence"]))

    def test_update_probability_warns_when_no_evidence_is_available(self) -> None:
        service = BayesianProbabilityService()

        result = service.update_probability(
            baseline_probability=1.5,
            trial={},
            sponsor_mapping=None,
            expected_reaction_context=None,
        )

        self.assertEqual(result["prior_probability"], 0.99)
        self.assertEqual(result["confidence_tier"], "low")
        self.assertIn("baseline_probability_was_clamped", result["warnings"])
        self.assertIn("no_bayesian_evidence_available", result["warnings"])


if __name__ == "__main__":
    unittest.main()
