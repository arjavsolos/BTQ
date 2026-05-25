from __future__ import annotations

import unittest

from app.services.market_view_comparison_service import MarketViewComparisonService


class MarketViewComparisonServiceTests(unittest.TestCase):
    def test_compare_market_view_builds_realized_volatility_proxy(self) -> None:
        service = MarketViewComparisonService()

        result = service.compare_market_view(
            trial={"nct_id": "NCT00000001"},
            event_risk_simulation={
                "status": "available",
                "expected_event_day_return": 0.071,
                "event_day_percentiles": {"p10": -0.051, "p90": 0.171},
            },
            bayesian_probability={"posterior_probability": 0.684},
            market_summary={
                "records": [
                    {"close": 10.0},
                    {"close": 10.2},
                    {"close": 10.1},
                    {"close": 10.4},
                    {"close": 10.35},
                ]
            },
        )

        self.assertEqual(result["status"], "available")
        self.assertEqual(result["classification"], "market_underpricing_event_risk")
        self.assertEqual(result["market_view_proxy"]["source"], "realized_volatility_proxy")
        self.assertGreater(result["modeled_move_percent"], result["market_expected_move_percent"])

    def test_compare_market_view_requires_market_proxy(self) -> None:
        service = MarketViewComparisonService()

        result = service.compare_market_view(
            trial={"nct_id": "NCT00000001"},
            event_risk_simulation={"status": "available", "expected_event_day_return": 0.02},
            market_summary={"records": [{"close": 10.0}]},
        )

        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["reason"], "missing_market_move_proxy")


if __name__ == "__main__":
    unittest.main()
