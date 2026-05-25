from __future__ import annotations

from typing import Any


def _display(value: Any, default: str = "unknown") -> str:
    if value is None:
        return default
    if isinstance(value, float):
        return str(round(value, 6))
    clean = " ".join(str(value).split()).strip()
    return clean or default


def _bullet(label: str, value: Any) -> str:
    return f"- **{label}:** `{_display(value)}`"


def render_trial_analysis_markdown(analysis: dict[str, Any]) -> str:
    summary = analysis.get("summary") or {}
    final_summary = analysis.get("final_comparison_summary") or summary.get("final_comparison_summary") or {}
    comparison = (
        analysis.get("market_expected_reaction_comparison")
        or summary.get("market_expected_reaction_comparison")
        or {}
    )
    expected_reaction = analysis.get("expected_reaction") or {}
    expected_profile = (
        expected_reaction.get("profile")
        or summary.get("expected_reaction_profile")
        or {}
    )
    modeled_probability = (
        analysis.get("modeled_success_probability")
        or summary.get("modeled_success_probability")
        or {}
    )
    bayesian_probability = analysis.get("bayesian_probability") or summary.get("bayesian_probability") or {}
    event_risk_simulation = analysis.get("event_risk_simulation") or summary.get("event_risk_simulation") or {}
    market_view_comparison = analysis.get("market_view_comparison") or summary.get("market_view_comparison") or {}
    event_date_quality = analysis.get("event_date_quality") or summary.get("event_date_quality") or {}
    analysis_readiness = analysis.get("analysis_readiness") or summary.get("analysis_readiness") or {}
    warnings = analysis.get("warnings") or []

    lines = [
        "# Trial Analysis Report",
        "",
        "## Final Comparison",
        "",
        _display(final_summary.get("headline"), "No final comparison summary is available."),
        "",
        _bullet("Conclusion", final_summary.get("conclusion")),
        _bullet("Expected direction", final_summary.get("expected_direction")),
        _bullet("Expected-reaction confidence", final_summary.get("expected_reaction_confidence")),
        _bullet("Event-date quality", final_summary.get("event_date_quality_tier")),
        _bullet("Return gap", final_summary.get("return_gap")),
        "",
        "## Production Readiness",
        "",
        _bullet("Readiness status", analysis_readiness.get("status")),
        _bullet("Readiness score", analysis_readiness.get("score")),
        _bullet("Blockers", ", ".join(analysis_readiness.get("blockers") or [])),
        _bullet("Cautions", ", ".join(analysis_readiness.get("cautions") or [])),
        "",
        "## Modeled Success Probability",
        "",
        _bullet("Model", modeled_probability.get("model_version")),
        _bullet("Success probability", modeled_probability.get("probability_percent")),
        _bullet("Probability tier", modeled_probability.get("probability_tier")),
        _bullet("Bayesian posterior", bayesian_probability.get("posterior_probability_percent")),
        _bullet("Bayesian confidence", bayesian_probability.get("confidence_tier")),
        "",
        "## Monte Carlo Event Risk",
        "",
        _bullet("Simulation status", event_risk_simulation.get("status")),
        _bullet("Simulation count", event_risk_simulation.get("simulation_count")),
        _bullet("Probability source", event_risk_simulation.get("probability_source")),
        _bullet("Expected event-day return", event_risk_simulation.get("expected_event_day_return")),
        _bullet("Expected post-window return", event_risk_simulation.get("expected_post_window_return")),
        _bullet("Downside probability", event_risk_simulation.get("downside_probability")),
        _bullet(
            "Bear / base / bull",
            ", ".join(
                f"{item.get('scenario')}={item.get('event_day_return')}"
                for item in event_risk_simulation.get("scenario_table") or []
            ),
        ),
        "",
        "## Market View Comparison",
        "",
        _bullet("Comparison status", market_view_comparison.get("status")),
        _bullet("Classification", market_view_comparison.get("classification")),
        _bullet("Modeled move", market_view_comparison.get("modeled_move_percent")),
        _bullet("Market move proxy", market_view_comparison.get("market_expected_move_percent")),
        _bullet("Move gap", market_view_comparison.get("move_gap")),
        _bullet("Signal", market_view_comparison.get("probability_adjusted_signal")),
        "",
        "## Trial",
        "",
        _bullet("NCT ID", summary.get("nct_id")),
        _bullet("Sponsor", summary.get("sponsor_name")),
        _bullet("Mapped ticker", summary.get("mapped_ticker")),
        _bullet("Phase", summary.get("phase_label")),
        _bullet("Therapeutic area", summary.get("therapeutic_area")),
        _bullet("Event date", summary.get("event_date_candidate")),
        "",
        "## Observed vs Expected Reaction",
        "",
        _bullet("Comparison status", comparison.get("status")),
        _bullet("Classification", comparison.get("classification")),
        _bullet("Actual event-day return", comparison.get("actual_event_day_return")),
        _bullet("Expected event-day return", comparison.get("expected_event_day_return")),
        _bullet("Expected profile direction", expected_profile.get("expected_direction")),
        _bullet("Expected profile confidence", expected_profile.get("confidence_tier")),
        "",
        "## Event-Date Quality",
        "",
        _bullet("Quality tier", event_date_quality.get("quality_tier")),
        _bullet("Quality score", event_date_quality.get("quality_score")),
        _bullet("Source", event_date_quality.get("source")),
        _bullet("Precision", event_date_quality.get("precision")),
        "",
        "## Caveats",
        "",
    ]

    confidence_notes = final_summary.get("confidence_notes") or []
    profile_caveats = expected_profile.get("caveats") or []
    caveats = [*confidence_notes, *profile_caveats, *warnings]
    if caveats:
        lines.extend(f"- {note}" for note in caveats)
    else:
        lines.append("- No major caveats were reported by the analysis pipeline.")

    return "\n".join(lines)
