from __future__ import annotations

import unittest

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


if __name__ == "__main__":
    unittest.main()
