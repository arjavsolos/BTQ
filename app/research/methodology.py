from __future__ import annotations

from typing import Any

METHODOLOGY_VERSION = "1.0"


def build_methodology_snapshot() -> dict[str, Any]:
    return {
        "methodology_version": METHODOLOGY_VERSION,
        "project_identity": {
            "name": "BTQ",
            "category": "biotech event intelligence and historical dataset engineering",
            "end_goal": (
                "Build a research-grade pipeline that converts clinical trial, sponsor, "
                "regulatory, and market data into analyzable event records for biotech "
                "catalyst research, dataset QA, and later probabilistic modeling."
            ),
            "primary_users": [
                "quant researchers",
                "biotech investors",
                "healthcare data scientists",
                "students building event-driven financial research systems",
            ],
        },
        "system_scope": {
            "current_capabilities": [
                "ingest and normalize ClinicalTrials.gov studies",
                "map sponsors to public-market entities through SEC reference data",
                "retrieve sponsor-linked OpenFDA approval context",
                "build market event windows around trial catalyst dates",
                "persist trial analyses and historical event rows to PostgreSQL",
                "audit the historical event dataset for completeness and model readiness",
                "run manual and scheduled GitHub Actions workflows for backfill and analysis",
            ],
            "future_capabilities": [
                "larger-scale historical dataset expansion",
                "sponsor-mapping benchmarking and error analysis",
                "event-date confidence scoring",
                "predictive modeling and backtesting",
                "probability-vs-market comparison once higher-fidelity options data is integrated",
            ],
        },
        "dataset_methodology": {
            "unit_of_analysis": (
                "One historical trial-event row represents one analyzed clinical study, "
                "a chosen event-date candidate, a sponsor-to-ticker mapping outcome, "
                "regulatory context, and an aligned market reaction window."
            ),
            "inclusion_criteria": [
                "Study must have a canonical ClinicalTrials.gov NCT identifier.",
                "Study must be normalizable into the canonical clinical_trials record shape.",
                "Study should have an event date candidate for event-study use cases.",
                "Stored backfill selection may be filtered by status, phase, study type, sponsor, "
                "therapeutic area, and results availability.",
                "Historical event construction accepts imperfect rows, but labels them for QA rather "
                "than silently dropping them.",
            ],
            "exclusion_criteria": [
                "Trials with no canonical NCT identifier are not valid dataset rows.",
                "Rows that cannot be normalized from the source payload are excluded from persistence.",
                "Rows with non-day-precision event dates are excluded from market event-window return "
                "calculation, but they may still be stored for audit visibility.",
                "Rows with no confident public ticker mapping are excluded from market data enrichment, "
                "but retained as incomplete historical events.",
            ],
            "selection_principle": (
                "Prefer retaining analyzable-but-incomplete rows with explicit warnings over "
                "silently discarding ambiguous cases. This supports auditability and later "
                "method improvement."
            ),
        },
        "event_date_methodology": {
            "objective": (
                "Choose the best available catalyst-date proxy from ClinicalTrials.gov status "
                "metadata while preserving source transparency and date precision."
            ),
            "precedence": [
                {
                    "rank": 1,
                    "field": "primary_completion_date",
                    "reason": "Best proxy for primary endpoint completion when available.",
                },
                {
                    "rank": 2,
                    "field": "completion_date",
                    "reason": "Fallback proxy for trial completion when primary completion is absent.",
                },
                {
                    "rank": 3,
                    "field": "results_first_posted",
                    "reason": "Best publication-style signal when completion dates are weaker.",
                },
                {
                    "rank": 4,
                    "field": "last_update_posted",
                    "reason": "Fallback administrative date when stronger milestone dates are absent.",
                },
            ],
            "precision_policy": [
                "Day precision is preferred over month precision.",
                "Month precision is preferred over year precision.",
                "If a lower-ranked field has better precision than a higher-ranked field, the "
                "higher-precision candidate is preferred.",
                "Market event-window analysis only runs when the chosen event date is day precision.",
            ],
        },
        "sponsor_mapping_methodology": {
            "objective": (
                "Resolve raw sponsor strings into public-market entities using deterministic "
                "normalization, candidate generation, exact matching, token overlap scoring, "
                "and fuzzy similarity."
            ),
            "normalization_steps": [
                "uppercase and whitespace normalization",
                "parenthetical removal",
                "symbol normalization such as ampersand-to-and",
                "suffix cleanup without over-aggressive removal of industry-relevant tokens",
            ],
            "matching_stages": [
                "exact normalized-name matching",
                "candidate normalized-name expansion",
                "token overlap scoring",
                "fuzzy similarity with substring-aware bonus logic",
            ],
            "quality_policy": [
                "Tickerless mappings are retained as unresolved rather than fabricated.",
                "Low-confidence mappings are surfaced as warnings.",
                "Historical dataset audits explicitly measure low-confidence mapping prevalence.",
            ],
        },
        "dataset_quality_methodology": {
            "philosophy": (
                "Dataset quality is measured directly and continuously, not assumed from source-system "
                "completeness."
            ),
            "record_level_signals": [
                "data_completeness_score",
                "data_completeness_ratio",
                "warning_count",
                "mapping_confidence",
                "event_date_precision",
                "market_record_count",
                "approval_record_count",
                "is_model_ready",
            ],
            "audit_metrics": [
                "model_ready_ratio",
                "missing_ticker_ratio",
                "missing_event_date_ratio",
                "missing_market_data_ratio",
                "missing_event_return_ratio",
                "missing_fda_context_ratio",
                "low_confidence_mapping_ratio",
                "low_completeness_ratio",
                "warning_event_ratio",
            ],
            "model_ready_definition": [
                "must have canonical nct_id",
                "must have mapped ticker",
                "must have event_date_candidate",
                "event_date_precision must equal day",
                "must have market window records",
                "must have event_day_return",
            ],
        },
        "evaluation_methodology": {
            "current_state": [
                "manual single-trial analysis",
                "historical dataset backfill from stored trials",
                "historical dataset QA and issue surfacing",
            ],
            "next_research_targets": [
                "define a larger historical cohort with explicit inclusion windows",
                "benchmark sponsor mapping accuracy against a reviewed sample",
                "measure event-date proxy quality against known announcement dates where available",
                "run descriptive backtests on event-day and post-window returns",
                "separate exploratory findings from out-of-sample claims",
            ],
            "claim_boundary": (
                "The current system supports data engineering, event-study scaffolding, and QA. "
                "It does not yet justify strong claims of exploitable mispricing, causal prediction, "
                "or live trading edge without a larger validated dataset and formal backtests."
            ),
        },
        "limitations": [
            "ClinicalTrials.gov dates are often proxy dates rather than exact public readout dates.",
            "Sponsor names do not always map cleanly to a public parent or directly tradeable ticker.",
            "Free market data sources can miss intraday detail, delistings, or corporate-action nuance.",
            "OpenFDA sponsor-linked approval context is informative but not a complete regulatory history.",
            "Current analysis is closer to research infrastructure than a deployable alpha engine.",
        ],
        "product_direction": {
            "research_value": (
                "Provides a reproducible, inspectable dataset and workflow for biotech event studies."
            ),
            "recruiter_value": (
                "Demonstrates full-stack data engineering, API integration, entity resolution, "
                "database design, workflow automation, and research framing."
            ),
            "commercialization_direction": [
                "internal biotech catalyst intelligence dashboard",
                "dataset licensing or premium analytics reports",
                "institutional research workflow with upgraded data vendors",
                "decision-support product for catalyst calendars and event scoring",
            ],
        },
    }


def render_methodology_markdown() -> str:
    snapshot = build_methodology_snapshot()
    project = snapshot["project_identity"]
    system_scope = snapshot["system_scope"]
    dataset_methodology = snapshot["dataset_methodology"]
    event_methodology = snapshot["event_date_methodology"]
    sponsor_methodology = snapshot["sponsor_mapping_methodology"]
    quality_methodology = snapshot["dataset_quality_methodology"]
    evaluation_methodology = snapshot["evaluation_methodology"]
    product_direction = snapshot["product_direction"]

    def bullet_list(values: list[str]) -> str:
        return "\n".join(f"- {value}" for value in values)

    event_precedence = "\n".join(
        f"{entry['rank']}. `{entry['field']}`: {entry['reason']}"
        for entry in event_methodology["precedence"]
    )

    sections = [
        "# Methodology",
        "",
        "## Project Identity",
        "",
        f"**Methodology version:** `{snapshot['methodology_version']}`",
        "",
        f"**End goal:** {project['end_goal']}",
        "",
        "**Primary users**",
        bullet_list(project["primary_users"]),
        "",
        "## System Scope",
        "",
        "**Current capabilities**",
        bullet_list(system_scope["current_capabilities"]),
        "",
        "**Future capabilities**",
        bullet_list(system_scope["future_capabilities"]),
        "",
        "## Dataset Methodology",
        "",
        f"**Unit of analysis:** {dataset_methodology['unit_of_analysis']}",
        "",
        "**Inclusion criteria**",
        bullet_list(dataset_methodology["inclusion_criteria"]),
        "",
        "**Exclusion criteria**",
        bullet_list(dataset_methodology["exclusion_criteria"]),
        "",
        f"**Selection principle:** {dataset_methodology['selection_principle']}",
        "",
        "## Event-Date Methodology",
        "",
        f"**Objective:** {event_methodology['objective']}",
        "",
        "**Precedence**",
        event_precedence,
        "",
        "**Precision policy**",
        bullet_list(event_methodology["precision_policy"]),
        "",
        "## Sponsor Mapping Methodology",
        "",
        f"**Objective:** {sponsor_methodology['objective']}",
        "",
        "**Normalization steps**",
        bullet_list(sponsor_methodology["normalization_steps"]),
        "",
        "**Matching stages**",
        bullet_list(sponsor_methodology["matching_stages"]),
        "",
        "**Quality policy**",
        bullet_list(sponsor_methodology["quality_policy"]),
        "",
        "## Dataset Quality Methodology",
        "",
        f"**Philosophy:** {quality_methodology['philosophy']}",
        "",
        "**Record-level signals**",
        bullet_list(quality_methodology["record_level_signals"]),
        "",
        "**Audit metrics**",
        bullet_list(quality_methodology["audit_metrics"]),
        "",
        "**Model-ready definition**",
        bullet_list(quality_methodology["model_ready_definition"]),
        "",
        "## Evaluation Methodology",
        "",
        "**Current state**",
        bullet_list(evaluation_methodology["current_state"]),
        "",
        "**Next research targets**",
        bullet_list(evaluation_methodology["next_research_targets"]),
        "",
        f"**Claim boundary:** {evaluation_methodology['claim_boundary']}",
        "",
        "## Limitations",
        bullet_list(snapshot["limitations"]),
        "",
        "## Product Direction",
        "",
        f"**Research value:** {product_direction['research_value']}",
        "",
        f"**Recruiter value:** {product_direction['recruiter_value']}",
        "",
        "**Commercialization direction**",
        bullet_list(product_direction["commercialization_direction"]),
    ]
    return "\n".join(sections).strip() + "\n"
