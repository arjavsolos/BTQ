from __future__ import annotations

import unittest
from dataclasses import dataclass

from app.services.trial_analysis_service import TrialAnalysisService


class _ClinicalStub:
    def fetch_trial_data(self, nct_id: str, include_raw: bool = False) -> dict:
        return {
            "nct_id": nct_id,
            "brief_title": "Example Trial",
            "sponsor_name": "Pfizer Inc",
            "phase_label": "PHASE3",
            "overall_status": "COMPLETED",
            "therapeutic_area": "Oncology",
            "event_date_candidate": "2025-01-15",
            "event_date_source": "primary_completion_date",
            "event_date_source_rank": 4,
            "event_date_quality_score": 95,
            "event_date_quality_tier": "high",
            "event_date_quality_issues": [],
        }


class _ClinicalLowQualityStub:
    def fetch_trial_data(self, nct_id: str, include_raw: bool = False) -> dict:
        return {
            "nct_id": nct_id,
            "brief_title": "Example Trial",
            "sponsor_name": "Pfizer Inc",
            "phase_label": "PHASE2",
            "overall_status": "COMPLETED",
            "therapeutic_area": "Oncology",
            "event_date_candidate": "2025-01",
            "event_date_source": "last_update_posted",
            "event_date_source_rank": 1,
            "event_date_quality_score": 38,
            "event_date_quality_tier": "low",
            "event_date_quality_issues": [
                "non_day_precision_event_date",
                "low_rank_event_date_source",
                "low_confidence_event_date",
            ],
        }


class _SecStub:
    def match_sponsor_to_ticker(self, sponsor_name: str):
        @dataclass(slots=True)
        class Result:
            sponsor_name: str
            matched_company_name: str | None
            ticker: str | None
            cik: str | None
            confidence: float
            match_type: str
            alternatives: list[dict]

        return Result(
            sponsor_name=sponsor_name,
            matched_company_name="PFIZER INC",
            ticker="PFE",
            cik="0000078003",
            confidence=1.0,
            match_type="exact_normalized",
            alternatives=[],
        )


class _OpenFDAStub:
    def fetch_approval_snapshot(self, sponsor_name: str | None = None, search: str | None = None, limit: int = 25):
        return [{"application_number": "NDA000001", "sponsor_name": sponsor_name}]


class _MarketStub:
    def summarize_event_reaction(self, ticker: str, event_date: str, pre_days: int = 5, post_days: int = 5):
        return {
            "ticker": ticker,
            "event_date": event_date,
            "record_count": 10,
            "event_day_return": 0.123,
            "post_window_return": 0.045,
        }


class _SponsorReviewStub:
    def __init__(self, override_ticker: str | None = None) -> None:
        self.override_ticker = override_ticker

    def apply_review_override(self, sponsor_name: str | None, match_result: dict | None) -> dict:
        if not self.override_ticker or not match_result:
            return {
                "mapping": match_result,
                "review_record": None,
                "override_applied": False,
            }

        overridden_mapping = dict(match_result)
        overridden_mapping["ticker"] = self.override_ticker
        overridden_mapping["mapping_source"] = "sponsor_mapping_review"
        overridden_mapping["reviewed_mapping_status"] = "approved_override"
        return {
            "mapping": overridden_mapping,
            "review_record": {"review_status": "approved"},
            "override_applied": True,
        }


class TrialAnalysisServiceTests(unittest.TestCase):
    def test_analyze_trial_returns_joined_output(self) -> None:
        service = TrialAnalysisService(
            clinical_trials_ingestor=_ClinicalStub(),
            sec_mapper=_SecStub(),
            openfda_ingestor=_OpenFDAStub(),
            market_data_ingestor=_MarketStub(),
            sponsor_mapping_review_service=_SponsorReviewStub(),
        )

        result = service.analyze_trial("NCT00000001")

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["summary"]["mapped_ticker"], "PFE")
        self.assertEqual(result["summary"]["event_date_source_rank"], 4)
        self.assertEqual(result["summary"]["event_date_quality_score"], 95)
        self.assertEqual(result["summary"]["event_date_quality_tier"], "high")
        self.assertEqual(result["fda_context"]["approval_record_count"], 1)
        self.assertEqual(result["market_data"]["event_day_return"], 0.123)
        self.assertEqual(result["warnings"], [])

    def test_analyze_trial_uses_approved_mapping_override_when_available(self) -> None:
        service = TrialAnalysisService(
            clinical_trials_ingestor=_ClinicalStub(),
            sec_mapper=_SecStub(),
            openfda_ingestor=_OpenFDAStub(),
            market_data_ingestor=_MarketStub(),
            sponsor_mapping_review_service=_SponsorReviewStub(override_ticker="MRK"),
        )

        result = service.analyze_trial("NCT00000001")

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["summary"]["mapped_ticker"], "MRK")
        self.assertEqual(result["market_data"]["ticker"], "MRK")
        self.assertIn(
            "Sponsor mapping used a reviewed override instead of the raw SEC match.",
            result["warnings"],
        )

    def test_analyze_trial_surfaces_low_event_date_quality_warnings(self) -> None:
        service = TrialAnalysisService(
            clinical_trials_ingestor=_ClinicalLowQualityStub(),
            sec_mapper=_SecStub(),
            openfda_ingestor=_OpenFDAStub(),
            market_data_ingestor=_MarketStub(),
            sponsor_mapping_review_service=_SponsorReviewStub(),
        )

        result = service.analyze_trial("NCT00000002")

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["summary"]["event_date_quality_tier"], "low")
        self.assertIsNone(result["market_data"])
        self.assertIn(
            "Event date quality is low, so the selected catalyst date may be a weak "
            "proxy for the true market-moving event.",
            result["warnings"],
        )
        self.assertIn(
            "Event date relies on a lower-ranked proxy source instead of a primary completion milestone.",
            result["warnings"],
        )
        self.assertIn(
            "Event date confidence is low based on the available source and date precision.",
            result["warnings"],
        )
        self.assertIn(
            "Event date is not day-precision, so market event-window analysis was skipped.",
            result["warnings"],
        )


if __name__ == "__main__":
    unittest.main()
