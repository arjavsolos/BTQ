from __future__ import annotations

import json
import os
from pathlib import Path


def main() -> None:
    output_path = Path(os.getenv("HISTORICAL_AUDIT_OUTPUT_PATH", "logs/historical_dataset_audit_output.json"))
    summary_path = os.getenv("GITHUB_STEP_SUMMARY")
    if not summary_path or not output_path.exists():
        return

    payload = json.loads(output_path.read_text(encoding="utf-8"))

    if payload.get("status") == "error":
        summary_lines = [
            "",
            "### Historical Dataset Audit",
            "",
            "- Status: `error`",
            f"- Error: `{payload.get('error', 'unknown')}`",
        ]
    else:
        summary = payload.get("summary") or {}
        warning_frequency = payload.get("warning_frequency") or []
        recent_issues = payload.get("recent_issues") or []
        summary_lines = [
            "",
            "### Historical Dataset Audit",
            "",
            "- Status: `success`",
            f"- Total events: `{summary.get('total_events', 'unknown')}`",
            f"- Model-ready events: `{summary.get('model_ready_events', 'unknown')}`",
            f"- Model-ready ratio: `{summary.get('model_ready_ratio', 'unknown')}`",
            f"- Missing ticker ratio: `{summary.get('missing_ticker_ratio', 'unknown')}`",
            f"- Missing event-date ratio: `{summary.get('missing_event_date_ratio', 'unknown')}`",
            f"- Missing market-data ratio: `{summary.get('missing_market_data_ratio', 'unknown')}`",
            f"- Low-confidence mapping ratio: `{summary.get('low_confidence_mapping_ratio', 'unknown')}`",
            f"- Low-completeness ratio: `{summary.get('low_completeness_ratio', 'unknown')}`",
        ]

        if warning_frequency:
            summary_lines.extend(["", "### Top Warnings", ""])
            summary_lines.extend(
                f"- `{item.get('warning', 'unknown')}`: `{item.get('warning_count', 'unknown')}`"
                for item in warning_frequency[:5]
            )

        if recent_issues:
            summary_lines.extend(["", "### Recent Issues", ""])
            summary_lines.extend(
                (
                    f"- `{item.get('nct_id', 'unknown')}` | ticker=`{item.get('mapped_ticker')}` "
                    f"| warnings=`{item.get('warning_count')}` | model_ready=`{item.get('is_model_ready')}`"
                )
                for item in recent_issues[:5]
            )

    with open(summary_path, "a", encoding="utf-8") as handle:
        handle.write("\n".join(summary_lines) + "\n")


if __name__ == "__main__":
    main()
