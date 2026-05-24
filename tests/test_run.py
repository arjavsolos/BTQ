from __future__ import annotations

import io
import json
import sys
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

import run


class _BenchmarkServiceStub:
    def __init__(self, result: dict | None = None) -> None:
        self.result = result or {
            "status": "success",
            "group_by": "phase_label",
                "summary": {"event_count": 2, "group_count": 1},
                "expected_reaction_profile": {"expected_direction": "positive"},
                "groups": [],
            }
        self.calls: list[dict] = []

    def benchmark_dataset(
        self,
        group_by: str = "phase_label",
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
        min_group_size: int | None = None,
    ) -> dict:
        self.calls.append(
            {
                "group_by": group_by,
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
                "min_group_size": min_group_size,
            }
        )
        return dict(self.result)


class _HistoricalEventRepositoryStub:
    def __init__(self, events: list[dict]) -> None:
        self.events = events
        self.created = False
        self.list_events_calls: list[dict] = []

    def create_tables(self) -> None:
        self.created = True

    def list_events(
        self,
        limit: int = 100,
        offset: int = 0,
        is_model_ready: bool | None = None,
        mapped_ticker: str | None = None,
        phase_label: str | None = None,
        event_date_quality_tier: str | None = None,
        min_event_date_quality_score: int | None = None,
    ) -> list[dict]:
        self.list_events_calls.append(
            {
                "limit": limit,
                "offset": offset,
                "is_model_ready": is_model_ready,
                "mapped_ticker": mapped_ticker,
                "phase_label": phase_label,
                "event_date_quality_tier": event_date_quality_tier,
                "min_event_date_quality_score": min_event_date_quality_score,
            }
        )
        return list(self.events)


class _EventDateReviewRepositoryStub:
    def __init__(self, reviews: list[dict]) -> None:
        self.reviews = reviews
        self.created = False
        self.list_reviews_calls: list[dict] = []

    def create_tables(self) -> None:
        self.created = True

    def list_reviews(
        self,
        limit: int = 100,
        offset: int = 0,
        review_status: str | None = None,
        mapped_ticker: str | None = None,
        event_date_quality_tier: str | None = None,
    ) -> list[dict]:
        self.list_reviews_calls.append(
            {
                "limit": limit,
                "offset": offset,
                "review_status": review_status,
                "mapped_ticker": mapped_ticker,
                "event_date_quality_tier": event_date_quality_tier,
            }
        )
        return list(self.reviews)


class _ConnectionStub:
    def __enter__(self) -> _ConnectionStub:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


class RunParserTests(unittest.TestCase):
    def test_build_parser_supports_sponsor_mapping_review_export_command(self) -> None:
        parser = run.build_parser()

        args = parser.parse_args(
            [
                "export-sponsor-mapping-reviews",
                "--limit",
                "25",
                "--offset",
                "5",
                "--review-status",
                "pending",
                "--suggested-ticker",
                "PFE",
                "--reviewer-email",
                "arjaviyer@gmail.com",
                "--format",
                "jsonl",
                "--include-summary",
            ]
        )

        self.assertEqual(args.command, "export-sponsor-mapping-reviews")
        self.assertEqual(args.limit, 25)
        self.assertEqual(args.offset, 5)
        self.assertEqual(args.review_status, "pending")
        self.assertEqual(args.suggested_ticker, "PFE")
        self.assertEqual(args.reviewer_email, "arjaviyer@gmail.com")
        self.assertEqual(args.format, "jsonl")
        self.assertTrue(args.include_summary)

    def test_build_parser_supports_event_date_quality_backfill_filters(self) -> None:
        parser = run.build_parser()

        args = parser.parse_args(
            [
                "build-historical-dataset",
                "--limit",
                "50",
                "--min-event-date-quality-score",
                "80",
                "--event-date-quality-tier",
                "high",
            ]
        )

        self.assertEqual(args.command, "build-historical-dataset")
        self.assertEqual(args.limit, 50)
        self.assertEqual(args.min_event_date_quality_score, 80)
        self.assertEqual(args.event_date_quality_tier, "high")

    def test_build_parser_supports_historical_event_export_command(self) -> None:
        parser = run.build_parser()

        args = parser.parse_args(
            [
                "export-historical-trial-events",
                "--limit",
                "25",
                "--offset",
                "5",
                "--is-model-ready",
                "--mapped-ticker",
                "PFE",
                "--phase",
                "PHASE 3",
                "--event-date-quality-tier",
                "high",
                "--min-event-date-quality-score",
                "80",
                "--format",
                "jsonl",
                "--include-summary",
            ]
        )

        self.assertEqual(args.command, "export-historical-trial-events")
        self.assertEqual(args.limit, 25)
        self.assertEqual(args.offset, 5)
        self.assertTrue(args.is_model_ready)
        self.assertEqual(args.mapped_ticker, "PFE")
        self.assertEqual(args.phase, "PHASE 3")
        self.assertEqual(args.event_date_quality_tier, "high")
        self.assertEqual(args.min_event_date_quality_score, 80)
        self.assertEqual(args.format, "jsonl")
        self.assertTrue(args.include_summary)

    def test_build_parser_supports_event_date_review_export_command(self) -> None:
        parser = run.build_parser()

        args = parser.parse_args(
            [
                "export-event-date-reviews",
                "--limit",
                "25",
                "--offset",
                "5",
                "--review-status",
                "pending",
                "--mapped-ticker",
                "PFE",
                "--event-date-quality-tier",
                "low",
                "--format",
                "jsonl",
                "--include-summary",
            ]
        )

        self.assertEqual(args.command, "export-event-date-reviews")
        self.assertEqual(args.limit, 25)
        self.assertEqual(args.offset, 5)
        self.assertEqual(args.review_status, "pending")
        self.assertEqual(args.mapped_ticker, "PFE")
        self.assertEqual(args.event_date_quality_tier, "low")
        self.assertEqual(args.format, "jsonl")
        self.assertTrue(args.include_summary)

    def test_build_parser_supports_event_return_benchmark_command(self) -> None:
        parser = run.build_parser()

        args = parser.parse_args(
            [
                "benchmark-event-returns",
                "--group-by",
                "therapeutic_area",
                "--limit",
                "250",
                "--offset",
                "10",
                "--is-model-ready",
                "--mapped-ticker",
                "PFE",
                "--sponsor",
                "Pfizer",
                "--phase",
                "PHASE 3",
                "--event-date-quality-tier",
                "high",
                "--sponsor-mapping-review-status",
                "approved",
                "--event-date-review-status",
                "approved",
                "--sponsor-mapping-override",
                "--event-date-override",
                "--min-event-date-quality-score",
                "80",
                "--min-group-size",
                "3",
                "--format",
                "markdown",
            ]
        )

        self.assertEqual(args.command, "benchmark-event-returns")
        self.assertEqual(args.group_by, "therapeutic_area")
        self.assertEqual(args.limit, 250)
        self.assertEqual(args.offset, 10)
        self.assertTrue(args.is_model_ready)
        self.assertEqual(args.mapped_ticker, "PFE")
        self.assertEqual(args.sponsor, "Pfizer")
        self.assertEqual(args.phase, "PHASE 3")
        self.assertEqual(args.event_date_quality_tier, "high")
        self.assertEqual(args.sponsor_mapping_review_status, "approved")
        self.assertEqual(args.event_date_review_status, "approved")
        self.assertTrue(args.sponsor_mapping_override)
        self.assertTrue(args.event_date_override)
        self.assertEqual(args.min_event_date_quality_score, 80)
        self.assertEqual(args.min_group_size, 3)
        self.assertEqual(args.format, "markdown")

    def test_main_exports_historical_events_with_summary(self) -> None:
        repository = _HistoricalEventRepositoryStub(
            [
                {
                    "event_id": 1,
                    "event_date_quality_tier": "high",
                    "event_date_quality_score": 90,
                    "is_model_ready": True,
                },
                {
                    "event_id": 2,
                    "event_date_quality_tier": "moderate",
                    "event_date_quality_score": 70,
                    "is_model_ready": False,
                },
            ]
        )
        stdout = io.StringIO()

        with (
            patch.object(
                sys,
                "argv",
                [
                    "run.py",
                    "export-historical-trial-events",
                    "--limit",
                    "25",
                    "--offset",
                    "5",
                    "--is-model-ready",
                    "--mapped-ticker",
                    "PFE",
                    "--phase",
                    "PHASE 3",
                    "--event-date-quality-tier",
                    "high",
                    "--min-event-date-quality-score",
                    "80",
                    "--include-summary",
                ],
            ),
            patch("run.get_connection", return_value=_ConnectionStub()),
            patch("run.HistoricalTrialEventRepository", return_value=repository),
            redirect_stdout(stdout),
        ):
            run.main()

        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["status"], "success")
        self.assertEqual(payload["summary"]["exported_event_count"], 2)
        self.assertEqual(payload["summary"]["model_ready_count"], 1)
        self.assertEqual(payload["summary"]["average_event_date_quality_score"], 80.0)
        self.assertTrue(repository.created)
        self.assertEqual(
            repository.list_events_calls[0],
            {
                "limit": 25,
                "offset": 5,
                "is_model_ready": True,
                "mapped_ticker": "PFE",
                "phase_label": "PHASE 3",
                "event_date_quality_tier": "high",
                "min_event_date_quality_score": 80,
            },
        )

    def test_main_exports_event_date_reviews_with_summary(self) -> None:
        repository = _EventDateReviewRepositoryStub(
            [
                {
                    "review_id": 1,
                    "review_status": "pending",
                    "event_date_quality_tier": "low",
                    "mapped_ticker": "PFE",
                },
                {
                    "review_id": 2,
                    "review_status": "approved",
                    "event_date_quality_tier": "moderate",
                    "mapped_ticker": "MRK",
                },
            ]
        )
        stdout = io.StringIO()

        with (
            patch.object(
                sys,
                "argv",
                [
                    "run.py",
                    "export-event-date-reviews",
                    "--limit",
                    "25",
                    "--offset",
                    "5",
                    "--review-status",
                    "pending",
                    "--mapped-ticker",
                    "PFE",
                    "--event-date-quality-tier",
                    "low",
                    "--include-summary",
                ],
            ),
            patch("run.get_connection", return_value=_ConnectionStub()),
            patch("run.EventDateReviewRepository", return_value=repository),
            redirect_stdout(stdout),
        ):
            run.main()

        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["status"], "success")
        self.assertEqual(payload["summary"]["exported_review_count"], 2)
        self.assertEqual(payload["summary"]["status_counts"]["pending"], 1)
        self.assertEqual(payload["summary"]["event_date_quality_tier_counts"]["low"], 1)
        self.assertTrue(repository.created)
        self.assertEqual(
            repository.list_reviews_calls[0],
            {
                "limit": 25,
                "offset": 5,
                "review_status": "pending",
                "mapped_ticker": "PFE",
                "event_date_quality_tier": "low",
            },
        )

    def test_main_benchmarks_event_returns(self) -> None:
        service = _BenchmarkServiceStub(
            result={
                "status": "success",
                "group_by": "sponsor_class",
                "summary": {"event_count": 3, "group_count": 2},
                "summary_sections": [
                    {"title": "coverage", "metrics": {}, "display_summary": "coverage"},
                    {"title": "sample_size_warnings", "metrics": {}, "display_summary": "sample warnings"},
                    {"title": "cohort_comparisons", "metrics": {}, "display_summary": "comparisons"},
                    {"title": "expected_reaction", "metrics": {}, "display_summary": "expected reaction"},
                    {"title": "top_groups", "metrics": {}, "display_summary": "top groups"},
                ],
                "expected_reaction_profile": {"expected_direction": "positive"},
                "groups": [{"group": "PHASE3", "event_count": 2}],
            }
        )
        stdout = io.StringIO()

        with (
            patch.object(
                sys,
                "argv",
                [
                    "run.py",
                    "benchmark-event-returns",
                    "--group-by",
                    "sponsor_class",
                    "--limit",
                    "250",
                    "--offset",
                    "10",
                    "--is-model-ready",
                    "--mapped-ticker",
                    "PFE",
                    "--sponsor",
                    "Pfizer",
                    "--phase",
                    "PHASE 3",
                    "--event-date-quality-tier",
                    "high",
                    "--sponsor-mapping-review-status",
                    "approved",
                    "--event-date-review-status",
                    "approved",
                    "--sponsor-mapping-override",
                    "--event-date-override",
                    "--min-event-date-quality-score",
                    "80",
                    "--min-group-size",
                    "3",
                    "--format",
                    "markdown",
                ],
            ),
            patch("run.EventReturnBenchmarkService", return_value=service),
            redirect_stdout(stdout),
        ):
            run.main()

        output = stdout.getvalue()
        self.assertIn("# Event Return Benchmark", output)
        self.assertIn("### sample_size_warnings", output)
        self.assertIn("### cohort_comparisons", output)
        self.assertIn("### expected_reaction", output)
        self.assertIn("### top_groups", output)
        self.assertIn("PHASE3", output)
        self.assertEqual(
            service.calls[0],
            {
                "group_by": "sponsor_class",
                "limit": 250,
                "offset": 10,
                "is_model_ready": True,
                "mapped_ticker": "PFE",
                "sponsor_name": "Pfizer",
                "phase_label": "PHASE 3",
                "event_date_quality_tier": "high",
                "sponsor_mapping_review_status": "approved",
                "event_date_review_status": "approved",
                "sponsor_mapping_override_applied": True,
                "event_date_override_applied": True,
                "min_event_date_quality_score": 80,
                "min_group_size": 3,
            },
        )


if __name__ == "__main__":
    unittest.main()
