from __future__ import annotations

import unittest

from app.services.demo_dataset_publisher_service import DemoDatasetPublisherService


class _SourceRepositoryStub:
    def __init__(self, events: list[dict]) -> None:
        self.events = events
        self.calls: list[dict] = []

    def list_full_events_for_demo_publish(
        self,
        limit: int = 100,
        offset: int = 0,
        is_model_ready: bool = True,
        event_date_quality_tier: str | None = None,
        min_event_date_quality_score: int | None = None,
    ) -> list[dict]:
        self.calls.append(
            {
                "limit": limit,
                "offset": offset,
                "is_model_ready": is_model_ready,
                "event_date_quality_tier": event_date_quality_tier,
                "min_event_date_quality_score": min_event_date_quality_score,
            }
        )
        return list(self.events)


class _TargetRepositoryStub:
    def __init__(self) -> None:
        self.created = False
        self.upserted_events: list[dict] = []

    def create_tables(self) -> None:
        self.created = True

    def upsert_event(self, event: dict) -> int:
        self.upserted_events.append(dict(event))
        return len(self.upserted_events)


class DemoDatasetPublisherServiceTests(unittest.TestCase):
    def test_copy_events_dry_run_returns_selected_events_without_writing(self) -> None:
        service = DemoDatasetPublisherService()
        source = _SourceRepositoryStub(
            [
                {
                    "nct_id": "NCT00000001",
                    "mapped_ticker": "PFE",
                    "event_date_quality_score": 95,
                }
            ]
        )

        result = service._copy_events(
            source_repository=source,
            target_repository=None,
            limit=25,
            offset=5,
            dry_run=True,
            event_date_quality_tier="high",
            min_event_date_quality_score=80,
        )

        self.assertEqual(result["status"], "dry_run")
        self.assertEqual(result["selected_event_count"], 1)
        self.assertEqual(result["published_event_count"], 0)
        self.assertEqual(result["events"][0]["mapped_ticker"], "PFE")
        self.assertEqual(
            source.calls[0],
            {
                "limit": 25,
                "offset": 5,
                "is_model_ready": True,
                "event_date_quality_tier": "high",
                "min_event_date_quality_score": 80,
            },
        )

    def test_copy_events_apply_writes_to_target_repository(self) -> None:
        service = DemoDatasetPublisherService()
        source = _SourceRepositoryStub(
            [
                {"nct_id": "NCT00000001", "mapped_ticker": "PFE"},
                {"nct_id": "NCT00000002", "mapped_ticker": "MRK"},
            ]
        )
        target = _TargetRepositoryStub()

        result = service._copy_events(
            source_repository=source,
            target_repository=target,
            limit=50,
            offset=0,
            dry_run=False,
            event_date_quality_tier="high",
            min_event_date_quality_score=80,
        )

        self.assertEqual(result["status"], "published")
        self.assertTrue(target.created)
        self.assertEqual(result["published_event_count"], 2)
        self.assertEqual(result["published_event_ids"], [1, 2])
        self.assertEqual(target.upserted_events[1]["mapped_ticker"], "MRK")
        self.assertEqual(result["events"], [])


if __name__ == "__main__":
    unittest.main()
