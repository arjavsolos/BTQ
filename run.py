from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.database.repositories import initialize_database
from app.services import HistoricalDatasetBackfillService, TrialAnalysisService


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
    build_dataset.add_argument("--approval-limit", type=int, default=5)
    build_dataset.add_argument("--market-pre-days", type=int, default=5)
    build_dataset.add_argument("--market-post-days", type=int, default=5)
    build_dataset.add_argument("--status")
    build_dataset.add_argument("--sponsor")
    build_dataset.add_argument("--has-results", action="store_true")
    build_dataset.add_argument("--without-results", action="store_true")
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
            approval_limit=args.approval_limit,
            market_pre_days=args.market_pre_days,
            market_post_days=args.market_post_days,
            overall_status=args.status,
            sponsor_name=args.sponsor,
            has_results=False if args.without_results else (True if args.has_results else None),
        )
        print(json.dumps(result, indent=2, ensure_ascii=True))
        return

    raise SystemExit(f"Unknown command: {args.command}")


if __name__ == "__main__":
    main()
