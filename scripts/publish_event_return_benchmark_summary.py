from __future__ import annotations

import json
import os
from pathlib import Path


def main() -> None:
    output_path = Path(os.getenv("EVENT_RETURN_BENCHMARK_OUTPUT_PATH", "logs/event_return_benchmark_output.json"))
    summary_path = os.getenv("GITHUB_STEP_SUMMARY")
    if not summary_path or not output_path.exists():
        return

    payload = json.loads(output_path.read_text(encoding="utf-8"))

    if payload.get("status") == "error":
        summary_lines = [
            "",
            "### Event Return Benchmark",
            "",
            "- Status: `error`",
            f"- Error: `{payload.get('error', 'unknown')}`",
        ]
    else:
        summary = payload.get("summary") or {}
        sections = payload.get("summary_sections") or []
        groups = payload.get("groups") or []
        summary_lines = [
            "",
            "### Event Return Benchmark",
            "",
            "- Status: `success`",
            f"- Grouped by: `{payload.get('group_by', 'unknown')}`",
            f"- Event count: `{summary.get('event_count', 'unknown')}`",
            f"- Group count: `{summary.get('group_count', 'unknown')}`",
            f"- Event-day return count: `{summary.get('event_day_return_count', 'unknown')}`",
            f"- Average event-day return: `{summary.get('average_event_day_return', 'unknown')}`",
        ]

        if sections:
            summary_lines.extend(["", "### Benchmark Highlights", ""])
            summary_lines.extend(
                (
                    f"- `{section.get('title', 'unknown')}`: "
                    f"{section.get('display_summary', '')}"
                )
                for section in sections[:4]
            )

        if groups:
            summary_lines.extend(["", "### Top Benchmark Groups", ""])
            summary_lines.extend(
                (
                    f"- `{group.get('group', 'unknown')}` | count=`{group.get('event_count', 'unknown')}` "
                    f"| avg_event_day_return=`{group.get('average_event_day_return', 'unknown')}` "
                    f"| median_event_day_return=`{group.get('median_event_day_return', 'unknown')}`"
                )
                for group in groups[:5]
            )

    with open(summary_path, "a", encoding="utf-8") as handle:
        handle.write("\n".join(summary_lines) + "\n")


if __name__ == "__main__":
    main()
