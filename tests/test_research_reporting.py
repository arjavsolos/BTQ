from __future__ import annotations

import unittest

from app.research import render_trial_analysis_markdown


class ResearchReportingTests(unittest.TestCase):
    def test_render_trial_analysis_markdown_includes_final_comparison(self) -> None:
        markdown = render_trial_analysis_markdown(
            {
                "summary": {
                    "nct_id": "NCT00000001",
                    "sponsor_name": "Pfizer Inc",
                    "mapped_ticker": "PFE",
                    "phase_label": "PHASE3",
                    "therapeutic_area": "Oncology",
                    "event_date_candidate": "2025-01-15",
                    "event_date_quality": {"quality_tier": "high", "quality_score": 95},
                },
                "event_date_quality": {
                    "quality_tier": "high",
                    "quality_score": 95,
                    "source": "primary_completion_date",
                    "precision": "day",
                },
                "expected_reaction": {
                    "profile": {
                        "expected_direction": "positive",
                        "confidence_tier": "moderate",
                        "caveats": [],
                    }
                },
                "market_expected_reaction_comparison": {
                    "status": "available",
                    "classification": "stronger_than_expected",
                    "actual_event_day_return": 0.123,
                    "expected_event_day_return": 0.08,
                },
                "final_comparison_summary": {
                    "headline": "Observed market reaction was stronger than historical expectation.",
                    "conclusion": "stronger_than_expected",
                    "expected_direction": "positive",
                    "expected_reaction_confidence": "moderate",
                    "event_date_quality_tier": "high",
                    "return_gap": 0.043,
                    "confidence_notes": [],
                },
                "analysis_readiness": {
                    "status": "production_ready",
                    "score": 96,
                    "blockers": [],
                    "cautions": ["manual_review_available"],
                },
                "modeled_success_probability": {
                    "model_version": "baseline-logistic-v1",
                    "probability_percent": 71.2,
                    "probability_tier": "favorable",
                },
                "bayesian_probability": {
                    "posterior_probability_percent": 68.4,
                    "confidence_tier": "moderate",
                },
                "warnings": [],
            }
        )

        self.assertIn("# Trial Analysis Report", markdown)
        self.assertIn("Observed market reaction was stronger than historical expectation.", markdown)
        self.assertIn("**Mapped ticker:** `PFE`", markdown)
        self.assertIn("**Classification:** `stronger_than_expected`", markdown)
        self.assertIn("## Production Readiness", markdown)
        self.assertIn("**Readiness status:** `production_ready`", markdown)
        self.assertIn("**Readiness score:** `96`", markdown)
        self.assertIn("## Modeled Success Probability", markdown)
        self.assertIn("**Success probability:** `71.2`", markdown)
        self.assertIn("**Bayesian posterior:** `68.4`", markdown)
        self.assertIn("**Bayesian confidence:** `moderate`", markdown)
        self.assertIn("**Quality tier:** `high`", markdown)


if __name__ == "__main__":
    unittest.main()
