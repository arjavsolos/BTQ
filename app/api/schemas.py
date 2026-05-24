from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class TrialAnalysisRequest:
    nct_id: str
    approval_limit: int = 5
    market_pre_days: int = 5
    market_post_days: int = 5
    include_raw_trial: bool = False
    save_to_db: bool = False
    summary_only: bool = False

    @classmethod
    def from_payload(cls, payload: dict[str, Any] | TrialAnalysisRequest) -> TrialAnalysisRequest:
        if isinstance(payload, cls):
            return payload

        nct_id = str(payload.get("nct_id") or "").strip()
        if not nct_id:
            raise ValueError("nct_id is required for trial analysis requests.")

        return cls(
            nct_id=nct_id,
            approval_limit=int(payload.get("approval_limit", 5)),
            market_pre_days=int(payload.get("market_pre_days", 5)),
            market_post_days=int(payload.get("market_post_days", 5)),
            include_raw_trial=bool(payload.get("include_raw_trial", False)),
            save_to_db=bool(payload.get("save_to_db", False)),
            summary_only=bool(payload.get("summary_only", False)),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
