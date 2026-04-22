from __future__ import annotations

import unittest

from app.database.repositories import SponsorMappingReviewRepository
from app.database.schemas import (
    SPONSOR_MAPPING_REVIEWS_INDEX_SQL,
    SPONSOR_MAPPING_REVIEWS_TABLE_SQL,
)


class _FakeCursor:
    def __init__(self, executed: list[str]) -> None:
        self.executed = executed

    def __enter__(self) -> _FakeCursor:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def execute(self, statement: str, params=None) -> None:
        self.executed.append(statement.strip())


class _FakeConnection:
    def __init__(self) -> None:
        self.executed: list[str] = []

    def cursor(self) -> _FakeCursor:
        return _FakeCursor(self.executed)


class SponsorMappingReviewRepositoryTests(unittest.TestCase):
    def test_create_tables_executes_table_and_index_statements(self) -> None:
        connection = _FakeConnection()
        repository = SponsorMappingReviewRepository(connection)

        repository.create_tables()

        self.assertEqual(connection.executed[0], SPONSOR_MAPPING_REVIEWS_TABLE_SQL.strip())
        self.assertEqual(
            connection.executed[1:],
            [statement.strip() for statement in SPONSOR_MAPPING_REVIEWS_INDEX_SQL],
        )


if __name__ == "__main__":
    unittest.main()
