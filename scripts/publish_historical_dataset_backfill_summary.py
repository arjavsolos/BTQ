from __future__ import annotations

import json
import os
from pathlib import Path


def _build_export_metrics(results: list[dict]) -> dict[str, object]:
    successful_rows = [item for item in results if item.get("status") == "success"]
    market_usable_count = 0
    quality_tier_counts: dict[str, int] = {}
    total_quality_score = 0
    quality_score_count = 0

    for item in successful_rows:
        event_date_quality = item.get("event_date_quality") or {}
        if event_date_quality.get("is_market_usable"):
            market_usable_count += 1

        quality_tier = str(item.get("event_date_quality_tier") or "unknown")
        quality_tier_counts[quality_tier] = quality_tier_counts.get(quality_tier, 0) + 1

        quality_score = item.get("event_date_quality_score")
        if isinstance(quality_score, int | float):
            total_quality_score += float(quality_score)
            quality_score_count += 1

    average_quality_score = None
    if quality_score_count:
        average_quality_score = round(total_quality_score / quality_score_count, 2)

    dominant_quality_tier = None
    if quality_tier_counts:
        dominant_quality_tier = sorted(
            quality_tier_counts.items(),
            key=lambda item: (-item[1], item[0]),
        )[0][0]

    return {
        "successful_rows": len(successful_rows),
        "market_usable_count": market_usable_count,
        "average_quality_score": average_quality_score,
        "quality_tier_counts": quality_tier_counts,
        "dominant_quality_tier": dominant_quality_tier,
    }


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
        export_metrics = _build_export_metrics(payload.get("results") or [])
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
            f"- Min event-date quality score filter: `{filters.get('min_event_date_quality_score')}`",
            f"- Event-date quality tier filter: `{filters.get('event_date_quality_tier')}`",
            f"- Exclude existing events: `{filters.get('exclude_existing_historical_events')}`",
            f"- Successful event rows: `{export_metrics.get('successful_rows')}`",
            f"- Market-usable event dates: `{export_metrics.get('market_usable_count')}`",
            f"- Average event-date quality score: `{export_metrics.get('average_quality_score')}`",
            f"- Dominant event-date quality tier: `{export_metrics.get('dominant_quality_tier')}`",
        ]

        quality_tier_counts = export_metrics.get("quality_tier_counts") or {}
        if quality_tier_counts:
            summary_lines.extend(["", "### Event-Date Quality Tiers", ""])
            summary_lines.extend(
                f"- `{quality_tier}`: `{count}`"
                for quality_tier, count in sorted(
                    quality_tier_counts.items(),
                    key=lambda item: (-item[1], item[0]),
                )
            )

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
