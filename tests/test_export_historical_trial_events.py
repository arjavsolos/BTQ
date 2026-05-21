from __future__ import annotations

import io
import json
import os
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from scripts import export_historical_trial_events


class _RepositoryStub:
    def __init__(self, events: list[dict]) -> None:
        self.events = events
        self.created = False
        self.list_events_calls: list[dict] = []

    def create_tables(self) -> None:
        self.created = True

    def list_events(
        self,
        limit: int = 100,
        offset: int = 0,
        is_model_ready: bool | None = None,
        mapped_ticker: str | None = None,
        phase_label: str | None = None,
        event_date_quality_tier: str | None = None,
        min_event_date_quality_score: int | None = None,
    ) -> list[dict]:
        self.list_events_calls.append(
            {
                "limit": limit,
                "offset": offset,
                "is_model_ready": is_model_ready,
                "mapped_ticker": mapped_ticker,
                "phase_label": phase_label,
                "event_date_quality_tier": event_date_quality_tier,
                "min_event_date_quality_score": min_event_date_quality_score,
            }
        )
        return list(self.events)


class _ConnectionStub:
    def __enter__(self) -> _ConnectionStub:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


class ExportHistoricalTrialEventsScriptTests(unittest.TestCase):
    def test_main_outputs_json_payload_with_summary(self) -> None:
        repository = _RepositoryStub(
            [
                {
                    "event_id": 1,
                    "mapped_ticker": "PFE",
                    "event_date_quality_score": 92,
                    "event_date_quality_tier": "high",
                    "event_date_review_status": "approved",
                    "event_date_override_applied": True,
                    "is_model_ready": True,
                },
                {
                    "event_id": 2,
                    "mapped_ticker": "MRK",
                    "event_date_quality_score": 66,
                    "event_date_quality_tier": "moderate",
                    "event_date_review_status": "unknown",
                    "event_date_override_applied": False,
                    "is_model_ready": False,
                },
            ]
        )
        stdout = io.StringIO()

        with (
            patch.dict(
                os.environ,
                {
                    "HISTORICAL_EVENT_EXPORT_LIMIT": "25",
                    "HISTORICAL_EVENT_EXPORT_OFFSET": "5",
                    "HISTORICAL_EVENT_EXPORT_MODEL_READY": "true",
                    "HISTORICAL_EVENT_EXPORT_MAPPED_TICKER": "PFE",
                    "HISTORICAL_EVENT_EXPORT_PHASE": "PHASE 3",
                    "HISTORICAL_EVENT_EXPORT_EVENT_DATE_QUALITY_TIER": "high",
                    "HISTORICAL_EVENT_EXPORT_MIN_EVENT_DATE_QUALITY_SCORE": "80",
                    "HISTORICAL_EVENT_EXPORT_FORMAT": "json",
                    "HISTORICAL_EVENT_EXPORT_INCLUDE_SUMMARY": "true",
                },
                clear=False,
            ),
            patch(
                "scripts.export_historical_trial_events.get_connection",
                return_value=_ConnectionStub(),
            ),
            patch(
                "scripts.export_historical_trial_events.HistoricalTrialEventRepository",
                return_value=repository,
            ),
            redirect_stdout(stdout),
        ):
            export_historical_trial_events.main()

        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["status"], "success")
        self.assertEqual(payload["summary"]["exported_event_count"], 2)
        self.assertEqual(payload["summary"]["model_ready_count"], 1)
        self.assertEqual(payload["summary"]["event_date_quality_tier_counts"]["high"], 1)
        self.assertEqual(payload["summary"]["event_date_review_status_counts"]["approved"], 1)
        self.assertEqual(payload["summary"]["event_date_override_applied_count"], 1)
        self.assertEqual(payload["summary"]["average_event_date_quality_score"], 79.0)
        self.assertTrue(repository.created)
        self.assertEqual(
            repository.list_events_calls[0],
            {
                "limit": 25,
                "offset": 5,
                "is_model_ready": True,
                "mapped_ticker": "PFE",
                "phase_label": "PHASE 3",
                "event_date_quality_tier": "high",
                "min_event_date_quality_score": 80,
            },
        )

    def test_main_outputs_jsonl_lines_without_summary_wrapper(self) -> None:
        repository = _RepositoryStub(
            [
                {"event_id": 1, "event_date_quality_tier": "high"},
                {"event_id": 2, "event_date_quality_tier": "moderate"},
            ]
        )
        stdout = io.StringIO()

        with (
            patch.dict(
                os.environ,
                {
                    "HISTORICAL_EVENT_EXPORT_FORMAT": "jsonl",
                },
                clear=False,
            ),
            patch(
                "scripts.export_historical_trial_events.get_connection",
                return_value=_ConnectionStub(),
            ),
            patch(
                "scripts.export_historical_trial_events.HistoricalTrialEventRepository",
                return_value=repository,
            ),
            redirect_stdout(stdout),
        ):
            export_historical_trial_events.main()

        lines = [line for line in stdout.getvalue().splitlines() if line.strip()]
        self.assertEqual(len(lines), 2)
        self.assertEqual(json.loads(lines[0])["event_id"], 1)
        self.assertEqual(json.loads(lines[1])["event_id"], 2)

    def test_main_emits_structured_error_payload_for_invalid_format(self) -> None:
        stdout = io.StringIO()

        with (
            patch.dict(
                os.environ,
                {
                    "HISTORICAL_EVENT_EXPORT_FORMAT": "csv",
                },
                clear=False,
            ),
            redirect_stdout(stdout),
        ):
            with self.assertRaises(SystemExit) as context:
                export_historical_trial_events.main()

        self.assertEqual(context.exception.code, 1)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["status"], "error")
        self.assertIn("json, jsonl", payload["error"])


if __name__ == "__main__":
    unittest.main()
