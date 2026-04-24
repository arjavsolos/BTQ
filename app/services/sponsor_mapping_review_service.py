from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import UTC, datetime
from typing import Any

from app.database.connection import get_connection
from app.database.repositories import SponsorMappingReviewRepository
from app.ingestion.sec_mapping import SecCompanyMapper, SponsorMatchResult


class SponsorMappingReviewService:
    """
    Builds and queues sponsor-mapping review records for low-confidence or unresolved matches.
    """

    def __init__(
        self,
        sec_mapper: SecCompanyMapper | None = None,
        review_confidence_threshold: float = 0.85,
    ) -> None:
        self.sec_mapper = sec_mapper or SecCompanyMapper()
        self.review_confidence_threshold = review_confidence_threshold

    def normalize_sponsor_name(self, sponsor_name: str | None) -> str:
        return self.sec_mapper._normalize_company_name(sponsor_name)

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

    def _derive_reviewed_mapping_status(
        self,
        review_status: str,
        suggested_ticker: str | None,
        reviewed_ticker: str | None,
        explicit_status: str | None = None,
    ) -> str:
        if explicit_status:
            return explicit_status.strip().lower()

        clean_review_status = (review_status or "").strip().lower()
        clean_suggested_ticker = (suggested_ticker or "").strip().upper() or None
        clean_reviewed_ticker = (reviewed_ticker or "").strip().upper() or None

        if clean_review_status == "pending":
            return "unreviewed"
        if clean_review_status == "rejected":
            return "rejected"
        if clean_review_status == "approved":
            if (
                clean_reviewed_ticker
                and clean_suggested_ticker
                and clean_reviewed_ticker != clean_suggested_ticker
            ):
                return "approved_override"
            return "approved_suggested"
        return "unreviewed"

    def _coerce_match_payload(
        self, match_result: SponsorMatchResult | dict[str, Any] | None
    ) -> dict[str, Any]:
        if match_result is None:
            return {}
        if isinstance(match_result, dict):
            return match_result
        if is_dataclass(match_result):
            return asdict(match_result)
        raise TypeError("match_result must be a SponsorMatchResult, dict, or None.")

    def requires_review(self, match_result: SponsorMatchResult | dict[str, Any] | None) -> bool:
        payload = self._coerce_match_payload(match_result)
        ticker = payload.get("ticker")
        confidence = float(payload.get("confidence") or 0.0)
        match_type = (payload.get("match_type") or "").strip().lower()

        if not ticker:
            return True
        if confidence < self.review_confidence_threshold:
            return True
        return match_type in {"no_match", "fuzzy"}

    def _build_effective_mapping_from_review(
        self, review_record: dict[str, Any] | None
    ) -> dict[str, Any] | None:
        if review_record is None:
            return None
        if (review_record.get("review_status") or "").strip().lower() != "approved":
            return None

        company_name = review_record.get("reviewed_company_name") or review_record.get("suggested_company_name")
        ticker = (
            (review_record.get("reviewed_ticker") or review_record.get("suggested_ticker") or "")
            .strip()
            .upper()
        )
        cik = review_record.get("reviewed_cik") or review_record.get("suggested_cik")
        if not ticker:
            return None

        reviewed_mapping_status = (review_record.get("reviewed_mapping_status") or "").strip().lower() or None
        return {
            "sponsor_name": review_record.get("sponsor_name"),
            "matched_company_name": company_name,
            "ticker": ticker,
            "cik": cik,
            "confidence": review_record.get("suggested_confidence"),
            "match_type": f"reviewed_{reviewed_mapping_status or 'approved'}",
            "alternatives": review_record.get("alternatives") or [],
            "mapping_source": "sponsor_mapping_review",
            "review_status": review_record.get("review_status"),
            "reviewed_mapping_status": reviewed_mapping_status,
        }

    def build_review_record(
        self,
        sponsor_name: str,
        match_result: SponsorMatchResult | dict[str, Any] | None,
        source_nct_id: str | None = None,
        review_status: str = "pending",
        reviewed_mapping_status: str | None = None,
        reviewer_name: str | None = None,
        reviewer_email: str | None = None,
        review_notes: str | None = None,
        reviewed_company_name: str | None = None,
        reviewed_ticker: str | None = None,
        reviewed_cik: str | None = None,
        reviewed_at: str | None = None,
    ) -> dict[str, Any]:
        clean_sponsor_name = " ".join((sponsor_name or "").split()).strip()
        if not clean_sponsor_name:
            raise ValueError("sponsor_name is required to build a sponsor mapping review record.")

        normalized_sponsor_name = self.normalize_sponsor_name(clean_sponsor_name)
        if not normalized_sponsor_name:
            raise ValueError("sponsor_name did not produce a usable normalized sponsor key.")

        match_payload = self._coerce_match_payload(match_result)
        clean_review_status = (review_status or "pending").strip().lower()
        clean_suggested_ticker = (match_payload.get("ticker") or "").strip().upper() or None
        clean_reviewed_ticker = (reviewed_ticker or "").strip().upper() or None
        suggested_cik = match_payload.get("cik")
        reviewed_cik_value = (reviewed_cik or "").strip() or None
        clean_reviewed_mapping_status = self._derive_reviewed_mapping_status(
            review_status=clean_review_status,
            suggested_ticker=clean_suggested_ticker,
            reviewed_ticker=clean_reviewed_ticker,
            explicit_status=reviewed_mapping_status,
        )

        if clean_review_status in {"approved", "rejected"} and reviewed_at is None:
            reviewed_at = datetime.now(UTC).isoformat()

        return {
            "sponsor_name": clean_sponsor_name,
            "normalized_sponsor_name": normalized_sponsor_name,
            "source_nct_id": source_nct_id,
            "suggested_company_name": match_payload.get("matched_company_name"),
            "suggested_ticker": clean_suggested_ticker,
            "suggested_cik": suggested_cik,
            "suggested_confidence": match_payload.get("confidence"),
            "suggested_match_type": match_payload.get("match_type"),
            "alternatives": match_payload.get("alternatives") or [],
            "review_status": clean_review_status,
            "reviewed_mapping_status": clean_reviewed_mapping_status,
            "reviewed_company_name": reviewed_company_name,
            "reviewed_ticker": clean_reviewed_ticker,
            "reviewed_cik": reviewed_cik_value,
            "reviewer_name": reviewer_name,
            "reviewer_email": reviewer_email,
            "review_notes": self._normalize_review_notes(review_notes),
            "reviewed_at": reviewed_at,
        }

    def submit_review_decision(
        self,
        sponsor_name: str,
        review_status: str,
        match_result: SponsorMatchResult | dict[str, Any] | None = None,
        source_nct_id: str | None = None,
        reviewed_company_name: str | None = None,
        reviewed_ticker: str | None = None,
        reviewed_cik: str | None = None,
        reviewed_mapping_status: str | None = None,
        reviewer_name: str | None = None,
        reviewer_email: str | None = None,
        review_notes: str | None = None,
    ) -> dict[str, Any]:
        normalized_sponsor_name = self.normalize_sponsor_name(sponsor_name)
        existing_review: dict[str, Any] | None = None
        with get_connection() as connection:
            repository = SponsorMappingReviewRepository(connection)
            repository.create_tables()
            if normalized_sponsor_name:
                existing_review = repository.get_review_by_normalized_name(normalized_sponsor_name)

            match_payload = self._coerce_match_payload(match_result)
            if not match_payload and existing_review is not None:
                match_payload = {
                    "matched_company_name": existing_review.get("suggested_company_name"),
                    "ticker": existing_review.get("suggested_ticker"),
                    "cik": existing_review.get("suggested_cik"),
                    "confidence": existing_review.get("suggested_confidence"),
                    "match_type": existing_review.get("suggested_match_type"),
                    "alternatives": existing_review.get("alternatives") or [],
                }

            clean_review_status = (review_status or "pending").strip().lower()
            resolved_reviewed_company_name = reviewed_company_name
            resolved_reviewed_ticker = reviewed_ticker
            resolved_reviewed_cik = reviewed_cik

            if clean_review_status == "approved":
                if not resolved_reviewed_company_name:
                    resolved_reviewed_company_name = (
                        existing_review.get("suggested_company_name")
                        if existing_review is not None
                        else match_payload.get("matched_company_name")
                    )
                if not resolved_reviewed_ticker:
                    resolved_reviewed_ticker = (
                        existing_review.get("suggested_ticker")
                        if existing_review is not None
                        else match_payload.get("ticker")
                    )
                if not resolved_reviewed_cik:
                    resolved_reviewed_cik = (
                        existing_review.get("suggested_cik")
                        if existing_review is not None
                        else match_payload.get("cik")
                    )
            merged_review_notes = self._merge_review_notes(
                existing_review_notes=None if existing_review is None else existing_review.get("review_notes"),
                new_review_notes=review_notes,
                review_status=clean_review_status,
                reviewer_name=reviewer_name,
                reviewer_email=reviewer_email,
            )

            review_record = self.build_review_record(
                sponsor_name=sponsor_name,
                match_result=match_payload,
                source_nct_id=source_nct_id
                or (None if existing_review is None else existing_review.get("source_nct_id")),
                review_status=clean_review_status,
                reviewed_mapping_status=reviewed_mapping_status,
                reviewer_name=reviewer_name,
                reviewer_email=reviewer_email,
                review_notes=merged_review_notes,
                reviewed_company_name=resolved_reviewed_company_name,
                reviewed_ticker=resolved_reviewed_ticker,
                reviewed_cik=resolved_reviewed_cik,
            )
            review_id = repository.upsert_review(review_record)
            saved_review = repository.get_review_by_normalized_name(review_record["normalized_sponsor_name"])

        return {
            "review_id": review_id,
            "review_record": saved_review if saved_review is not None else review_record,
        }

    def apply_review_override(
        self,
        sponsor_name: str | None,
        match_result: SponsorMatchResult | dict[str, Any] | None,
    ) -> dict[str, Any]:
        payload = self._coerce_match_payload(match_result)
        normalized_sponsor_name = self.normalize_sponsor_name(sponsor_name)
        if not normalized_sponsor_name:
            return {
                "mapping": None if not payload else payload,
                "review_record": None,
                "override_applied": False,
            }

        with get_connection() as connection:
            repository = SponsorMappingReviewRepository(connection)
            repository.create_tables()
            review_record = repository.get_review_by_normalized_name(normalized_sponsor_name)

        effective_mapping = self._build_effective_mapping_from_review(review_record)
        if effective_mapping is None:
            return {
                "mapping": None if not payload else payload,
                "review_record": review_record,
                "override_applied": False,
            }

        raw_ticker = (payload.get("ticker") or "").strip().upper() or None
        override_applied = effective_mapping.get("ticker") != raw_ticker
        return {
            "mapping": effective_mapping,
            "review_record": review_record,
            "override_applied": override_applied,
        }

    def queue_review(
        self,
        sponsor_name: str,
        match_result: SponsorMatchResult | dict[str, Any] | None,
        source_nct_id: str | None = None,
        force: bool = False,
    ) -> dict[str, Any]:
        if not force and not self.requires_review(match_result):
            return {
                "queued": False,
                "reason": "mapping_does_not_require_review",
                "review_id": None,
                "review_record": None,
            }

        review_record = self.build_review_record(
            sponsor_name=sponsor_name,
            match_result=match_result,
            source_nct_id=source_nct_id,
        )
        with get_connection() as connection:
            repository = SponsorMappingReviewRepository(connection)
            repository.create_tables()
            review_id = repository.upsert_review(review_record)

        return {
            "queued": True,
            "reason": "review_record_upserted",
            "review_id": review_id,
            "review_record": review_record,
        }
