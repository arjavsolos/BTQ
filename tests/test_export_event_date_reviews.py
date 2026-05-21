from __future__ import annotations

import io
import json
import os
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from scripts import export_event_date_reviews


class _RepositoryStub:
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


class ExportEventDateReviewsScriptTests(unittest.TestCase):
    def test_main_outputs_json_payload_with_summary(self) -> None:
        repository = _RepositoryStub(
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
            patch.dict(
                os.environ,
                {
                    "EVENT_DATE_REVIEW_EXPORT_LIMIT": "25",
                    "EVENT_DATE_REVIEW_EXPORT_OFFSET": "5",
                    "EVENT_DATE_REVIEW_EXPORT_STATUS": "pending",
                    "EVENT_DATE_REVIEW_EXPORT_TICKER": "PFE",
                    "EVENT_DATE_REVIEW_EXPORT_EVENT_DATE_QUALITY_TIER": "low",
                    "EVENT_DATE_REVIEW_EXPORT_FORMAT": "json",
                    "EVENT_DATE_REVIEW_EXPORT_INCLUDE_SUMMARY": "true",
                },
                clear=False,
            ),
            patch(
                "scripts.export_event_date_reviews.get_connection",
                return_value=_ConnectionStub(),
            ),
            patch(
                "scripts.export_event_date_reviews.EventDateReviewRepository",
                return_value=repository,
            ),
            redirect_stdout(stdout),
        ):
            export_event_date_reviews.main()

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

    def test_main_outputs_jsonl_lines_without_summary_wrapper(self) -> None:
        repository = _RepositoryStub(
            [
                {"review_id": 1, "review_status": "pending", "event_date_quality_tier": "low"},
                {"review_id": 2, "review_status": "approved", "event_date_quality_tier": "high"},
            ]
        )
        stdout = io.StringIO()

        with (
            patch.dict(
                os.environ,
                {
                    "EVENT_DATE_REVIEW_EXPORT_FORMAT": "jsonl",
                },
                clear=False,
            ),
            patch(
                "scripts.export_event_date_reviews.get_connection",
                return_value=_ConnectionStub(),
            ),
            patch(
                "scripts.export_event_date_reviews.EventDateReviewRepository",
                return_value=repository,
            ),
            redirect_stdout(stdout),
        ):
            export_event_date_reviews.main()

        lines = [line for line in stdout.getvalue().splitlines() if line.strip()]
        self.assertEqual(len(lines), 2)
        self.assertEqual(json.loads(lines[0])["review_id"], 1)
        self.assertEqual(json.loads(lines[1])["review_id"], 2)

    def test_main_emits_structured_error_payload_for_invalid_format(self) -> None:
        stdout = io.StringIO()

        with (
            patch.dict(
                os.environ,
                {
                    "EVENT_DATE_REVIEW_EXPORT_FORMAT": "csv",
                },
                clear=False,
            ),
            redirect_stdout(stdout),
        ):
            with self.assertRaises(SystemExit) as context:
                export_event_date_reviews.main()

        self.assertEqual(context.exception.code, 1)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["status"], "error")
        self.assertIn("json, jsonl", payload["error"])


if __name__ == "__main__":
    unittest.main()
