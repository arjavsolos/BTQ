from __future__ import annotations

import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services import EventReturnBenchmarkService


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


def _get_optional_bool_env(name: str) -> bool | None:
    value = os.getenv(name)
    if value is None or not value.strip():
        return None
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"Environment variable {name} must be a boolean-like value, got: {value!r}")


def main() -> None:
    service = EventReturnBenchmarkService()
    result = service.benchmark_dataset(
        group_by=_get_str_env("EVENT_RETURN_BENCHMARK_GROUP_BY") or "phase_label",
        limit=_get_int_env("EVENT_RETURN_BENCHMARK_LIMIT", 1000),
        offset=_get_int_env("EVENT_RETURN_BENCHMARK_OFFSET", 0),
        is_model_ready=_get_optional_bool_env("EVENT_RETURN_BENCHMARK_MODEL_READY"),
        mapped_ticker=_get_str_env("EVENT_RETURN_BENCHMARK_MAPPED_TICKER"),
        phase_label=_get_str_env("EVENT_RETURN_BENCHMARK_PHASE"),
        event_date_quality_tier=_get_str_env("EVENT_RETURN_BENCHMARK_EVENT_DATE_QUALITY_TIER"),
        min_event_date_quality_score=(
            _get_int_env("EVENT_RETURN_BENCHMARK_MIN_EVENT_DATE_QUALITY_SCORE", 0)
            if os.getenv("EVENT_RETURN_BENCHMARK_MIN_EVENT_DATE_QUALITY_SCORE") not in {None, ""}
            else None
        ),
    )
    print(json.dumps(result, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
