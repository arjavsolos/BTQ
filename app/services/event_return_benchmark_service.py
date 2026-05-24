from __future__ import annotations

from statistics import median
from typing import Any

from app.database.connection import get_connection
from app.database.repositories import HistoricalTrialEventRepository


class EventReturnBenchmarkService:
    """
    Builds grouped return benchmarks from stored historical trial-event rows.
    """

    VALID_GROUP_BY_FIELDS = {
        "phase_label",
        "mapped_ticker",
        "event_date_quality_tier",
        "sponsor_mapping_review_status",
        "event_date_review_status",
    }

    def _normalize_group_by(self, group_by: str | None) -> str:
        clean_group_by = " ".join(str(group_by or "phase_label").split()).strip().lower()
        if clean_group_by not in self.VALID_GROUP_BY_FIELDS:
            valid_values = ", ".join(sorted(self.VALID_GROUP_BY_FIELDS))
            raise ValueError(f"group_by must be one of: {valid_values}. Got: {group_by!r}")
        return clean_group_by

    def _coerce_group_value(self, event: dict[str, Any], group_by: str) -> str:
        clean_value = " ".join(str(event.get(group_by) or "").split()).strip()
        return clean_value or "UNKNOWN"

    def _safe_average(self, values: list[float]) -> float | None:
        if not values:
            return None
        return round(sum(values) / len(values), 6)

    def _safe_median(self, values: list[float]) -> float | None:
        if not values:
            return None
        return round(float(median(values)), 6)

    def _build_group_summary(self, group_value: str, events: list[dict[str, Any]]) -> dict[str, Any]:
        event_day_returns = [
            float(event["event_day_return"])
            for event in events
            if isinstance(event.get("event_day_return"), int | float)
        ]
        post_window_returns = [
            float(event["post_window_return"])
            for event in events
            if isinstance(event.get("post_window_return"), int | float)
        ]
        model_ready_count = sum(1 for event in events if event.get("is_model_ready"))
        positive_event_day_count = sum(1 for value in event_day_returns if value > 0)
        override_applied_count = sum(1 for event in events if event.get("event_date_override_applied"))

        return {
            "group": group_value,
            "event_count": len(events),
            "model_ready_count": model_ready_count,
            "model_ready_ratio": None if not events else round(model_ready_count / len(events), 6),
            "event_day_return_count": len(event_day_returns),
            "average_event_day_return": self._safe_average(event_day_returns),
            "median_event_day_return": self._safe_median(event_day_returns),
            "positive_event_day_ratio": (
                None if not event_day_returns else round(positive_event_day_count / len(event_day_returns), 6)
            ),
            "average_post_window_return": self._safe_average(post_window_returns),
            "median_post_window_return": self._safe_median(post_window_returns),
            "event_date_override_applied_count": override_applied_count,
        }

    def build_benchmark_from_repository(
        self,
        repository: Any,
        group_by: str = "phase_label",
        limit: int = 1000,
        offset: int = 0,
        is_model_ready: bool | None = None,
        mapped_ticker: str | None = None,
        phase_label: str | None = None,
        event_date_quality_tier: str | None = None,
        min_event_date_quality_score: int | None = None,
    ) -> dict[str, Any]:
        resolved_group_by = self._normalize_group_by(group_by)
        events = repository.list_events(
            limit=limit,
            offset=offset,
            is_model_ready=is_model_ready,
            mapped_ticker=mapped_ticker,
            phase_label=phase_label,
            event_date_quality_tier=event_date_quality_tier,
            min_event_date_quality_score=min_event_date_quality_score,
        )

        grouped_events: dict[str, list[dict[str, Any]]] = {}
        for event in events:
            grouped_events.setdefault(self._coerce_group_value(event, resolved_group_by), []).append(event)

        groups = [
            self._build_group_summary(group_value, group_events)
            for group_value, group_events in sorted(
                grouped_events.items(),
                key=lambda item: (-len(item[1]), item[0]),
            )
        ]

        event_day_returns = [
            float(event["event_day_return"])
            for event in events
            if isinstance(event.get("event_day_return"), int | float)
        ]
        return {
            "status": "success",
            "group_by": resolved_group_by,
            "summary": {
                "event_count": len(events),
                "group_count": len(groups),
                "event_day_return_count": len(event_day_returns),
                "average_event_day_return": self._safe_average(event_day_returns),
            },
            "groups": groups,
        }

    def benchmark_dataset(
        self,
        group_by: str = "phase_label",
        limit: int = 1000,
        offset: int = 0,
        is_model_ready: bool | None = None,
        mapped_ticker: str | None = None,
        phase_label: str | None = None,
        event_date_quality_tier: str | None = None,
        min_event_date_quality_score: int | None = None,
    ) -> dict[str, Any]:
        with get_connection() as connection:
            repository = HistoricalTrialEventRepository(connection)
            repository.create_tables()
            return self.build_benchmark_from_repository(
                repository=repository,
                group_by=group_by,
                limit=limit,
                offset=offset,
                is_model_ready=is_model_ready,
                mapped_ticker=mapped_ticker,
                phase_label=phase_label,
                event_date_quality_tier=event_date_quality_tier,
                min_event_date_quality_score=min_event_date_quality_score,
            )
