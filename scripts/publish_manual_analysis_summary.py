from __future__ import annotations

import json
import os
from pathlib import Path


def main() -> None:
    output_path = Path(os.getenv("MANUAL_ANALYSIS_OUTPUT_PATH", "logs/manual_analysis_output.json"))
    summary_path = os.getenv("GITHUB_STEP_SUMMARY")
    if not summary_path or not output_path.exists():
        return

    payload = json.loads(output_path.read_text(encoding="utf-8"))

    if payload.get("status") == "error":
        summary_lines = [
            "",
            "### Analysis Result",
            "",
            "- Status: `error`",
            f"- Error: `{payload.get('error', 'unknown')}`",
        ]
    else:
        summary = payload.get("summary", payload)
        summary_lines = [
            "",
            "### Analysis Result",
            "",
            f"- Status: `{payload.get('status', 'success')}`",
            f"- NCT ID: `{summary.get('nct_id', 'unknown')}`",
            f"- Requested NCT ID: `{summary.get('requested_nct_id', 'unknown')}`",
            f"- Sponsor: `{summary.get('sponsor_name', 'unknown')}`",
            f"- Ticker: `{summary.get('mapped_ticker', 'unknown')}`",
            f"- Event date: `{summary.get('event_date_candidate', 'unknown')}`",
            f"- Approval records: `{summary.get('approval_record_count', 'unknown')}`",
            f"- Market records: `{summary.get('market_record_count', 'unknown')}`",
            f"- Event-day return: `{summary.get('event_day_return', 'unknown')}`",
            f"- Post-window return: `{summary.get('post_window_return', 'unknown')}`",
        ]

        warnings = payload.get("warnings") or []
        if warnings:
            summary_lines.extend(["", "### Warnings", ""])
            summary_lines.extend(f"- {warning}" for warning in warnings)

        persistence = payload.get("persistence")
        if persistence is not None:
            summary_lines.extend(
                [
                    "",
                    "### Persistence",
                    "",
                    f"- Saved: `{persistence.get('saved')}`",
                    f"- Analysis ID: `{persistence.get('analysis_id')}`",
                    f"- Historical event ID: `{persistence.get('historical_event_id')}`",
                ]
            )

    with open(summary_path, "a", encoding="utf-8") as handle:
        handle.write("\n".join(summary_lines) + "\n")


if __name__ == "__main__":
    main()
