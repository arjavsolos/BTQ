from __future__ import annotations

import os
from typing import Any

from app.database import get_connection_for_url
from app.database.repositories import HistoricalTrialEventRepository


class DemoDatasetPublisherService:
    """
    Publishes a curated historical-event subset from a source DB to a demo DB.
    """

    def _resolve_source_url(self, source_database_url: str | None) -> str:
        resolved = source_database_url or os.getenv("DEMO_PUBLISH_SOURCE_DATABASE_URL") or os.getenv(
            "LOCAL_DATABASE_URL"
        )
        if not resolved:
            raise ValueError("Set DEMO_PUBLISH_SOURCE_DATABASE_URL or LOCAL_DATABASE_URL.")
        return resolved

    def _resolve_target_url(self, target_database_url: str | None, dry_run: bool) -> str | None:
        resolved = target_database_url or os.getenv("DEMO_PUBLISH_TARGET_DATABASE_URL") or os.getenv(
            "NEON_DATABASE_URL"
        )
        if not resolved and not dry_run:
            raise ValueError("Set DEMO_PUBLISH_TARGET_DATABASE_URL or NEON_DATABASE_URL before using apply mode.")
        return resolved

    def _copy_events(
        self,
        source_repository: HistoricalTrialEventRepository,
        target_repository: HistoricalTrialEventRepository | None,
        limit: int,
        offset: int,
        dry_run: bool,
        event_date_quality_tier: str | None,
        min_event_date_quality_score: int | None,
    ) -> dict[str, Any]:
        events = source_repository.list_full_events_for_demo_publish(
            limit=limit,
            offset=offset,
            is_model_ready=True,
            event_date_quality_tier=event_date_quality_tier,
            min_event_date_quality_score=min_event_date_quality_score,
        )

        published_ids = []
        if not dry_run and target_repository is not None:
            target_repository.create_tables()
            for event in events:
                published_ids.append(target_repository.upsert_event(event))

        return {
            "status": "dry_run" if dry_run else "published",
            "selected_event_count": len(events),
            "published_event_count": 0 if dry_run else len(published_ids),
            "published_event_ids": published_ids,
            "filters": {
                "is_model_ready": True,
                "event_date_quality_tier": event_date_quality_tier,
                "min_event_date_quality_score": min_event_date_quality_score,
                "limit": limit,
                "offset": offset,
            },
            "events": events if dry_run else [],
        }

    def publish_demo_dataset(
        self,
        source_database_url: str | None = None,
        target_database_url: str | None = None,
        limit: int = 50,
        offset: int = 0,
        dry_run: bool = True,
        event_date_quality_tier: str | None = "high",
        min_event_date_quality_score: int | None = 80,
    ) -> dict[str, Any]:
        resolved_source_url = self._resolve_source_url(source_database_url)
        resolved_target_url = self._resolve_target_url(target_database_url, dry_run=dry_run)

        with get_connection_for_url(resolved_source_url, application_name="btq-demo-publisher-source") as source:
            source_repository = HistoricalTrialEventRepository(source)

            if dry_run:
                return self._copy_events(
                    source_repository=source_repository,
                    target_repository=None,
                    limit=limit,
                    offset=offset,
                    dry_run=True,
                    event_date_quality_tier=event_date_quality_tier,
                    min_event_date_quality_score=min_event_date_quality_score,
                )

            with get_connection_for_url(
                str(resolved_target_url),
                application_name="btq-demo-publisher-target",
            ) as target:
                target_repository = HistoricalTrialEventRepository(target)
                return self._copy_events(
                    source_repository=source_repository,
                    target_repository=target_repository,
                    limit=limit,
                    offset=offset,
                    dry_run=False,
                    event_date_quality_tier=event_date_quality_tier,
                    min_event_date_quality_score=min_event_date_quality_score,
                )
