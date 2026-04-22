from __future__ import annotations

import unittest
from dataclasses import dataclass
from unittest.mock import patch

from app.services.sponsor_mapping_review_service import SponsorMappingReviewService


@dataclass(slots=True)
class _MatchResult:
    sponsor_name: str
    matched_company_name: str | None
    ticker: str | None
    cik: str | None
    confidence: float
    match_type: str
    alternatives: list[dict]


class _MapperStub:
    def _normalize_company_name(self, value: str | None) -> str:
        if not value:
            return ""
        return " ".join(str(value).lower().replace("inc.", "").replace("inc", "").split()).strip()


class _RepositoryStub:
    def __init__(self) -> None:
        self.created = False
        self.records: list[dict] = []

    def create_tables(self) -> None:
        self.created = True

    def upsert_review(self, review_record: dict[str, object]) -> int:
        self.records.append(review_record)
        return 101


class _ConnectionStub:
    def __init__(self, repository: _RepositoryStub) -> None:
        self.repository = repository

    def __enter__(self) -> _ConnectionStub:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


class SponsorMappingReviewServiceTests(unittest.TestCase):
    def test_requires_review_for_missing_ticker(self) -> None:
        service = SponsorMappingReviewService(sec_mapper=_MapperStub())

        requires_review = service.requires_review(
            _MatchResult(
                sponsor_name="Unknown Sponsor",
                matched_company_name=None,
                ticker=None,
                cik=None,
                confidence=0.0,
                match_type="no_match",
                alternatives=[],
            )
        )

        self.assertTrue(requires_review)

    def test_requires_review_for_low_confidence_match(self) -> None:
        service = SponsorMappingReviewService(sec_mapper=_MapperStub(), review_confidence_threshold=0.85)

        requires_review = service.requires_review(
            {
                "ticker": "PFE",
                "confidence": 0.74,
                "match_type": "fuzzy",
            }
        )

        self.assertTrue(requires_review)

    def test_build_review_record_normalizes_fields(self) -> None:
        service = SponsorMappingReviewService(sec_mapper=_MapperStub())

        record = service.build_review_record(
            sponsor_name="Pfizer Inc.",
            match_result={
                "matched_company_name": "Pfizer Inc.",
                "ticker": "pfe",
                "cik": "0000078003",
                "confidence": 0.81,
                "match_type": "fuzzy",
                "alternatives": [{"ticker": "PFE"}],
            },
            source_nct_id="NCT00000001",
        )

        self.assertEqual(record["sponsor_name"], "Pfizer Inc.")
        self.assertEqual(record["normalized_sponsor_name"], "pfizer")
        self.assertEqual(record["suggested_ticker"], "PFE")
        self.assertEqual(record["source_nct_id"], "NCT00000001")
        self.assertEqual(record["alternatives"], [{"ticker": "PFE"}])

    def test_build_review_record_sets_reviewed_at_for_terminal_status(self) -> None:
        service = SponsorMappingReviewService(sec_mapper=_MapperStub())

        record = service.build_review_record(
            sponsor_name="Pfizer Inc.",
            match_result=None,
            review_status="approved",
            reviewed_ticker="pfe",
        )

        self.assertEqual(record["review_status"], "approved")
        self.assertEqual(record["reviewed_ticker"], "PFE")
        self.assertIsNotNone(record["reviewed_at"])

    def test_queue_review_persists_when_review_is_needed(self) -> None:
        service = SponsorMappingReviewService(sec_mapper=_MapperStub())
        repository = _RepositoryStub()

        with (
            patch("app.services.sponsor_mapping_review_service.get_connection", return_value=_ConnectionStub(repository)),
            patch(
                "app.services.sponsor_mapping_review_service.SponsorMappingReviewRepository",
                return_value=repository,
            ),
        ):
            result = service.queue_review(
                sponsor_name="Unknown Sponsor",
                match_result={
                    "ticker": None,
                    "confidence": 0.0,
                    "match_type": "no_match",
                    "alternatives": [{"ticker": "PFE"}],
                },
                source_nct_id="NCT00000002",
            )

        self.assertTrue(result["queued"])
        self.assertEqual(result["review_id"], 101)
        self.assertTrue(repository.created)
        self.assertEqual(repository.records[0]["normalized_sponsor_name"], "unknown sponsor")

    def test_queue_review_skips_confident_non_review_match(self) -> None:
        service = SponsorMappingReviewService(sec_mapper=_MapperStub())

        result = service.queue_review(
            sponsor_name="Pfizer Inc.",
            match_result={
                "ticker": "PFE",
                "confidence": 1.0,
                "match_type": "exact_normalized",
                "alternatives": [],
            },
        )

        self.assertFalse(result["queued"])
        self.assertEqual(result["reason"], "mapping_does_not_require_review")


if __name__ == "__main__":
    unittest.main()
