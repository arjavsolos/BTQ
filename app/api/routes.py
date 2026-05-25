from __future__ import annotations

from typing import Any

from app.api.schemas import TrialAnalysisRequest
from app.services import ReadinessService, TrialAnalysisService

FINAL_COMPARISON_FIELDS = {
    "analysis_readiness",
    "bayesian_probability",
    "expected_reaction_status",
    "expected_reaction_profile",
    "market_expected_reaction_comparison",
    "final_comparison_summary",
}


def _build_trial_analysis_service(service: TrialAnalysisService | None = None) -> TrialAnalysisService:
    return service or TrialAnalysisService()


def _validate_summary_contract(summary: dict[str, Any]) -> None:
    missing_fields = sorted(field for field in FINAL_COMPARISON_FIELDS if field not in summary)
    if missing_fields:
        raise ValueError(f"Trial analysis summary is missing final comparison fields: {missing_fields}")


def health_route(
    include_database: bool = False,
    service: ReadinessService | None = None,
) -> dict[str, Any]:
    readiness = (service or ReadinessService()).check_readiness(include_database=include_database)
    return {
        "status": readiness.get("status", "unknown"),
        "service": "btq-api",
        "include_database": include_database,
        "readiness": readiness,
    }


def analyze_trial_route(
    payload: dict[str, Any] | TrialAnalysisRequest,
    service: TrialAnalysisService | None = None,
) -> dict[str, Any]:
    request = TrialAnalysisRequest.from_payload(payload)
    result = _build_trial_analysis_service(service).analyze_trial(
        nct_id=request.nct_id,
        approval_limit=request.approval_limit,
        market_pre_days=request.market_pre_days,
        market_post_days=request.market_post_days,
        include_raw_trial=request.include_raw_trial,
        save_to_db=request.save_to_db,
    )

    summary = result.get("summary") or {}
    _validate_summary_contract(summary)
    if request.summary_only:
        return {
            "status": result.get("status", "success"),
            "request": request.to_dict(),
            "summary": summary,
        }

    return {
        "status": result.get("status", "success"),
        "request": request.to_dict(),
        "analysis": result,
    }
