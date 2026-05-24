from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import (
    publish_event_return_benchmark_summary,
    publish_historical_dataset_audit_summary,
    publish_historical_dataset_backfill_summary,
)


class PublishHistoricalDatasetSummariesTests(unittest.TestCase):
    def test_backfill_summary_includes_event_date_quality_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "backfill.json"
            summary_path = Path(tmpdir) / "summary.md"
            output_path.write_text(
                json.dumps(
                    {
                        "status": "success",
                        "selected_trial_count": 3,
                        "processed_trial_count": 2,
                        "successful_analyses": 2,
                        "failed_analyses": 0,
                        "processed_batches": 1,
                        "batch_size": 2,
                        "requested_limit": 25,
                        "requested_offset": 5,
                        "filters": {
                            "overall_status": "COMPLETED",
                            "sponsor_name": None,
                            "phase_label": "PHASE 3",
                            "study_type": "INTERVENTIONAL",
                            "therapeutic_area": "Oncology",
                            "has_results": True,
                            "min_event_date_quality_score": 80,
                            "event_date_quality_tier": "high",
                            "exclude_existing_historical_events": True,
                        },
                        "results": [
                            {
                                "nct_id": "NCT00000001",
                                "status": "success",
                                "event_date_quality_score": 95,
                                "event_date_quality_tier": "high",
                                "event_date_quality": {"is_market_usable": True},
                            },
                            {
                                "nct_id": "NCT00000002",
                                "status": "success",
                                "event_date_quality_score": 65,
                                "event_date_quality_tier": "moderate",
                                "event_date_quality": {"is_market_usable": False},
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )

            with patch.dict(
                os.environ,
                {
                    "HISTORICAL_DATASET_OUTPUT_PATH": str(output_path),
                    "GITHUB_STEP_SUMMARY": str(summary_path),
                },
                clear=False,
            ):
                publish_historical_dataset_backfill_summary.main()

            summary_text = summary_path.read_text(encoding="utf-8")
            self.assertIn("Min event-date quality score filter: `80`", summary_text)
            self.assertIn("Event-date quality tier filter: `high`", summary_text)
            self.assertIn("Successful event rows: `2`", summary_text)
            self.assertIn("Market-usable event dates: `1`", summary_text)
            self.assertIn("Average event-date quality score: `80.0`", summary_text)
            self.assertIn("Dominant event-date quality tier: `high`", summary_text)
            self.assertIn("### Event-Date Quality Tiers", summary_text)
            self.assertIn("- `high`: `1`", summary_text)
            self.assertIn("- `moderate`: `1`", summary_text)

    def test_audit_summary_includes_event_date_quality_section(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "audit.json"
            summary_path = Path(tmpdir) / "summary.md"
            output_path.write_text(
                json.dumps(
                    {
                        "status": "success",
                        "summary": {
                            "total_events": 10,
                            "model_ready_events": 6,
                            "model_ready_ratio": 0.6,
                            "missing_ticker_ratio": 0.2,
                            "missing_event_date_ratio": 0.1,
                            "missing_market_data_ratio": 0.3,
                            "low_confidence_mapping_ratio": 0.2,
                            "low_completeness_ratio": 0.3,
                            "low_event_date_quality_ratio": 0.4,
                            "average_event_date_quality_score": 67.4,
                        },
                        "event_date_quality": {
                            "average_quality_score": 67.4,
                            "low_quality_ratio": 0.4,
                            "day_precision_ratio": 0.8,
                            "top_source_rank": 4,
                            "top_confidence_bucket": "high",
                            "top_quality_tier": "high",
                        },
                        "warning_frequency": [],
                        "recent_issues": [],
                    }
                ),
                encoding="utf-8",
            )

            with patch.dict(
                os.environ,
                {
                    "HISTORICAL_AUDIT_OUTPUT_PATH": str(output_path),
                    "GITHUB_STEP_SUMMARY": str(summary_path),
                },
                clear=False,
            ):
                publish_historical_dataset_audit_summary.main()

            summary_text = summary_path.read_text(encoding="utf-8")
            self.assertIn("Low event-date quality ratio: `0.4`", summary_text)
            self.assertIn("Average event-date quality score: `67.4`", summary_text)
            self.assertIn("### Event-Date Quality", summary_text)
            self.assertIn("Average quality score: `67.4`", summary_text)
            self.assertIn("Top source rank: `4`", summary_text)
            self.assertIn("Top confidence bucket: `high`", summary_text)

    def test_benchmark_summary_includes_highlights_and_top_groups(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "benchmark.json"
            summary_path = Path(tmpdir) / "summary.md"
            output_path.write_text(
                json.dumps(
                    {
                        "status": "success",
                        "group_by": "phase_label",
                        "summary": {
                            "event_count": 12,
                            "group_count": 3,
                            "event_day_return_count": 10,
                            "average_event_day_return": 0.0412,
                        },
                        "summary_sections": [
                            {
                                "title": "coverage",
                                "display_summary": "Benchmarked 12 historical events across 3 groups.",
                            },
                            {
                                "title": "top_groups",
                                "display_summary": "Top positive cohort: PHASE3 at 0.08.",
                            },
                        ],
                        "groups": [
                            {
                                "group": "PHASE3",
                                "event_count": 5,
                                "average_event_day_return": 0.08,
                                "median_event_day_return": 0.05,
                            },
                            {
                                "group": "PHASE2",
                                "event_count": 4,
                                "average_event_day_return": -0.01,
                                "median_event_day_return": -0.02,
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )

            with patch.dict(
                os.environ,
                {
                    "EVENT_RETURN_BENCHMARK_OUTPUT_PATH": str(output_path),
                    "GITHUB_STEP_SUMMARY": str(summary_path),
                },
                clear=False,
            ):
                publish_event_return_benchmark_summary.main()

            summary_text = summary_path.read_text(encoding="utf-8")
            self.assertIn("### Event Return Benchmark", summary_text)
            self.assertIn("Grouped by: `phase_label`", summary_text)
            self.assertIn("### Benchmark Highlights", summary_text)
            self.assertIn("`coverage`", summary_text)
            self.assertIn("### Top Benchmark Groups", summary_text)
            self.assertIn("`PHASE3` | count=`5`", summary_text)


if __name__ == "__main__":
    unittest.main()
