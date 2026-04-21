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

    def build_from_trials(
        self,
        trials: list[dict[str, Any]],
        approval_limit: int = 5,
        market_pre_days: int = 5,
        market_post_days: int = 5,
        max_batches: int | None = None,
        batch_size: int | None = None,
    ) -> dict[str, Any]:
        effective_batch_size = max(1, batch_size or len(trials) or 1)
        results: list[dict[str, Any]] = []
        success_count = 0
        failure_count = 0
        processed_batches = 0

        for batch_start in range(0, len(trials), effective_batch_size):
            if max_batches is not None and processed_batches >= max_batches:
                break

            batch = trials[batch_start : batch_start + effective_batch_size]
            processed_batches += 1
            for trial in batch:
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
            "selected_trial_count": len(trials),
            "processed_trial_count": len(results),
            "successful_analyses": success_count,
            "failed_analyses": failure_count,
            "processed_batches": processed_batches,
            "batch_size": effective_batch_size,
            "results": results,
        }

    def build_from_database(
        self,
        limit: int = 25,
        offset: int = 0,
        approval_limit: int = 5,
        market_pre_days: int = 5,
        market_post_days: int = 5,
        overall_status: str | None = None,
        sponsor_name: str | None = None,
        phase_label: str | None = None,
        study_type: str | None = None,
        therapeutic_area: str | None = None,
        has_results: bool | None = None,
        exclude_existing_historical_events: bool = True,
        batch_size: int | None = None,
        max_batches: int | None = None,
    ) -> dict[str, Any]:
        with get_connection() as connection:
            repository = ClinicalTrialsRepository(connection)
            trials = repository.list_trial_identifiers(
                limit=limit,
                offset=offset,
                overall_status=overall_status,
                sponsor_name=sponsor_name,
                phase_label=phase_label,
                study_type=study_type,
                therapeutic_area=therapeutic_area,
                has_results=has_results,
                require_event_date=True,
                exclude_existing_historical_events=exclude_existing_historical_events,
            )

        result = self.build_from_trials(
            trials=trials,
            approval_limit=approval_limit,
            market_pre_days=market_pre_days,
            market_post_days=market_post_days,
            max_batches=max_batches,
            batch_size=batch_size,
        )

        return {
            **result,
            "requested_limit": limit,
            "requested_offset": offset,
            "filters": {
                "overall_status": overall_status,
                "sponsor_name": sponsor_name,
                "phase_label": phase_label,
                "study_type": study_type,
                "therapeutic_area": therapeutic_area,
                "has_results": has_results,
                "exclude_existing_historical_events": exclude_existing_historical_events,
            },
        }
