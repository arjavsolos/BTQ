from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = [
    "EventReturnBenchmarkService",
    "DemoDatasetPublisherService",
    "EventDateReviewService",
    "EventDateQualityService",
    "HistoricalDatasetAuditService",
    "HistoricalDatasetBackfillService",
    "HistoricalTrialEventService",
    "ReadinessService",
    "SponsorMappingReviewService",
    "TrialAnalysisService",
]

_SERVICE_MODULES = {
    "EventReturnBenchmarkService": "app.services.event_return_benchmark_service",
    "DemoDatasetPublisherService": "app.services.demo_dataset_publisher_service",
    "EventDateReviewService": "app.services.event_date_review_service",
    "EventDateQualityService": "app.services.event_date_quality_service",
    "HistoricalDatasetAuditService": "app.services.historical_dataset_audit_service",
    "HistoricalDatasetBackfillService": "app.services.historical_dataset_backfill_service",
    "HistoricalTrialEventService": "app.services.historical_trial_event_service",
    "ReadinessService": "app.services.readiness_service",
    "SponsorMappingReviewService": "app.services.sponsor_mapping_review_service",
    "TrialAnalysisService": "app.services.trial_analysis_service",
}


def __getattr__(name: str) -> Any:
    module_name = _SERVICE_MODULES.get(name)
    if module_name is None:
        raise AttributeError(f"module 'app.services' has no attribute {name!r}")
    module = import_module(module_name)
    return getattr(module, name)
