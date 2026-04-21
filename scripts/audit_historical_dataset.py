from __future__ import annotations

import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services import HistoricalDatasetAuditService


def _get_int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return int(value.strip())


def main() -> None:
    try:
        service = HistoricalDatasetAuditService()
        result = service.audit_dataset(
            top_warning_limit=_get_int_env("HISTORICAL_AUDIT_TOP_WARNING_LIMIT", 10),
            issue_limit=_get_int_env("HISTORICAL_AUDIT_ISSUE_LIMIT", 25),
            therapeutic_area_limit=_get_int_env("HISTORICAL_AUDIT_THERAPEUTIC_AREA_LIMIT", 10),
        )
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "error",
                    "error": str(exc),
                    "input": {
                        "top_warning_limit": os.getenv("HISTORICAL_AUDIT_TOP_WARNING_LIMIT"),
                        "issue_limit": os.getenv("HISTORICAL_AUDIT_ISSUE_LIMIT"),
                        "therapeutic_area_limit": os.getenv("HISTORICAL_AUDIT_THERAPEUTIC_AREA_LIMIT"),
                    },
                },
                indent=2,
            )
        )
        raise SystemExit(1) from exc

    print(json.dumps(result, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
