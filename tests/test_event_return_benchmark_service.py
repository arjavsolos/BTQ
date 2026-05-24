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
        self.assertEqual(result["summary_sections"][3]["title"], "sample_size_warnings")
        self.assertEqual(result["summary_sections"][4]["title"], "cohort_comparisons")
        self.assertEqual(result["summary_sections"][5]["title"], "top_groups")
        self.assertEqual(result["summary_sections"][5]["metrics"]["top_positive_group"], "PHASE3")
        self.assertEqual(result["summary_sections"][5]["metrics"]["top_negative_group"], "PHASE2")
        self.assertEqual(result["summary_sections"][2]["metrics"]["event_date_override_applied_count"], 1)
        self.assertEqual(result["groups"][0]["group"], "PHASE3")
        self.assertEqual(result["groups"][0]["event_count"], 2)
        self.assertTrue(result["groups"][0]["is_small_sample"])
        self.assertIn("Only 2 event(s)", result["groups"][0]["small_sample_warning"])
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

    def test_build_benchmark_supports_therapeutic_area_grouping(self) -> None:
        service = EventReturnBenchmarkService()
        repository = _BenchmarkRepositoryStub(
            [
                {
                    "therapeutic_area": "Oncology",
                    "event_day_return": 0.18,
                    "post_window_return": 0.07,
                    "is_model_ready": True,
                    "event_date_override_applied": False,
                },
                {
                    "therapeutic_area": "Oncology",
                    "event_day_return": -0.02,
                    "post_window_return": -0.01,
                    "is_model_ready": True,
                    "event_date_override_applied": False,
                },
                {
                    "therapeutic_area": "Rare Disease",
                    "event_day_return": 0.03,
                    "post_window_return": 0.01,
                    "is_model_ready": False,
                    "event_date_override_applied": False,
                },
            ]
        )

        result = service.build_benchmark_from_repository(
            repository=repository,
            group_by="therapeutic_area",
        )

        self.assertEqual(result["group_by"], "therapeutic_area")
        self.assertEqual(result["groups"][0]["group"], "Oncology")
        self.assertEqual(result["groups"][0]["event_count"], 2)
        self.assertEqual(result["groups"][0]["average_event_day_return"], 0.08)
        self.assertEqual(result["groups"][1]["group"], "Rare Disease")

    def test_build_benchmark_adds_model_ready_and_review_heavy_comparisons(self) -> None:
        service = EventReturnBenchmarkService()
        repository = _BenchmarkRepositoryStub(
            [
                {
                    "phase_label": "PHASE3",
                    "event_day_return": 0.10,
                    "post_window_return": 0.03,
                    "is_model_ready": True,
                    "event_date_override_applied": False,
                    "sponsor_mapping_review_status": None,
                    "event_date_review_status": None,
                    "sponsor_mapping_override_applied": False,
                },
                {
                    "phase_label": "PHASE2",
                    "event_day_return": -0.02,
                    "post_window_return": 0.00,
                    "is_model_ready": False,
                    "event_date_override_applied": False,
                    "sponsor_mapping_review_status": None,
                    "event_date_review_status": None,
                    "sponsor_mapping_override_applied": False,
                },
                {
                    "phase_label": "PHASE2",
                    "event_day_return": 0.04,
                    "post_window_return": 0.01,
                    "is_model_ready": True,
                    "event_date_override_applied": True,
                    "sponsor_mapping_review_status": "approved",
                    "event_date_review_status": "approved",
                    "sponsor_mapping_override_applied": False,
                },
            ]
        )

        result = service.build_benchmark_from_repository(repository=repository, group_by="phase_label")
        comparison_section = result["summary_sections"][4]

        self.assertEqual(comparison_section["title"], "cohort_comparisons")
        self.assertEqual(comparison_section["metrics"]["model_ready_event_count"], 2)
        self.assertEqual(comparison_section["metrics"]["model_ready_average_event_day_return"], 0.07)
        self.assertEqual(comparison_section["metrics"]["non_model_ready_event_count"], 1)
        self.assertEqual(comparison_section["metrics"]["non_model_ready_average_event_day_return"], -0.02)
        self.assertEqual(comparison_section["metrics"]["review_heavy_event_count"], 1)
        self.assertEqual(comparison_section["metrics"]["review_heavy_average_event_day_return"], 0.04)
        self.assertEqual(comparison_section["metrics"]["clean_event_count"], 2)
        self.assertEqual(comparison_section["metrics"]["clean_average_event_day_return"], 0.04)
        self.assertEqual(comparison_section["metrics"]["model_ready_minus_non_model_ready_return_gap"], 0.09)
        self.assertEqual(comparison_section["metrics"]["review_heavy_minus_clean_return_gap"], 0.0)

    def test_build_benchmark_marks_small_sample_groups_against_threshold(self) -> None:
        service = EventReturnBenchmarkService()
        repository = _BenchmarkRepositoryStub(
            [
                {
                    "phase_label": "PHASE3",
                    "event_day_return": 0.10,
                    "post_window_return": 0.03,
                    "is_model_ready": True,
                },
                {
                    "phase_label": "PHASE2",
                    "event_day_return": 0.02,
                    "post_window_return": 0.01,
                    "is_model_ready": True,
                },
                {
                    "phase_label": "PHASE2",
                    "event_day_return": 0.04,
                    "post_window_return": 0.01,
                    "is_model_ready": True,
                },
            ]
        )

        result = service.build_benchmark_from_repository(
            repository=repository,
            group_by="phase_label",
            min_group_size=2,
        )
        warning_section = result["summary_sections"][3]

        self.assertEqual(warning_section["title"], "sample_size_warnings")
        self.assertEqual(warning_section["metrics"]["min_group_size"], 2)
        self.assertEqual(warning_section["metrics"]["small_sample_group_count"], 1)
        self.assertEqual(warning_section["metrics"]["small_sample_groups"], ["PHASE3"])
        self.assertTrue(result["groups"][1]["is_small_sample"])
        self.assertIsNone(result["groups"][0]["small_sample_warning"])

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
                group_by="unknown_group",
            )


if __name__ == "__main__":
    unittest.main()
