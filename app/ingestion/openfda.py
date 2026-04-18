import argparse
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests


OPENFDA_BASE_URL = "https://api.fda.gov"


@dataclass(slots=True)
class OpenFDAQuery:
    search: str | None = None
    sponsor_name: str | None = None
    product_type: str | None = None
    application_number: str | None = None
    limit: int = 25
    skip: int = 0


class OpenFDAIngestor:
    def __init__(
        self,
        use_env_proxy: bool = False,
        timeout: int = 30,
        user_agent: str = "BTQ OpenFDA Ingestor/1.0",
        max_retries: int = 3,
        retry_backoff_seconds: float = 1.25,
    ) -> None:
        self.base_url = OPENFDA_BASE_URL
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

    def _get_json(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                response = self.session.get(url, params=params, timeout=self.timeout)
                if response.status_code in {429, 500, 502, 503, 504} and attempt < self.max_retries:
                    time.sleep(self.retry_backoff_seconds * attempt)
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
        raise RuntimeError(f"OpenFDA request failed after {self.max_retries} attempts: {last_error}") from last_error

    def _build_search_expression(self, query: OpenFDAQuery) -> str | None:
        parts: list[str] = []
        if query.search:
            parts.append(query.search)
        if query.sponsor_name:
            sponsor = query.sponsor_name.replace('"', '\\"')
            parts.append(f'openfda.manufacturer_name:"{sponsor}"')
        if query.product_type:
            product_type = query.product_type.replace('"', '\\"')
            parts.append(f'products.dosage_form:"{product_type}"')
        if query.application_number:
            application_number = query.application_number.replace('"', '\\"')
            parts.append(f'openfda.application_number:"{application_number}"')
        if not parts:
            return None
        return "+AND+".join(parts)

    def search_drug_labels(self, query: OpenFDAQuery) -> dict[str, Any]:
        params = {
            "limit": max(1, min(query.limit, 100)),
            "skip": max(0, query.skip),
        }
        search_expression = self._build_search_expression(query)
        if search_expression:
            params["search"] = search_expression
        return self._get_json("/drug/label.json", params=params)

    def search_drug_approvals(self, query: OpenFDAQuery) -> dict[str, Any]:
        params = {
            "limit": max(1, min(query.limit, 100)),
            "skip": max(0, query.skip),
        }
        search_expression = self._build_search_expression(query)
        if search_expression:
            params["search"] = search_expression
        return self._get_json("/drug/drugsfda.json", params=params)

    def count_approvals_by_field(self, search: str, count_field: str) -> dict[str, Any]:
        params = {"search": search, "count": count_field}
        return self._get_json("/drug/drugsfda.json", params=params)

    def normalize_approval_records(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for item in payload.get("results", []):
            openfda = item.get("openfda", {})
            products = item.get("products", []) or []
            submissions = item.get("submissions", []) or []
            first_product = products[0] if products else {}
            first_submission = submissions[0] if submissions else {}
            rows.append(
                {
                    "application_number": item.get("application_number"),
                    "sponsor_name": item.get("sponsor_name") or (openfda.get("manufacturer_name") or [None])[0],
                    "brand_name": first_product.get("brand_name"),
                    "generic_name": first_product.get("generic_name"),
                    "product_type": first_product.get("dosage_form"),
                    "marketing_status": first_product.get("marketing_status"),
                    "submission_status": first_submission.get("submission_status"),
                    "submission_type": first_submission.get("submission_type"),
                    "submission_number": first_submission.get("submission_number"),
                    "submission_status_date": first_submission.get("submission_status_date"),
                    "raw_record": item,
                }
            )
        return rows

    def fetch_approval_snapshot(
        self,
        sponsor_name: str | None = None,
        search: str | None = None,
        limit: int = 25,
    ) -> list[dict[str, Any]]:
        payload = self.search_drug_approvals(
            OpenFDAQuery(
                search=search,
                sponsor_name=sponsor_name,
                limit=limit,
            )
        )
        return self.normalize_approval_records(payload)

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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Query OpenFDA drug approval and label datasets")
    parser.add_argument("mode", choices=["approvals", "labels"])
    parser.add_argument("--search")
    parser.add_argument("--sponsor")
    parser.add_argument("--application-number")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--skip", type=int, default=0)
    parser.add_argument("--out")
    parser.add_argument("--out-format", choices=["json", "jsonl"], default="json")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    ingestor = OpenFDAIngestor()
    query = OpenFDAQuery(
        search=args.search,
        sponsor_name=args.sponsor,
        application_number=args.application_number,
        limit=args.limit,
        skip=args.skip,
    )
    if args.mode == "approvals":
        payload = ingestor.search_drug_approvals(query)
        records = ingestor.normalize_approval_records(payload)
    else:
        payload = ingestor.search_drug_labels(query)
        records = payload.get("results", [])

    if args.out:
        ingestor.export_records(records, args.out, format=args.out_format)

    print(
        json.dumps(
            {
                "count": len(records),
                "records": records[: min(len(records), args.limit)],
            },
            indent=2,
            ensure_ascii=True,
        )
    )


if __name__ == "__main__":
    main()
