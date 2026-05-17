from __future__ import annotations

import unittest
from unittest.mock import patch

from app.services.historical_dataset_backfill_service import HistoricalDatasetBackfillService


class _TrialAnalysisServiceStub:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def analyze_trial(
        self,
        nct_id: str,
        approval_limit: int = 5,
        market_pre_days: int = 5,
        market_post_days: int = 5,
        include_raw_trial: bool = False,
        save_to_db: bool = True,
    ) -> dict:
        self.calls.append(nct_id)
        return {
            "status": "success",
            "summary": {
                "mapped_ticker": f"TICK{nct_id[-1]}",
                "event_date_candidate": "2025-01-15",
            },
            "warnings": [],
            "persistence": {
                "analysis_id": len(self.calls),
                "historical_event_id": len(self.calls) + 100,
            },
        }


class _RepositoryStub:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def list_trial_identifiers(self, **kwargs):
        self.calls.append(kwargs)
        return [{"nct_id": "NCT00000011", "event_date_quality_score": 95, "event_date_quality_tier": "high"}]


class _ConnectionStub:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class HistoricalDatasetBackfillServiceTests(unittest.TestCase):
    def test_build_from_trials_processes_in_batches(self) -> None:
        analysis_stub = _TrialAnalysisServiceStub()
        service = HistoricalDatasetBackfillService(trial_analysis_service=analysis_stub)
        trials = [
            {"nct_id": "NCT00000001"},
            {"nct_id": "NCT00000002"},
            {"nct_id": "NCT00000003"},
        ]

        result = service.build_from_trials(
            trials=trials,
            approval_limit=5,
            market_pre_days=5,
            market_post_days=5,
            batch_size=2,
            max_batches=1,
        )

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["selected_trial_count"], 3)
        self.assertEqual(result["processed_trial_count"], 2)
        self.assertEqual(result["successful_analyses"], 2)
        self.assertEqual(result["processed_batches"], 1)
        self.assertEqual(analysis_stub.calls, ["NCT00000001", "NCT00000002"])

    def test_build_from_database_passes_event_date_quality_filters(self) -> None:
        analysis_stub = _TrialAnalysisServiceStub()
        repository_stub = _RepositoryStub()
        service = HistoricalDatasetBackfillService(trial_analysis_service=analysis_stub)

        with (
            patch(
                "app.services.historical_dataset_backfill_service.get_connection",
                return_value=_ConnectionStub(),
            ),
            patch(
                "app.services.historical_dataset_backfill_service.ClinicalTrialsRepository",
                return_value=repository_stub,
            ),
        ):
            result = service.build_from_database(
                limit=10,
                min_event_date_quality_score=80,
                event_date_quality_tier="high",
            )

        self.assertEqual(result["selected_trial_count"], 1)
        self.assertEqual(result["filters"]["min_event_date_quality_score"], 80)
        self.assertEqual(result["filters"]["event_date_quality_tier"], "high")
        self.assertEqual(repository_stub.calls[0]["min_event_date_quality_score"], 80)
        self.assertEqual(repository_stub.calls[0]["event_date_quality_tier"], "high")


if __name__ == "__main__":
    unittest.main()
