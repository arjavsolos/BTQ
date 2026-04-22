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

    def _coerce_match_payload(self, match_result: SponsorMatchResult | dict[str, Any] | None) -> dict[str, Any]:
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

    def build_review_record(
        self,
        sponsor_name: str,
        match_result: SponsorMatchResult | dict[str, Any] | None,
        source_nct_id: str | None = None,
        review_status: str = "pending",
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
            "reviewed_company_name": reviewed_company_name,
            "reviewed_ticker": clean_reviewed_ticker,
            "reviewed_cik": reviewed_cik_value,
            "reviewer_name": reviewer_name,
            "reviewer_email": reviewer_email,
            "review_notes": review_notes,
            "reviewed_at": reviewed_at,
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
