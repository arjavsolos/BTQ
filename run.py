from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.database import get_connection
from app.database.repositories import SponsorMappingReviewRepository
from app.database.repositories import initialize_database
from app.research import build_methodology_snapshot, render_methodology_markdown
from app.services import HistoricalDatasetAuditService, HistoricalDatasetBackfillService, TrialAnalysisService


def _build_sponsor_mapping_review_export_summary(reviews: list[dict[str, Any]]) -> dict[str, Any]:
    status_counts: dict[str, int] = {}
    for review in reviews:
        status = str(review.get("review_status") or "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1
    return {
        "exported_review_count": len(reviews),
        "status_counts": status_counts,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="BTQ project runner")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init-db", help="Initialize database tables")

    analyze = subparsers.add_parser("analyze-trial", help="Run end-to-end analysis for one NCT ID")
    analyze.add_argument("nct_id")
    analyze.add_argument("--approval-limit", type=int, default=5)
    analyze.add_argument("--market-pre-days", type=int, default=5)
    analyze.add_argument("--market-post-days", type=int, default=5)
    analyze.add_argument("--include-raw-trial", action="store_true")
    analyze.add_argument("--save", action="store_true")
    analyze.add_argument("--summary-only", action="store_true")

    build_dataset = subparsers.add_parser(
        "build-historical-dataset",
        help="Build historical trial-event dataset rows from stored clinical trials",
    )
    build_dataset.add_argument("--limit", type=int, default=25)
    build_dataset.add_argument("--offset", type=int, default=0)
    build_dataset.add_argument("--batch-size", type=int)
    build_dataset.add_argument("--max-batches", type=int)
    build_dataset.add_argument("--approval-limit", type=int, default=5)
    build_dataset.add_argument("--market-pre-days", type=int, default=5)
    build_dataset.add_argument("--market-post-days", type=int, default=5)
    build_dataset.add_argument("--status")
    build_dataset.add_argument("--sponsor")
    build_dataset.add_argument("--phase")
    build_dataset.add_argument("--study-type")
    build_dataset.add_argument("--therapeutic-area")
    build_dataset.add_argument("--has-results", action="store_true")
    build_dataset.add_argument("--without-results", action="store_true")
    build_dataset.add_argument("--include-existing", action="store_true")

    audit_dataset = subparsers.add_parser(
        "audit-historical-dataset",
        help="Audit the historical trial-event dataset for completeness and model readiness",
    )
    audit_dataset.add_argument("--top-warning-limit", type=int, default=10)
    audit_dataset.add_argument("--issue-limit", type=int, default=25)
    audit_dataset.add_argument("--therapeutic-area-limit", type=int, default=10)

    describe_methodology = subparsers.add_parser(
        "describe-methodology",
        help="Print the project methodology in JSON or Markdown form",
    )
    describe_methodology.add_argument("--format", choices=["json", "markdown"], default="json")

    export_sponsor_mapping_reviews = subparsers.add_parser(
        "export-sponsor-mapping-reviews",
        help="Export sponsor mapping review rows in JSON or JSONL format",
    )
    export_sponsor_mapping_reviews.add_argument("--limit", type=int, default=100)
    export_sponsor_mapping_reviews.add_argument("--offset", type=int, default=0)
    export_sponsor_mapping_reviews.add_argument("--review-status")
    export_sponsor_mapping_reviews.add_argument("--suggested-ticker")
    export_sponsor_mapping_reviews.add_argument("--reviewer-email")
    export_sponsor_mapping_reviews.add_argument("--format", choices=["json", "jsonl"], default="json")
    export_sponsor_mapping_reviews.add_argument("--include-summary", action="store_true")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "init-db":
        initialize_database()
        print(json.dumps({"status": "success", "message": "Database initialized."}, indent=2))
        return

    if args.command == "analyze-trial":
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
        return

    if args.command == "build-historical-dataset":
        if args.has_results and args.without_results:
            raise SystemExit("--has-results and --without-results cannot be used together.")

        service = HistoricalDatasetBackfillService()
        result = service.build_from_database(
            limit=args.limit,
            offset=args.offset,
            approval_limit=args.approval_limit,
            market_pre_days=args.market_pre_days,
            market_post_days=args.market_post_days,
            overall_status=args.status,
            sponsor_name=args.sponsor,
            phase_label=args.phase,
            study_type=args.study_type,
            therapeutic_area=args.therapeutic_area,
            has_results=False if args.without_results else (True if args.has_results else None),
            exclude_existing_historical_events=not args.include_existing,
            batch_size=args.batch_size,
            max_batches=args.max_batches,
        )
        print(json.dumps(result, indent=2, ensure_ascii=True))
        return

    if args.command == "audit-historical-dataset":
        service = HistoricalDatasetAuditService()
        result = service.audit_dataset(
            top_warning_limit=args.top_warning_limit,
            issue_limit=args.issue_limit,
            therapeutic_area_limit=args.therapeutic_area_limit,
        )
        print(json.dumps(result, indent=2, ensure_ascii=True))
        return

    if args.command == "describe-methodology":
        if args.format == "markdown":
            print(render_methodology_markdown())
            return
        print(json.dumps(build_methodology_snapshot(), indent=2, ensure_ascii=True))
        return

    if args.command == "export-sponsor-mapping-reviews":
        with get_connection() as connection:
            repository = SponsorMappingReviewRepository(connection)
            repository.create_tables()
            reviews = repository.list_reviews(
                limit=args.limit,
                offset=args.offset,
                review_status=args.review_status,
                suggested_ticker=args.suggested_ticker,
                reviewer_email=args.reviewer_email,
            )

        if args.format == "jsonl":
            for review in reviews:
                print(json.dumps(review, ensure_ascii=True))
            return

        payload: dict[str, Any] = {
            "status": "success",
            "generated_at": datetime.now(UTC).isoformat(),
            "input": {
                "limit": args.limit,
                "offset": args.offset,
                "review_status": args.review_status,
                "suggested_ticker": args.suggested_ticker,
                "reviewer_email": args.reviewer_email,
                "format": args.format,
                "include_summary": args.include_summary,
            },
            "reviews": reviews,
        }
        if args.include_summary:
            payload["summary"] = _build_sponsor_mapping_review_export_summary(reviews)
        print(json.dumps(payload, indent=2, ensure_ascii=True))
        return

    raise SystemExit(f"Unknown command: {args.command}")


if __name__ == "__main__":
    main()
