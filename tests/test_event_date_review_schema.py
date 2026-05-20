from __future__ import annotations

import unittest

from app.database.repositories import EventDateReviewRepository
from app.database.schemas import (
    EVENT_DATE_REVIEWS_INDEX_SQL,
    EVENT_DATE_REVIEWS_MIGRATION_SQL,
    EVENT_DATE_REVIEWS_TABLE_SQL,
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


class EventDateReviewRepositoryTests(unittest.TestCase):
    def test_create_tables_executes_table_migration_and_index_statements(self) -> None:
        connection = _FakeConnection()
        repository = EventDateReviewRepository(connection)

        repository.create_tables()

        self.assertEqual(connection.executed[0][0], EVENT_DATE_REVIEWS_TABLE_SQL.strip())
        self.assertEqual(
            [statement for statement, _ in connection.executed[1:]],
            [statement.strip() for statement in EVENT_DATE_REVIEWS_MIGRATION_SQL]
            + [statement.strip() for statement in EVENT_DATE_REVIEWS_INDEX_SQL],
        )

    def test_upsert_review_serializes_quality_issues_and_returns_review_id(self) -> None:
        connection = _FakeConnection()
        connection.fetchone_results.append((17,))
        repository = EventDateReviewRepository(connection)

        review_id = repository.upsert_review(
            {
                "nct_id": "NCT00000001",
                "requested_nct_id": "NCT00000001",
                "sponsor_name": "Pfizer Inc.",
                "mapped_ticker": "PFE",
                "event_date_candidate": "2025-01-15",
                "event_date_source": "last_update_posted",
                "event_date_source_rank": 1,
                "event_date_precision": "day",
                "event_date_confidence": "low",
                "event_date_quality_score": 42,
                "event_date_quality_tier": "low",
                "event_date_quality_issues": ["low_rank_event_date_source"],
                "review_reason": "weak_source_proxy",
                "review_status": "pending",
            }
        )

        self.assertEqual(review_id, 17)
        statement, params = connection.executed[0]
        self.assertIn("insert into event_date_reviews", statement)
        self.assertEqual(params[0], "NCT00000001")
        self.assertEqual(params[11], '["low_rank_event_date_source"]')

    def test_get_review_by_nct_id_returns_deserialized_payload(self) -> None:
        connection = _FakeConnection()
        connection.fetchone_results.append(
            (
                3,
                "NCT00000001",
                "NCT00000001",
                "Pfizer Inc.",
                "PFE",
                "2025-01-15",
                "last_update_posted",
                1,
                "day",
                "low",
                42,
                "low",
                ["low_rank_event_date_source"],
                "weak_source_proxy",
                "pending",
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
        repository = EventDateReviewRepository(connection)

        review = repository.get_review_by_nct_id("NCT00000001")

        self.assertIsNotNone(review)
        assert review is not None
        self.assertEqual(review["review_id"], 3)
        self.assertEqual(review["event_date_quality_tier"], "low")
        self.assertEqual(review["event_date_quality_issues"][0], "low_rank_event_date_source")

    def test_list_reviews_applies_filters_and_returns_rows(self) -> None:
        connection = _FakeConnection()
        connection.fetchall_results.append(
            [
                (
                    5,
                    "NCT00000001",
                    "NCT00000001",
                    "Pfizer Inc.",
                    "PFE",
                    "2025-01-15",
                    "primary_completion_date",
                    4,
                    "day",
                    "high",
                    95,
                    "high",
                    [],
                    "manual_review_sample",
                    "approved",
                    "2025-01-14",
                    "press_release",
                    "Arjav",
                    "arjaviyer@gmail.com",
                    "Reviewed manually.",
                    None,
                    None,
                    None,
                )
            ]
        )
        repository = EventDateReviewRepository(connection)

        reviews = repository.list_reviews(
            limit=25,
            offset=5,
            review_status="Approved",
            mapped_ticker="pfe",
            event_date_quality_tier="High",
        )

        self.assertEqual(len(reviews), 1)
        self.assertEqual(reviews[0]["review_status"], "approved")
        self.assertEqual(reviews[0]["mapped_ticker"], "PFE")
        statement, params = connection.executed[0]
        self.assertIn("where review_status = %s and mapped_ticker = %s and event_date_quality_tier = %s", statement)
        self.assertEqual(params, ("approved", "PFE", "high", 25, 5))

    def test_upsert_review_requires_nct_id(self) -> None:
        connection = _FakeConnection()
        repository = EventDateReviewRepository(connection)

        with self.assertRaises(ValueError):
            repository.upsert_review({"mapped_ticker": "PFE"})


if __name__ == "__main__":
    unittest.main()
