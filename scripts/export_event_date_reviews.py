from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.database import get_connection
from app.database.repositories import EventDateReviewRepository


def _get_str_env(name: str) -> str | None:
    value = os.getenv(name)
    if value is None:
        return None
    clean = value.strip()
    return clean or None


def _get_int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return int(value.strip())


def _get_bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"Environment variable {name} must be a boolean-like value, got: {value!r}")


def _get_format_env(name: str, default: str = "json") -> str:
    value = _get_str_env(name)
    if value is None:
        return default
    normalized = value.lower()
    if normalized not in {"json", "jsonl"}:
        raise ValueError(f"Environment variable {name} must be one of: json, jsonl. Got: {value!r}")
    return normalized


def _build_summary(reviews: list[dict[str, Any]]) -> dict[str, Any]:
    status_counts: dict[str, int] = {}
    quality_tier_counts: dict[str, int] = {}

    for review in reviews:
        review_status = str(review.get("review_status") or "unknown")
        status_counts[review_status] = status_counts.get(review_status, 0) + 1

        quality_tier = str(review.get("event_date_quality_tier") or "unknown")
        quality_tier_counts[quality_tier] = quality_tier_counts.get(quality_tier, 0) + 1

    return {
        "exported_review_count": len(reviews),
        "status_counts": status_counts,
        "event_date_quality_tier_counts": quality_tier_counts,
    }


def main() -> None:
    try:
        limit = _get_int_env("EVENT_DATE_REVIEW_EXPORT_LIMIT", 100)
        offset = _get_int_env("EVENT_DATE_REVIEW_EXPORT_OFFSET", 0)
        review_status = _get_str_env("EVENT_DATE_REVIEW_EXPORT_STATUS")
        mapped_ticker = _get_str_env("EVENT_DATE_REVIEW_EXPORT_TICKER")
        event_date_quality_tier = _get_str_env("EVENT_DATE_REVIEW_EXPORT_EVENT_DATE_QUALITY_TIER")
        output_format = _get_format_env("EVENT_DATE_REVIEW_EXPORT_FORMAT", "json")
        include_summary = _get_bool_env("EVENT_DATE_REVIEW_EXPORT_INCLUDE_SUMMARY", True)

        with get_connection() as connection:
            repository = EventDateReviewRepository(connection)
            repository.create_tables()
            reviews = repository.list_reviews(
                limit=limit,
                offset=offset,
                review_status=review_status,
                mapped_ticker=mapped_ticker,
                event_date_quality_tier=event_date_quality_tier,
            )

        if output_format == "jsonl":
            for review in reviews:
                print(json.dumps(review, ensure_ascii=True))
            return

        payload: dict[str, Any] = {
            "status": "success",
            "generated_at": datetime.now(UTC).isoformat(),
            "input": {
                "limit": limit,
                "offset": offset,
                "review_status": review_status,
                "mapped_ticker": mapped_ticker,
                "event_date_quality_tier": event_date_quality_tier,
                "format": output_format,
                "include_summary": include_summary,
            },
            "reviews": reviews,
        }
        if include_summary:
            payload["summary"] = _build_summary(reviews)
        print(json.dumps(payload, indent=2, ensure_ascii=True))
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "error",
                    "error": str(exc),
                    "input": {
                        "limit": os.getenv("EVENT_DATE_REVIEW_EXPORT_LIMIT"),
                        "offset": os.getenv("EVENT_DATE_REVIEW_EXPORT_OFFSET"),
                        "review_status": os.getenv("EVENT_DATE_REVIEW_EXPORT_STATUS"),
                        "mapped_ticker": os.getenv("EVENT_DATE_REVIEW_EXPORT_TICKER"),
                        "event_date_quality_tier": os.getenv(
                            "EVENT_DATE_REVIEW_EXPORT_EVENT_DATE_QUALITY_TIER"
                        ),
                        "format": os.getenv("EVENT_DATE_REVIEW_EXPORT_FORMAT"),
                        "include_summary": os.getenv("EVENT_DATE_REVIEW_EXPORT_INCLUDE_SUMMARY"),
                    },
                },
                indent=2,
                ensure_ascii=True,
            )
        )
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
