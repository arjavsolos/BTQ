from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from app.database.connection import get_connection_for_url
from app.database.repositories import (
    ClinicalTrialsRepository,
    EventDateReviewRepository,
    HistoricalTrialEventRepository,
    SponsorMappingReviewRepository,
    TrialAnalysisRepository,
)

SYNC_TABLES = [
    "clinical_trials",
    "trial_analyses",
    "historical_trial_events",
    "event_date_reviews",
    "sponsor_mapping_reviews",
]

SEQUENCE_TARGETS = {
    "trial_analyses": "analysis_id",
    "historical_trial_events": "event_id",
    "event_date_reviews": "review_id",
    "sponsor_mapping_reviews": "review_id",
}


class DatabaseSyncService:
    """
    Copies the full BTQ dataset from one Postgres database to another.
    """

    def __init__(self) -> None:
        load_dotenv(Path(".env"))

    def _resolve_source_url(self, source_database_url: str | None) -> str:
        resolved = (
            source_database_url
            or os.getenv("SYNC_SOURCE_DATABASE_URL")
            or os.getenv("LOCAL_DATABASE_URL")
            or os.getenv("DATABASE_URL")
        )
        if not resolved:
            raise ValueError("Set SYNC_SOURCE_DATABASE_URL, LOCAL_DATABASE_URL, or DATABASE_URL.")
        return resolved

    def _resolve_target_url(self, target_database_url: str | None) -> str:
        resolved = (
            target_database_url
            or os.getenv("SYNC_TARGET_DATABASE_URL")
            or os.getenv("NEON_DATABASE_URL")
            or os.getenv("HOSTED_DATABASE_URL")
        )
        if not resolved:
            raise ValueError("Set SYNC_TARGET_DATABASE_URL, NEON_DATABASE_URL, or HOSTED_DATABASE_URL.")
        return resolved

    def _normalize_value(self, value: Any) -> Any:
        if isinstance(value, dict | list):
            return json.dumps(value)
        return value

    def _initialize_target_tables(self, connection: Any) -> None:
        ClinicalTrialsRepository(connection).create_tables()
        TrialAnalysisRepository(connection).create_tables()
        EventDateReviewRepository(connection).create_tables()
        HistoricalTrialEventRepository(connection).create_tables()
        SponsorMappingReviewRepository(connection).create_tables()

    def _fetch_columns(self, connection: Any, table: str) -> list[str]:
        sql = """
        select column_name
        from information_schema.columns
        where table_schema = 'public' and table_name = %s
        order by ordinal_position
        """
        with connection.cursor() as cursor:
            cursor.execute(sql, (table,))
            return [row[0] for row in cursor.fetchall()]

    def _fetch_rows(self, connection: Any, table: str, columns: list[str]) -> list[tuple[Any, ...]]:
        quoted_columns = ", ".join(columns)
        with connection.cursor() as cursor:
            cursor.execute(f"select {quoted_columns} from {table}")
            return cursor.fetchall()

    def _truncate_target(self, connection: Any) -> None:
        with connection.cursor() as cursor:
            cursor.execute(
                "truncate table historical_trial_events, trial_analyses, "
                "event_date_reviews, sponsor_mapping_reviews, clinical_trials "
                "restart identity cascade;"
            )

    def _insert_rows(self, connection: Any, table: str, columns: list[str], rows: list[tuple[Any, ...]]) -> int:
        if not rows:
            return 0
        placeholders = ", ".join(["%s"] * len(columns))
        insert_columns = ", ".join(columns)
        sql = f"insert into {table} ({insert_columns}) values ({placeholders})"
        normalized_rows = [tuple(self._normalize_value(value) for value in row) for row in rows]
        with connection.cursor() as cursor:
            cursor.executemany(sql, normalized_rows)
        return len(rows)

    def _reset_sequences(self, connection: Any) -> None:
        with connection.cursor() as cursor:
            for table, primary_key in SEQUENCE_TARGETS.items():
                cursor.execute("select pg_get_serial_sequence(%s, %s)", (table, primary_key))
                sequence_name = cursor.fetchone()[0]
                if not sequence_name:
                    continue
                cursor.execute(
                    f"select setval(%s, coalesce((select max({primary_key}) from {table}), 1), "
                    f"(select count(*) > 0 from {table}))",
                    (sequence_name,),
                )

    def _count_rows(self, connection: Any, table: str) -> int:
        with connection.cursor() as cursor:
            cursor.execute(f"select count(*) from {table}")
            return int(cursor.fetchone()[0])

    def sync_full_dataset(
        self,
        source_database_url: str | None = None,
        target_database_url: str | None = None,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        resolved_source_url = self._resolve_source_url(source_database_url)
        resolved_target_url = self._resolve_target_url(target_database_url)

        source_counts: dict[str, int] = {}
        with get_connection_for_url(resolved_source_url, application_name="btq-sync-source") as source:
            for table in SYNC_TABLES:
                columns = self._fetch_columns(source, table)
                source_counts[table] = len(self._fetch_rows(source, table, columns))

        if dry_run:
            return {
                "status": "dry_run",
                "source_counts": source_counts,
                "target_counts": {},
                "tables": list(SYNC_TABLES),
            }

        copied_counts: dict[str, int] = {}
        with (
            get_connection_for_url(resolved_source_url, application_name="btq-sync-source") as source,
            get_connection_for_url(resolved_target_url, application_name="btq-sync-target") as target,
        ):
            self._initialize_target_tables(target)
            self._truncate_target(target)

            for table in SYNC_TABLES:
                columns = self._fetch_columns(source, table)
                rows = self._fetch_rows(source, table, columns)
                copied_counts[table] = self._insert_rows(target, table, columns, rows)

            self._reset_sequences(target)
            target_counts = {table: self._count_rows(target, table) for table in SYNC_TABLES}

        return {
            "status": "success",
            "source_counts": source_counts,
            "copied_counts": copied_counts,
            "target_counts": target_counts,
            "tables": list(SYNC_TABLES),
        }
