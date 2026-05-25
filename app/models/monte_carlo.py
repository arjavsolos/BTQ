from __future__ import annotations

import random
from dataclasses import asdict, dataclass
from statistics import mean
from typing import Any

from app.models.bayesian import clamp_probability

MONTE_CARLO_MODEL_VERSION = "event-risk-monte-carlo-v1"


@dataclass(frozen=True, slots=True)
class MonteCarloInput:
    success_probability: float
    expected_success_return: float
    expected_failure_return: float
    post_window_success_return: float
    post_window_failure_return: float
    volatility: float = 0.04
    simulation_count: int = 5000
    random_seed: int = 17


@dataclass(frozen=True, slots=True)
class MonteCarloResult:
    status: str
    model_version: str
    simulation_count: int
    success_probability: float
    expected_event_day_return: float
    expected_post_window_return: float
    downside_probability: float
    event_day_percentiles: dict[str, float]
    post_window_percentiles: dict[str, float]
    scenario_table: list[dict[str, Any]]
    warnings: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def percentile(values: list[float], quantile: float) -> float:
    if not values:
        raise ValueError("percentile requires at least one value")
    if quantile <= 0:
        return min(values)
    if quantile >= 1:
        return max(values)
    ordered = sorted(values)
    index = (len(ordered) - 1) * quantile
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = index - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def _rounded_percentiles(values: list[float]) -> dict[str, float]:
    return {
        "p10": round(percentile(values, 0.10), 6),
        "p50": round(percentile(values, 0.50), 6),
        "p90": round(percentile(values, 0.90), 6),
    }


def build_scenario_table(
    event_day_percentiles: dict[str, float],
    post_window_percentiles: dict[str, float],
) -> list[dict[str, Any]]:
    return [
        {
            "scenario": "bear",
            "event_day_return": event_day_percentiles["p10"],
            "post_window_return": post_window_percentiles["p10"],
        },
        {
            "scenario": "base",
            "event_day_return": event_day_percentiles["p50"],
            "post_window_return": post_window_percentiles["p50"],
        },
        {
            "scenario": "bull",
            "event_day_return": event_day_percentiles["p90"],
            "post_window_return": post_window_percentiles["p90"],
        },
    ]


def simulate_event_risk(config: MonteCarloInput) -> dict[str, Any]:
    warnings: list[str] = []
    success_probability = clamp_probability(config.success_probability)
    if success_probability != config.success_probability:
        warnings.append("success_probability_was_clamped")

    simulation_count = max(100, int(config.simulation_count))
    if simulation_count != config.simulation_count:
        warnings.append("simulation_count_was_raised_to_minimum")

    volatility = max(0.0, float(config.volatility))
    rng = random.Random(config.random_seed)
    event_day_returns: list[float] = []
    post_window_returns: list[float] = []
    downside_count = 0

    for _ in range(simulation_count):
        success = rng.random() <= success_probability
        event_mean = config.expected_success_return if success else config.expected_failure_return
        post_mean = config.post_window_success_return if success else config.post_window_failure_return
        event_return = rng.gauss(event_mean, volatility)
        post_return = rng.gauss(post_mean, volatility * 1.4)
        event_day_returns.append(event_return)
        post_window_returns.append(post_return)
        if event_return < 0:
            downside_count += 1

    event_day_percentiles = _rounded_percentiles(event_day_returns)
    post_window_percentiles = _rounded_percentiles(post_window_returns)
    result = MonteCarloResult(
        status="available",
        model_version=MONTE_CARLO_MODEL_VERSION,
        simulation_count=simulation_count,
        success_probability=round(success_probability, 4),
        expected_event_day_return=round(mean(event_day_returns), 6),
        expected_post_window_return=round(mean(post_window_returns), 6),
        downside_probability=round(downside_count / simulation_count, 4),
        event_day_percentiles=event_day_percentiles,
        post_window_percentiles=post_window_percentiles,
        scenario_table=build_scenario_table(event_day_percentiles, post_window_percentiles),
        warnings=warnings,
    )
    return result.to_dict()
