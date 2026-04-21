from __future__ import annotations

import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services import HistoricalDatasetBackfillService


def _get_str_env(name: str) -> str | None:
    value = os.getenv(name)
    if value is None:
        return None
    clean = value.strip()
    return clean or None


def _get_bool_env(name: str) -> bool | None:
    value = os.getenv(name)
    if value is None or not value.strip():
        return None
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"Environment variable {name} must be boolean-like, got {value!r}")


def _get_int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return int(value.strip())


def _get_optional_int_env(name: str) -> int | None:
    value = os.getenv(name)
    if value is None or not value.strip():
        return None
    return int(value.strip())


def main() -> None:
    try:
        has_results = _get_bool_env("HISTORICAL_DATASET_HAS_RESULTS")
        without_results = _get_bool_env("HISTORICAL_DATASET_WITHOUT_RESULTS")
        include_existing = _get_bool_env("HISTORICAL_DATASET_INCLUDE_EXISTING")

        if has_results and without_results:
            raise ValueError(
                "HISTORICAL_DATASET_HAS_RESULTS and HISTORICAL_DATASET_WITHOUT_RESULTS cannot both be true."
            )

        service = HistoricalDatasetBackfillService()
        result = service.build_from_database(
            limit=_get_int_env("HISTORICAL_DATASET_LIMIT", 25),
            offset=_get_int_env("HISTORICAL_DATASET_OFFSET", 0),
            batch_size=_get_optional_int_env("HISTORICAL_DATASET_BATCH_SIZE"),
            max_batches=_get_optional_int_env("HISTORICAL_DATASET_MAX_BATCHES"),
            approval_limit=_get_int_env("HISTORICAL_DATASET_APPROVAL_LIMIT", 5),
            market_pre_days=_get_int_env("HISTORICAL_DATASET_MARKET_PRE_DAYS", 5),
            market_post_days=_get_int_env("HISTORICAL_DATASET_MARKET_POST_DAYS", 5),
            overall_status=_get_str_env("HISTORICAL_DATASET_STATUS"),
            sponsor_name=_get_str_env("HISTORICAL_DATASET_SPONSOR"),
            phase_label=_get_str_env("HISTORICAL_DATASET_PHASE"),
            study_type=_get_str_env("HISTORICAL_DATASET_STUDY_TYPE"),
            therapeutic_area=_get_str_env("HISTORICAL_DATASET_THERAPEUTIC_AREA"),
            has_results=False if without_results else has_results,
            exclude_existing_historical_events=not bool(include_existing),
        )
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "error",
                    "error": str(exc),
                    "input": {
                        "limit": os.getenv("HISTORICAL_DATASET_LIMIT"),
                        "offset": os.getenv("HISTORICAL_DATASET_OFFSET"),
                        "batch_size": os.getenv("HISTORICAL_DATASET_BATCH_SIZE"),
                        "max_batches": os.getenv("HISTORICAL_DATASET_MAX_BATCHES"),
                        "approval_limit": os.getenv("HISTORICAL_DATASET_APPROVAL_LIMIT"),
                        "market_pre_days": os.getenv("HISTORICAL_DATASET_MARKET_PRE_DAYS"),
                        "market_post_days": os.getenv("HISTORICAL_DATASET_MARKET_POST_DAYS"),
                        "status_filter": os.getenv("HISTORICAL_DATASET_STATUS"),
                        "sponsor": os.getenv("HISTORICAL_DATASET_SPONSOR"),
                        "phase": os.getenv("HISTORICAL_DATASET_PHASE"),
                        "study_type": os.getenv("HISTORICAL_DATASET_STUDY_TYPE"),
                        "therapeutic_area": os.getenv("HISTORICAL_DATASET_THERAPEUTIC_AREA"),
                        "has_results": os.getenv("HISTORICAL_DATASET_HAS_RESULTS"),
                        "without_results": os.getenv("HISTORICAL_DATASET_WITHOUT_RESULTS"),
                        "include_existing": os.getenv("HISTORICAL_DATASET_INCLUDE_EXISTING"),
                    },
                },
                indent=2,
            )
        )
        raise SystemExit(1) from exc

    print(json.dumps(result, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
