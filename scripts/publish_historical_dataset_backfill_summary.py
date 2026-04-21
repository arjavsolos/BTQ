from __future__ import annotations

import json
import os
from pathlib import Path


def main() -> None:
    output_path = Path(
        os.getenv("HISTORICAL_DATASET_OUTPUT_PATH", "logs/historical_dataset_backfill_output.json")
    )
    summary_path = os.getenv("GITHUB_STEP_SUMMARY")
    if not summary_path or not output_path.exists():
        return

    payload = json.loads(output_path.read_text(encoding="utf-8"))

    if payload.get("status") == "error":
        summary_lines = [
            "",
            "### Historical Dataset Backfill Result",
            "",
            "- Status: `error`",
            f"- Error: `{payload.get('error', 'unknown')}`",
        ]
    else:
        filters = payload.get("filters") or {}
        summary_lines = [
            "",
            "### Historical Dataset Backfill Result",
            "",
            f"- Status: `{payload.get('status', 'unknown')}`",
            f"- Selected trials: `{payload.get('selected_trial_count', 'unknown')}`",
            f"- Processed trials: `{payload.get('processed_trial_count', 'unknown')}`",
            f"- Successful analyses: `{payload.get('successful_analyses', 'unknown')}`",
            f"- Failed analyses: `{payload.get('failed_analyses', 'unknown')}`",
            f"- Processed batches: `{payload.get('processed_batches', 'unknown')}`",
            f"- Batch size: `{payload.get('batch_size', 'unknown')}`",
            f"- Requested limit: `{payload.get('requested_limit', 'unknown')}`",
            f"- Requested offset: `{payload.get('requested_offset', 'unknown')}`",
            f"- Status filter: `{filters.get('overall_status')}`",
            f"- Sponsor filter: `{filters.get('sponsor_name')}`",
            f"- Phase filter: `{filters.get('phase_label')}`",
            f"- Study type filter: `{filters.get('study_type')}`",
            f"- Therapeutic area filter: `{filters.get('therapeutic_area')}`",
            f"- Has results filter: `{filters.get('has_results')}`",
            f"- Exclude existing events: `{filters.get('exclude_existing_historical_events')}`",
        ]

        failures = [item for item in payload.get("results") or [] if item.get("status") == "error"]
        if failures:
            summary_lines.extend(["", "### Failed Trials", ""])
            summary_lines.extend(
                f"- `{item.get('nct_id', 'unknown')}`: `{item.get('error', 'unknown error')}`" for item in failures[:10]
            )

    with open(summary_path, "a", encoding="utf-8") as handle:
        handle.write("\n".join(summary_lines) + "\n")


if __name__ == "__main__":
    main()
