from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class BenchmarkSummary:
    event_count: int
    group_count: int
    event_day_return_count: int
    average_event_day_return: float | None


@dataclass(frozen=True, slots=True)
class BenchmarkGroup:
    group: str
    event_count: int
    is_small_sample: bool
    small_sample_warning: str | None
    model_ready_count: int
    model_ready_ratio: float | None
    event_day_return_count: int
    average_event_day_return: float | None
    median_event_day_return: float | None
    positive_event_day_ratio: float | None
    average_post_window_return: float | None
    median_post_window_return: float | None
    event_date_override_applied_count: int


@dataclass(frozen=True, slots=True)
class BenchmarkSummarySection:
    title: str
    metrics: dict[str, Any]
    display_summary: str


@dataclass(frozen=True, slots=True)
class ExpectedReactionProfile:
    event_count: int
    event_day_return_count: int
    average_event_day_return: float | None
    median_event_day_return: float | None
    positive_event_day_ratio: float | None
    average_post_window_return: float | None
    median_post_window_return: float | None
    expected_direction: str
    confidence_tier: str
    caveats: list[str]


@dataclass(frozen=True, slots=True)
class BenchmarkReport:
    status: str
    group_by: str
    summary: BenchmarkSummary
    expected_reaction_profile: ExpectedReactionProfile
    summary_sections: list[BenchmarkSummarySection]
    groups: list[BenchmarkGroup]

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "group_by": self.group_by,
            "summary": asdict(self.summary),
            "expected_reaction_profile": asdict(self.expected_reaction_profile),
            "summary_sections": [asdict(section) for section in self.summary_sections],
            "groups": [asdict(group) for group in self.groups],
        }
