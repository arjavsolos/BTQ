from __future__ import annotations

import re

EVENT_DATE_SOURCE_RANKS = {
    "last_update_posted": 1,
    "results_first_posted": 2,
    "completion_date": 3,
    "primary_completion_date": 4,
}

PRECISION_POINTS = {
    "day": 45,
    "month": 25,
    "year": 10,
    "unknown": 0,
}

SOURCE_RANK_POINTS = {
    4: 35,
    3: 28,
    2: 18,
    1: 10,
    0: 0,
}

CONFIDENCE_POINTS = {
    "high": 15,
    "moderate": 8,
    "low": 3,
    "unknown": 0,
}


class EventDateQualityService:
    """
    Centralizes event-date quality logic for catalyst-date proxies.
    """

    def infer_precision(self, value: str | None) -> str | None:
        if not value:
            return None
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            return "day"
        if re.fullmatch(r"\d{4}-\d{2}", value):
            return "month"
        if re.fullmatch(r"\d{4}", value):
            return "year"
        return "unknown"

    def rank_source(self, event_date_source: str | None) -> int | None:
        if not event_date_source:
            return None
        return EVENT_DATE_SOURCE_RANKS.get(event_date_source)

    def score_confidence(
        self,
        event_date_value: str | None,
        event_date_source: str | None,
        precision: str | None = None,
    ) -> str:
        resolved_precision = precision or self.infer_precision(event_date_value)
        if not event_date_value or not event_date_source or resolved_precision is None:
            return "unknown"

        if resolved_precision == "day":
            if event_date_source in {"primary_completion_date", "completion_date"}:
                return "high"
            if event_date_source == "results_first_posted":
                return "moderate"
            if event_date_source == "last_update_posted":
                return "low"
        if resolved_precision == "month":
            if event_date_source in {"primary_completion_date", "completion_date"}:
                return "moderate"
            return "low"
        if resolved_precision == "year":
            return "low"
        return "unknown"

    def score_quality(
        self,
        event_date_value: str | None,
        event_date_source: str | None,
        precision: str | None = None,
        source_rank: int | None = None,
        confidence: str | None = None,
    ) -> int:
        resolved_precision = precision or self.infer_precision(event_date_value) or "unknown"
        resolved_source_rank = source_rank if source_rank is not None else (self.rank_source(event_date_source) or 0)
        resolved_confidence = confidence or self.score_confidence(
            event_date_value=event_date_value,
            event_date_source=event_date_source,
            precision=resolved_precision,
        )
        score = (
            PRECISION_POINTS.get(resolved_precision, 0)
            + SOURCE_RANK_POINTS.get(resolved_source_rank, 0)
            + CONFIDENCE_POINTS.get(resolved_confidence, 0)
        )
        return max(0, min(100, score))

    def derive_quality_tier(self, quality_score: int) -> str:
        if quality_score >= 80:
            return "high"
        if quality_score >= 55:
            return "moderate"
        if quality_score > 0:
            return "low"
        return "unknown"

    def build_quality_issues(
        self,
        event_date_value: str | None,
        event_date_source: str | None,
        precision: str | None,
        source_rank: int | None,
        confidence: str,
    ) -> list[str]:
        issues: list[str] = []
        if not event_date_value:
            return ["missing_event_date"]
        if not event_date_source:
            issues.append("missing_event_date_source")
        if precision in {None, "unknown"}:
            issues.append("unknown_event_date_precision")
        elif precision != "day":
            issues.append("non_day_precision_event_date")
        if source_rank is not None and source_rank <= 2:
            issues.append("low_rank_event_date_source")
        if confidence == "low":
            issues.append("low_confidence_event_date")
        if confidence == "unknown":
            issues.append("unknown_event_date_confidence")
        return issues

    def assess_event_date(
        self,
        event_date_value: str | None,
        event_date_source: str | None,
    ) -> dict[str, object]:
        precision = self.infer_precision(event_date_value)
        source_rank = self.rank_source(event_date_source)
        confidence = self.score_confidence(
            event_date_value=event_date_value,
            event_date_source=event_date_source,
            precision=precision,
        )
        quality_score = self.score_quality(
            event_date_value=event_date_value,
            event_date_source=event_date_source,
            precision=precision,
            source_rank=source_rank,
            confidence=confidence,
        )
        quality_tier = self.derive_quality_tier(quality_score)
        quality_issues = self.build_quality_issues(
            event_date_value=event_date_value,
            event_date_source=event_date_source,
            precision=precision,
            source_rank=source_rank,
            confidence=confidence,
        )
        return {
            "event_date_precision": precision,
            "event_date_source_rank": source_rank,
            "event_date_confidence": confidence,
            "event_date_quality_score": quality_score,
            "event_date_quality_tier": quality_tier,
            "event_date_quality_issues": quality_issues,
            "is_market_usable": precision == "day",
        }
