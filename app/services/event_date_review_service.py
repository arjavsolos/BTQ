from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.database.connection import get_connection
from app.database.repositories import EventDateReviewRepository


class EventDateReviewService:
    """
    Builds and queues event-date review records for weak or ambiguous catalyst-date proxies.
    """

    def __init__(self, review_quality_score_threshold: int = 70) -> None:
        self.review_quality_score_threshold = max(0, review_quality_score_threshold)

    def _normalize_review_notes(self, review_notes: str | None) -> str | None:
        if review_notes is None:
            return None
        clean_review_notes = " ".join(str(review_notes).split()).strip()
        return clean_review_notes or None

    def _compose_review_note_entry(
        self,
        review_notes: str,
        review_status: str,
        reviewer_name: str | None = None,
        reviewer_email: str | None = None,
    ) -> str:
        timestamp = datetime.now(UTC).isoformat()
        note_parts = [timestamp, f"status={review_status}"]
        if reviewer_name:
            note_parts.append(f"reviewer={reviewer_name.strip()}")
        if reviewer_email:
            note_parts.append(f"email={reviewer_email.strip()}")
        prefix = " | ".join(note_parts)
        return f"[{prefix}] {review_notes}"

    def _merge_review_notes(
        self,
        existing_review_notes: str | None,
        new_review_notes: str | None,
        review_status: str,
        reviewer_name: str | None = None,
        reviewer_email: str | None = None,
    ) -> str | None:
        clean_existing_review_notes = self._normalize_review_notes(existing_review_notes)
        clean_new_review_notes = self._normalize_review_notes(new_review_notes)
        if clean_new_review_notes is None:
            return clean_existing_review_notes

        note_entry = self._compose_review_note_entry(
            review_notes=clean_new_review_notes,
            review_status=review_status,
            reviewer_name=reviewer_name,
            reviewer_email=reviewer_email,
        )
        if clean_existing_review_notes is None:
            return note_entry
        if note_entry in clean_existing_review_notes:
            return clean_existing_review_notes
        return f"{clean_existing_review_notes}\n{note_entry}"

    def _build_effective_trial_from_review(
        self,
        trial_record: dict[str, Any],
        review_record: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        if review_record is None:
            return None
        if (review_record.get("review_status") or "").strip().lower() != "approved":
            return None

        reviewed_event_date = (review_record.get("reviewed_event_date") or "").strip()
        if not reviewed_event_date:
            return None

        effective_trial = dict(trial_record)
        effective_trial["event_date_candidate"] = reviewed_event_date
        reviewed_event_date_source = (review_record.get("reviewed_event_date_source") or "").strip() or None
        if reviewed_event_date_source:
            effective_trial["event_date_source"] = reviewed_event_date_source

        # Force downstream quality logic to reassess the final reviewed timing choice.
        effective_trial["event_date_source_rank"] = None
        effective_trial["event_date_precision"] = None
        effective_trial["event_date_confidence"] = None
        effective_trial["event_date_quality_score"] = None
        effective_trial["event_date_quality_tier"] = None
        effective_trial["event_date_quality_issues"] = []
        return effective_trial

    def _derive_review_reason(self, trial_record: dict[str, Any]) -> str:
        event_date_candidate = (trial_record.get("event_date_candidate") or "").strip()
        event_date_precision = (trial_record.get("event_date_precision") or "").strip().lower()
        quality_score = int(trial_record.get("event_date_quality_score") or 0)
        quality_tier = (trial_record.get("event_date_quality_tier") or "").strip().lower()
        quality_issues = list(trial_record.get("event_date_quality_issues") or [])

        if not event_date_candidate:
            return "missing_event_date_candidate"
        if event_date_precision != "day":
            return "non_day_precision_event_date"
        if quality_score < self.review_quality_score_threshold:
            return "low_event_date_quality_score"
        if quality_tier in {"low", "unknown"}:
            return f"{quality_tier}_event_date_quality"
        if "low_rank_event_date_source" in quality_issues:
            return "low_rank_event_date_source"
        if "low_confidence_event_date" in quality_issues:
            return "low_confidence_event_date"
        return "manual_review_requested"

    def requires_review(self, trial_record: dict[str, Any] | None) -> bool:
        if not trial_record:
            return True

        event_date_candidate = (trial_record.get("event_date_candidate") or "").strip()
        event_date_precision = (trial_record.get("event_date_precision") or "").strip().lower()
        quality_score = int(trial_record.get("event_date_quality_score") or 0)
        quality_tier = (trial_record.get("event_date_quality_tier") or "").strip().lower()

        if not event_date_candidate:
            return True
        if event_date_precision != "day":
            return True
        if quality_tier in {"low", "unknown"}:
            return True
        return quality_score < self.review_quality_score_threshold

    def build_review_record(
        self,
        trial_record: dict[str, Any],
        review_reason: str | None = None,
        review_status: str = "pending",
        reviewer_name: str | None = None,
        reviewer_email: str | None = None,
        review_notes: str | None = None,
        reviewed_event_date: str | None = None,
        reviewed_event_date_source: str | None = None,
        reviewed_at: str | None = None,
    ) -> dict[str, Any]:
        nct_id = " ".join(str(trial_record.get("nct_id") or "").split()).strip()
        if not nct_id:
            raise ValueError("nct_id is required to build an event date review record.")

        clean_review_status = (review_status or "pending").strip().lower()
        if clean_review_status in {"approved", "rejected"} and reviewed_at is None:
            reviewed_at = datetime.now(UTC).isoformat()

        resolved_review_reason = (
            " ".join(str(review_reason).split()).strip() if review_reason else self._derive_review_reason(trial_record)
        )

        return {
            "nct_id": nct_id,
            "requested_nct_id": trial_record.get("requested_nct_id"),
            "sponsor_name": trial_record.get("sponsor_name"),
            "mapped_ticker": (
                " ".join(str(trial_record.get("mapped_ticker") or "").split()).strip().upper() or None
            ),
            "event_date_candidate": trial_record.get("event_date_candidate"),
            "event_date_source": trial_record.get("event_date_source"),
            "event_date_source_rank": trial_record.get("event_date_source_rank"),
            "event_date_precision": trial_record.get("event_date_precision"),
            "event_date_confidence": trial_record.get("event_date_confidence"),
            "event_date_quality_score": trial_record.get("event_date_quality_score"),
            "event_date_quality_tier": (
                " ".join(str(trial_record.get("event_date_quality_tier") or "").split()).strip().lower() or None
            ),
            "event_date_quality_issues": trial_record.get("event_date_quality_issues") or [],
            "review_reason": resolved_review_reason,
            "review_status": clean_review_status,
            "reviewed_event_date": reviewed_event_date,
            "reviewed_event_date_source": reviewed_event_date_source,
            "reviewer_name": reviewer_name,
            "reviewer_email": reviewer_email,
            "review_notes": self._normalize_review_notes(review_notes),
            "reviewed_at": reviewed_at,
        }

    def submit_review_decision(
        self,
        trial_record: dict[str, Any],
        review_status: str,
        review_reason: str | None = None,
        reviewed_event_date: str | None = None,
        reviewed_event_date_source: str | None = None,
        reviewer_name: str | None = None,
        reviewer_email: str | None = None,
        review_notes: str | None = None,
    ) -> dict[str, Any]:
        nct_id = " ".join(str(trial_record.get("nct_id") or "").split()).strip()
        if not nct_id:
            raise ValueError("nct_id is required to submit an event date review decision.")

        clean_review_status = (review_status or "pending").strip().lower()
        with get_connection() as connection:
            repository = EventDateReviewRepository(connection)
            repository.create_tables()
            existing_review = repository.get_review_by_nct_id(nct_id)

            resolved_reviewed_event_date = reviewed_event_date
            resolved_reviewed_event_date_source = reviewed_event_date_source
            if clean_review_status == "approved":
                if not resolved_reviewed_event_date:
                    resolved_reviewed_event_date = trial_record.get("event_date_candidate")
                if not resolved_reviewed_event_date_source:
                    resolved_reviewed_event_date_source = trial_record.get("event_date_source")

            merged_review_notes = self._merge_review_notes(
                existing_review_notes=None if existing_review is None else existing_review.get("review_notes"),
                new_review_notes=review_notes,
                review_status=clean_review_status,
                reviewer_name=reviewer_name,
                reviewer_email=reviewer_email,
            )

            review_record = self.build_review_record(
                trial_record=trial_record,
                review_reason=review_reason,
                review_status=clean_review_status,
                reviewer_name=reviewer_name,
                reviewer_email=reviewer_email,
                review_notes=merged_review_notes,
                reviewed_event_date=resolved_reviewed_event_date,
                reviewed_event_date_source=resolved_reviewed_event_date_source,
            )
            review_id = repository.upsert_review(review_record)
            saved_review = repository.get_review_by_nct_id(review_record["nct_id"])

        return {
            "review_id": review_id,
            "review_record": saved_review if saved_review is not None else review_record,
        }

    def queue_review(
        self,
        trial_record: dict[str, Any],
        review_reason: str | None = None,
        force: bool = False,
    ) -> dict[str, Any]:
        if not force and not self.requires_review(trial_record):
            return {
                "queued": False,
                "reason": "event_date_does_not_require_review",
                "review_id": None,
                "review_record": None,
            }

        review_record = self.build_review_record(
            trial_record=trial_record,
            review_reason=review_reason,
        )
        with get_connection() as connection:
            repository = EventDateReviewRepository(connection)
            repository.create_tables()
            review_id = repository.upsert_review(review_record)

        return {
            "queued": True,
            "reason": "review_record_upserted",
            "review_id": review_id,
            "review_record": review_record,
        }

    def apply_review_override(self, trial_record: dict[str, Any] | None) -> dict[str, Any]:
        if not trial_record:
            return {
                "trial_record": trial_record,
                "review_record": None,
                "override_applied": False,
            }

        nct_id = " ".join(str(trial_record.get("nct_id") or "").split()).strip()
        if not nct_id:
            return {
                "trial_record": trial_record,
                "review_record": None,
                "override_applied": False,
            }

        with get_connection() as connection:
            repository = EventDateReviewRepository(connection)
            repository.create_tables()
            review_record = repository.get_review_by_nct_id(nct_id)

        effective_trial = self._build_effective_trial_from_review(trial_record, review_record)
        if effective_trial is None:
            return {
                "trial_record": trial_record,
                "review_record": review_record,
                "override_applied": False,
            }

        override_applied = (
            effective_trial.get("event_date_candidate") != trial_record.get("event_date_candidate")
            or effective_trial.get("event_date_source") != trial_record.get("event_date_source")
        )
        return {
            "trial_record": effective_trial,
            "review_record": review_record,
            "override_applied": override_applied,
        }
