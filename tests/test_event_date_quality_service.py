from __future__ import annotations

import unittest

from app.services import EventDateQualityService


class EventDateQualityServiceTests(unittest.TestCase):
    def test_assess_event_date_scores_high_quality_primary_completion_day(self) -> None:
        service = EventDateQualityService()

        assessment = service.assess_event_date(
            event_date_value="2025-01-15",
            event_date_source="primary_completion_date",
        )

        self.assertEqual(assessment["event_date_precision"], "day")
        self.assertEqual(assessment["event_date_source_rank"], 4)
        self.assertEqual(assessment["event_date_confidence"], "high")
        self.assertEqual(assessment["event_date_quality_score"], 95)
        self.assertEqual(assessment["event_date_quality_tier"], "high")
        self.assertEqual(assessment["event_date_quality_issues"], [])
        self.assertTrue(assessment["is_market_usable"])

    def test_assess_event_date_scores_moderate_results_posted_day(self) -> None:
        service = EventDateQualityService()

        assessment = service.assess_event_date(
            event_date_value="2025-02-10",
            event_date_source="results_first_posted",
        )

        self.assertEqual(assessment["event_date_quality_score"], 71)
        self.assertEqual(assessment["event_date_quality_tier"], "moderate")
        self.assertEqual(
            assessment["event_date_quality_issues"],
            ["low_rank_event_date_source"],
        )

    def test_assess_event_date_flags_low_quality_month_precision_fallback(self) -> None:
        service = EventDateQualityService()

        assessment = service.assess_event_date(
            event_date_value="2025-03",
            event_date_source="last_update_posted",
        )

        self.assertEqual(assessment["event_date_precision"], "month")
        self.assertEqual(assessment["event_date_confidence"], "low")
        self.assertEqual(assessment["event_date_quality_score"], 38)
        self.assertEqual(assessment["event_date_quality_tier"], "low")
        self.assertEqual(
            assessment["event_date_quality_issues"],
            [
                "non_day_precision_event_date",
                "low_rank_event_date_source",
                "low_confidence_event_date",
            ],
        )
        self.assertFalse(assessment["is_market_usable"])


if __name__ == "__main__":
    unittest.main()
