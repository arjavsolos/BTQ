from __future__ import annotations

import unittest

from app.services.historical_dataset_audit_service import HistoricalDatasetAuditService


class _HistoricalAuditRepoStub:
    def get_quality_summary(self) -> dict:
        return {
            "total_events": 10,
            "model_ready_events": 6,
            "missing_ticker_events": 2,
            "missing_event_date_events": 1,
            "missing_market_data_events": 3,
            "missing_event_return_events": 4,
            "missing_fda_context_events": 5,
            "warning_events": 4,
            "missing_mapping_confidence_events": 1,
            "low_confidence_mapping_events": 2,
            "low_completeness_events": 3,
            "average_data_completeness_ratio": 0.745,
            "average_mapping_confidence": 0.88,
            "average_event_day_return": 0.03123,
            "average_post_window_return": 0.05234,
        }

    def get_phase_breakdown(self) -> list[dict]:
        return [
            {"phase_label": "PHASE3", "event_count": 4, "model_ready_count": 3},
            {"phase_label": "PHASE2", "event_count": 2, "model_ready_count": 1},
        ]

    def get_therapeutic_area_breakdown(self, limit: int = 10) -> list[dict]:
        return [
            {"therapeutic_area": "Oncology", "event_count": 5, "model_ready_count": 3},
            {"therapeutic_area": "Neurology", "event_count": 2, "model_ready_count": 2},
        ][:limit]

    def get_event_date_precision_breakdown(self) -> list[dict]:
        return [
            {"event_date_precision": "day", "event_count": 8},
            {"event_date_precision": "month", "event_count": 2},
        ]

    def get_event_date_source_rank_breakdown(self) -> list[dict]:
        return [
            {"event_date_source_rank": 4, "event_count": 5},
            {"event_date_source_rank": 2, "event_count": 3},
            {"event_date_source_rank": 1, "event_count": 2},
        ]

    def get_event_date_confidence_breakdown(self) -> list[dict]:
        return [
            {"event_date_confidence": "high", "event_count": 6},
            {"event_date_confidence": "moderate", "event_count": 3},
            {"event_date_confidence": "low", "event_count": 1},
        ]

    def get_warning_frequency(self, limit: int = 10) -> list[dict]:
        return [
            {"warning": "Low confidence mapping", "warning_count": 2},
            {"warning": "Missing market data", "warning_count": 1},
        ][:limit]

    def get_recent_issues(self, limit: int = 25) -> list[dict]:
        return [
            {
                "event_id": 1,
                "nct_id": "NCT00000001",
                "sponsor_name": "Example Bio",
                "mapped_ticker": None,
                "event_date_candidate": "2025-01-15",
                "is_model_ready": False,
                "warning_count": 1,
                "mapping_confidence": 0.6,
                "data_completeness_ratio": 0.55,
                "event_day_return": None,
                "created_at": "2026-04-21T00:00:00+00:00",
            }
        ][:limit]


class HistoricalDatasetAuditServiceTests(unittest.TestCase):
    def test_build_report_from_repository_calculates_ratios(self) -> None:
        service = HistoricalDatasetAuditService()

        report = service.build_report_from_repository(
            repository=_HistoricalAuditRepoStub(),
            top_warning_limit=5,
            issue_limit=5,
            therapeutic_area_limit=5,
        )

        self.assertEqual(report["status"], "success")
        self.assertEqual(report["summary"]["total_events"], 10)
        self.assertEqual(report["summary"]["model_ready_ratio"], 0.6)
        self.assertEqual(report["summary"]["missing_fda_context_ratio"], 0.5)
        self.assertEqual(report["breakdowns"]["phase"][0]["model_ready_ratio"], 0.75)
        self.assertEqual(report["breakdowns"]["therapeutic_area"][1]["model_ready_ratio"], 1.0)
        self.assertEqual(report["breakdowns"]["event_date_source_rank"][0]["event_date_source_rank"], 4)
        self.assertEqual(report["breakdowns"]["event_date_confidence"][0]["event_date_confidence"], "high")
        self.assertEqual(report["warning_frequency"][0]["warning"], "Low confidence mapping")
        self.assertEqual(report["recent_issues"][0]["nct_id"], "NCT00000001")


if __name__ == "__main__":
    unittest.main()
