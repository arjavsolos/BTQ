from __future__ import annotations

from typing import Any

from app.database.connection import get_connection
from app.database.repositories import HistoricalTrialEventRepository


class HistoricalDatasetAuditService:
    """
    Produces quality metrics for the historical trial event dataset.
    """

    def _safe_ratio(self, numerator: int, denominator: int) -> float | None:
        if denominator <= 0:
            return None
        return round(numerator / denominator, 6)

    def _round_nullable(self, value: Any, places: int = 6) -> float | None:
        if value is None:
            return None
        return round(float(value), places)

    def _attach_model_ready_ratio(self, rows: list[dict[str, Any]], count_key: str) -> list[dict[str, Any]]:
        enriched: list[dict[str, Any]] = []
        for row in rows:
            total_count = int(row.get(count_key) or 0)
            model_ready_count = int(row.get("model_ready_count") or 0)
            enriched.append(
                {
                    **row,
                    "model_ready_ratio": self._safe_ratio(model_ready_count, total_count),
                }
            )
        return enriched

    def _find_top_bucket(self, rows: list[dict[str, Any]], key: str) -> dict[str, Any] | None:
        if not rows:
            return None
        ordered = sorted(
            rows,
            key=lambda row: (-int(row.get("event_count") or 0), str(row.get(key) or "")),
        )
        return ordered[0]

    def _build_event_date_quality_display(
        self,
        total_events: int,
        summary: dict[str, Any],
        event_date_precision: list[dict[str, Any]],
        event_date_source_rank: list[dict[str, Any]],
        event_date_confidence: list[dict[str, Any]],
        event_date_quality_tier: list[dict[str, Any]],
        event_date_review_status: list[dict[str, Any]],
    ) -> dict[str, Any]:
        top_precision = self._find_top_bucket(event_date_precision, "event_date_precision")
        top_source_rank = self._find_top_bucket(event_date_source_rank, "event_date_source_rank")
        top_confidence = self._find_top_bucket(event_date_confidence, "event_date_confidence")
        top_quality_tier = self._find_top_bucket(event_date_quality_tier, "event_date_quality_tier")
        top_review_status = self._find_top_bucket(event_date_review_status, "event_date_review_status")
        day_precision_count = sum(
            int(row.get("event_count") or 0)
            for row in event_date_precision
            if row.get("event_date_precision") == "day"
        )

        return {
            "average_quality_score": self._round_nullable(summary.get("average_event_date_quality_score")),
            "low_quality_ratio": self._safe_ratio(
                int(summary.get("low_event_date_quality_events") or 0),
                total_events,
            ),
            "day_precision_ratio": self._safe_ratio(day_precision_count, total_events),
            "top_precision_bucket": None if top_precision is None else top_precision.get("event_date_precision"),
            "top_source_rank": None if top_source_rank is None else top_source_rank.get("event_date_source_rank"),
            "top_confidence_bucket": None if top_confidence is None else top_confidence.get("event_date_confidence"),
            "top_quality_tier": None if top_quality_tier is None else top_quality_tier.get("event_date_quality_tier"),
            "top_review_status": (
                None
                if top_review_status is None
                else top_review_status.get("event_date_review_status")
            ),
            "reviewed_ratio": self._safe_ratio(int(summary.get("event_date_reviewed_events") or 0), total_events),
            "override_applied_ratio": self._safe_ratio(
                int(summary.get("event_date_override_events") or 0),
                total_events,
            ),
            "display_summary": (
                f"Average event-date quality score is "
                f"{self._round_nullable(summary.get('average_event_date_quality_score'))}, "
                f"with {self._safe_ratio(day_precision_count, total_events)} of rows at day precision "
                f"and {self._safe_ratio(int(summary.get('low_event_date_quality_events') or 0), total_events)} "
                f"flagged as low-quality event-date proxies. "
                f"{self._safe_ratio(int(summary.get('event_date_override_events') or 0), total_events)} "
                f"used approved reviewed timing overrides."
            ),
        }

    def build_report_from_repository(
        self,
        repository: Any,
        top_warning_limit: int = 10,
        issue_limit: int = 25,
        therapeutic_area_limit: int = 10,
    ) -> dict[str, Any]:
        summary = repository.get_quality_summary()
        total_events = int(summary.get("total_events") or 0)
        model_ready_events = int(summary.get("model_ready_events") or 0)
        event_date_precision = repository.get_event_date_precision_breakdown()
        event_date_source_rank = repository.get_event_date_source_rank_breakdown()
        event_date_confidence = repository.get_event_date_confidence_breakdown()
        event_date_quality_tier = repository.get_event_date_quality_tier_breakdown()
        event_date_review_status = repository.get_event_date_review_status_breakdown()

        report_summary = {
            **summary,
            "model_ready_ratio": self._safe_ratio(model_ready_events, total_events),
            "missing_ticker_ratio": self._safe_ratio(int(summary.get("missing_ticker_events") or 0), total_events),
            "missing_event_date_ratio": self._safe_ratio(
                int(summary.get("missing_event_date_events") or 0),
                total_events,
            ),
            "missing_market_data_ratio": self._safe_ratio(
                int(summary.get("missing_market_data_events") or 0),
                total_events,
            ),
            "missing_event_return_ratio": self._safe_ratio(
                int(summary.get("missing_event_return_events") or 0),
                total_events,
            ),
            "missing_fda_context_ratio": self._safe_ratio(
                int(summary.get("missing_fda_context_events") or 0),
                total_events,
            ),
            "warning_event_ratio": self._safe_ratio(int(summary.get("warning_events") or 0), total_events),
            "low_confidence_mapping_ratio": self._safe_ratio(
                int(summary.get("low_confidence_mapping_events") or 0),
                total_events,
            ),
            "low_completeness_ratio": self._safe_ratio(
                int(summary.get("low_completeness_events") or 0),
                total_events,
            ),
            "low_event_date_quality_ratio": self._safe_ratio(
                int(summary.get("low_event_date_quality_events") or 0),
                total_events,
            ),
            "event_date_reviewed_ratio": self._safe_ratio(
                int(summary.get("event_date_reviewed_events") or 0),
                total_events,
            ),
            "event_date_override_ratio": self._safe_ratio(
                int(summary.get("event_date_override_events") or 0),
                total_events,
            ),
            "average_data_completeness_ratio": self._round_nullable(summary.get("average_data_completeness_ratio")),
            "average_mapping_confidence": self._round_nullable(summary.get("average_mapping_confidence")),
            "average_event_date_quality_score": self._round_nullable(summary.get("average_event_date_quality_score")),
            "average_event_day_return": self._round_nullable(summary.get("average_event_day_return")),
            "average_post_window_return": self._round_nullable(summary.get("average_post_window_return")),
        }

        return {
            "status": "success",
            "dataset": "historical_trial_events",
            "summary": report_summary,
            "event_date_quality": self._build_event_date_quality_display(
                total_events=total_events,
                summary=summary,
                event_date_precision=event_date_precision,
                event_date_source_rank=event_date_source_rank,
                event_date_confidence=event_date_confidence,
                event_date_quality_tier=event_date_quality_tier,
                event_date_review_status=event_date_review_status,
            ),
            "breakdowns": {
                "phase": self._attach_model_ready_ratio(repository.get_phase_breakdown(), "event_count"),
                "therapeutic_area": self._attach_model_ready_ratio(
                    repository.get_therapeutic_area_breakdown(limit=therapeutic_area_limit),
                    "event_count",
                ),
                "event_date_precision": event_date_precision,
                "event_date_source_rank": event_date_source_rank,
                "event_date_confidence": event_date_confidence,
                "event_date_quality_tier": event_date_quality_tier,
                "event_date_review_status": event_date_review_status,
            },
            "warning_frequency": repository.get_warning_frequency(limit=top_warning_limit),
            "recent_issues": repository.get_recent_issues(limit=issue_limit),
        }

    def audit_dataset(
        self,
        top_warning_limit: int = 10,
        issue_limit: int = 25,
        therapeutic_area_limit: int = 10,
    ) -> dict[str, Any]:
        with get_connection() as connection:
            repository = HistoricalTrialEventRepository(connection)
            return self.build_report_from_repository(
                repository=repository,
                top_warning_limit=top_warning_limit,
                issue_limit=issue_limit,
                therapeutic_area_limit=therapeutic_area_limit,
            )
