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
from app.database.repositories import HistoricalTrialEventRepository


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


def _get_optional_bool_env(name: str) -> bool | None:
    value = os.getenv(name)
    if value is None or not value.strip():
        return None
    return _get_bool_env(name)


def _get_format_env(name: str, default: str = "json") -> str:
    value = _get_str_env(name)
    if value is None:
        return default
    normalized = value.lower()
    if normalized not in {"json", "jsonl"}:
        raise ValueError(f"Environment variable {name} must be one of: json, jsonl. Got: {value!r}")
    return normalized


def _build_summary(events: list[dict[str, Any]]) -> dict[str, Any]:
    quality_tier_counts: dict[str, int] = {}
    model_ready_count = 0
    total_quality_score = 0
    quality_score_count = 0

    for event in events:
        tier = str(event.get("event_date_quality_tier") or "unknown")
        quality_tier_counts[tier] = quality_tier_counts.get(tier, 0) + 1
        if event.get("is_model_ready"):
            model_ready_count += 1
        quality_score = event.get("event_date_quality_score")
        if isinstance(quality_score, int | float):
            total_quality_score += int(quality_score)
            quality_score_count += 1

    average_quality_score = None
    if quality_score_count:
        average_quality_score = round(total_quality_score / quality_score_count, 2)

    return {
        "exported_event_count": len(events),
        "model_ready_count": model_ready_count,
        "event_date_quality_tier_counts": quality_tier_counts,
        "average_event_date_quality_score": average_quality_score,
    }


def main() -> None:
    try:
        limit = _get_int_env("HISTORICAL_EVENT_EXPORT_LIMIT", 100)
        offset = _get_int_env("HISTORICAL_EVENT_EXPORT_OFFSET", 0)
        is_model_ready = _get_optional_bool_env("HISTORICAL_EVENT_EXPORT_MODEL_READY")
        mapped_ticker = _get_str_env("HISTORICAL_EVENT_EXPORT_MAPPED_TICKER")
        phase_label = _get_str_env("HISTORICAL_EVENT_EXPORT_PHASE")
        event_date_quality_tier = _get_str_env("HISTORICAL_EVENT_EXPORT_EVENT_DATE_QUALITY_TIER")
        min_event_date_quality_score = _get_int_env(
            "HISTORICAL_EVENT_EXPORT_MIN_EVENT_DATE_QUALITY_SCORE",
            0,
        )
        output_format = _get_format_env("HISTORICAL_EVENT_EXPORT_FORMAT", "json")
        include_summary = _get_bool_env("HISTORICAL_EVENT_EXPORT_INCLUDE_SUMMARY", True)

        min_quality_score_filter: int | None = min_event_date_quality_score
        if os.getenv("HISTORICAL_EVENT_EXPORT_MIN_EVENT_DATE_QUALITY_SCORE") in {None, ""}:
            min_quality_score_filter = None

        with get_connection() as connection:
            repository = HistoricalTrialEventRepository(connection)
            repository.create_tables()
            events = repository.list_events(
                limit=limit,
                offset=offset,
                is_model_ready=is_model_ready,
                mapped_ticker=mapped_ticker,
                phase_label=phase_label,
                event_date_quality_tier=event_date_quality_tier,
                min_event_date_quality_score=min_quality_score_filter,
            )

        if output_format == "jsonl":
            for event in events:
                print(json.dumps(event, ensure_ascii=True))
            return

        payload: dict[str, Any] = {
            "status": "success",
            "generated_at": datetime.now(UTC).isoformat(),
            "input": {
                "limit": limit,
                "offset": offset,
                "is_model_ready": is_model_ready,
                "mapped_ticker": mapped_ticker,
                "phase_label": phase_label,
                "event_date_quality_tier": event_date_quality_tier,
                "min_event_date_quality_score": min_quality_score_filter,
                "format": output_format,
                "include_summary": include_summary,
            },
            "events": events,
        }
        if include_summary:
            payload["summary"] = _build_summary(events)
        print(json.dumps(payload, indent=2, ensure_ascii=True))
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "error",
                    "error": str(exc),
                    "input": {
                        "limit": os.getenv("HISTORICAL_EVENT_EXPORT_LIMIT"),
                        "offset": os.getenv("HISTORICAL_EVENT_EXPORT_OFFSET"),
                        "is_model_ready": os.getenv("HISTORICAL_EVENT_EXPORT_MODEL_READY"),
                        "mapped_ticker": os.getenv("HISTORICAL_EVENT_EXPORT_MAPPED_TICKER"),
                        "phase_label": os.getenv("HISTORICAL_EVENT_EXPORT_PHASE"),
                        "event_date_quality_tier": os.getenv(
                            "HISTORICAL_EVENT_EXPORT_EVENT_DATE_QUALITY_TIER"
                        ),
                        "min_event_date_quality_score": os.getenv(
                            "HISTORICAL_EVENT_EXPORT_MIN_EVENT_DATE_QUALITY_SCORE"
                        ),
                        "format": os.getenv("HISTORICAL_EVENT_EXPORT_FORMAT"),
                        "include_summary": os.getenv("HISTORICAL_EVENT_EXPORT_INCLUDE_SUMMARY"),
                    },
                },
                indent=2,
                ensure_ascii=True,
            )
        )
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
