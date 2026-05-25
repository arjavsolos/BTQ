from __future__ import annotations

from math import sqrt
from statistics import pstdev
from typing import Any

from app.models.options_pricing import build_market_expected_move, classify_market_pricing


class MarketViewComparisonService:
    """
    Compares modeled event-risk outputs against a market move expectation.

    When direct options-implied volatility is unavailable, it falls back to a
    realized-volatility proxy derived from the fetched event-window prices.
    """

    def _coerce_float(self, value: Any) -> float | None:
        try:
            if value is None:
                return None
            return float(value)
        except (TypeError, ValueError):
            return None

    def _build_modeled_move_percent(self, event_risk_simulation: dict[str, Any] | None) -> float | None:
        simulation = event_risk_simulation or {}
        if simulation.get("status") != "available":
            return None
        event_day_percentiles = simulation.get("event_day_percentiles") or {}
        p10 = self._coerce_float(event_day_percentiles.get("p10"))
        p90 = self._coerce_float(event_day_percentiles.get("p90"))
        expected_event_day_return = self._coerce_float(simulation.get("expected_event_day_return"))
        candidates = [abs(value) for value in [expected_event_day_return, p10, p90] if value is not None]
        if not candidates:
            return None
        percentile_width = None
        if p10 is not None and p90 is not None:
            percentile_width = abs(p90 - p10) / 2
            candidates.append(percentile_width)
        return round(max(candidates), 6)

    def _build_realized_volatility_proxy(self, market_summary: dict[str, Any] | None) -> dict[str, Any] | None:
        records = (market_summary or {}).get("records") or []
        closes = [
            float(record["close"])
            for record in records
            if isinstance(record.get("close"), int | float)
        ]
        if len(closes) < 3:
            return None
        daily_returns = [
            (closes[index] - closes[index - 1]) / closes[index - 1]
            for index in range(1, len(closes))
            if closes[index - 1] not in {None, 0}
        ]
        if len(daily_returns) < 2:
            return None
        daily_volatility = pstdev(daily_returns)
        annualized_volatility = round(daily_volatility * sqrt(252), 6)
        result = build_market_expected_move(
            config=type(
                "_Config",
                (),
                {
                    "annualized_volatility": annualized_volatility,
                    "trading_days_to_event": 1,
                    "source": "realized_volatility_proxy",
                },
            )()
        )
        result["daily_volatility"] = round(daily_volatility, 6)
        return result

    def compare_market_view(
        self,
        trial: dict[str, Any],
        event_risk_simulation: dict[str, Any] | None = None,
        bayesian_probability: dict[str, Any] | None = None,
        market_summary: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        del trial
        modeled_move_percent = self._build_modeled_move_percent(event_risk_simulation)
        if modeled_move_percent is None:
            return {
                "status": "unavailable",
                "reason": "missing_modeled_move",
                "warnings": ["Monte Carlo event-risk simulation did not provide a usable modeled move."],
            }

        market_view_proxy = self._build_realized_volatility_proxy(market_summary)
        if market_view_proxy is None:
            return {
                "status": "unavailable",
                "reason": "missing_market_move_proxy",
                "modeled_move_percent": modeled_move_percent,
                "warnings": ["Market data did not include enough history to build a volatility proxy."],
            }

        modeled_probability = self._coerce_float((bayesian_probability or {}).get("posterior_probability"))
        comparison = classify_market_pricing(
            modeled_move_percent=modeled_move_percent,
            market_expected_move_percent=market_view_proxy["expected_move_percent"],
            modeled_probability=modeled_probability,
        )
        comparison["market_view_proxy"] = market_view_proxy
        return comparison
