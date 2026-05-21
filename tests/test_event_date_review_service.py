from __future__ import annotations

import unittest
from unittest.mock import patch

from app.services.event_date_review_service import EventDateReviewService


class _RepositoryStub:
    def __init__(self) -> None:
        self.created = False
        self.records: list[dict] = []
        self.reviews_by_nct_id: dict[str, dict] = {}

    def create_tables(self) -> None:
        self.created = True

    def upsert_review(self, review_record: dict[str, object]) -> int:
        self.records.append(review_record)
        nct_id = str(review_record["nct_id"])
        self.reviews_by_nct_id[nct_id] = {"review_id": 301, **review_record}
        return 301

    def get_review_by_nct_id(self, nct_id: str) -> dict | None:
        return self.reviews_by_nct_id.get(nct_id)


class _ConnectionStub:
    def __enter__(self) -> _ConnectionStub:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


class EventDateReviewServiceTests(unittest.TestCase):
    def test_requires_review_for_missing_event_date(self) -> None:
        service = EventDateReviewService()

        self.assertTrue(service.requires_review({"nct_id": "NCT00000001"}))

    def test_requires_review_for_non_day_precision_event_date(self) -> None:
        service = EventDateReviewService()

        self.assertTrue(
            service.requires_review(
                {
                    "nct_id": "NCT00000001",
                    "event_date_candidate": "2025-01",
                    "event_date_precision": "month",
                    "event_date_quality_score": 78,
                    "event_date_quality_tier": "moderate",
                }
            )
        )

    def test_build_review_record_sets_reason_and_normalizes_fields(self) -> None:
        service = EventDateReviewService(review_quality_score_threshold=70)

        record = service.build_review_record(
            trial_record={
                "nct_id": "NCT00000001",
                "requested_nct_id": "NCT00000001",
                "sponsor_name": "Pfizer Inc.",
                "mapped_ticker": "pfe",
                "event_date_candidate": "2025-01-15",
                "event_date_source": "last_update_posted",
                "event_date_source_rank": 1,
                "event_date_precision": "day",
                "event_date_confidence": "low",
                "event_date_quality_score": 42,
                "event_date_quality_tier": "low",
                "event_date_quality_issues": ["low_rank_event_date_source"],
            },
            review_notes="  weak   proxy   source  ",
        )

        self.assertEqual(record["nct_id"], "NCT00000001")
        self.assertEqual(record["mapped_ticker"], "PFE")
        self.assertEqual(record["event_date_quality_tier"], "low")
        self.assertEqual(record["review_reason"], "low_event_date_quality_score")
        self.assertEqual(record["review_notes"], "weak proxy source")

    def test_build_review_record_sets_reviewed_at_for_terminal_status(self) -> None:
        service = EventDateReviewService()

        record = service.build_review_record(
            trial_record={"nct_id": "NCT00000001"},
            review_status="approved",
        )

        self.assertEqual(record["review_status"], "approved")
        self.assertIsNotNone(record["reviewed_at"])

    def test_queue_review_persists_when_review_is_needed(self) -> None:
        service = EventDateReviewService()
        repository = _RepositoryStub()

        with (
            patch(
                "app.services.event_date_review_service.get_connection",
                return_value=_ConnectionStub(),
            ),
            patch(
                "app.services.event_date_review_service.EventDateReviewRepository",
                return_value=repository,
            ),
        ):
            result = service.queue_review(
                trial_record={
                    "nct_id": "NCT00000001",
                    "event_date_candidate": "2025-01",
                    "event_date_precision": "month",
                    "event_date_quality_score": 68,
                    "event_date_quality_tier": "moderate",
                }
            )

        self.assertTrue(result["queued"])
        self.assertEqual(result["review_id"], 301)
        self.assertTrue(repository.created)
        self.assertEqual(repository.records[0]["review_reason"], "non_day_precision_event_date")

    def test_queue_review_skips_high_quality_day_precision_event_dates(self) -> None:
        service = EventDateReviewService(review_quality_score_threshold=70)

        result = service.queue_review(
            trial_record={
                "nct_id": "NCT00000001",
                "event_date_candidate": "2025-01-15",
                "event_date_precision": "day",
                "event_date_quality_score": 95,
                "event_date_quality_tier": "high",
            }
        )

        self.assertFalse(result["queued"])
        self.assertEqual(result["reason"], "event_date_does_not_require_review")

    def test_submit_review_decision_defaults_approved_reviewed_values(self) -> None:
        service = EventDateReviewService()
        repository = _RepositoryStub()

        with (
            patch(
                "app.services.event_date_review_service.get_connection",
                return_value=_ConnectionStub(),
            ),
            patch(
                "app.services.event_date_review_service.EventDateReviewRepository",
                return_value=repository,
            ),
        ):
            result = service.submit_review_decision(
                trial_record={
                    "nct_id": "NCT00000001",
                    "event_date_candidate": "2025-01-15",
                    "event_date_source": "primary_completion_date",
                    "event_date_precision": "day",
                    "event_date_quality_score": 95,
                    "event_date_quality_tier": "high",
                },
                review_status="approved",
            )

        record = result["review_record"]
        self.assertEqual(record["review_status"], "approved")
        self.assertEqual(record["reviewed_event_date"], "2025-01-15")
        self.assertEqual(record["reviewed_event_date_source"], "primary_completion_date")

    def test_submit_review_decision_preserves_explicit_reviewed_override_values(self) -> None:
        service = EventDateReviewService()
        repository = _RepositoryStub()

        with (
            patch(
                "app.services.event_date_review_service.get_connection",
                return_value=_ConnectionStub(),
            ),
            patch(
                "app.services.event_date_review_service.EventDateReviewRepository",
                return_value=repository,
            ),
        ):
            result = service.submit_review_decision(
                trial_record={
                    "nct_id": "NCT00000001",
                    "event_date_candidate": "2025-01-15",
                    "event_date_source": "primary_completion_date",
                    "event_date_precision": "day",
                    "event_date_quality_score": 95,
                    "event_date_quality_tier": "high",
                },
                review_status="approved",
                reviewed_event_date="2025-01-12",
                reviewed_event_date_source="company_press_release",
            )

        record = result["review_record"]
        self.assertEqual(record["review_status"], "approved")
        self.assertEqual(record["reviewed_event_date"], "2025-01-12")
        self.assertEqual(record["reviewed_event_date_source"], "company_press_release")

    def test_submit_review_decision_appends_reviewer_notes(self) -> None:
        service = EventDateReviewService()
        repository = _RepositoryStub()
        repository.reviews_by_nct_id["NCT00000001"] = {
            "review_id": 301,
            "nct_id": "NCT00000001",
            "review_notes": "[2026-05-19T12:00:00+00:00 | status=pending] existing note",
        }

        with (
            patch(
                "app.services.event_date_review_service.get_connection",
                return_value=_ConnectionStub(),
            ),
            patch(
                "app.services.event_date_review_service.EventDateReviewRepository",
                return_value=repository,
            ),
        ):
            result = service.submit_review_decision(
                trial_record={"nct_id": "NCT00000001"},
                review_status="approved",
                reviewer_name="Arjav",
                reviewer_email="arjaviyer@gmail.com",
                review_notes="approved after checking company guidance",
            )

        notes = result["review_record"]["review_notes"]
        self.assertIn("existing note", notes)
        self.assertIn("approved after checking company guidance", notes)
        self.assertIn("status=approved", notes)
        self.assertIn("reviewer=Arjav", notes)

    def test_submit_review_decision_preserves_existing_notes_when_new_note_is_blank(self) -> None:
        service = EventDateReviewService()
        repository = _RepositoryStub()
        repository.reviews_by_nct_id["NCT00000001"] = {
            "review_id": 301,
            "nct_id": "NCT00000001",
            "review_notes": "[2026-05-19T12:00:00+00:00 | status=pending] existing note",
        }

        with (
            patch(
                "app.services.event_date_review_service.get_connection",
                return_value=_ConnectionStub(),
            ),
            patch(
                "app.services.event_date_review_service.EventDateReviewRepository",
                return_value=repository,
            ),
        ):
            result = service.submit_review_decision(
                trial_record={"nct_id": "NCT00000001"},
                review_status="approved",
                review_notes="   ",
            )

        self.assertEqual(
            result["review_record"]["review_notes"],
            "[2026-05-19T12:00:00+00:00 | status=pending] existing note",
        )

    def test_apply_review_override_prefers_approved_reviewed_event_date(self) -> None:
        service = EventDateReviewService()
        repository = _RepositoryStub()
        repository.reviews_by_nct_id["NCT00000001"] = {
            "review_id": 301,
            "nct_id": "NCT00000001",
            "review_status": "approved",
            "reviewed_event_date": "2025-01-12",
            "reviewed_event_date_source": "company_press_release",
        }

        with (
            patch(
                "app.services.event_date_review_service.get_connection",
                return_value=_ConnectionStub(),
            ),
            patch(
                "app.services.event_date_review_service.EventDateReviewRepository",
                return_value=repository,
            ),
        ):
            result = service.apply_review_override(
                {
                    "nct_id": "NCT00000001",
                    "event_date_candidate": "2025-01-15",
                    "event_date_source": "primary_completion_date",
                    "event_date_quality_score": 95,
                }
            )

        self.assertTrue(result["override_applied"])
        self.assertEqual(result["trial_record"]["event_date_candidate"], "2025-01-12")
        self.assertEqual(result["trial_record"]["event_date_source"], "company_press_release")


if __name__ == "__main__":
    unittest.main()
