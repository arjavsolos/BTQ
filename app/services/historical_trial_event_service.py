from __future__ import annotations

from typing import Any

DATASET_VERSION = "1.0"


class HistoricalTrialEventService:
    """
    Builds a model-ready historical event snapshot from an analysis payload.
    """

    def _normalize_unique_strings(self, values: list[Any]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for value in values:
            clean = " ".join(str(value or "").split()).strip()
            if not clean or clean in seen:
                continue
            seen.add(clean)
            normalized.append(clean)
        return normalized

    def _build_feature_payload(self, analysis: dict[str, Any]) -> dict[str, Any]:
        trial = analysis.get("trial") or {}
        sponsor_mapping = analysis.get("sponsor_mapping") or {}
        market_data = analysis.get("market_data") or {}
        approval_records = (analysis.get("fda_context") or {}).get("approval_records") or []

        return {
            "trial_features": {
                "phase_label": trial.get("phase_label"),
                "phase_score": trial.get("phase_score"),
                "study_type": trial.get("study_type"),
                "therapeutic_area": trial.get("therapeutic_area"),
                "enrollment_count": trial.get("enrollment_count"),
                "intervention_types": trial.get("intervention_types") or [],
                "conditions": trial.get("conditions") or [],
                "condition_keywords": trial.get("condition_keywords") or [],
                "primary_endpoint_measures": trial.get("primary_endpoint_measures") or [],
                "secondary_endpoint_measures": trial.get("secondary_endpoint_measures") or [],
                "has_results": trial.get("has_results"),
                "data_completeness_score": trial.get("data_completeness_score"),
                "data_completeness_ratio": trial.get("data_completeness_ratio"),
                "event_date_confidence": trial.get("event_date_confidence"),
            },
            "mapping_features": {
                "ticker": sponsor_mapping.get("ticker"),
                "cik": sponsor_mapping.get("cik"),
                "matched_company_name": sponsor_mapping.get("matched_company_name"),
                "confidence": sponsor_mapping.get("confidence"),
                "match_type": sponsor_mapping.get("match_type"),
            },
            "regulatory_features": {
                "approval_record_count": len(approval_records),
                "submission_statuses": self._normalize_unique_strings(
                    [record.get("submission_status") for record in approval_records]
                ),
                "submission_types": self._normalize_unique_strings(
                    [record.get("submission_type") for record in approval_records]
                ),
            },
            "market_features": {
                "record_count": market_data.get("record_count"),
                "trade_start": market_data.get("trade_start"),
                "trade_end": market_data.get("trade_end"),
                "event_day_return": market_data.get("event_day_return"),
                "post_window_return": market_data.get("post_window_return"),
            },
            "model_readiness": {
                "is_model_ready": self._derive_model_readiness_issues(analysis) == [],
                "issues": self._derive_model_readiness_issues(analysis),
            },
        }

    def _derive_model_readiness_issues(self, analysis: dict[str, Any]) -> list[str]:
        trial = analysis.get("trial") or {}
        sponsor_mapping = analysis.get("sponsor_mapping") or {}
        market_data = analysis.get("market_data") or {}

        issues: list[str] = []
        if not trial.get("nct_id"):
            issues.append("missing_nct_id")
        if not sponsor_mapping.get("ticker"):
            issues.append("missing_ticker")
        if not trial.get("event_date_candidate"):
            issues.append("missing_event_date")
        elif trial.get("event_date_precision") != "day":
            issues.append("non_day_precision_event_date")
        if not market_data.get("record_count"):
            issues.append("missing_market_window")
        if market_data.get("event_day_return") is None:
            issues.append("missing_event_day_return")
        return issues

    def build_event_record(
        self,
        analysis: dict[str, Any],
        analysis_id: int | None = None,
    ) -> dict[str, Any]:
        trial = analysis.get("trial") or {}
        sponsor_mapping = analysis.get("sponsor_mapping") or {}
        market_data = analysis.get("market_data") or {}
        fda_context = analysis.get("fda_context") or {}
        approval_records = fda_context.get("approval_records") or []
        warnings = analysis.get("warnings") or []

        approval_application_numbers = self._normalize_unique_strings(
            [record.get("application_number") for record in approval_records]
        )
        approval_brand_names = self._normalize_unique_strings([record.get("brand_name") for record in approval_records])
        approval_sponsor_names = self._normalize_unique_strings(
            [record.get("sponsor_name") for record in approval_records]
        )

        model_readiness_issues = self._derive_model_readiness_issues(analysis)
        is_model_ready = len(model_readiness_issues) == 0

        return {
            "analysis_id": analysis_id,
            "nct_id": trial.get("nct_id"),
            "requested_nct_id": trial.get("requested_nct_id"),
            "brief_title": trial.get("brief_title"),
            "sponsor_name": trial.get("sponsor_name"),
            "sponsor_class": trial.get("sponsor_class"),
            "overall_status": trial.get("overall_status"),
            "phase_label": trial.get("phase_label"),
            "phase_score": trial.get("phase_score"),
            "study_type": trial.get("study_type"),
            "therapeutic_area": trial.get("therapeutic_area"),
            "enrollment_count": trial.get("enrollment_count"),
            "has_results": trial.get("has_results"),
            "data_completeness_score": trial.get("data_completeness_score"),
            "data_completeness_ratio": trial.get("data_completeness_ratio"),
            "event_date_candidate": trial.get("event_date_candidate"),
            "event_date_source": trial.get("event_date_source"),
            "event_date_precision": trial.get("event_date_precision"),
            "event_date_confidence": trial.get("event_date_confidence"),
            "mapped_ticker": sponsor_mapping.get("ticker"),
            "mapped_cik": sponsor_mapping.get("cik"),
            "matched_company_name": sponsor_mapping.get("matched_company_name"),
            "mapping_confidence": sponsor_mapping.get("confidence"),
            "mapping_match_type": sponsor_mapping.get("match_type"),
            "approval_record_count": len(approval_records),
            "approval_application_numbers": approval_application_numbers,
            "approval_brand_names": approval_brand_names,
            "approval_sponsor_names": approval_sponsor_names,
            "market_record_count": market_data.get("record_count"),
            "trade_start": market_data.get("trade_start"),
            "trade_end": market_data.get("trade_end"),
            "prior_close": market_data.get("prior_close"),
            "event_close": market_data.get("event_close"),
            "latest_close": market_data.get("latest_close"),
            "event_day_return": market_data.get("event_day_return"),
            "post_window_return": market_data.get("post_window_return"),
            "warning_count": len(warnings),
            "warnings": warnings,
            "is_model_ready": is_model_ready,
            "dataset_version": DATASET_VERSION,
            "source_analysis_version": analysis.get("analysis_version"),
            "feature_payload": self._build_feature_payload(analysis),
        }
