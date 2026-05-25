from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any

from app.models.bayesian import clamp_probability

OPTIONS_PRICING_MODEL_VERSION = "market-expected-move-v1"
TRADING_DAYS_PER_YEAR = 252


@dataclass(frozen=True, slots=True)
class MarketExpectedMoveInput:
    annualized_volatility: float
    trading_days_to_event: int = 1
    source: str = "options_implied"


@dataclass(frozen=True, slots=True)
class MarketExpectedMoveResult:
    status: str
    model_version: str
    source: str
    annualized_volatility: float
    trading_days_to_event: int
    expected_move_percent: float
    warnings: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def annualized_volatility_to_expected_move_percent(
    annualized_volatility: float,
    trading_days_to_event: int = 1,
) -> float:
    safe_volatility = max(0.0, float(annualized_volatility))
    safe_days = max(1, int(trading_days_to_event))
    return round(safe_volatility * math.sqrt(safe_days / TRADING_DAYS_PER_YEAR), 6)


def build_market_expected_move(config: MarketExpectedMoveInput) -> dict[str, Any]:
    warnings: list[str] = []
    annualized_volatility = max(0.0, float(config.annualized_volatility))
    if annualized_volatility != config.annualized_volatility:
        warnings.append("annualized_volatility_was_clamped")
    trading_days_to_event = max(1, int(config.trading_days_to_event))
    if trading_days_to_event != config.trading_days_to_event:
        warnings.append("trading_days_to_event_was_raised_to_minimum")

    result = MarketExpectedMoveResult(
        status="available",
        model_version=OPTIONS_PRICING_MODEL_VERSION,
        source=config.source,
        annualized_volatility=round(annualized_volatility, 6),
        trading_days_to_event=trading_days_to_event,
        expected_move_percent=annualized_volatility_to_expected_move_percent(
            annualized_volatility=annualized_volatility,
            trading_days_to_event=trading_days_to_event,
        ),
        warnings=warnings,
    )
    return result.to_dict()


def classify_market_pricing(
    modeled_move_percent: float,
    market_expected_move_percent: float,
    modeled_probability: float | None = None,
) -> dict[str, Any]:
    safe_modeled_move = max(0.0, float(modeled_move_percent))
    safe_market_move = max(0.0, float(market_expected_move_percent))
    move_gap = round(safe_modeled_move - safe_market_move, 6)

    if abs(move_gap) <= 0.015:
        classification = "aligned"
        interpretation = "Modeled event risk is broadly aligned with the market move proxy."
    elif move_gap > 0:
        classification = "market_underpricing_event_risk"
        interpretation = "Modeled event risk is wider than the market move proxy."
    else:
        classification = "market_overpricing_event_risk"
        interpretation = "Market move proxy is wider than the modeled event-risk view."

    probability_adjusted_signal = "neutral"
    if modeled_probability is not None:
        safe_probability = clamp_probability(modeled_probability)
        if classification == "market_underpricing_event_risk" and safe_probability >= 0.6:
            probability_adjusted_signal = "bullish_if_directionally_correct"
        elif classification == "market_underpricing_event_risk" and safe_probability <= 0.4:
            probability_adjusted_signal = "bearish_if_directionally_correct"
        elif classification == "market_overpricing_event_risk":
            probability_adjusted_signal = "premium_priced"

    return {
        "status": "available",
        "classification": classification,
        "modeled_move_percent": round(safe_modeled_move, 6),
        "market_expected_move_percent": round(safe_market_move, 6),
        "move_gap": move_gap,
        "probability_adjusted_signal": probability_adjusted_signal,
        "interpretation": interpretation,
    }
