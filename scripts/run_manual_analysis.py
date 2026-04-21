from __future__ import annotations

import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services import TrialAnalysisService


def _get_required_str_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"Environment variable {name} is required.")
    return value


def _get_bool_env(name: str, default: bool = False) -> bool:
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


def main() -> None:
    try:
        nct_id = _get_required_str_env("ANALYZE_NCT_ID")
        approval_limit = _get_int_env("ANALYZE_APPROVAL_LIMIT", 5)
        market_pre_days = _get_int_env("ANALYZE_MARKET_PRE_DAYS", 5)
        market_post_days = _get_int_env("ANALYZE_MARKET_POST_DAYS", 5)
        include_raw_trial = _get_bool_env("ANALYZE_INCLUDE_RAW_TRIAL", False)
        save_to_db = _get_bool_env("ANALYZE_SAVE_TO_DB", False)
        summary_only = _get_bool_env("ANALYZE_SUMMARY_ONLY", False)

        service = TrialAnalysisService()
        result = service.analyze_trial(
            nct_id=nct_id,
            approval_limit=approval_limit,
            market_pre_days=market_pre_days,
            market_post_days=market_post_days,
            include_raw_trial=include_raw_trial,
            save_to_db=save_to_db,
        )
        payload = result["summary"] if summary_only else result
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "error",
                    "error": str(exc),
                    "input": {
                        "nct_id": os.getenv("ANALYZE_NCT_ID"),
                        "approval_limit": os.getenv("ANALYZE_APPROVAL_LIMIT"),
                        "market_pre_days": os.getenv("ANALYZE_MARKET_PRE_DAYS"),
                        "market_post_days": os.getenv("ANALYZE_MARKET_POST_DAYS"),
                        "include_raw_trial": os.getenv("ANALYZE_INCLUDE_RAW_TRIAL"),
                        "save_to_db": os.getenv("ANALYZE_SAVE_TO_DB"),
                        "summary_only": os.getenv("ANALYZE_SUMMARY_ONLY"),
                    },
                },
                indent=2,
            )
        )
        raise SystemExit(1) from exc

    print(json.dumps(payload, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
