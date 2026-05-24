from __future__ import annotations

import io
import json
import os
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from scripts import benchmark_event_returns


class _BenchmarkServiceStub:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def benchmark_dataset(
        self,
        group_by: str = "phase_label",
        limit: int = 1000,
        offset: int = 0,
        is_model_ready: bool | None = None,
        mapped_ticker: str | None = None,
        phase_label: str | None = None,
        event_date_quality_tier: str | None = None,
        min_event_date_quality_score: int | None = None,
    ) -> dict:
        self.calls.append(
            {
                "group_by": group_by,
                "limit": limit,
                "offset": offset,
                "is_model_ready": is_model_ready,
                "mapped_ticker": mapped_ticker,
                "phase_label": phase_label,
                "event_date_quality_tier": event_date_quality_tier,
                "min_event_date_quality_score": min_event_date_quality_score,
            }
        )
        return {
            "status": "success",
            "group_by": group_by,
            "summary": {"event_count": 3, "group_count": 2},
            "summary_sections": [
                {"title": "coverage", "metrics": {"event_count": 3}, "display_summary": "coverage"},
            ],
            "groups": [{"group": "PHASE3", "event_count": 2}],
        }


class BenchmarkEventReturnsScriptTests(unittest.TestCase):
    def test_main_uses_env_configuration(self) -> None:
        service = _BenchmarkServiceStub()
        stdout = io.StringIO()

        with (
            patch.dict(
                os.environ,
                {
                    "EVENT_RETURN_BENCHMARK_GROUP_BY": "event_date_quality_tier",
                    "EVENT_RETURN_BENCHMARK_LIMIT": "250",
                    "EVENT_RETURN_BENCHMARK_OFFSET": "10",
                    "EVENT_RETURN_BENCHMARK_MODEL_READY": "true",
                    "EVENT_RETURN_BENCHMARK_MAPPED_TICKER": "PFE",
                    "EVENT_RETURN_BENCHMARK_PHASE": "PHASE 3",
                    "EVENT_RETURN_BENCHMARK_EVENT_DATE_QUALITY_TIER": "high",
                    "EVENT_RETURN_BENCHMARK_MIN_EVENT_DATE_QUALITY_SCORE": "80",
                },
                clear=False,
            ),
            patch("scripts.benchmark_event_returns.EventReturnBenchmarkService", return_value=service),
            redirect_stdout(stdout),
        ):
            benchmark_event_returns.main()

        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["status"], "success")
        self.assertEqual(payload["group_by"], "event_date_quality_tier")
        self.assertEqual(payload["summary"]["event_count"], 3)
        self.assertEqual(payload["summary_sections"][0]["title"], "coverage")
        self.assertEqual(
            service.calls[0],
            {
                "group_by": "event_date_quality_tier",
                "limit": 250,
                "offset": 10,
                "is_model_ready": True,
                "mapped_ticker": "PFE",
                "phase_label": "PHASE 3",
                "event_date_quality_tier": "high",
                "min_event_date_quality_score": 80,
            },
        )


if __name__ == "__main__":
    unittest.main()
