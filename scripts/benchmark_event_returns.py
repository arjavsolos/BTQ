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


def _get_format_env(name: str, default: str = "json") -> str:
    value = _get_str_env(name)
    if value is None:
        return default
    normalized = value.lower()
    if normalized not in {"json", "jsonl", "markdown"}:
        raise ValueError(f"Environment variable {name} must be one of: json, jsonl, markdown. Got: {value!r}")
    return normalized


def _render_markdown(report: dict) -> str:
    lines = [
        "# Event Return Benchmark",
        "",
        f"- `group_by`: {report.get('group_by')}",
        f"- `event_count`: {(report.get('summary') or {}).get('event_count')}",
        f"- `group_count`: {(report.get('summary') or {}).get('group_count')}",
        "",
        "## Summary Sections",
    ]
    for section in report.get("summary_sections") or []:
        lines.extend(
            [
                "",
                f"### {section.get('title')}",
                "",
                str(section.get("display_summary") or ""),
            ]
        )
    lines.extend(["", "## Groups"])
    for group in report.get("groups") or []:
        lines.append(
            f"- `{group.get('group')}`: count={group.get('event_count')}, "
            f"avg_event_day_return={group.get('average_event_day_return')}, "
            f"median_event_day_return={group.get('median_event_day_return')}"
        )
    return "\n".join(lines)


def main() -> None:
    service = EventReturnBenchmarkService()
    result = service.benchmark_dataset(
        group_by=_get_str_env("EVENT_RETURN_BENCHMARK_GROUP_BY") or "phase_label",
        limit=_get_int_env("EVENT_RETURN_BENCHMARK_LIMIT", 1000),
        offset=_get_int_env("EVENT_RETURN_BENCHMARK_OFFSET", 0),
        is_model_ready=_get_optional_bool_env("EVENT_RETURN_BENCHMARK_MODEL_READY"),
        mapped_ticker=_get_str_env("EVENT_RETURN_BENCHMARK_MAPPED_TICKER"),
        sponsor_name=_get_str_env("EVENT_RETURN_BENCHMARK_SPONSOR"),
        phase_label=_get_str_env("EVENT_RETURN_BENCHMARK_PHASE"),
        event_date_quality_tier=_get_str_env("EVENT_RETURN_BENCHMARK_EVENT_DATE_QUALITY_TIER"),
        sponsor_mapping_review_status=_get_str_env("EVENT_RETURN_BENCHMARK_SPONSOR_MAPPING_REVIEW_STATUS"),
        event_date_review_status=_get_str_env("EVENT_RETURN_BENCHMARK_EVENT_DATE_REVIEW_STATUS"),
        sponsor_mapping_override_applied=_get_optional_bool_env("EVENT_RETURN_BENCHMARK_SPONSOR_MAPPING_OVERRIDE"),
        event_date_override_applied=_get_optional_bool_env("EVENT_RETURN_BENCHMARK_EVENT_DATE_OVERRIDE"),
        min_event_date_quality_score=(
            _get_int_env("EVENT_RETURN_BENCHMARK_MIN_EVENT_DATE_QUALITY_SCORE", 0)
            if os.getenv("EVENT_RETURN_BENCHMARK_MIN_EVENT_DATE_QUALITY_SCORE") not in {None, ""}
            else None
        ),
        min_group_size=_get_int_env("EVENT_RETURN_BENCHMARK_MIN_GROUP_SIZE", 5),
    )
    output_format = _get_format_env("EVENT_RETURN_BENCHMARK_FORMAT", "json")
    if output_format == "jsonl":
        for group in result.get("groups") or []:
            print(json.dumps(group, ensure_ascii=True))
        return
    if output_format == "markdown":
        print(_render_markdown(result))
        return
    print(json.dumps(result, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
