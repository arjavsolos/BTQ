from __future__ import annotations

import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.database.connection import DatabaseConfigError, get_connection
from app.database.repositories import ClinicalTrialsRepository
from app.ingestion.clinical_trials import ClinicalTrialsIngestor, TrialQuery


def _get_str_env(name: str) -> str | None:
    value = os.getenv(name)
    if value is None:
        return None
    value = value.strip()
    return value or None


def _get_bool_env(name: str, default: bool | None = None) -> bool | None:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"Environment variable {name} must be a boolean-like value, got: {value!r}")


def _get_int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return int(value.strip())


def build_query_from_env() -> TrialQuery:
    has_results = _get_bool_env("BACKFILL_HAS_RESULTS")
    without_results = _get_bool_env("BACKFILL_WITHOUT_RESULTS", False)

    if has_results and without_results:
        raise ValueError("BACKFILL_HAS_RESULTS and BACKFILL_WITHOUT_RESULTS cannot both be true.")

    return TrialQuery(
        query_term=_get_str_env("BACKFILL_QUERY"),
        filter_overall_status=_get_str_env("BACKFILL_STATUS"),
        filter_phase=_get_str_env("BACKFILL_PHASE"),
        filter_study_type=_get_str_env("BACKFILL_STUDY_TYPE"),
        sponsor_name=_get_str_env("BACKFILL_SPONSOR"),
        condition=_get_str_env("BACKFILL_CONDITION"),
        intervention_name=_get_str_env("BACKFILL_INTERVENTION"),
        intervention_type=_get_str_env("BACKFILL_INTERVENTION_TYPE"),
        country=_get_str_env("BACKFILL_COUNTRY"),
        has_results=False if without_results else has_results,
        page_size=_get_int_env("BACKFILL_PAGE_SIZE", 50),
        max_pages=_get_int_env("BACKFILL_PAGES", 2),
    )


def main() -> None:
    query = None
    try:
        query = build_query_from_env()
        ingestor = ClinicalTrialsIngestor()
        records = ingestor.search_trials(query)

        with get_connection() as connection:
            repository = ClinicalTrialsRepository(connection)
            repository.create_tables()
            upserted_records = repository.upsert_trials(records)
    except (DatabaseConfigError, ValueError, RuntimeError) as exc:
        print(
            json.dumps(
                {
                    "status": "error",
                    "error": str(exc),
                    "query": None
                    if query is None
                    else {
                        "query_term": query.query_term,
                        "status": query.filter_overall_status,
                        "phase": query.filter_phase,
                        "study_type": query.filter_study_type,
                        "sponsor": query.sponsor_name,
                        "condition": query.condition,
                        "intervention": query.intervention_name,
                        "intervention_type": query.intervention_type,
                        "country": query.country,
                        "has_results": query.has_results,
                        "page_size": query.page_size,
                        "max_pages": query.max_pages,
                    },
                },
                indent=2,
            )
        )
        raise SystemExit(1) from exc

    print(
        json.dumps(
            {
                "status": "success",
                "fetched_records": len(records),
                "upserted_records": upserted_records,
                "query": {
                    "query_term": query.query_term,
                    "status": query.filter_overall_status,
                    "phase": query.filter_phase,
                    "study_type": query.filter_study_type,
                    "sponsor": query.sponsor_name,
                    "condition": query.condition,
                    "intervention": query.intervention_name,
                    "intervention_type": query.intervention_type,
                    "country": query.country,
                    "has_results": query.has_results,
                    "page_size": query.page_size,
                    "max_pages": query.max_pages,
                },
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
