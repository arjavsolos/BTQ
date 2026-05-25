from __future__ import annotations

from typing import Any

from app.models.bayesian import clamp_probability
from app.models.monte_carlo import MonteCarloInput, simulate_event_risk


class MonteCarloRiskService:
    """
    Builds an auditable event-risk simulation from the current probability
    and historical expected-reaction context.
    """

    def _coerce_float(self, value: Any) -> float | None:
        try:
            if value is None:
                return None
            return float(value)
        except (TypeError, ValueError):
            return None

    def _build_random_seed(self, trial: dict[str, Any]) -> int:
        nct_id = " ".join(str(trial.get("nct_id") or "").split()).strip().upper()
        if not nct_id:
            return 17
        return max(17, sum(ord(char) for char in nct_id))

    def _resolve_probability(
        self,
        bayesian_probability: dict[str, Any] | None,
        baseline_probability: dict[str, Any] | None,
    ) -> tuple[float, str]:
        posterior_probability = self._coerce_float((bayesian_probability or {}).get("posterior_probability"))
        if posterior_probability is not None:
            return clamp_probability(posterior_probability), "bayesian_posterior"

        baseline_value = self._coerce_float((baseline_probability or {}).get("success_probability"))
        if baseline_value is not None:
            return clamp_probability(baseline_value), "baseline_probability"

        return 0.5, "default_prior"

    def _resolve_expected_returns(
        self,
        expected_reaction_context: dict[str, Any] | None,
    ) -> tuple[float | None, float | None]:
        profile = (expected_reaction_context or {}).get("profile") or {}
        event_day_return = self._coerce_float(profile.get("average_event_day_return"))
        post_window_return = self._coerce_float(profile.get("average_post_window_return"))
        return event_day_return, post_window_return

    def _derive_failure_return(self, success_return: float) -> float:
        magnitude = max(abs(success_return) + 0.03, 0.04)
        return round(-magnitude, 6)

    def _derive_post_window_failure_return(self, post_window_success_return: float) -> float:
        magnitude = max(abs(post_window_success_return) + 0.02, 0.03)
        return round(-magnitude, 6)

    def _resolve_volatility(
        self,
        expected_success_return: float,
        market_summary: dict[str, Any] | None,
    ) -> float:
        actual_event_day_return = self._coerce_float((market_summary or {}).get("event_day_return"))
        if actual_event_day_return is None:
            return 0.04
        calibrated = abs(actual_event_day_return - expected_success_return) * 0.8 + 0.03
        return round(max(0.02, min(0.12, calibrated)), 6)

    def simulate_trial_event_risk(
        self,
        trial: dict[str, Any],
        baseline_probability: dict[str, Any] | None = None,
        bayesian_probability: dict[str, Any] | None = None,
        expected_reaction_context: dict[str, Any] | None = None,
        market_summary: dict[str, Any] | None = None,
        simulation_count: int = 5000,
    ) -> dict[str, Any]:
        expected_success_return, expected_post_window_return = self._resolve_expected_returns(
            expected_reaction_context=expected_reaction_context
        )
        if expected_success_return is None:
            return {
                "status": "unavailable",
                "reason": "missing_expected_event_day_return",
                "warnings": ["Expected reaction profile did not include an average event-day return."],
            }

        probability, probability_source = self._resolve_probability(
            bayesian_probability=bayesian_probability,
            baseline_probability=baseline_probability,
        )
        post_window_success_return = (
            expected_post_window_return
            if expected_post_window_return is not None
            else round(expected_success_return * 0.45, 6)
        )
        config = MonteCarloInput(
            success_probability=probability,
            expected_success_return=expected_success_return,
            expected_failure_return=self._derive_failure_return(expected_success_return),
            post_window_success_return=post_window_success_return,
            post_window_failure_return=self._derive_post_window_failure_return(post_window_success_return),
            volatility=self._resolve_volatility(expected_success_return, market_summary),
            simulation_count=simulation_count,
            random_seed=self._build_random_seed(trial),
        )
        result = simulate_event_risk(config)
        result["probability_source"] = probability_source
        result["inputs"] = {
            "success_probability": round(config.success_probability, 4),
            "expected_success_return": round(config.expected_success_return, 6),
            "expected_failure_return": round(config.expected_failure_return, 6),
            "post_window_success_return": round(config.post_window_success_return, 6),
            "post_window_failure_return": round(config.post_window_failure_return, 6),
            "volatility": round(config.volatility, 6),
            "random_seed": config.random_seed,
        }
        return result
