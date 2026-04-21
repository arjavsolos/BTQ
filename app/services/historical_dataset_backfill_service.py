from __future__ import annotations

from typing import Any

from app.database.connection import get_connection
from app.database.repositories import ClinicalTrialsRepository
from app.services.trial_analysis_service import TrialAnalysisService


class HistoricalDatasetBackfillService:
    """
    Builds historical event rows for previously ingested trials.
    """

    def __init__(self, trial_analysis_service: TrialAnalysisService | None = None) -> None:
        self.trial_analysis_service = trial_analysis_service or TrialAnalysisService()

    def build_from_database(
        self,
        limit: int = 25,
        approval_limit: int = 5,
        market_pre_days: int = 5,
        market_post_days: int = 5,
        overall_status: str | None = None,
        sponsor_name: str | None = None,
        has_results: bool | None = None,
    ) -> dict[str, Any]:
        with get_connection() as connection:
            repository = ClinicalTrialsRepository(connection)
            trials = repository.list_trial_identifiers(
                limit=limit,
                overall_status=overall_status,
                sponsor_name=sponsor_name,
                has_results=has_results,
                require_event_date=True,
            )

        results: list[dict[str, Any]] = []
        success_count = 0
        failure_count = 0
        for trial in trials:
            nct_id = trial["nct_id"]
            try:
                analysis = self.trial_analysis_service.analyze_trial(
                    nct_id=nct_id,
                    approval_limit=approval_limit,
                    market_pre_days=market_pre_days,
                    market_post_days=market_post_days,
                    include_raw_trial=False,
                    save_to_db=True,
                )
                persistence = analysis.get("persistence") or {}
                results.append(
                    {
                        "nct_id": nct_id,
                        "status": analysis.get("status"),
                        "analysis_id": persistence.get("analysis_id"),
                        "historical_event_id": persistence.get("historical_event_id"),
                        "mapped_ticker": (analysis.get("summary") or {}).get("mapped_ticker"),
                        "event_date_candidate": (analysis.get("summary") or {}).get("event_date_candidate"),
                        "warning_count": len(analysis.get("warnings") or []),
                    }
                )
                success_count += 1
            except Exception as exc:
                results.append({"nct_id": nct_id, "status": "error", "error": str(exc)})
                failure_count += 1

        return {
            "status": "success" if failure_count == 0 else "partial_success",
            "requested_limit": limit,
            "selected_trial_count": len(trials),
            "successful_analyses": success_count,
            "failed_analyses": failure_count,
            "filters": {
                "overall_status": overall_status,
                "sponsor_name": sponsor_name,
                "has_results": has_results,
            },
            "results": results,
        }
