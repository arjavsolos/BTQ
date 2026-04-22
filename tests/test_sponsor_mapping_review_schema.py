from __future__ import annotations

import unittest

from app.database.repositories import SponsorMappingReviewRepository
from app.database.schemas import (
    SPONSOR_MAPPING_REVIEWS_INDEX_SQL,
    SPONSOR_MAPPING_REVIEWS_TABLE_SQL,
)


class _FakeCursor:
    def __init__(
        self,
        executed: list[tuple[str, object | None]],
        fetchone_results: list[tuple],
        fetchall_results: list[list[tuple]],
    ) -> None:
        self.executed = executed
        self.fetchone_results = fetchone_results
        self.fetchall_results = fetchall_results

    def __enter__(self) -> _FakeCursor:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def execute(self, statement: str, params=None) -> None:
        self.executed.append((statement.strip(), params))

    def fetchone(self):
        return self.fetchone_results.pop(0) if self.fetchone_results else None

    def fetchall(self):
        return self.fetchall_results.pop(0) if self.fetchall_results else []


class _FakeConnection:
    def __init__(self) -> None:
        self.executed: list[tuple[str, object | None]] = []
        self.fetchone_results: list[tuple] = []
        self.fetchall_results: list[list[tuple]] = []

    def cursor(self) -> _FakeCursor:
        return _FakeCursor(self.executed, self.fetchone_results, self.fetchall_results)


class SponsorMappingReviewRepositoryTests(unittest.TestCase):
    def test_create_tables_executes_table_and_index_statements(self) -> None:
        connection = _FakeConnection()
        repository = SponsorMappingReviewRepository(connection)

        repository.create_tables()

        self.assertEqual(connection.executed[0][0], SPONSOR_MAPPING_REVIEWS_TABLE_SQL.strip())
        self.assertEqual(
            [statement for statement, _ in connection.executed[1:]],
            [statement.strip() for statement in SPONSOR_MAPPING_REVIEWS_INDEX_SQL],
        )

    def test_upsert_review_serializes_alternatives_and_returns_review_id(self) -> None:
        connection = _FakeConnection()
        connection.fetchone_results.append((42,))
        repository = SponsorMappingReviewRepository(connection)

        review_id = repository.upsert_review(
            {
                "sponsor_name": "Pfizer Inc.",
                "normalized_sponsor_name": "pfizer",
                "source_nct_id": "NCT00000001",
                "suggested_company_name": "Pfizer Inc.",
                "suggested_ticker": "PFE",
                "suggested_cik": "0000078003",
                "suggested_confidence": 1.0,
                "suggested_match_type": "exact_normalized",
                "alternatives": [{"ticker": "PFE", "confidence": 1.0}],
                "review_status": "pending",
            }
        )

        self.assertEqual(review_id, 42)
        statement, params = connection.executed[0]
        self.assertIn("insert into sponsor_mapping_reviews", statement)
        self.assertEqual(params[0], "Pfizer Inc.")
        self.assertEqual(params[1], "pfizer")
        self.assertEqual(params[8], '[{"ticker": "PFE", "confidence": 1.0}]')

    def test_get_review_by_normalized_name_returns_deserialized_payload(self) -> None:
        connection = _FakeConnection()
        connection.fetchone_results.append(
            (
                7,
                "Pfizer Inc.",
                "pfizer",
                "NCT00000001",
                "Pfizer Inc.",
                "PFE",
                "0000078003",
                0.99,
                "exact_normalized",
                [{"ticker": "PFE", "confidence": 0.99}],
                "pending",
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
            )
        )
        repository = SponsorMappingReviewRepository(connection)

        review = repository.get_review_by_normalized_name("pfizer")

        self.assertIsNotNone(review)
        assert review is not None
        self.assertEqual(review["review_id"], 7)
        self.assertEqual(review["suggested_ticker"], "PFE")
        self.assertEqual(review["alternatives"][0]["ticker"], "PFE")

    def test_list_reviews_applies_filters_and_returns_rows(self) -> None:
        connection = _FakeConnection()
        connection.fetchall_results.append(
            [
                (
                    9,
                    "Pfizer Inc.",
                    "pfizer",
                    "NCT00000001",
                    "Pfizer Inc.",
                    "PFE",
                    "0000078003",
                    0.99,
                    "exact_normalized",
                    [],
                    "approved",
                    "Pfizer Inc.",
                    "PFE",
                    "0000078003",
                    "Arjav",
                    "arjaviyer@gmail.com",
                    "Reviewed and approved.",
                    None,
                    None,
                    None,
                )
            ]
        )
        repository = SponsorMappingReviewRepository(connection)

        reviews = repository.list_reviews(limit=25, offset=5, review_status="approved", suggested_ticker="pfe")

        self.assertEqual(len(reviews), 1)
        self.assertEqual(reviews[0]["review_status"], "approved")
        statement, params = connection.executed[0]
        self.assertIn("where review_status = %s and suggested_ticker = %s", statement)
        self.assertEqual(params, ("approved", "PFE", 25, 5))

    def test_upsert_review_requires_sponsor_identity_fields(self) -> None:
        connection = _FakeConnection()
        repository = SponsorMappingReviewRepository(connection)

        with self.assertRaises(ValueError):
            repository.upsert_review({"normalized_sponsor_name": "pfizer"})

        with self.assertRaises(ValueError):
            repository.upsert_review({"sponsor_name": "Pfizer Inc."})


if __name__ == "__main__":
    unittest.main()
