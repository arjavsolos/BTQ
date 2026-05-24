from __future__ import annotations

from statistics import median
from typing import Any

from app.database.connection import get_connection
from app.database.repositories import HistoricalTrialEventRepository
from app.models.benchmark_report import (
    BenchmarkGroup,
    BenchmarkReport,
    BenchmarkSummary,
    BenchmarkSummarySection,
    ExpectedReactionProfile,
)


class EventReturnBenchmarkService:
    """
    Builds grouped return benchmarks from stored historical trial-event rows.
    """

    VALID_GROUP_BY_FIELDS = {
        "phase_label",
        "mapped_ticker",
        "sponsor_class",
        "therapeutic_area",
        "event_date_quality_tier",
        "sponsor_mapping_review_status",
        "event_date_review_status",
    }

    def _normalize_group_by(self, group_by: str | None) -> str:
        clean_group_by = " ".join(str(group_by or "phase_label").split()).strip().lower()
        if clean_group_by not in self.VALID_GROUP_BY_FIELDS:
            valid_values = ", ".join(sorted(self.VALID_GROUP_BY_FIELDS))
            raise ValueError(f"group_by must be one of: {valid_values}. Got: {group_by!r}")
        return clean_group_by

    def _coerce_group_value(self, event: dict[str, Any], group_by: str) -> str:
        clean_value = " ".join(str(event.get(group_by) or "").split()).strip()
        return clean_value or "UNKNOWN"

    def _safe_average(self, values: list[float]) -> float | None:
        if not values:
            return None
        return round(sum(values) / len(values), 6)

    def _safe_median(self, values: list[float]) -> float | None:
        if not values:
            return None
        return round(float(median(values)), 6)

    def _has_meaningful_review_status(self, value: Any) -> bool:
        normalized = " ".join(str(value or "").split()).strip().lower()
        return normalized not in {"", "unknown", "unreviewed"}

    def _is_review_heavy(self, event: dict[str, Any]) -> bool:
        return bool(
            event.get("sponsor_mapping_override_applied")
            or event.get("event_date_override_applied")
            or self._has_meaningful_review_status(event.get("sponsor_mapping_review_status"))
            or self._has_meaningful_review_status(event.get("event_date_review_status"))
        )

    def _build_subset_metrics(self, events: list[dict[str, Any]]) -> dict[str, Any]:
        event_day_returns = [
            float(event["event_day_return"])
            for event in events
            if isinstance(event.get("event_day_return"), int | float)
        ]
        positive_return_count = sum(1 for value in event_day_returns if value > 0)
        return {
            "event_count": len(events),
            "average_event_day_return": self._safe_average(event_day_returns),
            "positive_event_day_ratio": (
                None if not event_day_returns else round(positive_return_count / len(event_day_returns), 6)
            ),
        }

    def _normalize_min_group_size(self, min_group_size: int | None) -> int:
        if min_group_size is None:
            return 5
        return max(1, int(min_group_size))

    def _build_group_summary(
        self,
        group_value: str,
        events: list[dict[str, Any]],
        min_group_size: int,
    ) -> BenchmarkGroup:
        event_day_returns = [
            float(event["event_day_return"])
            for event in events
            if isinstance(event.get("event_day_return"), int | float)
        ]
        post_window_returns = [
            float(event["post_window_return"])
            for event in events
            if isinstance(event.get("post_window_return"), int | float)
        ]
        model_ready_count = sum(1 for event in events if event.get("is_model_ready"))
        positive_event_day_count = sum(1 for value in event_day_returns if value > 0)
        override_applied_count = sum(1 for event in events if event.get("event_date_override_applied"))
        is_small_sample = len(events) < min_group_size

        return BenchmarkGroup(
            group=group_value,
            event_count=len(events),
            is_small_sample=is_small_sample,
            small_sample_warning=(
                f"Only {len(events)} event(s); interpret this cohort cautiously."
                if is_small_sample
                else None
            ),
            model_ready_count=model_ready_count,
            model_ready_ratio=None if not events else round(model_ready_count / len(events), 6),
            event_day_return_count=len(event_day_returns),
            average_event_day_return=self._safe_average(event_day_returns),
            median_event_day_return=self._safe_median(event_day_returns),
            positive_event_day_ratio=(
                None if not event_day_returns else round(positive_event_day_count / len(event_day_returns), 6)
            ),
            average_post_window_return=self._safe_average(post_window_returns),
            median_post_window_return=self._safe_median(post_window_returns),
            event_date_override_applied_count=override_applied_count,
        )

    def _classify_expected_direction(self, average_event_day_return: float | None) -> str:
        if average_event_day_return is None:
            return "unknown"
        if average_event_day_return >= 0.02:
            return "positive"
        if average_event_day_return <= -0.02:
            return "negative"
        return "mixed"

    def _classify_profile_confidence(
        self,
        event_day_return_count: int,
        small_sample_group_count: int,
    ) -> str:
        if event_day_return_count >= 100 and small_sample_group_count == 0:
            return "strong"
        if event_day_return_count >= 30:
            return "moderate"
        if event_day_return_count > 0:
            return "thin"
        return "unknown"

    def _build_expected_reaction_profile(
        self,
        events: list[dict[str, Any]],
        groups: list[BenchmarkGroup],
    ) -> ExpectedReactionProfile:
        event_day_returns = [
            float(event["event_day_return"])
            for event in events
            if isinstance(event.get("event_day_return"), int | float)
        ]
        post_window_returns = [
            float(event["post_window_return"])
            for event in events
            if isinstance(event.get("post_window_return"), int | float)
        ]
        positive_event_day_count = sum(1 for value in event_day_returns if value > 0)
        average_event_day_return = self._safe_average(event_day_returns)
        small_sample_group_count = sum(1 for group in groups if group.is_small_sample)
        caveats = []
        if not event_day_returns:
            caveats.append("No usable event-day returns are available for this benchmark.")
        if small_sample_group_count:
            caveats.append(f"{small_sample_group_count} cohort(s) are below the configured minimum group size.")
        if len(event_day_returns) < 30:
            caveats.append("The expected reaction profile is based on fewer than 30 usable event-day returns.")

        return ExpectedReactionProfile(
            event_count=len(events),
            event_day_return_count=len(event_day_returns),
            average_event_day_return=average_event_day_return,
            median_event_day_return=self._safe_median(event_day_returns),
            positive_event_day_ratio=(
                None if not event_day_returns else round(positive_event_day_count / len(event_day_returns), 6)
            ),
            average_post_window_return=self._safe_average(post_window_returns),
            median_post_window_return=self._safe_median(post_window_returns),
            expected_direction=self._classify_expected_direction(average_event_day_return),
            confidence_tier=self._classify_profile_confidence(len(event_day_returns), small_sample_group_count),
            caveats=caveats,
        )

    def _build_summary_sections(
        self,
        summary: BenchmarkSummary,
        groups: list[BenchmarkGroup],
        events: list[dict[str, Any]],
        min_group_size: int,
    ) -> list[BenchmarkSummarySection]:
        model_ready_count = sum(1 for event in events if event.get("is_model_ready"))
        event_date_override_count = sum(1 for event in events if event.get("event_date_override_applied"))
        sponsor_mapping_override_count = sum(1 for event in events if event.get("sponsor_mapping_override_applied"))
        largest_group = max(groups, key=lambda group: (group.event_count, group.group), default=None)

        coverage_section = BenchmarkSummarySection(
            title="coverage",
            metrics={
                "event_count": summary.event_count,
                "group_count": summary.group_count,
                "event_day_return_count": summary.event_day_return_count,
                "model_ready_count": model_ready_count,
                "model_ready_ratio": None if not events else round(model_ready_count / len(events), 6),
            },
            display_summary=(
                f"Benchmarked {summary.event_count} historical events across {summary.group_count} groups, "
                f"with usable event-day returns on {summary.event_day_return_count} rows."
            ),
        )
        returns_section = BenchmarkSummarySection(
            title="returns",
            metrics={
                "average_event_day_return": summary.average_event_day_return,
                "largest_group": None if largest_group is None else largest_group.group,
                "largest_group_average_event_day_return": (
                    None if largest_group is None else largest_group.average_event_day_return
                ),
                "largest_group_median_event_day_return": (
                    None if largest_group is None else largest_group.median_event_day_return
                ),
            },
            display_summary=(
                f"The benchmark-wide average event-day return is {summary.average_event_day_return}, "
                f"with the largest cohort "
                f"{'UNKNOWN' if largest_group is None else largest_group.group} contributing the deepest slice."
            ),
        )
        review_section = BenchmarkSummarySection(
            title="review_provenance",
            metrics={
                "event_date_override_applied_count": event_date_override_count,
                "sponsor_mapping_override_applied_count": sponsor_mapping_override_count,
                "event_date_override_applied_ratio": (
                    None if not events else round(event_date_override_count / len(events), 6)
                ),
                "sponsor_mapping_override_applied_ratio": (
                    None if not events else round(sponsor_mapping_override_count / len(events), 6)
                ),
            },
            display_summary=(
                f"{event_date_override_count} rows used approved event-date overrides and "
                f"{sponsor_mapping_override_count} used sponsor-mapping overrides."
            ),
        )
        small_sample_groups = [group for group in groups if group.is_small_sample]
        small_sample_section = BenchmarkSummarySection(
            title="sample_size_warnings",
            metrics={
                "min_group_size": min_group_size,
                "small_sample_group_count": len(small_sample_groups),
                "small_sample_groups": [group.group for group in small_sample_groups],
            },
            display_summary=(
                f"{len(small_sample_groups)} cohort(s) are below the minimum group size of "
                f"{min_group_size}; treat their return estimates as directional only."
            ),
        )
        model_ready_events = [event for event in events if event.get("is_model_ready")]
        not_model_ready_events = [event for event in events if not event.get("is_model_ready")]
        review_heavy_events = [event for event in events if self._is_review_heavy(event)]
        clean_events = [event for event in events if not self._is_review_heavy(event)]
        model_ready_metrics = self._build_subset_metrics(model_ready_events)
        not_model_ready_metrics = self._build_subset_metrics(not_model_ready_events)
        review_heavy_metrics = self._build_subset_metrics(review_heavy_events)
        clean_metrics = self._build_subset_metrics(clean_events)
        comparison_section = BenchmarkSummarySection(
            title="cohort_comparisons",
            metrics={
                "model_ready_event_count": model_ready_metrics["event_count"],
                "model_ready_average_event_day_return": model_ready_metrics["average_event_day_return"],
                "non_model_ready_event_count": not_model_ready_metrics["event_count"],
                "non_model_ready_average_event_day_return": not_model_ready_metrics["average_event_day_return"],
                "review_heavy_event_count": review_heavy_metrics["event_count"],
                "review_heavy_average_event_day_return": review_heavy_metrics["average_event_day_return"],
                "clean_event_count": clean_metrics["event_count"],
                "clean_average_event_day_return": clean_metrics["average_event_day_return"],
                "model_ready_minus_non_model_ready_return_gap": (
                    None
                    if model_ready_metrics["average_event_day_return"] is None
                    or not_model_ready_metrics["average_event_day_return"] is None
                    else round(
                        model_ready_metrics["average_event_day_return"]
                        - not_model_ready_metrics["average_event_day_return"],
                        6,
                    )
                ),
                "review_heavy_minus_clean_return_gap": (
                    None
                    if review_heavy_metrics["average_event_day_return"] is None
                    or clean_metrics["average_event_day_return"] is None
                    else round(
                        review_heavy_metrics["average_event_day_return"]
                        - clean_metrics["average_event_day_return"],
                        6,
                    )
                ),
            },
            display_summary=(
                f"Model-ready rows average "
                f"{model_ready_metrics['average_event_day_return']} versus "
                f"{not_model_ready_metrics['average_event_day_return']} for incomplete rows; "
                f"review-heavy rows average {review_heavy_metrics['average_event_day_return']} "
                f"versus {clean_metrics['average_event_day_return']} for clean rows."
            ),
        )
        ranked_groups = [
            group
            for group in sorted(
                groups,
                key=lambda group: (
                    -999999 if group.average_event_day_return is None else -group.average_event_day_return,
                    group.group,
                ),
            )
            if group.average_event_day_return is not None
        ]
        top_positive_group = ranked_groups[0] if ranked_groups else None
        top_negative_group = ranked_groups[-1] if ranked_groups else None
        top_groups_section = BenchmarkSummarySection(
            title="top_groups",
            metrics={
                "top_positive_group": None if top_positive_group is None else top_positive_group.group,
                "top_positive_average_event_day_return": (
                    None if top_positive_group is None else top_positive_group.average_event_day_return
                ),
                "top_negative_group": None if top_negative_group is None else top_negative_group.group,
                "top_negative_average_event_day_return": (
                    None if top_negative_group is None else top_negative_group.average_event_day_return
                ),
            },
            display_summary=(
                f"Top positive cohort: "
                f"{'UNKNOWN' if top_positive_group is None else top_positive_group.group} "
                f"at {None if top_positive_group is None else top_positive_group.average_event_day_return}; "
                f"top negative cohort: "
                f"{'UNKNOWN' if top_negative_group is None else top_negative_group.group} "
                f"at {None if top_negative_group is None else top_negative_group.average_event_day_return}."
            ),
        )
        expected_reaction_profile = self._build_expected_reaction_profile(events, groups)
        expected_reaction_section = BenchmarkSummarySection(
            title="expected_reaction",
            metrics={
                "expected_direction": expected_reaction_profile.expected_direction,
                "confidence_tier": expected_reaction_profile.confidence_tier,
                "average_event_day_return": expected_reaction_profile.average_event_day_return,
                "median_event_day_return": expected_reaction_profile.median_event_day_return,
                "positive_event_day_ratio": expected_reaction_profile.positive_event_day_ratio,
            },
            display_summary=(
                f"Expected reaction is {expected_reaction_profile.expected_direction} with "
                f"{expected_reaction_profile.confidence_tier} historical support; "
                f"average event-day return is {expected_reaction_profile.average_event_day_return}."
            ),
        )
        return [
            coverage_section,
            returns_section,
            review_section,
            small_sample_section,
            comparison_section,
            expected_reaction_section,
            top_groups_section,
        ]

    def build_benchmark_from_repository(
        self,
        repository: Any,
        group_by: str = "phase_label",
        limit: int = 1000,
        offset: int = 0,
        is_model_ready: bool | None = None,
        mapped_ticker: str | None = None,
        sponsor_name: str | None = None,
        phase_label: str | None = None,
        event_date_quality_tier: str | None = None,
        sponsor_mapping_review_status: str | None = None,
        event_date_review_status: str | None = None,
        sponsor_mapping_override_applied: bool | None = None,
        event_date_override_applied: bool | None = None,
        min_event_date_quality_score: int | None = None,
        min_group_size: int | None = None,
    ) -> dict[str, Any]:
        resolved_group_by = self._normalize_group_by(group_by)
        resolved_min_group_size = self._normalize_min_group_size(min_group_size)
        events = repository.list_events(
            limit=limit,
            offset=offset,
            is_model_ready=is_model_ready,
            mapped_ticker=mapped_ticker,
            sponsor_name=sponsor_name,
            phase_label=phase_label,
            event_date_quality_tier=event_date_quality_tier,
            sponsor_mapping_review_status=sponsor_mapping_review_status,
            event_date_review_status=event_date_review_status,
            sponsor_mapping_override_applied=sponsor_mapping_override_applied,
            event_date_override_applied=event_date_override_applied,
            min_event_date_quality_score=min_event_date_quality_score,
        )

        grouped_events: dict[str, list[dict[str, Any]]] = {}
        for event in events:
            grouped_events.setdefault(self._coerce_group_value(event, resolved_group_by), []).append(event)

        groups = [
            self._build_group_summary(group_value, group_events, resolved_min_group_size)
            for group_value, group_events in sorted(
                grouped_events.items(),
                key=lambda item: (-len(item[1]), item[0]),
            )
        ]

        event_day_returns = [
            float(event["event_day_return"])
            for event in events
            if isinstance(event.get("event_day_return"), int | float)
        ]
        summary = BenchmarkSummary(
            event_count=len(events),
            group_count=len(groups),
            event_day_return_count=len(event_day_returns),
            average_event_day_return=self._safe_average(event_day_returns),
        )
        expected_reaction_profile = self._build_expected_reaction_profile(events, groups)
        report = BenchmarkReport(
            status="success",
            group_by=resolved_group_by,
            summary=summary,
            expected_reaction_profile=expected_reaction_profile,
            summary_sections=self._build_summary_sections(summary, groups, events, resolved_min_group_size),
            groups=groups,
        )
        return report.to_dict()

    def benchmark_dataset(
        self,
        group_by: str = "phase_label",
        limit: int = 1000,
        offset: int = 0,
        is_model_ready: bool | None = None,
        mapped_ticker: str | None = None,
        sponsor_name: str | None = None,
        phase_label: str | None = None,
        event_date_quality_tier: str | None = None,
        sponsor_mapping_review_status: str | None = None,
        event_date_review_status: str | None = None,
        sponsor_mapping_override_applied: bool | None = None,
        event_date_override_applied: bool | None = None,
        min_event_date_quality_score: int | None = None,
        min_group_size: int | None = None,
    ) -> dict[str, Any]:
        with get_connection() as connection:
            repository = HistoricalTrialEventRepository(connection)
            repository.create_tables()
            return self.build_benchmark_from_repository(
                repository=repository,
                group_by=group_by,
                limit=limit,
                offset=offset,
                is_model_ready=is_model_ready,
                mapped_ticker=mapped_ticker,
                sponsor_name=sponsor_name,
                phase_label=phase_label,
                event_date_quality_tier=event_date_quality_tier,
                sponsor_mapping_review_status=sponsor_mapping_review_status,
                event_date_review_status=event_date_review_status,
                sponsor_mapping_override_applied=sponsor_mapping_override_applied,
                event_date_override_applied=event_date_override_applied,
                min_event_date_quality_score=min_event_date_quality_score,
                min_group_size=min_group_size,
            )
