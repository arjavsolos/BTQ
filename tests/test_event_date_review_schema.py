from __future__ import annotations

import unittest

from app.database.repositories import EventDateReviewRepository
from app.database.schemas import (
    EVENT_DATE_REVIEWS_INDEX_SQL,
    EVENT_DATE_REVIEWS_MIGRATION_SQL,
    EVENT_DATE_REVIEWS_TABLE_SQL,
)


class _FakeCursor:
    def __init__(self, executed: list[tuple[str, object | None]]) -> None:
        self.executed = executed

    def __enter__(self) -> _FakeCursor:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def execute(self, statement: str, params=None) -> None:
        self.executed.append((statement.strip(), params))


class _FakeConnection:
    def __init__(self) -> None:
        self.executed: list[tuple[str, object | None]] = []

    def cursor(self) -> _FakeCursor:
        return _FakeCursor(self.executed)


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


if __name__ == "__main__":
    unittest.main()
