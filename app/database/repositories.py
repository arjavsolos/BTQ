import json
from typing import Any

from app.database.connection import get_connection
from app.database.schemas import (
    CLINICAL_TRIALS_INDEX_SQL,
    CLINICAL_TRIALS_TABLE_SQL,
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


def initialize_database() -> None:
    with get_connection() as connection:
        trial_repository = ClinicalTrialsRepository(connection)
        analysis_repository = TrialAnalysisRepository(connection)
        trial_repository.create_tables()
        analysis_repository.create_tables()
