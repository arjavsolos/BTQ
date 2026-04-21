import argparse
import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

API_BASE_URL = "https://clinicaltrials.gov/api/v2/studies"
SOURCE_SYSTEM = "clinicaltrials.gov"
SOURCE_API_VERSION = "v2"

PHASE_ORDER = {
    "EARLY_PHASE1": 0,
    "PHASE1": 1,
    "PHASE2": 2,
    "PHASE3": 3,
    "PHASE4": 4,
}

KEYWORD_BUCKETS = {
    "oncology_signals": [
        "overall survival",
        "progression-free survival",
        "objective response rate",
        "tumor response",
        "recist",
    ],
    "regulatory_signals": [
        "primary endpoint",
        "statistically significant",
        "superiority",
        "non-inferiority",
        "approval",
    ],
    "safety_signals": [
        "adverse event",
        "serious adverse event",
        "dose limiting toxicity",
        "safety",
        "tolerability",
    ],
    "biomarker_signals": [
        "biomarker",
        "pd-l1",
        "egfr",
        "her2",
        "alk",
        "brca",
        "mutation",
        "expression",
    ],
}


@dataclass(slots=True)
class TrialQuery:
    query_term: str | None = None
    filter_overall_status: str | None = None
    filter_phase: str | None = None
    filter_study_type: str | None = None
    sponsor_name: str | None = None
    condition: str | None = None
    intervention_name: str | None = None
    intervention_type: str | None = None
    country: str | None = None
    has_results: bool | None = None
    page_size: int = 100
    max_pages: int | None = 1


class ClinicalTrialsIngestor:
    """
    ClinicalTrials.gov-focused ingestor for biotech event modeling.
    """

    def __init__(
        self,
        use_env_proxy: bool = False,
        timeout: int = 30,
        user_agent: str = "BTQ ClinicalTrials Ingestor/1.0",
        max_retries: int = 3,
        retry_backoff_seconds: float = 1.25,
    ) -> None:
        self.base_url = API_BASE_URL
        self.timeout = timeout
        self.max_retries = max(1, max_retries)
        self.retry_backoff_seconds = max(0.0, retry_backoff_seconds)
        self.session = requests.Session()
        self.session.trust_env = use_env_proxy
        self.session.headers.update(
            {
                "Accept": "application/json",
                "User-Agent": user_agent,
            }
        )

    def _get_json(self, url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                response = self.session.get(url, params=params, timeout=self.timeout)
                if response.status_code in {429, 500, 502, 503, 504} and attempt < self.max_retries:
                    retry_after = response.headers.get("Retry-After")
                    sleep_seconds = (
                        float(retry_after)
                        if retry_after and retry_after.isdigit()
                        else self.retry_backoff_seconds * attempt
                    )
                    time.sleep(sleep_seconds)
                    continue
                response.raise_for_status()
                return response.json()
            except requests.HTTPError as exc:
                status_code = exc.response.status_code if exc.response is not None else None
                if status_code not in {429, 500, 502, 503, 504}:
                    raise
                last_error = exc
                if attempt >= self.max_retries:
                    break
                time.sleep(self.retry_backoff_seconds * attempt)
            except (ValueError, requests.RequestException) as exc:
                last_error = exc
                if attempt >= self.max_retries:
                    break
                time.sleep(self.retry_backoff_seconds * attempt)
        raise RuntimeError(
            f"ClinicalTrials.gov request failed after {self.max_retries} attempts: {last_error}"
        ) from last_error

    def _coerce_int(self, value: Any) -> int | None:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _normalize_text(self, value: str | None) -> str:
        return re.sub(r"\s+", " ", (value or "").strip()).lower()

    def _normalize_list(self, values: list[Any] | None) -> list[Any]:
        return values or []

    def _collect_keywords(self, *parts: Any) -> dict[str, list[str]]:
        corpus = " ".join(str(part) for part in parts if part)
        normalized = self._normalize_text(corpus)
        hits: dict[str, list[str]] = {}
        for bucket, keywords in KEYWORD_BUCKETS.items():
            matched = [keyword for keyword in keywords if keyword in normalized]
            if matched:
                hits[bucket] = matched
        return hits

    def _phase_score(self, phases: list[str]) -> int | None:
        if not phases:
            return None
        values = [PHASE_ORDER[p] for p in phases if p in PHASE_ORDER]
        return max(values) if values else None

    def _infer_date_precision(self, value: str | None) -> str | None:
        if not value:
            return None
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            return "day"
        if re.fullmatch(r"\d{4}-\d{2}", value):
            return "month"
        if re.fullmatch(r"\d{4}", value):
            return "year"
        return "unknown"

    def _choose_event_date(
        self,
        status_module: dict[str, Any],
    ) -> tuple[str | None, str | None]:
        def precision_rank(value: str | None) -> int:
            precision = self._infer_date_precision(value)
            return {"day": 3, "month": 2, "year": 1}.get(precision or "", 0)

        candidates = [
            ("primary_completion_date", (status_module.get("primaryCompletionDateStruct") or {}).get("date")),
            ("completion_date", (status_module.get("completionDateStruct") or {}).get("date")),
            ("results_first_posted", (status_module.get("resultsFirstPostDateStruct") or {}).get("date")),
            ("last_update_posted", (status_module.get("lastUpdatePostDateStruct") or {}).get("date")),
        ]
        best_candidate: tuple[str | None, str | None] = (None, None)
        best_rank = -1
        for source, value in candidates:
            if not value:
                continue
            current_rank = precision_rank(value)
            if current_rank > best_rank:
                best_candidate = (value, source)
                best_rank = current_rank
            if current_rank == 3 and source in {"primary_completion_date", "completion_date"}:
                return value, source
        return best_candidate

    def _compute_completeness_flags(self, record: dict[str, Any]) -> dict[str, Any]:
        flags = {
            "has_sponsor": bool(record.get("sponsor_name")),
            "has_primary_outcomes": bool(record.get("primary_outcomes")),
            "has_secondary_outcomes": bool(record.get("secondary_outcomes")),
            "has_locations": bool(record.get("locations")),
            "has_interventions": bool(record.get("interventions")),
            "has_reference_support": bool(record.get("references")),
            "has_eligibility": bool(record.get("eligibility_criteria")),
            "has_event_date": bool(record.get("event_date_candidate")),
            "has_results_flag": bool(record.get("has_results")),
        }
        total_flags = len(flags)
        score = sum(1 for value in flags.values() if value)
        flags["data_completeness_score"] = score
        flags["data_completeness_ratio"] = round(score / max(total_flags, 1), 3)
        return flags

    def _post_filter_record(self, record: dict[str, Any], query: TrialQuery) -> bool:
        if query.sponsor_name and self._normalize_text(
            query.sponsor_name
        ) not in self._normalize_text(record.get("sponsor_name")):
            return False
        if query.condition:
            normalized_condition = self._normalize_text(query.condition)
            haystack = " ".join(record.get("conditions") or [])
            if normalized_condition not in self._normalize_text(haystack):
                return False
        if query.intervention_name:
            normalized_intervention = self._normalize_text(query.intervention_name)
            haystack = " ".join(record.get("intervention_names") or [])
            if normalized_intervention not in self._normalize_text(haystack):
                return False
        if query.intervention_type:
            normalized_type = self._normalize_text(query.intervention_type)
            types = [self._normalize_text(item) for item in (record.get("intervention_types") or [])]
            if normalized_type not in types:
                return False
        if query.country:
            normalized_country = self._normalize_text(query.country)
            countries = [
                self._normalize_text(item.get("country"))
                for item in (record.get("locations") or [])
                if item.get("country")
            ]
            if normalized_country not in countries:
                return False
        if query.has_results is not None and bool(record.get("has_results")) != query.has_results:
            return False
        return True

    def _dedupe_records(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        deduped: dict[str, dict[str, Any]] = {}
        for record in records:
            key = record.get("nct_id") or record.get("requested_nct_id")
            if not key:
                continue
            current = deduped.get(key)
            if current is None:
                deduped[key] = record
                continue
            if (record.get("data_completeness_score") or 0) >= (current.get("data_completeness_score") or 0):
                deduped[key] = record
        return list(deduped.values())

    def _extract_locations(self, contacts_locations: dict[str, Any]) -> list[dict[str, Any]]:
        locations = []
        for item in contacts_locations.get("locations", []):
            locations.append(
                {
                    "facility": item.get("facility"),
                    "city": item.get("city"),
                    "state": item.get("state"),
                    "country": item.get("country"),
                    "status": item.get("status"),
                }
            )
        return locations

    def _country_counts(self, locations: list[dict[str, Any]]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for item in locations:
            country = item.get("country")
            if not country:
                continue
            counts[country] = counts.get(country, 0) + 1
        return counts

    def _extract_interventions(self, interventions_module: dict[str, Any]) -> list[dict[str, Any]]:
        rows = []
        for item in interventions_module.get("interventions", []):
            rows.append(
                {
                    "type": item.get("type"),
                    "name": item.get("name"),
                    "description": item.get("description"),
                    "other_names": item.get("otherNames", []),
                }
            )
        return rows

    def _extract_outcomes(self, outcomes_module: dict[str, Any], key: str) -> list[dict[str, Any]]:
        rows = []
        for item in outcomes_module.get(key, []):
            rows.append(
                {
                    "measure": item.get("measure"),
                    "description": item.get("description"),
                    "time_frame": item.get("timeFrame"),
                }
            )
        return rows

    def _extract_references(self, references_module: dict[str, Any]) -> list[dict[str, Any]]:
        rows = []
        for item in references_module.get("references", []):
            rows.append(
                {
                    "pmid": item.get("pmid"),
                    "type": item.get("type"),
                    "citation": item.get("citation"),
                }
            )
        return rows

    def extract_trial_record(
        self,
        study: dict[str, Any],
        requested_nct_id: str | None = None,
        include_raw: bool = False,
    ) -> dict[str, Any]:
        protocol = study.get("protocolSection", {})
        derived = study.get("derivedSection", {})
        has_results = study.get("hasResults", False)

        identification = protocol.get("identificationModule", {})
        status = protocol.get("statusModule", {})
        sponsor = protocol.get("sponsorCollaboratorsModule", {})
        conditions = protocol.get("conditionsModule", {})
        design = protocol.get("designModule", {})
        arms = protocol.get("armsInterventionsModule", {})
        outcomes = protocol.get("outcomesModule", {})
        eligibility = protocol.get("eligibilityModule", {})
        contacts_locations = protocol.get("contactsLocationsModule", {})
        references = protocol.get("referencesModule", {})
        description = protocol.get("descriptionModule", {})
        oversight = protocol.get("oversightModule", {})

        lead_sponsor = sponsor.get("leadSponsor", {})
        organization = identification.get("organization", {})
        enrollment_info = design.get("enrollmentInfo", {})
        phases = design.get("phases", [])

        intervention_rows = self._extract_interventions(arms)
        primary_outcomes = self._extract_outcomes(outcomes, "primaryOutcomes")
        secondary_outcomes = self._extract_outcomes(outcomes, "secondaryOutcomes")
        other_outcomes = self._extract_outcomes(outcomes, "otherOutcomes")
        location_rows = self._extract_locations(contacts_locations)
        country_counts = self._country_counts(location_rows)
        reference_rows = self._extract_references(references)
        event_date_candidate, event_date_source = self._choose_event_date(status)

        conditions_list = conditions.get("conditions", [])
        keyword_hits = self._collect_keywords(
            description.get("briefSummary"),
            description.get("detailedDescription"),
            " ".join(item.get("measure", "") for item in primary_outcomes),
            " ".join(item.get("measure", "") for item in secondary_outcomes),
            " ".join(item.get("name", "") for item in intervention_rows),
            " ".join(conditions_list),
        )

        record = {
            "requested_nct_id": requested_nct_id or identification.get("nctId"),
            "nct_id": identification.get("nctId"),
            "nct_aliases": identification.get("nctIdAliases", []),
            "org_study_id": (identification.get("orgStudyIdInfo") or {}).get("id"),
            "secondary_ids": identification.get("secondaryIdInfos", []),
            "brief_title": identification.get("briefTitle"),
            "official_title": identification.get("officialTitle"),
            "acronym": identification.get("acronym"),
            "sponsor_name": lead_sponsor.get("name") or organization.get("fullName"),
            "sponsor_class": lead_sponsor.get("class") or organization.get("class"),
            "collaborators": sponsor.get("collaborators", []),
            "responsible_party": sponsor.get("responsibleParty", {}),
            "overall_status": status.get("overallStatus"),
            "why_stopped": status.get("whyStopped"),
            "status_verified_date": status.get("statusVerifiedDate"),
            "has_results": has_results,
            "expanded_access": (status.get("expandedAccessInfo") or {}).get("hasExpandedAccess"),
            "study_type": design.get("studyType"),
            "phases": phases,
            "phase_label": ", ".join(phases) if phases else None,
            "phase_score": self._phase_score(phases),
            "allocation": (design.get("designInfo") or {}).get("allocation"),
            "intervention_model": (design.get("designInfo") or {}).get("interventionModel"),
            "primary_purpose": (design.get("designInfo") or {}).get("primaryPurpose"),
            "masking": ((design.get("designInfo") or {}).get("maskingInfo") or {}).get("masking"),
            "enrollment_count": self._coerce_int(enrollment_info.get("count")),
            "enrollment_type": enrollment_info.get("type"),
            "conditions": conditions_list,
            "condition_keywords": conditions.get("keywords", []),
            "therapeutic_area": conditions_list[0] if conditions_list else None,
            "interventions": intervention_rows,
            "intervention_names": [item.get("name") for item in intervention_rows if item.get("name")],
            "intervention_types": [item.get("type") for item in intervention_rows if item.get("type")],
            "arm_groups": arms.get("armGroups", []),
            "primary_outcomes": primary_outcomes,
            "secondary_outcomes": secondary_outcomes,
            "other_outcomes": other_outcomes,
            "primary_endpoint_measures": [item.get("measure") for item in primary_outcomes if item.get("measure")],
            "secondary_endpoint_measures": [item.get("measure") for item in secondary_outcomes if item.get("measure")],
            "brief_summary": description.get("briefSummary"),
            "detailed_description": description.get("detailedDescription"),
            "eligibility_criteria": eligibility.get("eligibilityCriteria"),
            "healthy_volunteers": eligibility.get("healthyVolunteers"),
            "sex": eligibility.get("sex"),
            "minimum_age": eligibility.get("minimumAge"),
            "maximum_age": eligibility.get("maximumAge"),
            "std_ages": eligibility.get("stdAges", []),
            "fda_regulated_drug": oversight.get("isFdaRegulatedDrug"),
            "fda_regulated_device": oversight.get("isFdaRegulatedDevice"),
            "has_dmc": oversight.get("oversightHasDmc"),
            "start_date": (status.get("startDateStruct") or {}).get("date"),
            "primary_completion_date": (status.get("primaryCompletionDateStruct") or {}).get("date"),
            "completion_date": (status.get("completionDateStruct") or {}).get("date"),
            "study_first_posted": (status.get("studyFirstPostDateStruct") or {}).get("date"),
            "results_first_posted": (status.get("resultsFirstPostDateStruct") or {}).get("date"),
            "last_update_posted": (status.get("lastUpdatePostDateStruct") or {}).get("date"),
            "event_date_candidate": event_date_candidate,
            "event_date_source": event_date_source,
            "event_date_precision": self._infer_date_precision(event_date_candidate),
            "locations": location_rows,
            "location_count": len(location_rows),
            "country_counts": country_counts,
            "us_site_count": country_counts.get("United States", 0),
            "references": reference_rows,
            "reference_count": len(reference_rows),
            "see_also_links": references.get("seeAlsoLinks", []),
            "keyword_hits": keyword_hits,
            "derived_misc_info": derived.get("miscInfoModule", {}),
            "central_contacts": contacts_locations.get("centralContacts", []),
            "overall_officials": contacts_locations.get("overallOfficials", []),
            "ipd_sharing": (protocol.get("ipdSharingStatementModule") or {}).get("ipdSharing"),
            "source_system": SOURCE_SYSTEM,
            "source_api_version": SOURCE_API_VERSION,
        }

        record.update(self._compute_completeness_flags(record))

        if include_raw:
            record["raw_study"] = study

        return record

    def fetch_trial_data(
        self,
        nct_id: str,
        include_raw: bool = False,
    ) -> dict[str, Any]:
        url = f"{self.base_url}/{nct_id}"
        try:
            payload = self._get_json(url)
        except requests.HTTPError as exc:
            status_code = exc.response.status_code if exc.response is not None else "unknown"
            if status_code == 404:
                raise ValueError(f"Study '{nct_id}' was not found on ClinicalTrials.gov.") from exc
            raise RuntimeError(f"ClinicalTrials.gov request failed with status {status_code}.") from exc
        except requests.RequestException as exc:
            raise RuntimeError(f"ClinicalTrials.gov request failed: {exc}") from exc

        return self.extract_trial_record(payload, requested_nct_id=nct_id, include_raw=include_raw)

    def build_search_params(self, query: TrialQuery) -> dict[str, Any]:
        params: dict[str, Any] = {"pageSize": max(1, min(query.page_size, 1000))}
        if query.query_term:
            params["query.term"] = query.query_term
        if query.condition:
            params["query.cond"] = query.condition
        if query.intervention_name:
            params["query.intr"] = query.intervention_name
        if query.country:
            params["query.locn"] = query.country
        if query.sponsor_name:
            params["query.term"] = " ".join(
                item for item in [params.get("query.term"), query.sponsor_name] if item
            )
        if query.filter_overall_status:
            params["filter.overallStatus"] = query.filter_overall_status
        advanced_filters: list[str] = []
        if query.filter_phase:
            advanced_filters.append(f"AREA[Phase]{query.filter_phase}")
        if query.filter_study_type:
            advanced_filters.append(f"AREA[StudyType]{query.filter_study_type}")
        if advanced_filters:
            params["filter.advanced"] = " AND ".join(advanced_filters)
        return params

    def search_trials(
        self,
        query: TrialQuery,
        output_path: str | None = None,
        include_raw: bool = False,
    ) -> list[dict[str, Any]]:
        params = self.build_search_params(query)
        records: list[dict[str, Any]] = []
        page_token: str | None = None
        page_count = 0

        try:
            while True:
                request_params = dict(params)
                if page_token:
                    request_params["pageToken"] = page_token

                payload = self._get_json(self.base_url, params=request_params)
                for study in payload.get("studies", []):
                    record = self.extract_trial_record(study, include_raw=include_raw)
                    if not self._post_filter_record(record, query):
                        continue
                    records.append(record)

                page_count += 1
                page_token = payload.get("nextPageToken")
                if not page_token:
                    break
                if query.max_pages is not None and page_count >= query.max_pages:
                    break
        except requests.RequestException as exc:
            raise RuntimeError(f"ClinicalTrials.gov pagination failed: {exc}") from exc
        deduped_records = self._dedupe_records(records)
        if output_path:
            self.export_records(deduped_records, output_path)
        return deduped_records

    def fetch_multiple_trials(
        self,
        nct_ids: list[str],
        include_raw: bool = False,
    ) -> list[dict[str, Any]]:
        results = []
        for nct_id in nct_ids:
            try:
                results.append(self.fetch_trial_data(nct_id, include_raw=include_raw))
            except Exception as exc:
                results.append({"requested_nct_id": nct_id, "error": str(exc)})
        return results

    def summarize_record(self, record: dict[str, Any]) -> dict[str, Any]:
        return {
            "nct_id": record.get("nct_id"),
            "brief_title": record.get("brief_title"),
            "sponsor_name": record.get("sponsor_name"),
            "overall_status": record.get("overall_status"),
            "phase_label": record.get("phase_label"),
            "therapeutic_area": record.get("therapeutic_area"),
            "enrollment_count": record.get("enrollment_count"),
            "event_date_candidate": record.get("event_date_candidate"),
            "event_date_source": record.get("event_date_source"),
            "has_results": record.get("has_results"),
            "data_completeness_score": record.get("data_completeness_score"),
        }

    def export_records(
        self,
        records: list[dict[str, Any]],
        output_path: str,
        format: str = "jsonl",
    ) -> None:
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        format = format.lower()
        if format not in {"json", "jsonl"}:
            raise ValueError("format must be 'json' or 'jsonl'")
        if format == "json":
            output_file.write_text(json.dumps(records, indent=2, ensure_ascii=True), encoding="utf-8")
            return
        with output_file.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(json.dumps(record, ensure_ascii=True) + "\n")


BiologicalDataIngestor = ClinicalTrialsIngestor


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ClinicalTrials.gov ingestor")
    subparsers = parser.add_subparsers(dest="command")

    trial_parser = subparsers.add_parser("trial", help="Fetch a single study")
    trial_parser.add_argument("nct_id")
    trial_parser.add_argument("--raw", action="store_true")

    search_parser = subparsers.add_parser("search", help="Search and paginate studies")
    search_parser.add_argument("--query")
    search_parser.add_argument("--status")
    search_parser.add_argument("--phase")
    search_parser.add_argument("--study-type")
    search_parser.add_argument("--sponsor")
    search_parser.add_argument("--condition")
    search_parser.add_argument("--intervention")
    search_parser.add_argument("--intervention-type")
    search_parser.add_argument("--country")
    search_parser.add_argument("--has-results", action="store_true")
    search_parser.add_argument("--without-results", action="store_true")
    search_parser.add_argument("--page-size", type=int, default=25)
    search_parser.add_argument("--pages", type=int, default=1)
    search_parser.add_argument("--out")
    search_parser.add_argument("--out-format", default="jsonl")
    search_parser.add_argument("--raw", action="store_true")

    return parser


def main() -> None:
    parser = build_argument_parser()
    args = parser.parse_args()
    ingestor = ClinicalTrialsIngestor()

    if args.command == "trial":
        result = ingestor.fetch_trial_data(args.nct_id, include_raw=args.raw)
        print(json.dumps(result, indent=2, ensure_ascii=True))
        return

    if args.command == "search":
        has_results = None
        if args.has_results and args.without_results:
            raise ValueError("Choose only one of --has-results or --without-results")
        if args.has_results:
            has_results = True
        elif args.without_results:
            has_results = False
        result = ingestor.search_trials(
            TrialQuery(
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
            ),
            output_path=args.out,
            include_raw=args.raw,
        )
        if args.out and args.out_format != "jsonl":
            ingestor.export_records(result, args.out, format=args.out_format)
        print(json.dumps(result, indent=2, ensure_ascii=True))
        return

    result = ingestor.fetch_trial_data("NCT00276653")
    print(json.dumps(result, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
