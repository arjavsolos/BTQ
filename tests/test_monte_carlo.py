from __future__ import annotations

import unittest

from app.models.monte_carlo import (
    MONTE_CARLO_MODEL_VERSION,
    MonteCarloInput,
    percentile,
    simulate_event_risk,
)


class MonteCarloModelTests(unittest.TestCase):
    def test_percentile_interpolates_sorted_values(self) -> None:
        values = [10, 0, 30, 20]

        self.assertEqual(percentile(values, 0), 0)
        self.assertEqual(percentile(values, 1), 30)
        self.assertEqual(percentile(values, 0.5), 15)

    def test_simulate_event_risk_returns_deterministic_scenario_table(self) -> None:
        result = simulate_event_risk(
            MonteCarloInput(
                success_probability=0.68,
                expected_success_return=0.12,
                expected_failure_return=-0.18,
                post_window_success_return=0.08,
                post_window_failure_return=-0.12,
                volatility=0.03,
                simulation_count=1000,
                random_seed=42,
            )
        )

        self.assertEqual(result["status"], "available")
        self.assertEqual(result["model_version"], MONTE_CARLO_MODEL_VERSION)
        self.assertEqual(result["simulation_count"], 1000)
        self.assertEqual(result["success_probability"], 0.68)
        self.assertGreater(result["expected_event_day_return"], 0)
        self.assertGreater(result["event_day_percentiles"]["p90"], result["event_day_percentiles"]["p10"])
        self.assertEqual(
            [row["scenario"] for row in result["scenario_table"]],
            ["bear", "base", "bull"],
        )
        self.assertEqual(result["warnings"], [])

    def test_simulate_event_risk_clamps_probability_and_minimum_simulations(self) -> None:
        result = simulate_event_risk(
            MonteCarloInput(
                success_probability=1.4,
                expected_success_return=0.1,
                expected_failure_return=-0.2,
                post_window_success_return=0.05,
                post_window_failure_return=-0.1,
                simulation_count=10,
            )
        )

        self.assertEqual(result["success_probability"], 0.99)
        self.assertEqual(result["simulation_count"], 100)
        self.assertIn("success_probability_was_clamped", result["warnings"])
        self.assertIn("simulation_count_was_raised_to_minimum", result["warnings"])


if __name__ == "__main__":
    unittest.main()
