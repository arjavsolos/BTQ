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
            "sponsor_class": "industry",
            "phase_label": "PHASE3",
            "phase_score": 3,
            "overall_status": "COMPLETED",
            "therapeutic_area": "Oncology",
            "has_results": True,
            "data_completeness_ratio": 0.9,
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


class _EventDateReviewStub:
    def __init__(self, queue_result: dict | None = None, override_result: dict | None = None) -> None:
        self.queue_result = queue_result or {
            "queued": False,
            "reason": "event_date_does_not_require_review",
            "review_id": None,
            "review_record": None,
        }
        self.override_result = override_result or {
            "trial_record": None,
            "review_record": None,
            "override_applied": False,
        }
        self.calls: list[dict] = []
        self.override_calls: list[dict] = []

    def queue_review(self, trial_record: dict[str, object], review_reason: str | None = None, force: bool = False):
        self.calls.append(
            {
                "trial_record": dict(trial_record),
                "review_reason": review_reason,
                "force": force,
            }
        )
        return self.queue_result

    def apply_review_override(self, trial_record: dict[str, object]) -> dict:
        self.override_calls.append({"trial_record": dict(trial_record)})
        if self.override_result.get("trial_record") is None:
            return {
                "trial_record": trial_record,
                "review_record": self.override_result.get("review_record"),
                "override_applied": self.override_result.get("override_applied", False),
            }
        return self.override_result


class _ExpectedReactionBenchmarkStub:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def benchmark_dataset(
        self,
        group_by: str = "phase_label",
        limit: int = 1000,
        offset: int = 0,
        is_model_ready: bool | None = None,
        phase_label: str | None = None,
        event_date_quality_tier: str | None = None,
        min_group_size: int | None = None,
        **_: object,
    ) -> dict:
        self.calls.append(
            {
                "group_by": group_by,
                "limit": limit,
                "offset": offset,
                "is_model_ready": is_model_ready,
                "phase_label": phase_label,
                "event_date_quality_tier": event_date_quality_tier,
                "min_group_size": min_group_size,
            }
        )
        return {
            "status": "success",
            "group_by": group_by,
            "summary": {"event_count": 30, "group_count": 2},
            "expected_reaction_profile": {
                "expected_direction": "positive",
                "confidence_tier": "moderate",
                "average_event_day_return": 0.08,
                "median_event_day_return": 0.05,
                "caveats": [],
            },
            "summary_sections": [
                {
                    "title": "sample_size_warnings",
                    "metrics": {"small_sample_group_count": 0},
                    "display_summary": "No small sample groups.",
                }
            ],
        }


class TrialAnalysisServiceTests(unittest.TestCase):
    def test_analyze_trial_returns_joined_output(self) -> None:
        service = TrialAnalysisService(
            clinical_trials_ingestor=_ClinicalStub(),
            sec_mapper=_SecStub(),
            openfda_ingestor=_OpenFDAStub(),
            market_data_ingestor=_MarketStub(),
            sponsor_mapping_review_service=_SponsorReviewStub(),
            event_date_review_service=_EventDateReviewStub(),
            expected_reaction_benchmark_service=_ExpectedReactionBenchmarkStub(),
        )

        result = service.analyze_trial("NCT00000001")

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["summary"]["mapped_ticker"], "PFE")
        self.assertEqual(result["summary"]["event_date_source_rank"], 4)
        self.assertEqual(result["summary"]["event_date_quality_score"], 95)
        self.assertEqual(result["summary"]["event_date_quality_tier"], "high")
        self.assertEqual(result["summary"]["event_date_quality"]["quality_score"], 95)
        self.assertTrue(result["summary"]["event_date_quality"]["is_market_usable"])
        self.assertEqual(result["summary"]["modeled_success_probability"]["status"], "available")
        self.assertGreater(result["summary"]["modeled_success_probability"]["success_probability"], 0.6)
        self.assertEqual(result["modeled_success_probability"]["probability_tier"], "favorable")
        self.assertEqual(result["event_date_quality"]["quality_tier"], "high")
        self.assertFalse(result["event_date_review"]["queued"])
        self.assertEqual(result["fda_context"]["approval_record_count"], 1)
        self.assertEqual(result["market_data"]["event_day_return"], 0.123)
        self.assertEqual(result["analysis_readiness"]["status"], "production_ready")
        self.assertEqual(result["analysis_readiness"]["score"], 100)
        self.assertEqual(result["analysis_readiness"]["blockers"], [])
        self.assertEqual(result["summary"]["analysis_readiness"]["status"], "production_ready")
        self.assertEqual(result["warnings"], [])

    def test_analyze_trial_attaches_expected_reaction_context(self) -> None:
        benchmark_stub = _ExpectedReactionBenchmarkStub()
        service = TrialAnalysisService(
            clinical_trials_ingestor=_ClinicalStub(),
            sec_mapper=_SecStub(),
            openfda_ingestor=_OpenFDAStub(),
            market_data_ingestor=_MarketStub(),
            sponsor_mapping_review_service=_SponsorReviewStub(),
            event_date_review_service=_EventDateReviewStub(),
            expected_reaction_benchmark_service=benchmark_stub,
        )

        result = service.analyze_trial("NCT00000001")

        self.assertEqual(result["expected_reaction"]["status"], "available")
        self.assertEqual(result["expected_reaction"]["group_by"], "therapeutic_area")
        self.assertEqual(result["expected_reaction"]["mapped_ticker"], "PFE")
        self.assertEqual(result["expected_reaction"]["profile"]["expected_direction"], "positive")
        self.assertEqual(result["expected_reaction"]["profile"]["confidence_tier"], "moderate")
        self.assertEqual(result["summary"]["expected_reaction_status"], "available")
        self.assertEqual(result["summary"]["expected_reaction_profile"]["average_event_day_return"], 0.08)
        self.assertEqual(result["expected_reaction"]["benchmark_summary"]["event_count"], 30)
        self.assertEqual(result["market_expected_reaction_comparison"]["status"], "available")
        self.assertEqual(
            result["market_expected_reaction_comparison"]["classification"],
            "stronger_than_expected",
        )
        self.assertEqual(result["market_expected_reaction_comparison"]["actual_event_day_return"], 0.123)
        self.assertEqual(result["market_expected_reaction_comparison"]["expected_event_day_return"], 0.08)
        self.assertEqual(result["market_expected_reaction_comparison"]["return_gap"], 0.043)
        self.assertEqual(
            result["summary"]["market_expected_reaction_comparison"]["classification"],
            "stronger_than_expected",
        )
        self.assertEqual(result["final_comparison_summary"]["status"], "available")
        self.assertEqual(result["final_comparison_summary"]["conclusion"], "stronger_than_expected")
        self.assertEqual(
            result["final_comparison_summary"]["headline"],
            "Observed market reaction was stronger than historical expectation.",
        )
        self.assertEqual(result["final_comparison_summary"]["expected_direction"], "positive")
        self.assertEqual(result["final_comparison_summary"]["expected_reaction_confidence"], "moderate")
        self.assertEqual(result["final_comparison_summary"]["event_date_quality_tier"], "high")
        self.assertEqual(result["final_comparison_summary"]["return_gap"], 0.043)
        self.assertEqual(result["summary"]["final_comparison_summary"]["conclusion"], "stronger_than_expected")
        self.assertEqual(
            result["expected_reaction"]["cohort_filters"],
            {
                "is_model_ready": True,
                "phase_label": "PHASE3",
                "event_date_quality_tier": "high",
            },
        )
        self.assertEqual(
            benchmark_stub.calls[0],
            {
                "group_by": "therapeutic_area",
                "limit": 1000,
                "offset": 0,
                "is_model_ready": True,
                "phase_label": "PHASE3",
                "event_date_quality_tier": "high",
                "min_group_size": 5,
            },
        )

    def test_analyze_trial_uses_approved_mapping_override_when_available(self) -> None:
        service = TrialAnalysisService(
            clinical_trials_ingestor=_ClinicalStub(),
            sec_mapper=_SecStub(),
            openfda_ingestor=_OpenFDAStub(),
            market_data_ingestor=_MarketStub(),
            sponsor_mapping_review_service=_SponsorReviewStub(override_ticker="MRK"),
            event_date_review_service=_EventDateReviewStub(),
            expected_reaction_benchmark_service=_ExpectedReactionBenchmarkStub(),
        )

        result = service.analyze_trial("NCT00000001")

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["summary"]["mapped_ticker"], "MRK")
        self.assertEqual(result["market_data"]["ticker"], "MRK")
        self.assertIn(
            "Sponsor mapping used a reviewed override instead of the raw SEC match.",
            result["warnings"],
        )

    def test_analyze_trial_uses_approved_event_date_review_override_when_available(self) -> None:
        event_date_review_stub = _EventDateReviewStub(
            queue_result={
                "queued": False,
                "reason": "approved_review_exists",
                "review_id": 301,
                "review_record": {
                    "review_id": 301,
                    "review_status": "approved",
                    "reviewed_event_date": "2025-01-12",
                    "reviewed_event_date_source": "results_first_posted",
                },
                "override_applied": False,
            },
            override_result={
                "trial_record": {
                    "nct_id": "NCT00000001",
                    "brief_title": "Example Trial",
                    "sponsor_name": "Pfizer Inc",
                    "phase_label": "PHASE3",
                    "overall_status": "COMPLETED",
                    "therapeutic_area": "Oncology",
                    "event_date_candidate": "2025-01-12",
                    "event_date_source": "results_first_posted",
                    "event_date_source_rank": None,
                    "event_date_quality_score": None,
                    "event_date_quality_tier": None,
                    "event_date_quality_issues": [],
                },
                "review_record": {
                    "review_id": 301,
                    "review_status": "approved",
                    "reviewed_event_date": "2025-01-12",
                    "reviewed_event_date_source": "results_first_posted",
                },
                "override_applied": True,
            },
        )
        service = TrialAnalysisService(
            clinical_trials_ingestor=_ClinicalStub(),
            sec_mapper=_SecStub(),
            openfda_ingestor=_OpenFDAStub(),
            market_data_ingestor=_MarketStub(),
            sponsor_mapping_review_service=_SponsorReviewStub(),
            event_date_review_service=event_date_review_stub,
            expected_reaction_benchmark_service=_ExpectedReactionBenchmarkStub(),
        )

        result = service.analyze_trial("NCT00000001")

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["summary"]["event_date_candidate"], "2025-01-12")
        self.assertEqual(result["summary"]["event_date_source"], "results_first_posted")
        self.assertEqual(result["summary"]["event_date_source_rank"], 2)
        self.assertEqual(result["summary"]["event_date_quality_score"], 71)
        self.assertEqual(result["summary"]["event_date_quality_tier"], "moderate")
        self.assertEqual(result["market_data"]["event_date"], "2025-01-12")
        self.assertFalse(result["event_date_review"]["queued"])
        self.assertEqual(result["event_date_review"]["reason"], "approved_review_exists")
        self.assertTrue(result["event_date_review"]["override_applied"])
        self.assertIn(
            "Event date used an approved reviewed override instead of the original stored proxy.",
            result["warnings"],
        )

    def test_analyze_trial_surfaces_low_event_date_quality_warnings(self) -> None:
        review_stub = _EventDateReviewStub(
            queue_result={
                "queued": True,
                "reason": "review_record_upserted",
                "review_id": 301,
                "review_record": {
                    "nct_id": "NCT00000002",
                    "review_reason": "non_day_precision_event_date",
                    "review_status": "pending",
                },
            }
        )
        service = TrialAnalysisService(
            clinical_trials_ingestor=_ClinicalLowQualityStub(),
            sec_mapper=_SecStub(),
            openfda_ingestor=_OpenFDAStub(),
            market_data_ingestor=_MarketStub(),
            sponsor_mapping_review_service=_SponsorReviewStub(),
            event_date_review_service=review_stub,
            expected_reaction_benchmark_service=_ExpectedReactionBenchmarkStub(),
        )

        result = service.analyze_trial("NCT00000002")

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["summary"]["event_date_quality_tier"], "low")
        self.assertEqual(result["summary"]["event_date_quality"]["quality_tier"], "low")
        self.assertFalse(result["summary"]["event_date_quality"]["is_market_usable"])
        self.assertIn("low_confidence_event_date", result["event_date_quality"]["quality_issues"])
        self.assertTrue(result["event_date_review"]["queued"])
        self.assertEqual(result["event_date_review"]["review_record"]["review_reason"], "non_day_precision_event_date")
        self.assertIsNone(result["market_data"])
        self.assertEqual(review_stub.calls[0]["trial_record"]["mapped_ticker"], "PFE")
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
        self.assertIn(
            "Event date was queued for manual review because the catalyst-date proxy looks weak or ambiguous."
            " review_reason=non_day_precision_event_date",
            result["warnings"],
        )
        self.assertEqual(
            result["final_comparison_summary"]["headline"],
            "Insufficient data to compare observed market reaction with historical expectation.",
        )
        self.assertEqual(result["analysis_readiness"]["status"], "blocked")
        self.assertIn("event_date_not_market_usable", result["analysis_readiness"]["blockers"])
        self.assertIn("missing_market_reaction", result["analysis_readiness"]["blockers"])
        self.assertIn("analysis_returned_warnings", result["analysis_readiness"]["cautions"])
        self.assertIn(
            "Event-date quality weakens the reliability of the comparison.",
            result["final_comparison_summary"]["confidence_notes"],
        )


if __name__ == "__main__":
    unittest.main()
