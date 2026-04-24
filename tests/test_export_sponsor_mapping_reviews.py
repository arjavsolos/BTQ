from __future__ import annotations

import io
import json
import os
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from scripts import export_sponsor_mapping_reviews


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
        suggested_ticker: str | None = None,
        reviewer_email: str | None = None,
    ) -> list[dict]:
        self.list_reviews_calls.append(
            {
                "limit": limit,
                "offset": offset,
                "review_status": review_status,
                "suggested_ticker": suggested_ticker,
                "reviewer_email": reviewer_email,
            }
        )
        return list(self.reviews)


class _ConnectionStub:
    def __enter__(self) -> _ConnectionStub:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


class ExportSponsorMappingReviewsScriptTests(unittest.TestCase):
    def test_main_outputs_json_payload_with_summary(self) -> None:
        repository = _RepositoryStub(
            [
                {"review_id": 1, "review_status": "pending", "suggested_ticker": "PFE"},
                {"review_id": 2, "review_status": "approved", "suggested_ticker": "MRK"},
            ]
        )
        stdout = io.StringIO()

        with (
            patch.dict(
                os.environ,
                {
                    "SPONSOR_MAPPING_REVIEW_EXPORT_LIMIT": "25",
                    "SPONSOR_MAPPING_REVIEW_EXPORT_OFFSET": "5",
                    "SPONSOR_MAPPING_REVIEW_EXPORT_STATUS": "pending",
                    "SPONSOR_MAPPING_REVIEW_EXPORT_TICKER": "PFE",
                    "SPONSOR_MAPPING_REVIEW_EXPORT_REVIEWER_EMAIL": "arjaviyer@gmail.com",
                    "SPONSOR_MAPPING_REVIEW_EXPORT_FORMAT": "json",
                    "SPONSOR_MAPPING_REVIEW_EXPORT_INCLUDE_SUMMARY": "true",
                },
                clear=False,
            ),
            patch(
                "scripts.export_sponsor_mapping_reviews.get_connection",
                return_value=_ConnectionStub(),
            ),
            patch(
                "scripts.export_sponsor_mapping_reviews.SponsorMappingReviewRepository",
                return_value=repository,
            ),
            redirect_stdout(stdout),
        ):
            export_sponsor_mapping_reviews.main()

        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["status"], "success")
        self.assertEqual(payload["summary"]["exported_review_count"], 2)
        self.assertEqual(payload["summary"]["status_counts"]["pending"], 1)
        self.assertTrue(repository.created)
        self.assertEqual(
            repository.list_reviews_calls[0],
            {
                "limit": 25,
                "offset": 5,
                "review_status": "pending",
                "suggested_ticker": "PFE",
                "reviewer_email": "arjaviyer@gmail.com",
            },
        )

    def test_main_outputs_jsonl_lines_without_summary_wrapper(self) -> None:
        repository = _RepositoryStub(
            [
                {"review_id": 1, "review_status": "pending"},
                {"review_id": 2, "review_status": "approved"},
            ]
        )
        stdout = io.StringIO()

        with (
            patch.dict(
                os.environ,
                {
                    "SPONSOR_MAPPING_REVIEW_EXPORT_FORMAT": "jsonl",
                },
                clear=False,
            ),
            patch(
                "scripts.export_sponsor_mapping_reviews.get_connection",
                return_value=_ConnectionStub(),
            ),
            patch(
                "scripts.export_sponsor_mapping_reviews.SponsorMappingReviewRepository",
                return_value=repository,
            ),
            redirect_stdout(stdout),
        ):
            export_sponsor_mapping_reviews.main()

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
                    "SPONSOR_MAPPING_REVIEW_EXPORT_FORMAT": "csv",
                },
                clear=False,
            ),
            redirect_stdout(stdout),
        ):
            with self.assertRaises(SystemExit) as context:
                export_sponsor_mapping_reviews.main()

        self.assertEqual(context.exception.code, 1)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["status"], "error")
        self.assertIn("json, jsonl", payload["error"])


if __name__ == "__main__":
    unittest.main()
