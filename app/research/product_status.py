from __future__ import annotations

from typing import Any

PRODUCT_STATUS_VERSION = "2026-05-25"


def build_product_status_snapshot() -> dict[str, Any]:
    return {
        "status_version": PRODUCT_STATUS_VERSION,
        "product_name": "BTQ",
        "positioning": (
            "Biotech event intelligence platform for probability, event-risk, "
            "expected-reaction, and observed-market comparison."
        ),
        "production_readiness": {
            "status": "production_ready_core",
            "remaining_scope": [
                "larger historical backfill",
                "hosted UI/API wrapper",
                "premium data-vendor upgrade for live institutional use",
            ],
            "verification_gate": [
                "ruff check",
                "unit test suite",
                "readiness check",
                "dry-run demo publishing",
            ],
        },
        "core_capabilities": [
            {
                "name": "clinical_trial_ingestion",
                "status": "implemented",
                "value": "Normalizes ClinicalTrials.gov records with event-date quality scoring.",
            },
            {
                "name": "entity_resolution",
                "status": "implemented",
                "value": "Maps sponsors to public-market tickers with review override support.",
            },
            {
                "name": "historical_event_dataset",
                "status": "implemented",
                "value": "Builds auditable catalyst-event rows for benchmark and demo publishing.",
            },
            {
                "name": "modeled_success_probability",
                "status": "implemented",
                "value": "Provides an interpretable baseline probability layer with feature contributions.",
            },
            {
                "name": "bayesian_probability_update",
                "status": "implemented",
                "value": "Adjusts the baseline probability with auditable event-quality and analog evidence.",
            },
            {
                "name": "monte_carlo_event_risk",
                "status": "implemented",
                "value": "Simulates bear/base/bull event outcomes, downside risk, and return percentiles.",
            },
            {
                "name": "market_view_comparison",
                "status": "implemented",
                "value": "Compares modeled event risk to a market move proxy using volatility-based expected moves.",
            },
            {
                "name": "expected_reaction_comparison",
                "status": "implemented",
                "value": "Compares observed event-day reaction against historical expected-reaction profiles.",
            },
            {
                "name": "production_readiness_scoring",
                "status": "implemented",
                "value": "Scores each analysis for demo readiness, blockers, cautions, and trust checks.",
            },
        ],
        "demo_commands": [
            "python run.py check-readiness --skip-db",
            "python run.py describe-methodology --format markdown",
            "python run.py analyze-trial NCT00000001 --format markdown --output-path reports/NCT00000001.md",
            "python run.py benchmark-event-returns --group-by therapeutic_area --format markdown",
            "python run.py publish-demo-dataset",
            "python run.py project-status --format markdown",
        ],
    }


def render_product_status_markdown() -> str:
    snapshot = build_product_status_snapshot()
    readiness = snapshot["production_readiness"]
    lines = [
        "# BTQ Project Status",
        "",
        snapshot["positioning"],
        "",
        "## Production Readiness",
        "",
        f"- **Status:** `{readiness['status']}`",
        f"- **Status version:** `{snapshot['status_version']}`",
        "",
        "## Core Capabilities",
        "",
    ]
    for capability in snapshot["core_capabilities"]:
        lines.append(
            f"- `{capability['name']}`: {capability['status']} - {capability['value']}"
        )

    lines.extend(["", "## Verification Gate", ""])
    lines.extend(f"- `{item}`" for item in readiness["verification_gate"])
    lines.extend(["", "## Remaining Scope", ""])
    lines.extend(f"- {item}" for item in readiness["remaining_scope"])
    lines.extend(["", "## Demo Commands", ""])
    lines.extend(f"- `{command}`" for command in snapshot["demo_commands"])
    return "\n".join(lines)
