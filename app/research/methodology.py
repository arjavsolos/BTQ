from __future__ import annotations

from typing import Any

METHODOLOGY_VERSION = "1.2"


def build_methodology_snapshot() -> dict[str, Any]:
    return {
        "methodology_version": METHODOLOGY_VERSION,
        "project_identity": {
            "name": "BTQ",
            "category": "biotech event intelligence and historical dataset engineering",
            "north_star": (
                "BTQ is a research-grade system for quantifying biological uncertainty "
                "in public biotech markets by building an auditable historical "
                "trial-event dataset and comparing modeled event risk to observed "
                "market behavior."
            ),
            "end_goal": (
                "Build a research-grade pipeline that converts clinical trial, sponsor, "
                "regulatory, and market data into analyzable event records for biotech "
                "catalyst research, dataset QA, and a final probability, event-risk, "
                "and expected-reaction comparison layer."
            ),
            "final_product_definition": (
                "BTQ should become a research-grade biotech event intelligence platform "
                "that constructs an auditable historical dataset of clinical trial "
                "catalysts, links those events to public-market entities, measures "
                "biological and data uncertainty, models trial success probability and "
                "event risk, and compares that modeled view to observed market behavior."
            ),
            "primary_users": [
                "quant researchers",
                "biotech investors",
                "healthcare data scientists",
                "students building event-driven financial research systems",
            ],
            "positioning_summaries": {
                "readme": (
                    "BTQ is a biotech event intelligence platform that turns public "
                    "clinical-trial, regulatory, and market data into an auditable "
                    "historical catalyst dataset for probability, event-risk, and "
                    "expected-reaction analysis."
                ),
                "recruiter": (
                    "BTQ demonstrates full-stack data engineering, entity resolution, "
                    "workflow automation, event-study design, and uncertainty-aware "
                    "research modeling in a difficult biotech finance setting."
                ),
                "paper_abstract": (
                    "We present BTQ, a research pipeline for constructing and auditing a "
                    "historical dataset of clinical trial catalysts linked to public "
                    "biotech equities, with the goal of comparing modeled biological "
                    "uncertainty and expected market reaction to observed market behavior."
                ),
            },
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
                "expected-reaction comparison against observed market setup",
            ],
        },
        "final_output_framework": {
            "objective": (
                "The final analytical layer should compare model-implied biological uncertainty "
                "and event-risk signals against observed market behavior or market-implied event "
                "pricing, rather than claiming an exact future stock price target."
            ),
            "core_outputs": [
                "modeled trial success probability",
                "uncertainty band or confidence tier for that probability estimate",
                "event-risk classification based on trial, sponsor, and dataset quality signals",
                "expected event-day and post-window reaction context derived from historical analogs",
                "comparison between modeled view and observed market setup",
                "research-facing explanation of what drives the comparison result",
            ],
            "comparison_layers": [
                "probability comparison: modeled success probability versus market-implied or heuristic market view",
                (
                    "event-risk comparison: modeled catalyst risk and data quality "
                    "versus observed uncertainty in the setup"
                ),
                (
                    "expected-reaction comparison: historically grounded reaction "
                    "range versus realized or currently priced behavior"
                ),
            ],
            "non_goals": [
                "do not frame the final system as an exact point-price predictor",
                "do not claim a live tradable edge before formal backtests and out-of-sample validation",
                "do not hide low-quality data rows behind overly confident final scores",
            ],
            "example_output_contract": {
                "trial_identifier": "NCT example or canonical event row",
                "modeled_success_probability": "0-1 probability estimate",
                "probability_confidence_tier": "low, moderate, or high confidence in the estimate",
                "event_risk_score": "composite catalyst-risk or uncertainty score",
                "historical_expected_reaction": {
                    "event_day_range": "historical analog-based reaction range",
                    "post_window_context": "historical post-event behavior summary",
                },
                "market_view_proxy": "observed market setup or implied event-risk proxy",
                "comparison_summary": (
                    "plain-language statement describing whether the current setup appears "
                    "cheap, rich, aligned, or indeterminate relative to the model view"
                ),
            },
        },
        "dataset_methodology": {
            "unit_of_analysis": (
                "One historical trial-event row represents one analyzed clinical study, "
                "a chosen event-date candidate, its source and source rank, a sponsor-to-"
                "ticker mapping outcome, regulatory context, and an aligned market "
                "reaction window."
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
                "If two candidates have the same precision, the higher-ranked source is preferred.",
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
                "event_date_source_rank",
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
                "formalize the probability, event-risk, and expected-reaction comparison layer",
                "separate exploratory findings from out-of-sample claims",
            ],
            "claim_boundary": (
                "The current system supports data engineering, event-study scaffolding, and QA. "
                "It does not yet justify strong claims of exploitable mispricing, causal prediction, "
                "or live trading edge without a larger validated dataset, formal backtests, and "
                "validated market-comparison methodology."
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
                "Provides a reproducible, inspectable dataset and workflow for biotech event studies, "
                "with a path toward probability, event-risk, and expected-reaction comparison."
            ),
            "recruiter_value": (
                "Demonstrates full-stack data engineering, API integration, entity resolution, "
                "database design, workflow automation, and research framing around uncertainty-aware "
                "biotech event analysis."
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
    final_output_framework = snapshot["final_output_framework"]
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
        f"**North star:** {project['north_star']}",
        "",
        f"**End goal:** {project['end_goal']}",
        "",
        f"**Final product definition:** {project['final_product_definition']}",
        "",
        "**Primary users**",
        bullet_list(project["primary_users"]),
        "",
        "**Positioning summaries**",
        bullet_list(
            [
                f"README: {project['positioning_summaries']['readme']}",
                f"Recruiter: {project['positioning_summaries']['recruiter']}",
                f"Paper abstract: {project['positioning_summaries']['paper_abstract']}",
            ]
        ),
        "",
        "## System Scope",
        "",
        "**Current capabilities**",
        bullet_list(system_scope["current_capabilities"]),
        "",
        "**Future capabilities**",
        bullet_list(system_scope["future_capabilities"]),
        "",
        "## Final Output Framework",
        "",
        f"**Objective:** {final_output_framework['objective']}",
        "",
        "**Core outputs**",
        bullet_list(final_output_framework["core_outputs"]),
        "",
        "**Comparison layers**",
        bullet_list(final_output_framework["comparison_layers"]),
        "",
        "**Non-goals**",
        bullet_list(final_output_framework["non_goals"]),
        "",
        "**Example output contract**",
        bullet_list(
            [
                f"`{key}`: {value if not isinstance(value, dict) else 'see structured subfields'}"
                for key, value in final_output_framework["example_output_contract"].items()
            ]
        ),
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
