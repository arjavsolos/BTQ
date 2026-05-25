from __future__ import annotations

import unittest

from app.models.options_pricing import (
    annualized_volatility_to_expected_move_percent,
    build_market_expected_move,
    classify_market_pricing,
)


class OptionsPricingTests(unittest.TestCase):
    def test_annualized_volatility_to_expected_move_percent(self) -> None:
        self.assertEqual(annualized_volatility_to_expected_move_percent(0.63, trading_days_to_event=1), 0.039686)

    def test_build_market_expected_move_clamps_inputs(self) -> None:
        config = type(
            "_Config",
            (),
            {"annualized_volatility": -0.4, "trading_days_to_event": 0, "source": "options_implied"},
        )()

        result = build_market_expected_move(config)

        self.assertEqual(result["status"], "available")
        self.assertEqual(result["annualized_volatility"], 0.0)
        self.assertEqual(result["trading_days_to_event"], 1)
        self.assertIn("annualized_volatility_was_clamped", result["warnings"])
        self.assertIn("trading_days_to_event_was_raised_to_minimum", result["warnings"])

    def test_classify_market_pricing(self) -> None:
        result = classify_market_pricing(
            modeled_move_percent=0.11,
            market_expected_move_percent=0.04,
            modeled_probability=0.67,
        )

        self.assertEqual(result["classification"], "market_underpricing_event_risk")
        self.assertEqual(result["probability_adjusted_signal"], "bullish_if_directionally_correct")


if __name__ == "__main__":
    unittest.main()
