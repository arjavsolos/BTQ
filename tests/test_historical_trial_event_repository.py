from __future__ import annotations

import unittest

from app.database.repositories import HistoricalTrialEventRepository


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


class HistoricalTrialEventRepositoryTests(unittest.TestCase):
    def test_list_events_applies_export_filters_and_normalizes_values(self) -> None:
        connection = _FakeConnection()
        connection.fetchall_results.append(
            [
                (
                    11,
                    7,
                    "NCT00000001",
                    "NCT00000001",
                    "Pfizer Inc.",
                    "PHASE 3",
                    "PFE",
                    "2025-01-15",
                    "primary_completion_date",
                    4,
                    "high",
                    91,
                    "high",
                    "approved",
                    True,
                    "approved",
                    "low_event_date_quality_score",
                    True,
                    0.12,
                    0.18,
                    True,
                    1,
                    "2026-05-17T00:00:00+00:00",
                )
            ]
        )
        repository = HistoricalTrialEventRepository(connection)

        events = repository.list_events(
            limit=25,
            offset=5,
            is_model_ready=True,
            mapped_ticker="pfe",
            sponsor_name="pfizer",
            phase_label="PHASE 3",
            event_date_quality_tier="High",
            sponsor_mapping_review_status="Approved",
            event_date_review_status="Approved",
            sponsor_mapping_override_applied=True,
            event_date_override_applied=True,
            min_event_date_quality_score=-5,
        )

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event_id"], 11)
        self.assertEqual(events[0]["mapped_ticker"], "PFE")
        self.assertEqual(events[0]["event_date_quality_score"], 91)
        self.assertEqual(events[0]["sponsor_mapping_review_status"], "approved")
        self.assertTrue(events[0]["sponsor_mapping_override_applied"])
        self.assertEqual(events[0]["event_date_review_status"], "approved")
        self.assertTrue(events[0]["event_date_override_applied"])
        self.assertTrue(events[0]["is_model_ready"])

        statement, params = connection.executed[0]
        self.assertIn("where is_model_ready = %s", statement)
        self.assertIn("mapped_ticker = %s", statement)
        self.assertIn("sponsor_name ilike %s", statement)
        self.assertIn("phase_label = %s", statement)
        self.assertIn("event_date_quality_tier = %s", statement)
        self.assertIn("sponsor_mapping_review_status = %s", statement)
        self.assertIn("event_date_review_status = %s", statement)
        self.assertIn("sponsor_mapping_override_applied = %s", statement)
        self.assertIn("event_date_override_applied = %s", statement)
        self.assertIn("event_date_quality_score >= %s", statement)
        self.assertEqual(
            params,
            (
                True,
                "PFE",
                "%pfizer%",
                "PHASE 3",
                "high",
                "approved",
                "approved",
                True,
                True,
                0,
                25,
                5,
            ),
        )

    def test_list_events_without_filters_uses_paging_only(self) -> None:
        connection = _FakeConnection()
        connection.fetchall_results.append([])
        repository = HistoricalTrialEventRepository(connection)

        events = repository.list_events(limit=10, offset=3)

        self.assertEqual(events, [])
        statement, params = connection.executed[0]
        self.assertNotIn("where", statement.lower())
        self.assertEqual(params, (10, 3))


if __name__ == "__main__":
    unittest.main()
