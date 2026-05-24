from __future__ import annotations

import unittest

from app.services.event_return_benchmark_service import EventReturnBenchmarkService


class _BenchmarkRepositoryStub:
    def __init__(self, events: list[dict]) -> None:
        self.events = events
        self.list_events_calls: list[dict] = []

    def list_events(
        self,
        limit: int = 1000,
        offset: int = 0,
        is_model_ready: bool | None = None,
        mapped_ticker: str | None = None,
        sponsor_name: str | None = None,
        phase_label: str | None = None,
        event_date_quality_tier: str | None = None,
        sponsor_mapping_review_status: str | None = None,
        event_date_review_status: str | None = None,
        sponsor_mapping_override_applied: bool | None = None,
        event_date_override_applied: bool | None = None,
        min_event_date_quality_score: int | None = None,
    ) -> list[dict]:
        self.list_events_calls.append(
            {
                "limit": limit,
                "offset": offset,
                "is_model_ready": is_model_ready,
                "mapped_ticker": mapped_ticker,
                "sponsor_name": sponsor_name,
                "phase_label": phase_label,
                "event_date_quality_tier": event_date_quality_tier,
                "sponsor_mapping_review_status": sponsor_mapping_review_status,
                "event_date_review_status": event_date_review_status,
                "sponsor_mapping_override_applied": sponsor_mapping_override_applied,
                "event_date_override_applied": event_date_override_applied,
                "min_event_date_quality_score": min_event_date_quality_score,
            }
        )
        return list(self.events)


class EventReturnBenchmarkServiceTests(unittest.TestCase):
    def test_build_benchmark_groups_event_returns_by_phase(self) -> None:
        service = EventReturnBenchmarkService()
        repository = _BenchmarkRepositoryStub(
            [
                {
                    "phase_label": "PHASE3",
                    "event_day_return": 0.12,
                    "post_window_return": 0.08,
                    "is_model_ready": True,
                    "event_date_override_applied": True,
                },
                {
                    "phase_label": "PHASE3",
                    "event_day_return": -0.02,
                    "post_window_return": 0.01,
                    "is_model_ready": False,
                    "event_date_override_applied": False,
                },
                {
                    "phase_label": "PHASE2",
                    "event_day_return": 0.04,
                    "post_window_return": None,
                    "is_model_ready": True,
                    "event_date_override_applied": False,
                },
            ]
        )

        result = service.build_benchmark_from_repository(
            repository=repository,
            group_by="phase_label",
            limit=50,
            offset=5,
            is_model_ready=None,
            mapped_ticker="PFE",
            event_date_quality_tier="high",
            min_event_date_quality_score=80,
        )

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["group_by"], "phase_label")
        self.assertEqual(result["summary"]["event_count"], 3)
        self.assertEqual(result["summary"]["group_count"], 2)
        self.assertEqual(result["summary"]["average_event_day_return"], 0.046667)
        self.assertEqual(result["summary_sections"][0]["title"], "coverage")
        self.assertEqual(result["summary_sections"][0]["metrics"]["model_ready_count"], 2)
        self.assertEqual(result["summary_sections"][1]["title"], "returns")
        self.assertEqual(result["summary_sections"][2]["title"], "review_provenance")
        self.assertEqual(result["summary_sections"][3]["title"], "top_groups")
        self.assertEqual(result["summary_sections"][3]["metrics"]["top_positive_group"], "PHASE3")
        self.assertEqual(result["summary_sections"][3]["metrics"]["top_negative_group"], "PHASE2")
        self.assertEqual(result["summary_sections"][2]["metrics"]["event_date_override_applied_count"], 1)
        self.assertEqual(result["groups"][0]["group"], "PHASE3")
        self.assertEqual(result["groups"][0]["event_count"], 2)
        self.assertEqual(result["groups"][0]["model_ready_ratio"], 0.5)
        self.assertEqual(result["groups"][0]["average_event_day_return"], 0.05)
        self.assertEqual(result["groups"][0]["median_event_day_return"], 0.05)
        self.assertEqual(result["groups"][0]["positive_event_day_ratio"], 0.5)
        self.assertEqual(result["groups"][0]["event_date_override_applied_count"], 1)
        self.assertEqual(
            repository.list_events_calls[0],
            {
                "limit": 50,
                "offset": 5,
                "is_model_ready": None,
                "mapped_ticker": "PFE",
                "sponsor_name": None,
                "phase_label": None,
                "event_date_quality_tier": "high",
                "sponsor_mapping_review_status": None,
                "event_date_review_status": None,
                "sponsor_mapping_override_applied": None,
                "event_date_override_applied": None,
                "min_event_date_quality_score": 80,
            },
        )

    def test_build_benchmark_supports_review_status_grouping(self) -> None:
        service = EventReturnBenchmarkService()
        repository = _BenchmarkRepositoryStub(
            [
                {
                    "sponsor_mapping_review_status": "approved",
                    "event_day_return": 0.10,
                    "post_window_return": 0.02,
                    "is_model_ready": True,
                    "event_date_override_applied": False,
                    "sponsor_mapping_override_applied": True,
                },
                {
                    "sponsor_mapping_review_status": None,
                    "event_day_return": -0.05,
                    "post_window_return": -0.01,
                    "is_model_ready": False,
                    "event_date_override_applied": False,
                    "sponsor_mapping_override_applied": False,
                },
            ]
        )

        result = service.build_benchmark_from_repository(
            repository=repository,
            group_by="sponsor_mapping_review_status",
        )

        self.assertEqual(
            result["summary_sections"][2]["metrics"]["sponsor_mapping_override_applied_count"],
            1,
        )
        self.assertEqual(result["groups"][0]["group"], "UNKNOWN")
        self.assertEqual(result["groups"][1]["group"], "approved")

    def test_build_benchmark_passes_review_provenance_filters(self) -> None:
        service = EventReturnBenchmarkService()
        repository = _BenchmarkRepositoryStub([])

        service.build_benchmark_from_repository(
            repository=repository,
            group_by="event_date_review_status",
            sponsor_name="Pfizer",
            sponsor_mapping_review_status="approved",
            event_date_review_status="approved",
            sponsor_mapping_override_applied=True,
            event_date_override_applied=True,
        )

        self.assertEqual(
            repository.list_events_calls[0],
            {
                "limit": 1000,
                "offset": 0,
                "is_model_ready": None,
                "mapped_ticker": None,
                "sponsor_name": "Pfizer",
                "phase_label": None,
                "event_date_quality_tier": None,
                "sponsor_mapping_review_status": "approved",
                "event_date_review_status": "approved",
                "sponsor_mapping_override_applied": True,
                "event_date_override_applied": True,
                "min_event_date_quality_score": None,
            },
        )

    def test_build_benchmark_rejects_invalid_group_by(self) -> None:
        service = EventReturnBenchmarkService()

        with self.assertRaises(ValueError):
            service.build_benchmark_from_repository(
                repository=_BenchmarkRepositoryStub([]),
                group_by="therapeutic_area",
            )


if __name__ == "__main__":
    unittest.main()
