from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.database.connection import DatabaseConfigError, get_connection
from app.database.repositories import ClinicalTrialsRepository
from app.ingestion.clinical_trials import ClinicalTrialsIngestor, TrialQuery


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Backfill ClinicalTrials.gov data into Postgres")
    parser.add_argument("--query")
    parser.add_argument("--status")
    parser.add_argument("--phase")
    parser.add_argument("--study-type")
    parser.add_argument("--sponsor")
    parser.add_argument("--condition")
    parser.add_argument("--intervention")
    parser.add_argument("--intervention-type")
    parser.add_argument("--country")
    parser.add_argument("--has-results", action="store_true")
    parser.add_argument("--without-results", action="store_true")
    parser.add_argument("--page-size", type=int, default=25)
    parser.add_argument("--pages", type=int, default=1)
    parser.add_argument("--print-sample", action="store_true")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    has_results = None
    if args.has_results and args.without_results:
        raise ValueError("Choose only one of --has-results or --without-results")
    if args.has_results:
        has_results = True
    elif args.without_results:
        has_results = False

    ingestor = ClinicalTrialsIngestor()
    query = TrialQuery(
        query_term=args.query,
        filter_overall_status=args.status,
        filter_phase=args.phase,
        filter_study_type=args.study_type,
        sponsor_name=args.sponsor,
        condition=args.condition,
        intervention_name=args.intervention,
        intervention_type=args.intervention_type,
        country=args.country,
        has_results=has_results,
        page_size=args.page_size,
        max_pages=args.pages,
    )

    records = ingestor.search_trials(query)

    if args.print_sample and records:
        print(json.dumps(records[0], indent=2, ensure_ascii=True))

    try:
        with get_connection() as connection:
            repository = ClinicalTrialsRepository(connection)
            repository.create_tables()
            inserted_count = repository.upsert_trials(records)
    except DatabaseConfigError as exc:
        raise SystemExit(str(exc)) from exc

    print(
        json.dumps(
            {
                "status": "success",
                "fetched_records": len(records),
                "upserted_records": inserted_count,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
