import argparse
import json
import os
import re
import time
from dataclasses import asdict, dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import requests


SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
DEFAULT_CACHE_PATH = Path("data/raw/sec/company_tickers.json")
CORPORATE_SUFFIXES = {
    "inc",
    "incorporated",
    "corp",
    "corporation",
    "co",
    "company",
    "ltd",
    "limited",
    "llc",
    "plc",
    "sa",
    "nv",
    "ag",
    "holdings",
    "holding",
    "group",
    "therapeutics",
    "biopharma",
    "biosciences",
}


@dataclass(slots=True)
class SponsorMatchResult:
    sponsor_name: str
    matched_company_name: str | None
    ticker: str | None
    cik: str | None
    confidence: float
    match_type: str
    alternatives: list[dict[str, Any]]


class SecCompanyMapper:
    def __init__(
        self,
        cache_path: str | Path = DEFAULT_CACHE_PATH,
        cache_ttl_hours: int = 24,
        use_env_proxy: bool = False,
        timeout: int = 30,
        user_agent: str | None = None,
    ) -> None:
        self.cache_path = Path(cache_path)
        self.cache_ttl_hours = max(1, cache_ttl_hours)
        self.timeout = timeout
        contact_name = os.getenv("SEC_CONTACT_NAME", "BTQ Research")
        contact_email = os.getenv("SEC_CONTACT_EMAIL", "local@example.com")
        resolved_user_agent = user_agent or f"{contact_name} {contact_email}"
        self.session = requests.Session()
        self.session.trust_env = use_env_proxy
        self.session.headers.update(
            {
                "Accept": "application/json",
                "Accept-Encoding": "gzip, deflate",
                "Host": "www.sec.gov",
                "User-Agent": resolved_user_agent,
                "From": contact_email,
            }
        )
        self._registry: list[dict[str, Any]] | None = None

    def _normalize_company_name(self, value: str | None) -> str:
        if not value:
            return ""
        normalized = re.sub(r"[^a-zA-Z0-9\s]", " ", value).lower()
        parts = [part for part in normalized.split() if part]
        filtered = [part for part in parts if part not in CORPORATE_SUFFIXES]
        return " ".join(filtered)

    def _cache_is_fresh(self) -> bool:
        if not self.cache_path.exists():
            return False
        age_seconds = time.time() - self.cache_path.stat().st_mtime
        return age_seconds <= self.cache_ttl_hours * 3600

    def _normalize_registry_payload(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for item in payload.values():
            title = item.get("title")
            ticker = item.get("ticker")
            cik = str(item.get("cik_str")).zfill(10) if item.get("cik_str") is not None else None
            if not title or not ticker:
                continue
            rows.append(
                {
                    "company_name": title,
                    "normalized_company_name": self._normalize_company_name(title),
                    "ticker": ticker,
                    "cik": cik,
                }
            )
        return rows

    def refresh_registry(self, force: bool = False) -> list[dict[str, Any]]:
        if not force and self._registry is not None:
            return self._registry
        if not force and self._cache_is_fresh():
            self._registry = json.loads(self.cache_path.read_text(encoding="utf-8"))
            return self._registry

        try:
            response = self.session.get(SEC_TICKERS_URL, timeout=self.timeout)
            response.raise_for_status()
            registry = self._normalize_registry_payload(response.json())
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            self.cache_path.write_text(json.dumps(registry, indent=2, ensure_ascii=True), encoding="utf-8")
            self._registry = registry
            return registry
        except requests.RequestException as exc:
            if self.cache_path.exists():
                self._registry = json.loads(self.cache_path.read_text(encoding="utf-8"))
                return self._registry
            raise RuntimeError(
                "SEC registry download failed. Set SEC_CONTACT_EMAIL/SEC_CONTACT_NAME "
                "for a compliant User-Agent or provide a cached registry file."
            ) from exc

    def load_registry(self) -> list[dict[str, Any]]:
        if self._registry is not None:
            return self._registry
        if self.cache_path.exists():
            self._registry = json.loads(self.cache_path.read_text(encoding="utf-8"))
            return self._registry
        return self.refresh_registry()

    def lookup_by_ticker(self, ticker: str) -> dict[str, Any] | None:
        normalized_ticker = (ticker or "").strip().upper()
        for item in self.load_registry():
            if item.get("ticker") == normalized_ticker:
                return item
        return None

    def lookup_by_cik(self, cik: str) -> dict[str, Any] | None:
        normalized_cik = str(cik).zfill(10)
        for item in self.load_registry():
            if item.get("cik") == normalized_cik:
                return item
        return None

    def match_sponsor_to_ticker(self, sponsor_name: str, minimum_confidence: float = 0.72) -> SponsorMatchResult:
        registry = self.load_registry()
        normalized_target = self._normalize_company_name(sponsor_name)
        exact_match = next((item for item in registry if item["normalized_company_name"] == normalized_target), None)
        if exact_match is not None:
            return SponsorMatchResult(
                sponsor_name=sponsor_name,
                matched_company_name=exact_match["company_name"],
                ticker=exact_match["ticker"],
                cik=exact_match["cik"],
                confidence=1.0,
                match_type="exact_normalized",
                alternatives=[],
            )

        scored: list[tuple[float, dict[str, Any]]] = []
        for item in registry:
            score = SequenceMatcher(None, normalized_target, item["normalized_company_name"]).ratio()
            if score <= 0:
                continue
            scored.append((score, item))
        scored.sort(key=lambda row: row[0], reverse=True)

        alternatives = [
            {
                "company_name": item["company_name"],
                "ticker": item["ticker"],
                "cik": item["cik"],
                "confidence": round(score, 4),
            }
            for score, item in scored[:5]
        ]
        if scored and scored[0][0] >= minimum_confidence:
            best_score, best_item = scored[0]
            return SponsorMatchResult(
                sponsor_name=sponsor_name,
                matched_company_name=best_item["company_name"],
                ticker=best_item["ticker"],
                cik=best_item["cik"],
                confidence=round(best_score, 4),
                match_type="fuzzy",
                alternatives=alternatives[1:],
            )

        return SponsorMatchResult(
            sponsor_name=sponsor_name,
            matched_company_name=None,
            ticker=None,
            cik=None,
            confidence=0.0,
            match_type="no_match",
            alternatives=alternatives,
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Map sponsor names to public tickers via SEC company registry")
    parser.add_argument("sponsor_name")
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--minimum-confidence", type=float, default=0.72)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    mapper = SecCompanyMapper()
    if args.refresh:
        mapper.refresh_registry(force=True)
    result = mapper.match_sponsor_to_ticker(args.sponsor_name, minimum_confidence=args.minimum_confidence)
    print(json.dumps(asdict(result), indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
