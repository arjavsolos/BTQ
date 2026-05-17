from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.database.connection import DatabaseConfigError, get_connection
from app.database.repositories import (
    ClinicalTrialsRepository,
    HistoricalTrialEventRepository,
    TrialAnalysisRepository,
)
from app.ingestion import (
    ClinicalTrialsIngestor,
    MarketDataIngestor,
    OpenFDAIngestor,
    SecCompanyMapper,
)
from app.services.event_date_quality_service import EventDateQualityService
from app.services.historical_trial_event_service import HistoricalTrialEventService
from app.services.sponsor_mapping_review_service import SponsorMappingReviewService


DAY_PRECISION_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
ANALYSIS_VERSION = "1.0"


class TrialAnalysisService:
    """
    Orchestrates one end-to-end trial analysis across the ingestion layer.
    """

    def __init__(
        self,
        clinical_trials_ingestor: ClinicalTrialsIngestor | None = None,
        sec_mapper: SecCompanyMapper | None = None,
        openfda_ingestor: OpenFDAIngestor | None = None,
        market_data_ingestor: MarketDataIngestor | None = None,
        sponsor_mapping_review_service: SponsorMappingReviewService | None = None,
        persist_trial_records: bool = True,
    ) -> None:
        self.clinical_trials_ingestor = clinical_trials_ingestor or ClinicalTrialsIngestor()
        self.sec_mapper = sec_mapper or SecCompanyMapper()
        self.openfda_ingestor = openfda_ingestor or OpenFDAIngestor()
        self.market_data_ingestor = market_data_ingestor or MarketDataIngestor()
        self.sponsor_mapping_review_service = sponsor_mapping_review_service or SponsorMappingReviewService(
            sec_mapper=self.sec_mapper
        )
        self.persist_trial_records = persist_trial_records
        self.event_date_quality_service = EventDateQualityService()
        self.historical_event_service = HistoricalTrialEventService()

    def _normalize_warnings(self, warnings: list[str]) -> list[str]:
        deduped: list[str] = []
        seen: set[str] = set()
        for warning in warnings:
            clean = " ".join((warning or "").split()).strip()
            if not clean or clean in seen:
                continue
            seen.add(clean)
            deduped.append(clean)
        return deduped

    def _build_summary(
        self,
        trial: dict[str, Any],
        sponsor_mapping: dict[str, Any] | None,
        market_summary: dict[str, Any] | None,
        approval_records: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return {
            "nct_id": trial.get("nct_id"),
            "requested_nct_id": trial.get("requested_nct_id"),
            "brief_title": trial.get("brief_title"),
            "sponsor_name": trial.get("sponsor_name"),
            "phase_label": trial.get("phase_label"),
            "overall_status": trial.get("overall_status"),
            "therapeutic_area": trial.get("therapeutic_area"),
            "event_date_candidate": trial.get("event_date_candidate"),
            "event_date_source": trial.get("event_date_source"),
            "event_date_source_rank": trial.get("event_date_source_rank"),
            "event_date_quality_score": trial.get("event_date_quality_score"),
            "event_date_quality_tier": trial.get("event_date_quality_tier"),
            "mapped_ticker": None if sponsor_mapping is None else sponsor_mapping.get("ticker"),
            "mapped_cik": None if sponsor_mapping is None else sponsor_mapping.get("cik"),
            "approval_record_count": len(approval_records),
            "market_record_count": None if market_summary is None else market_summary.get("record_count"),
            "event_day_return": None if market_summary is None else market_summary.get("event_day_return"),
            "post_window_return": None if market_summary is None else market_summary.get("post_window_return"),
            "data_completeness_score": trial.get("data_completeness_score"),
        }

    def _normalize_sponsor_mapping(self, sponsor_name: str | None) -> tuple[dict[str, Any] | None, list[str]]:
        warnings: list[str] = []
        if not sponsor_name:
            warnings.append("Trial did not include a sponsor name, so ticker mapping was skipped.")
            return None, warnings
        try:
            result = self.sec_mapper.match_sponsor_to_ticker(sponsor_name)
            mapping = asdict(result)
            resolution = self.sponsor_mapping_review_service.apply_review_override(
                sponsor_name=sponsor_name,
                match_result=mapping,
            )
            mapping = resolution.get("mapping")
            if not mapping.get("ticker"):
                warnings.append("Sponsor mapping did not produce a confident public ticker match.")
            elif (mapping.get("confidence") or 0) < 0.85:
                warnings.append("Sponsor mapping produced a low-confidence ticker match that may need review.")
            if resolution.get("override_applied"):
                warnings.append("Sponsor mapping used a reviewed override instead of the raw SEC match.")
            return mapping, warnings
        except Exception as exc:
            warnings.append(f"SEC sponsor mapping failed: {exc}")
            return None, warnings

    def _build_event_date_quality_warnings(self, trial: dict[str, Any]) -> list[str]:
        assessment = self.event_date_quality_service.assess_event_date(
            event_date_value=trial.get("event_date_candidate"),
            event_date_source=trial.get("event_date_source"),
        )

        warnings: list[str] = []
        quality_tier = str(
            trial.get("event_date_quality_tier")
            or assessment.get("event_date_quality_tier")
            or "unknown"
        )
        quality_issues = list(
            trial.get("event_date_quality_issues")
            or assessment.get("event_date_quality_issues")
            or []
        )

        if quality_tier == "moderate":
            warnings.append(
                "Event date quality is moderate, so catalyst timing may be less reliable "
                "than a direct completion milestone."
            )
        elif quality_tier == "low":
            warnings.append(
                "Event date quality is low, so the selected catalyst date may be a weak "
                "proxy for the true market-moving event."
            )
        elif quality_tier == "unknown":
            warnings.append("Event date quality is unknown because the available catalyst-date metadata is incomplete.")

        if "low_rank_event_date_source" in quality_issues:
            warnings.append(
                "Event date relies on a lower-ranked proxy source instead of a primary "
                "completion milestone."
            )
        if "low_confidence_event_date" in quality_issues:
            warnings.append("Event date confidence is low based on the available source and date precision.")
        if "unknown_event_date_precision" in quality_issues:
            warnings.append("Event date precision could not be classified confidently from the source metadata.")
        return warnings

    def _fetch_market_summary(
        self,
        ticker: str | None,
        event_date: str | None,
        pre_days: int,
        post_days: int,
    ) -> tuple[dict[str, Any] | None, list[str]]:
        warnings: list[str] = []
        if not ticker:
            warnings.append("No mapped ticker was available, so market data was skipped.")
            return None, warnings
        if not event_date:
            warnings.append("No event date candidate was available, so market data was skipped.")
            return None, warnings
        if not DAY_PRECISION_PATTERN.fullmatch(event_date):
            warnings.append("Event date is not day-precision, so market event-window analysis was skipped.")
            return None, warnings
        try:
            market_summary = self.market_data_ingestor.summarize_event_reaction(
                ticker=ticker,
                event_date=event_date,
                pre_days=pre_days,
                post_days=post_days,
            )
            if market_summary.get("error"):
                warnings.append(str(market_summary["error"]))
            return market_summary, warnings
        except Exception as exc:
            warnings.append(f"Market data fetch failed: {exc}")
            return None, warnings

    def _fetch_fda_context(
        self,
        sponsor_name: str | None,
        approval_limit: int,
    ) -> tuple[list[dict[str, Any]], list[str]]:
        warnings: list[str] = []
        if not sponsor_name:
            warnings.append("No sponsor name was available, so FDA context was skipped.")
            return [], warnings
        try:
            records = self.openfda_ingestor.fetch_approval_snapshot(
                sponsor_name=sponsor_name,
                limit=approval_limit,
            )
            if not records:
                warnings.append("OpenFDA returned no sponsor-linked approval records.")
            return records, warnings
        except Exception as exc:
            warnings.append(f"OpenFDA fetch failed: {exc}")
            return [], warnings

    def _persist_analysis(self, trial: dict[str, Any], analysis: dict[str, Any]) -> dict[str, int] | None:
        try:
            with get_connection() as connection:
                trial_repository = ClinicalTrialsRepository(connection)
                analysis_repository = TrialAnalysisRepository(connection)
                historical_event_repository = HistoricalTrialEventRepository(connection)
                trial_repository.create_tables()
                analysis_repository.create_tables()
                historical_event_repository.create_tables()
                if self.persist_trial_records and trial.get("nct_id"):
                    trial_repository.upsert_trial(trial)
                analysis_id = analysis_repository.insert_analysis(analysis)
                event_record = self.historical_event_service.build_event_record(
                    analysis=analysis,
                    analysis_id=analysis_id,
                )
                event_id = historical_event_repository.upsert_event(event_record)
                return {"analysis_id": analysis_id, "historical_event_id": event_id}
        except DatabaseConfigError:
            return None

    def analyze_trial(
        self,
        nct_id: str,
        approval_limit: int = 5,
        market_pre_days: int = 5,
        market_post_days: int = 5,
        include_raw_trial: bool = False,
        save_to_db: bool = False,
    ) -> dict[str, Any]:
        warnings: list[str] = []

        trial = self.clinical_trials_ingestor.fetch_trial_data(nct_id, include_raw=include_raw_trial)
        warnings.extend(self._build_event_date_quality_warnings(trial))
        sponsor_mapping, sponsor_warnings = self._normalize_sponsor_mapping(trial.get("sponsor_name"))
        warnings.extend(sponsor_warnings)

        approval_records, fda_warnings = self._fetch_fda_context(
            sponsor_name=trial.get("sponsor_name"),
            approval_limit=approval_limit,
        )
        warnings.extend(fda_warnings)

        market_summary, market_warnings = self._fetch_market_summary(
            ticker=None if sponsor_mapping is None else sponsor_mapping.get("ticker"),
            event_date=trial.get("event_date_candidate"),
            pre_days=market_pre_days,
            post_days=market_post_days,
        )
        warnings.extend(market_warnings)
        warnings = self._normalize_warnings(warnings)

        analysis = {
            "status": "success",
            "analysis_type": "single_trial",
            "analysis_version": ANALYSIS_VERSION,
            "analyzed_at": datetime.now(UTC).isoformat(),
            "input": {
                "nct_id": nct_id,
                "approval_limit": approval_limit,
                "market_pre_days": market_pre_days,
                "market_post_days": market_post_days,
                "include_raw_trial": include_raw_trial,
                "save_to_db": save_to_db,
            },
            "summary": self._build_summary(
                trial=trial,
                sponsor_mapping=sponsor_mapping,
                market_summary=market_summary,
                approval_records=approval_records,
            ),
            "trial": trial,
            "sponsor_mapping": sponsor_mapping,
            "fda_context": {
                "approval_record_count": len(approval_records),
                "approval_records": approval_records,
            },
            "market_data": market_summary,
            "warnings": warnings,
        }
        if save_to_db:
            persistence_ids = self._persist_analysis(trial, analysis)
            if persistence_ids is not None:
                analysis["persistence"] = {
                    "saved": True,
                    "analysis_id": persistence_ids["analysis_id"],
                    "historical_event_id": persistence_ids["historical_event_id"],
                }
            else:
                analysis["persistence"] = {
                    "saved": False,
                    "analysis_id": None,
                    "historical_event_id": None,
                }
                analysis["warnings"] = self._normalize_warnings(
                    analysis["warnings"]
                    + [
                        "Analysis could not be persisted because the database was unavailable "
                        "or not configured."
                    ]
                )
        return analysis


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run an end-to-end analysis for one clinical trial")
    parser.add_argument("nct_id")
    parser.add_argument("--approval-limit", type=int, default=5)
    parser.add_argument("--market-pre-days", type=int, default=5)
    parser.add_argument("--market-post-days", type=int, default=5)
    parser.add_argument("--include-raw-trial", action="store_true")
    parser.add_argument("--save", action="store_true")
    parser.add_argument("--summary-only", action="store_true")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    service = TrialAnalysisService()
    result = service.analyze_trial(
        nct_id=args.nct_id,
        approval_limit=args.approval_limit,
        market_pre_days=args.market_pre_days,
        market_post_days=args.market_post_days,
        include_raw_trial=args.include_raw_trial,
        save_to_db=args.save,
    )
    payload = result["summary"] if args.summary_only else result
    print(json.dumps(payload, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
