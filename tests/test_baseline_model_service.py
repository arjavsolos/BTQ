from __future__ import annotations

import unittest

from app.services.baseline_model_service import BASELINE_MODEL_VERSION, BaselineModelService


class BaselineModelServiceTests(unittest.TestCase):
    def test_score_trial_returns_interpretable_probability_output(self) -> None:
        service = BaselineModelService()

        result = service.score_trial(
            {
                "phase_score": 3,
                "has_results": True,
                "data_completeness_ratio": 0.9,
                "event_date_quality_score": 95,
                "sponsor_class": "INDUSTRY",
            },
            sponsor_mapping={"ticker": "PFE"},
        )

        self.assertEqual(result["status"], "available")
        self.assertEqual(result["model_version"], BASELINE_MODEL_VERSION)
        self.assertGreater(result["success_probability"], 0.6)
        self.assertEqual(result["probability_tier"], "favorable")
        self.assertEqual(result["features"]["public_sponsor_mapping"], 1.0)
        self.assertIn("phase_score", result["contributions"])
        self.assertEqual(result["warnings"], [])

    def test_score_trial_flags_missing_feature_fallbacks(self) -> None:
        service = BaselineModelService()

        result = service.score_trial({"sponsor_class": "other"})

        self.assertEqual(result["status"], "available")
        self.assertLess(result["success_probability"], 0.5)
        self.assertEqual(result["probability_tier"], "elevated_risk")
        self.assertIn("phase_score_missing", result["warnings"])
        self.assertIn("data_completeness_missing", result["warnings"])
        self.assertIn("event_date_quality_missing", result["warnings"])


if __name__ == "__main__":
    unittest.main()
