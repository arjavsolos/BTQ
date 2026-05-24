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
from app.database.repositories import (
    EventDateReviewRepository,
    HistoricalTrialEventRepository,
    SponsorMappingReviewRepository,
    initialize_database,
)
from app.research import build_methodology_snapshot, render_methodology_markdown, render_trial_analysis_markdown
from app.services import (
    EventReturnBenchmarkService,
    HistoricalDatasetAuditService,
    HistoricalDatasetBackfillService,
    TrialAnalysisService,
)


def _build_sponsor_mapping_review_export_summary(reviews: list[dict[str, Any]]) -> dict[str, Any]:
    status_counts: dict[str, int] = {}
    for review in reviews:
        status = str(review.get("review_status") or "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1
    return {
        "exported_review_count": len(reviews),
        "status_counts": status_counts,
    }


def _build_historical_event_export_summary(events: list[dict[str, Any]]) -> dict[str, Any]:
    quality_tier_counts: dict[str, int] = {}
    model_ready_count = 0
    total_quality_score = 0
    quality_score_count = 0

    for event in events:
        tier = str(event.get("event_date_quality_tier") or "unknown")
        quality_tier_counts[tier] = quality_tier_counts.get(tier, 0) + 1
        if event.get("is_model_ready"):
            model_ready_count += 1
        quality_score = event.get("event_date_quality_score")
        if isinstance(quality_score, int | float):
            total_quality_score += int(quality_score)
            quality_score_count += 1

    average_quality_score = None
    if quality_score_count:
        average_quality_score = round(total_quality_score / quality_score_count, 2)

    return {
        "exported_event_count": len(events),
        "model_ready_count": model_ready_count,
        "event_date_quality_tier_counts": quality_tier_counts,
        "average_event_date_quality_score": average_quality_score,
    }


def _build_event_date_review_export_summary(reviews: list[dict[str, Any]]) -> dict[str, Any]:
    status_counts: dict[str, int] = {}
    quality_tier_counts: dict[str, int] = {}

    for review in reviews:
        review_status = str(review.get("review_status") or "unknown")
        status_counts[review_status] = status_counts.get(review_status, 0) + 1

        quality_tier = str(review.get("event_date_quality_tier") or "unknown")
        quality_tier_counts[quality_tier] = quality_tier_counts.get(quality_tier, 0) + 1

    return {
        "exported_review_count": len(reviews),
        "status_counts": status_counts,
        "event_date_quality_tier_counts": quality_tier_counts,
    }


def _render_benchmark_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Event Return Benchmark",
        "",
        f"- `group_by`: {report.get('group_by')}",
        f"- `event_count`: {(report.get('summary') or {}).get('event_count')}",
        f"- `group_count`: {(report.get('summary') or {}).get('group_count')}",
        "",
        "## Summary Sections",
    ]
    for section in report.get("summary_sections") or []:
        lines.extend(
            [
                "",
                f"### {section.get('title')}",
                "",
                str(section.get("display_summary") or ""),
            ]
        )
    lines.extend(["", "## Groups"])
    for group in report.get("groups") or []:
        lines.append(
            f"- `{group.get('group')}`: count={group.get('event_count')}, "
            f"avg_event_day_return={group.get('average_event_day_return')}, "
            f"median_event_day_return={group.get('median_event_day_return')}"
        )
    return "\n".join(lines)


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
    analyze.add_argument("--format", choices=["json", "markdown"], default="json")

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
    build_dataset.add_argument("--min-event-date-quality-score", type=int)
    build_dataset.add_argument("--event-date-quality-tier")
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

    export_historical_trial_events = subparsers.add_parser(
        "export-historical-trial-events",
        help="Export historical trial-event rows in JSON or JSONL format",
    )
    export_historical_trial_events.add_argument("--limit", type=int, default=100)
    export_historical_trial_events.add_argument("--offset", type=int, default=0)
    export_historical_trial_events.add_argument("--is-model-ready", action="store_true")
    export_historical_trial_events.add_argument("--mapped-ticker")
    export_historical_trial_events.add_argument("--phase")
    export_historical_trial_events.add_argument("--event-date-quality-tier")
    export_historical_trial_events.add_argument("--min-event-date-quality-score", type=int)
    export_historical_trial_events.add_argument("--format", choices=["json", "jsonl"], default="json")
    export_historical_trial_events.add_argument("--include-summary", action="store_true")

    export_event_date_reviews = subparsers.add_parser(
        "export-event-date-reviews",
        help="Export event-date review rows in JSON or JSONL format",
    )
    export_event_date_reviews.add_argument("--limit", type=int, default=100)
    export_event_date_reviews.add_argument("--offset", type=int, default=0)
    export_event_date_reviews.add_argument("--review-status")
    export_event_date_reviews.add_argument("--mapped-ticker")
    export_event_date_reviews.add_argument("--event-date-quality-tier")
    export_event_date_reviews.add_argument("--format", choices=["json", "jsonl"], default="json")
    export_event_date_reviews.add_argument("--include-summary", action="store_true")

    benchmark_event_returns = subparsers.add_parser(
        "benchmark-event-returns",
        help="Summarize historical event returns by a chosen cohort field",
    )
    benchmark_event_returns.add_argument(
        "--group-by",
        choices=[
            "phase_label",
            "mapped_ticker",
            "sponsor_class",
            "therapeutic_area",
            "event_date_quality_tier",
            "sponsor_mapping_review_status",
            "event_date_review_status",
        ],
        default="phase_label",
    )
    benchmark_event_returns.add_argument("--limit", type=int, default=1000)
    benchmark_event_returns.add_argument("--offset", type=int, default=0)
    benchmark_event_returns.add_argument("--is-model-ready", action="store_true")
    benchmark_event_returns.add_argument("--mapped-ticker")
    benchmark_event_returns.add_argument("--sponsor")
    benchmark_event_returns.add_argument("--phase")
    benchmark_event_returns.add_argument("--event-date-quality-tier")
    benchmark_event_returns.add_argument("--sponsor-mapping-review-status")
    benchmark_event_returns.add_argument("--event-date-review-status")
    benchmark_event_returns.add_argument("--sponsor-mapping-override", action="store_true")
    benchmark_event_returns.add_argument("--event-date-override", action="store_true")
    benchmark_event_returns.add_argument("--min-event-date-quality-score", type=int)
    benchmark_event_returns.add_argument("--min-group-size", type=int, default=5)
    benchmark_event_returns.add_argument("--format", choices=["json", "jsonl", "markdown"], default="json")
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
        if args.format == "markdown":
            print(render_trial_analysis_markdown(result))
            return
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
            min_event_date_quality_score=args.min_event_date_quality_score,
            event_date_quality_tier=args.event_date_quality_tier,
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

    if args.command == "export-historical-trial-events":
        is_model_ready_filter = True if args.is_model_ready else None

        with get_connection() as connection:
            repository = HistoricalTrialEventRepository(connection)
            repository.create_tables()
            events = repository.list_events(
                limit=args.limit,
                offset=args.offset,
                is_model_ready=is_model_ready_filter,
                mapped_ticker=args.mapped_ticker,
                phase_label=args.phase,
                event_date_quality_tier=args.event_date_quality_tier,
                min_event_date_quality_score=args.min_event_date_quality_score,
            )

        if args.format == "jsonl":
            for event in events:
                print(json.dumps(event, ensure_ascii=True))
            return

        payload = {
            "status": "success",
            "generated_at": datetime.now(UTC).isoformat(),
            "input": {
                "limit": args.limit,
                "offset": args.offset,
                "is_model_ready": is_model_ready_filter,
                "mapped_ticker": args.mapped_ticker,
                "phase_label": args.phase,
                "event_date_quality_tier": args.event_date_quality_tier,
                "min_event_date_quality_score": args.min_event_date_quality_score,
                "format": args.format,
                "include_summary": args.include_summary,
            },
            "events": events,
        }
        if args.include_summary:
            payload["summary"] = _build_historical_event_export_summary(events)
        print(json.dumps(payload, indent=2, ensure_ascii=True))
        return

    if args.command == "export-event-date-reviews":
        with get_connection() as connection:
            repository = EventDateReviewRepository(connection)
            repository.create_tables()
            reviews = repository.list_reviews(
                limit=args.limit,
                offset=args.offset,
                review_status=args.review_status,
                mapped_ticker=args.mapped_ticker,
                event_date_quality_tier=args.event_date_quality_tier,
            )

        if args.format == "jsonl":
            for review in reviews:
                print(json.dumps(review, ensure_ascii=True))
            return

        payload = {
            "status": "success",
            "generated_at": datetime.now(UTC).isoformat(),
            "input": {
                "limit": args.limit,
                "offset": args.offset,
                "review_status": args.review_status,
                "mapped_ticker": args.mapped_ticker,
                "event_date_quality_tier": args.event_date_quality_tier,
                "format": args.format,
                "include_summary": args.include_summary,
            },
            "reviews": reviews,
        }
        if args.include_summary:
            payload["summary"] = _build_event_date_review_export_summary(reviews)
        print(json.dumps(payload, indent=2, ensure_ascii=True))
        return

    if args.command == "benchmark-event-returns":
        service = EventReturnBenchmarkService()
        result = service.benchmark_dataset(
            group_by=args.group_by,
            limit=args.limit,
            offset=args.offset,
            is_model_ready=True if args.is_model_ready else None,
            mapped_ticker=args.mapped_ticker,
            sponsor_name=args.sponsor,
            phase_label=args.phase,
            event_date_quality_tier=args.event_date_quality_tier,
            sponsor_mapping_review_status=args.sponsor_mapping_review_status,
            event_date_review_status=args.event_date_review_status,
            sponsor_mapping_override_applied=True if args.sponsor_mapping_override else None,
            event_date_override_applied=True if args.event_date_override else None,
            min_event_date_quality_score=args.min_event_date_quality_score,
            min_group_size=args.min_group_size,
        )
        if args.format == "jsonl":
            for group in result.get("groups") or []:
                print(json.dumps(group, ensure_ascii=True))
            return
        if args.format == "markdown":
            print(_render_benchmark_markdown(result))
            return
        print(json.dumps(result, indent=2, ensure_ascii=True))
        return

    raise SystemExit(f"Unknown command: {args.command}")


if __name__ == "__main__":
    main()
