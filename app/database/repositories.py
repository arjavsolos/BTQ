import json
from typing import Any

from app.database.connection import get_connection
from app.database.schemas import (
    CLINICAL_TRIALS_INDEX_SQL,
    CLINICAL_TRIALS_MIGRATION_SQL,
    CLINICAL_TRIALS_TABLE_SQL,
    HISTORICAL_TRIAL_EVENTS_INDEX_SQL,
    HISTORICAL_TRIAL_EVENTS_MIGRATION_SQL,
    HISTORICAL_TRIAL_EVENTS_TABLE_SQL,
    SPONSOR_MAPPING_REVIEWS_MIGRATION_SQL,
    SPONSOR_MAPPING_REVIEWS_INDEX_SQL,
    SPONSOR_MAPPING_REVIEWS_TABLE_SQL,
    TRIAL_ANALYSES_INDEX_SQL,
    TRIAL_ANALYSES_TABLE_SQL,
)

JSON_FIELDS = {
    "nct_aliases",
    "secondary_ids",
    "collaborators",
    "responsible_party",
    "phases",
    "conditions",
    "condition_keywords",
    "interventions",
    "intervention_names",
    "intervention_types",
    "arm_groups",
    "primary_outcomes",
    "secondary_outcomes",
    "other_outcomes",
    "primary_endpoint_measures",
    "secondary_endpoint_measures",
    "std_ages",
    "locations",
    "country_counts",
    "trial_references",
    "see_also_links",
    "keyword_hits",
    "derived_misc_info",
    "central_contacts",
    "overall_officials",
}

HISTORICAL_EVENT_JSON_FIELDS = {
    "approval_application_numbers",
    "approval_brand_names",
    "approval_sponsor_names",
    "warnings",
    "feature_payload",
}

SPONSOR_MAPPING_REVIEW_JSON_FIELDS = {
    "alternatives",
}

COLUMN_SOURCE_MAP = {
    "trial_references": "references",
}


TRIAL_COLUMNS = [
    "nct_id",
    "requested_nct_id",
    "org_study_id",
    "acronym",
    "nct_aliases",
    "secondary_ids",
    "brief_title",
    "official_title",
    "sponsor_name",
    "sponsor_class",
    "collaborators",
    "responsible_party",
    "overall_status",
    "why_stopped",
    "status_verified_date",
    "has_results",
    "expanded_access",
    "study_type",
    "phases",
    "phase_label",
    "phase_score",
    "allocation",
    "intervention_model",
    "primary_purpose",
    "masking",
    "enrollment_count",
    "enrollment_type",
    "therapeutic_area",
    "conditions",
    "condition_keywords",
    "interventions",
    "intervention_names",
    "intervention_types",
    "arm_groups",
    "primary_outcomes",
    "secondary_outcomes",
    "other_outcomes",
    "primary_endpoint_measures",
    "secondary_endpoint_measures",
    "brief_summary",
    "detailed_description",
    "eligibility_criteria",
    "healthy_volunteers",
    "sex",
    "minimum_age",
    "maximum_age",
    "std_ages",
    "fda_regulated_drug",
    "fda_regulated_device",
    "has_dmc",
    "start_date",
    "primary_completion_date",
    "completion_date",
    "study_first_posted",
    "results_first_posted",
    "last_update_posted",
    "event_date_candidate",
    "event_date_source",
    "event_date_precision",
    "event_date_confidence",
    "locations",
    "location_count",
    "country_counts",
    "us_site_count",
    "trial_references",
    "reference_count",
    "see_also_links",
    "keyword_hits",
    "derived_misc_info",
    "central_contacts",
    "overall_officials",
    "ipd_sharing",
    "source_system",
    "source_api_version",
    "has_sponsor",
    "has_primary_outcomes",
    "has_secondary_outcomes",
    "has_locations",
    "has_interventions",
    "has_reference_support",
    "has_eligibility",
    "has_event_date",
    "has_results_flag",
    "data_completeness_score",
    "data_completeness_ratio",
]


def _serialize_value(column: str, value: Any) -> Any:
    if column in JSON_FIELDS:
        if value is None:
            default_value = (
                {}
                if column in {"responsible_party", "country_counts", "keyword_hits", "derived_misc_info"}
                else []
            )
            return json.dumps(default_value)
        return json.dumps(value)
    return value


def _record_value(trial_record: dict[str, Any], column: str) -> Any:
    source_key = COLUMN_SOURCE_MAP.get(column, column)
    return trial_record.get(source_key)


class ClinicalTrialsRepository:
    def __init__(self, connection: Any) -> None:
        self.connection = connection

    def create_tables(self) -> None:
        with self.connection.cursor() as cursor:
            cursor.execute(CLINICAL_TRIALS_TABLE_SQL)
            for statement in CLINICAL_TRIALS_MIGRATION_SQL:
                cursor.execute(statement)
            for statement in CLINICAL_TRIALS_INDEX_SQL:
                cursor.execute(statement)

    def upsert_trial(self, trial_record: dict[str, Any]) -> None:
        placeholders = ", ".join(["%s"] * len(TRIAL_COLUMNS))
        insert_columns = ", ".join(TRIAL_COLUMNS)
        update_assignments = ", ".join(
            f"{column} = excluded.{column}" for column in TRIAL_COLUMNS if column != "nct_id"
        )
        values = [_serialize_value(column, _record_value(trial_record, column)) for column in TRIAL_COLUMNS]

        sql = f"""
        insert into clinical_trials ({insert_columns})
        values ({placeholders})
        on conflict (nct_id) do update
        set {update_assignments},
            updated_at = now();
        """

        with self.connection.cursor() as cursor:
            cursor.execute(sql, values)

    def upsert_trials(self, trial_records: list[dict[str, Any]]) -> int:
        count = 0
        for trial_record in trial_records:
            if not trial_record.get("nct_id"):
                continue
            self.upsert_trial(trial_record)
            count += 1
        return count

    def list_trial_identifiers(
        self,
        limit: int = 100,
        offset: int = 0,
        overall_status: str | None = None,
        sponsor_name: str | None = None,
        phase_label: str | None = None,
        study_type: str | None = None,
        therapeutic_area: str | None = None,
        has_results: bool | None = None,
        require_event_date: bool = True,
        exclude_existing_historical_events: bool = False,
    ) -> list[dict[str, Any]]:
        clauses = []
        params: list[Any] = []
        join_clause = ""

        if overall_status:
            clauses.append("clinical_trials.overall_status = %s")
            params.append(overall_status)
        if sponsor_name:
            clauses.append("clinical_trials.sponsor_name ilike %s")
            params.append(f"%{sponsor_name}%")
        if phase_label:
            clauses.append("clinical_trials.phase_label = %s")
            params.append(phase_label)
        if study_type:
            clauses.append("clinical_trials.study_type = %s")
            params.append(study_type)
        if therapeutic_area:
            clauses.append("clinical_trials.therapeutic_area = %s")
            params.append(therapeutic_area)
        if has_results is not None:
            clauses.append("clinical_trials.has_results = %s")
            params.append(has_results)
        if require_event_date:
            clauses.append("clinical_trials.event_date_candidate is not null")
        if exclude_existing_historical_events:
            join_clause = """
            left join historical_trial_events hte
                on hte.nct_id = clinical_trials.nct_id
            """
            clauses.append("hte.nct_id is null")

        where_clause = ""
        if clauses:
            where_clause = "where " + " and ".join(clauses)

        sql = f"""
        select
            clinical_trials.nct_id,
            clinical_trials.sponsor_name,
            clinical_trials.overall_status,
            clinical_trials.phase_label,
            clinical_trials.study_type,
            clinical_trials.therapeutic_area,
            clinical_trials.has_results,
            clinical_trials.event_date_candidate
        from clinical_trials
        {join_clause}
        {where_clause}
        order by
            clinical_trials.event_date_candidate desc nulls last,
            clinical_trials.updated_at desc
        limit %s
        offset %s;
        """
        params.extend([max(1, limit), max(0, offset)])

        with self.connection.cursor() as cursor:
            cursor.execute(sql, tuple(params))
            rows = cursor.fetchall()

        return [
            {
                "nct_id": row[0],
                "sponsor_name": row[1],
                "overall_status": row[2],
                "phase_label": row[3],
                "study_type": row[4],
                "therapeutic_area": row[5],
                "has_results": row[6],
                "event_date_candidate": row[7],
            }
            for row in rows
        ]


class TrialAnalysisRepository:
    def __init__(self, connection: Any) -> None:
        self.connection = connection

    def create_tables(self) -> None:
        with self.connection.cursor() as cursor:
            cursor.execute(TRIAL_ANALYSES_TABLE_SQL)
            for statement in TRIAL_ANALYSES_INDEX_SQL:
                cursor.execute(statement)

    def insert_analysis(self, analysis_record: dict[str, Any]) -> int:
        summary = analysis_record.get("summary") or {}
        payload = json.dumps(analysis_record)
        sql = """
        insert into trial_analyses (
            nct_id,
            requested_nct_id,
            mapped_ticker,
            mapped_cik,
            sponsor_name,
            event_date_candidate,
            event_date_source,
            overall_status,
            phase_label,
            therapeutic_area,
            approval_record_count,
            market_record_count,
            event_day_return,
            post_window_return,
            warning_count,
            analysis_version,
            analysis_payload
        )
        values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        returning analysis_id;
        """
        values = (
            summary.get("nct_id"),
            analysis_record.get("trial", {}).get("requested_nct_id"),
            summary.get("mapped_ticker"),
            summary.get("mapped_cik"),
            summary.get("sponsor_name"),
            summary.get("event_date_candidate"),
            summary.get("event_date_source"),
            summary.get("overall_status"),
            summary.get("phase_label"),
            summary.get("therapeutic_area"),
            summary.get("approval_record_count"),
            summary.get("market_record_count"),
            summary.get("event_day_return"),
            summary.get("post_window_return"),
            len(analysis_record.get("warnings") or []),
            analysis_record.get("analysis_version", "1.0"),
            payload,
        )
        with self.connection.cursor() as cursor:
            cursor.execute(sql, values)
            row = cursor.fetchone()
        return int(row[0])


HISTORICAL_EVENT_COLUMNS = [
    "analysis_id",
    "nct_id",
    "requested_nct_id",
    "brief_title",
    "sponsor_name",
    "sponsor_class",
    "overall_status",
    "phase_label",
    "phase_score",
    "study_type",
    "therapeutic_area",
    "enrollment_count",
    "has_results",
    "data_completeness_score",
    "data_completeness_ratio",
    "event_date_candidate",
    "event_date_source",
    "event_date_precision",
    "event_date_confidence",
    "mapped_ticker",
    "mapped_cik",
    "matched_company_name",
    "mapping_confidence",
    "mapping_match_type",
    "approval_record_count",
    "approval_application_numbers",
    "approval_brand_names",
    "approval_sponsor_names",
    "market_record_count",
    "trade_start",
    "trade_end",
    "prior_close",
    "event_close",
    "latest_close",
    "event_day_return",
    "post_window_return",
    "warning_count",
    "warnings",
    "is_model_ready",
    "dataset_version",
    "source_analysis_version",
    "feature_payload",
]

SPONSOR_MAPPING_REVIEW_COLUMNS = [
    "sponsor_name",
    "normalized_sponsor_name",
    "source_nct_id",
    "suggested_company_name",
    "suggested_ticker",
    "suggested_cik",
    "suggested_confidence",
    "suggested_match_type",
    "alternatives",
    "review_status",
    "reviewed_mapping_status",
    "reviewed_company_name",
    "reviewed_ticker",
    "reviewed_cik",
    "reviewer_name",
    "reviewer_email",
    "review_notes",
    "reviewed_at",
]


class HistoricalTrialEventRepository:
    def __init__(self, connection: Any) -> None:
        self.connection = connection

    def create_tables(self) -> None:
        with self.connection.cursor() as cursor:
            cursor.execute(HISTORICAL_TRIAL_EVENTS_TABLE_SQL)
            for statement in HISTORICAL_TRIAL_EVENTS_MIGRATION_SQL:
                cursor.execute(statement)
            for statement in HISTORICAL_TRIAL_EVENTS_INDEX_SQL:
                cursor.execute(statement)

    def upsert_event(self, event_record: dict[str, Any]) -> int:
        placeholders = ", ".join(["%s"] * len(HISTORICAL_EVENT_COLUMNS))
        insert_columns = ", ".join(HISTORICAL_EVENT_COLUMNS)
        update_assignments = ", ".join(
            f"{column} = excluded.{column}" for column in HISTORICAL_EVENT_COLUMNS if column != "nct_id"
        )
        values = []
        for column in HISTORICAL_EVENT_COLUMNS:
            value = event_record.get(column)
            if column in HISTORICAL_EVENT_JSON_FIELDS:
                value = json.dumps(value if value is not None else ([] if column != "feature_payload" else {}))
            values.append(value)

        sql = f"""
        insert into historical_trial_events ({insert_columns})
        values ({placeholders})
        on conflict (nct_id, event_date_candidate, mapped_ticker) do update
        set {update_assignments},
            updated_at = now()
        returning event_id;
        """

        with self.connection.cursor() as cursor:
            cursor.execute(sql, values)
            row = cursor.fetchone()
        return int(row[0])

    def list_recent_events(self, limit: int = 100) -> list[dict[str, Any]]:
        sql = """
        select
            event_id,
            analysis_id,
            nct_id,
            requested_nct_id,
            sponsor_name,
            mapped_ticker,
            event_date_candidate,
            event_day_return,
            post_window_return,
            is_model_ready,
            created_at
        from historical_trial_events
        order by created_at desc
        limit %s;
        """
        with self.connection.cursor() as cursor:
            cursor.execute(sql, (max(1, limit),))
            rows = cursor.fetchall()
        return [
            {
                "event_id": row[0],
                "analysis_id": row[1],
                "nct_id": row[2],
                "requested_nct_id": row[3],
                "sponsor_name": row[4],
                "mapped_ticker": row[5],
                "event_date_candidate": row[6],
                "event_day_return": row[7],
                "post_window_return": row[8],
                "is_model_ready": row[9],
                "created_at": str(row[10]),
            }
            for row in rows
        ]

    def get_quality_summary(self) -> dict[str, Any]:
        sql = """
        select
            count(*) as total_events,
            count(*) filter (where is_model_ready) as model_ready_events,
            count(*) filter (
                where mapped_ticker is null or btrim(mapped_ticker) = ''
            ) as missing_ticker_events,
            count(*) filter (
                where event_date_candidate is null or btrim(event_date_candidate) = ''
            ) as missing_event_date_events,
            count(*) filter (
                where market_record_count is null or market_record_count = 0
            ) as missing_market_data_events,
            count(*) filter (where event_day_return is null) as missing_event_return_events,
            count(*) filter (where approval_record_count = 0) as missing_fda_context_events,
            count(*) filter (where warning_count > 0) as warning_events,
            count(*) filter (where mapping_confidence is null) as missing_mapping_confidence_events,
            count(*) filter (
                where mapping_confidence is not null and mapping_confidence < 0.8
            ) as low_confidence_mapping_events,
            count(*) filter (
                where data_completeness_ratio is null or data_completeness_ratio < 0.7
            ) as low_completeness_events,
            avg(data_completeness_ratio) as average_data_completeness_ratio,
            avg(mapping_confidence) as average_mapping_confidence,
            avg(event_day_return) as average_event_day_return,
            avg(post_window_return) as average_post_window_return
        from historical_trial_events;
        """
        with self.connection.cursor() as cursor:
            cursor.execute(sql)
            row = cursor.fetchone()
        return {
            "total_events": row[0],
            "model_ready_events": row[1],
            "missing_ticker_events": row[2],
            "missing_event_date_events": row[3],
            "missing_market_data_events": row[4],
            "missing_event_return_events": row[5],
            "missing_fda_context_events": row[6],
            "warning_events": row[7],
            "missing_mapping_confidence_events": row[8],
            "low_confidence_mapping_events": row[9],
            "low_completeness_events": row[10],
            "average_data_completeness_ratio": row[11],
            "average_mapping_confidence": row[12],
            "average_event_day_return": row[13],
            "average_post_window_return": row[14],
        }

    def get_phase_breakdown(self) -> list[dict[str, Any]]:
        sql = """
        select
            coalesce(nullif(phase_label, ''), 'UNKNOWN') as phase_label,
            count(*) as event_count,
            count(*) filter (where is_model_ready) as model_ready_count
        from historical_trial_events
        group by 1
        order by event_count desc, phase_label asc;
        """
        with self.connection.cursor() as cursor:
            cursor.execute(sql)
            rows = cursor.fetchall()
        return [
            {
                "phase_label": row[0],
                "event_count": row[1],
                "model_ready_count": row[2],
            }
            for row in rows
        ]

    def get_therapeutic_area_breakdown(self, limit: int = 10) -> list[dict[str, Any]]:
        sql = """
        select
            coalesce(nullif(therapeutic_area, ''), 'UNKNOWN') as therapeutic_area,
            count(*) as event_count,
            count(*) filter (where is_model_ready) as model_ready_count
        from historical_trial_events
        group by 1
        order by event_count desc, therapeutic_area asc
        limit %s;
        """
        with self.connection.cursor() as cursor:
            cursor.execute(sql, (max(1, limit),))
            rows = cursor.fetchall()
        return [
            {
                "therapeutic_area": row[0],
                "event_count": row[1],
                "model_ready_count": row[2],
            }
            for row in rows
        ]

    def get_event_date_precision_breakdown(self) -> list[dict[str, Any]]:
        sql = """
        select
            coalesce(nullif(event_date_precision, ''), 'UNKNOWN') as event_date_precision,
            count(*) as event_count
        from historical_trial_events
        group by 1
        order by event_count desc, event_date_precision asc;
        """
        with self.connection.cursor() as cursor:
            cursor.execute(sql)
            rows = cursor.fetchall()
        return [
            {
                "event_date_precision": row[0],
                "event_count": row[1],
            }
            for row in rows
        ]

    def get_event_date_confidence_breakdown(self) -> list[dict[str, Any]]:
        sql = """
        select
            coalesce(nullif(event_date_confidence, ''), 'UNKNOWN') as event_date_confidence,
            count(*) as event_count
        from historical_trial_events
        group by 1
        order by event_count desc, event_date_confidence asc;
        """
        with self.connection.cursor() as cursor:
            cursor.execute(sql)
            rows = cursor.fetchall()
        return [
            {
                "event_date_confidence": row[0],
                "event_count": row[1],
            }
            for row in rows
        ]

    def get_warning_frequency(self, limit: int = 10) -> list[dict[str, Any]]:
        sql = """
        select
            warning_text,
            count(*) as warning_count
        from (
            select jsonb_array_elements_text(warnings) as warning_text
            from historical_trial_events
            where jsonb_array_length(warnings) > 0
        ) expanded
        group by warning_text
        order by warning_count desc, warning_text asc
        limit %s;
        """
        with self.connection.cursor() as cursor:
            cursor.execute(sql, (max(1, limit),))
            rows = cursor.fetchall()
        return [
            {
                "warning": row[0],
                "warning_count": row[1],
            }
            for row in rows
        ]

    def get_recent_issues(self, limit: int = 25) -> list[dict[str, Any]]:
        sql = """
        select
            event_id,
            nct_id,
            sponsor_name,
            mapped_ticker,
            event_date_candidate,
            is_model_ready,
            warning_count,
            mapping_confidence,
            data_completeness_ratio,
            event_day_return,
            created_at
        from historical_trial_events
        where
            not is_model_ready
            or warning_count > 0
            or mapped_ticker is null
            or event_date_candidate is null
            or event_day_return is null
        order by created_at desc
        limit %s;
        """
        with self.connection.cursor() as cursor:
            cursor.execute(sql, (max(1, limit),))
            rows = cursor.fetchall()
        return [
            {
                "event_id": row[0],
                "nct_id": row[1],
                "sponsor_name": row[2],
                "mapped_ticker": row[3],
                "event_date_candidate": row[4],
                "is_model_ready": row[5],
                "warning_count": row[6],
                "mapping_confidence": row[7],
                "data_completeness_ratio": row[8],
                "event_day_return": row[9],
                "created_at": str(row[10]),
            }
            for row in rows
        ]


class SponsorMappingReviewRepository:
    def __init__(self, connection: Any) -> None:
        self.connection = connection

    def create_tables(self) -> None:
        with self.connection.cursor() as cursor:
            cursor.execute(SPONSOR_MAPPING_REVIEWS_TABLE_SQL)
            for statement in SPONSOR_MAPPING_REVIEWS_MIGRATION_SQL:
                cursor.execute(statement)
            for statement in SPONSOR_MAPPING_REVIEWS_INDEX_SQL:
                cursor.execute(statement)

    def _serialize_review_value(self, column: str, value: Any) -> Any:
        if column in SPONSOR_MAPPING_REVIEW_JSON_FIELDS:
            return json.dumps(value if value is not None else [])
        return value

    def _deserialize_review_row(self, row: tuple[Any, ...]) -> dict[str, Any]:
        return {
            "review_id": row[0],
            "sponsor_name": row[1],
            "normalized_sponsor_name": row[2],
            "source_nct_id": row[3],
            "suggested_company_name": row[4],
            "suggested_ticker": row[5],
            "suggested_cik": row[6],
            "suggested_confidence": row[7],
            "suggested_match_type": row[8],
            "alternatives": [] if row[9] is None else row[9],
            "review_status": row[10],
            "reviewed_mapping_status": row[11],
            "reviewed_company_name": row[12],
            "reviewed_ticker": row[13],
            "reviewed_cik": row[14],
            "reviewer_name": row[15],
            "reviewer_email": row[16],
            "review_notes": row[17],
            "reviewed_at": None if row[18] is None else str(row[18]),
            "created_at": None if row[19] is None else str(row[19]),
            "updated_at": None if row[20] is None else str(row[20]),
        }

    def upsert_review(self, review_record: dict[str, Any]) -> int:
        normalized_sponsor_name = (review_record.get("normalized_sponsor_name") or "").strip()
        sponsor_name = (review_record.get("sponsor_name") or "").strip()
        if not sponsor_name:
            raise ValueError("sponsor_name is required for sponsor mapping reviews.")
        if not normalized_sponsor_name:
            raise ValueError("normalized_sponsor_name is required for sponsor mapping reviews.")

        placeholders = ", ".join(["%s"] * len(SPONSOR_MAPPING_REVIEW_COLUMNS))
        insert_columns = ", ".join(SPONSOR_MAPPING_REVIEW_COLUMNS)
        update_assignments = ", ".join(
            f"{column} = excluded.{column}"
            for column in SPONSOR_MAPPING_REVIEW_COLUMNS
            if column != "normalized_sponsor_name"
        )
        values = [
            self._serialize_review_value(column, review_record.get(column))
            for column in SPONSOR_MAPPING_REVIEW_COLUMNS
        ]

        sql = f"""
        insert into sponsor_mapping_reviews ({insert_columns})
        values ({placeholders})
        on conflict (normalized_sponsor_name) do update
        set {update_assignments},
            updated_at = now()
        returning review_id;
        """
        with self.connection.cursor() as cursor:
            cursor.execute(sql, values)
            row = cursor.fetchone()
        return int(row[0])

    def get_review_by_normalized_name(self, normalized_sponsor_name: str) -> dict[str, Any] | None:
        sql = """
        select
            review_id,
            sponsor_name,
            normalized_sponsor_name,
            source_nct_id,
            suggested_company_name,
            suggested_ticker,
            suggested_cik,
            suggested_confidence,
            suggested_match_type,
            alternatives,
            review_status,
            reviewed_mapping_status,
            reviewed_company_name,
            reviewed_ticker,
            reviewed_cik,
            reviewer_name,
            reviewer_email,
            review_notes,
            reviewed_at,
            created_at,
            updated_at
        from sponsor_mapping_reviews
        where normalized_sponsor_name = %s;
        """
        with self.connection.cursor() as cursor:
            cursor.execute(sql, (normalized_sponsor_name.strip(),))
            row = cursor.fetchone()
        if row is None:
            return None
        return self._deserialize_review_row(row)

    def list_reviews(
        self,
        limit: int = 100,
        offset: int = 0,
        review_status: str | None = None,
        suggested_ticker: str | None = None,
        reviewer_email: str | None = None,
    ) -> list[dict[str, Any]]:
        clauses = []
        params: list[Any] = []

        if review_status:
            clauses.append("review_status = %s")
            params.append(review_status)
        if suggested_ticker:
            clauses.append("suggested_ticker = %s")
            params.append(suggested_ticker.strip().upper())
        if reviewer_email:
            clauses.append("reviewer_email = %s")
            params.append(reviewer_email.strip())

        where_clause = ""
        if clauses:
            where_clause = "where " + " and ".join(clauses)

        sql = f"""
        select
            review_id,
            sponsor_name,
            normalized_sponsor_name,
            source_nct_id,
            suggested_company_name,
            suggested_ticker,
            suggested_cik,
            suggested_confidence,
            suggested_match_type,
            alternatives,
            review_status,
            reviewed_mapping_status,
            reviewed_company_name,
            reviewed_ticker,
            reviewed_cik,
            reviewer_name,
            reviewer_email,
            review_notes,
            reviewed_at,
            created_at,
            updated_at
        from sponsor_mapping_reviews
        {where_clause}
        order by updated_at desc, review_id desc
        limit %s
        offset %s;
        """
        params.extend([max(1, limit), max(0, offset)])
        with self.connection.cursor() as cursor:
            cursor.execute(sql, tuple(params))
            rows = cursor.fetchall()
        return [self._deserialize_review_row(row) for row in rows]


def initialize_database() -> None:
    with get_connection() as connection:
        trial_repository = ClinicalTrialsRepository(connection)
        analysis_repository = TrialAnalysisRepository(connection)
        historical_repository = HistoricalTrialEventRepository(connection)
        sponsor_mapping_review_repository = SponsorMappingReviewRepository(connection)
        trial_repository.create_tables()
        analysis_repository.create_tables()
        historical_repository.create_tables()
        sponsor_mapping_review_repository.create_tables()
