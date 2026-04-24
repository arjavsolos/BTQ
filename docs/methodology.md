# Methodology

This document defines the formal research and dataset methodology for BTQ.

The code-backed version of this methodology lives in:

- `app/research/methodology.py`

You can export the current canonical methodology with:

```bash
python run.py describe-methodology --format markdown
```

## End Goal

**Official north star**

BTQ is a research-grade system for quantifying biological uncertainty in public biotech markets by building an auditable historical trial-event dataset and comparing modeled event risk to observed market behavior.

BTQ is designed to become a research-grade biotech event intelligence system. Its purpose is to transform clinical trial metadata, sponsor identity resolution, regulatory context, and market reaction data into a structured historical dataset that can support:

- catalyst research
- historical event studies
- dataset quality auditing
- future predictive and probabilistic modeling
- a final probability, event-risk, and expected-reaction comparison layer

The project is intentionally staged. Today it is strongest as a data and methodology platform. Over time it is intended to become a stronger research engine for analyzing whether biotech trial events produce repeatable market patterns.

**Final product definition**

BTQ should become a research-grade biotech event intelligence platform that constructs an auditable historical dataset of clinical trial catalysts, links those events to public-market entities, measures biological and data uncertainty, models trial success probability and event risk, and compares that modeled view to observed market behavior.

## Final Output Framework

The best end-state for BTQ is not an exact stock-price target.

The stronger and more defensible goal is to produce a comparison between:

- modeled biological success probability
- modeled event risk and uncertainty
- historically grounded expected market reaction
- the observed or currently priced market setup

That means the system should eventually answer questions like:

- does the model imply a higher or lower success probability than the market appears to assume?
- does this trial look unusually risky or unusually clean relative to historical analogs?
- does the current market setup look rich, cheap, aligned, or indeterminate relative to the model view?

The final output layer should therefore emphasize:

- probability comparison
- event-risk comparison
- expected-reaction comparison

and should explicitly avoid overselling the project as an exact point-price prediction engine.

The ideal final output for one analyzed trial should look more like:

- modeled success probability
- confidence tier for that estimate
- catalyst or event-risk score
- historical analog-based expected event-day reaction range
- historical post-window reaction context
- market-view proxy or market-implied event-risk proxy
- plain-language comparison summary

This framing is stronger for research credibility because it fits the actual structure of biotech catalyst events, which are noisy, expectation-driven, and often discontinuous.

## Core Research Principle

The system should not silently drop ambiguous data just because the row is imperfect.

Instead, BTQ follows a more rigorous principle:

- keep rows when they can still be normalized
- label uncertainty explicitly
- surface warnings and completeness metrics
- decide model readiness based on observable criteria

That approach makes the dataset far more useful for research because it preserves both coverage and auditability.

## Unit Of Analysis

The main research unit is a historical trial-event row.

One row combines:

- a canonical `nct_id`
- a normalized ClinicalTrials.gov trial record
- a chosen `event_date_candidate`
- an `event_date_source`
- an event-date precision label
- an event-date confidence label
- a sponsor-to-ticker mapping result
- sponsor-linked OpenFDA approval context
- a market event window around the selected date
- warnings and completeness signals
- a model-readiness label

This means the project is not merely storing raw trials. It is constructing research-ready event observations.

## Inclusion Criteria

Trials are eligible for the normalized dataset when:

- they have a canonical ClinicalTrials.gov NCT identifier
- they can be transformed into the canonical `clinical_trials` record shape
- the source payload contains enough structure to preserve identifiers, sponsor metadata, and trial design metadata

Trials are eligible for historical event construction when:

- they are already stored in the database or available through the analysis pipeline
- they have an event-date candidate that can be recorded, even if that date is only partial precision
- they can be analyzed end to end through the existing services

Backfill runs may apply additional filters such as:

- `overall_status`
- `phase`
- `study_type`
- `sponsor`
- `therapeutic_area`
- `has_results`

## Exclusion Criteria

Trials are excluded from canonical storage or event construction when:

- the system cannot determine a canonical `nct_id`
- the source record is too malformed to normalize into the expected contract

Trials may still remain in the historical dataset but be excluded from specific downstream calculations:

- non-day-precision event dates are excluded from market event-window return calculations
- unresolved sponsor mappings are excluded from ticker-based market enrichment
- missing market records prevent event-return calculations but do not force row deletion

This is important: exclusion from one enrichment stage does not automatically mean exclusion from the full dataset.

## Event-Date Methodology

ClinicalTrials.gov does not directly guarantee the exact public market-moving announcement date for every study. Because of that, BTQ uses a transparent event-date proxy method.

The current precedence order is:

1. `primary_completion_date`
2. `completion_date`
3. `results_first_posted`
4. `last_update_posted`

The system also prefers higher precision over lower precision:

- day precision is preferred over month precision
- month precision is preferred over year precision
- if a lower-ranked field has better precision than a higher-ranked field, the higher-precision candidate may be selected

Every chosen event-date proxy is stored with:

- `event_date_candidate`
- `event_date_source`
- `event_date_precision`
- `event_date_confidence`

This is one of the most important methodological safeguards in the entire project because it prevents hidden assumptions about catalyst timing.

## Sponsor-Mapping Methodology

Clinical trial registries use raw sponsor text. Financial analysis requires public-market entities. BTQ bridges that gap through a staged sponsor-mapping pipeline.

The current process includes:

- string normalization
- parenthetical cleanup
- symbol normalization such as converting `&` to `and`
- candidate name generation
- exact normalized-name matching
- token-overlap scoring
- fuzzy similarity scoring

The system is deliberately conservative:

- if no reliable mapping is found, it does not invent one
- if a mapping exists but confidence is low, it raises a warning
- dataset audits measure how often low-confidence mappings occur

This makes the system more credible for research, because it is better to preserve uncertainty than to hide it.

## Dataset Quality And QA Metrics

BTQ treats dataset QA as a first-class feature.

At the trial level, the system tracks fields such as:

- `data_completeness_score`
- `data_completeness_ratio`
- `warning_count`
- `mapping_confidence`
- `approval_record_count`
- `market_record_count`
- `event_date_precision`
- `is_model_ready`

At the historical dataset level, the audit layer tracks metrics such as:

- `model_ready_ratio`
- `missing_ticker_ratio`
- `missing_event_date_ratio`
- `missing_market_data_ratio`
- `missing_event_return_ratio`
- `missing_fda_context_ratio`
- `low_confidence_mapping_ratio`
- `low_completeness_ratio`
- `warning_event_ratio`

This lets you evaluate the dataset as a measurable artifact instead of assuming the pipeline is trustworthy just because it runs.

## Model-Ready Definition

A historical event row is currently treated as model-ready only when it has:

- a canonical `nct_id`
- a mapped ticker
- an event date candidate
- day-precision event timing
- an aligned market window
- a computed event-day return

Anything short of that is still useful, but it should be treated as an incomplete research row rather than a training-quality example.

## Current Evaluation State

The current project already supports:

- single-trial end-to-end analysis
- persistence of analysis snapshots
- construction of historical trial-event rows
- historical dataset backfilling from stored trials
- audit reporting on data quality and model readiness
- manual and scheduled GitHub Actions workflows

That means the project has crossed the threshold from prototype code into a reproducible research pipeline.

## What Still Needs To Happen For Strong Quant Claims

The system is not yet at the stage where it can honestly claim a robust tradable edge.

To make stronger quant and biotech claims, the next research steps should be:

- build a larger historical dataset
- lock explicit inclusion and exclusion rules for the study universe
- benchmark sponsor mapping against reviewed examples
- evaluate event-date proxy quality against known announcement dates when possible
- produce descriptive backtests across the stored event set
- formalize the probability, event-risk, and expected-reaction comparison layer
- separate exploratory findings from out-of-sample validation

That sequence matters because strong claims without dataset validation would weaken the credibility of the whole project.

## Limitations

The project currently has several real limitations:

- ClinicalTrials.gov milestone dates are often proxies rather than exact public catalyst dates.
- Sponsor names do not always map cleanly to a tradeable public parent.
- Free market data can miss detail that matters for event studies.
- OpenFDA sponsor context is helpful but not a complete approval-history model.
- Current outputs are best understood as research infrastructure, not live trading signals.
- The final comparison layer should not be framed as an exact stock-price predictor without much stronger evidence and richer market data.

These limitations do not make the project weak. They just define the boundary of what can be claimed honestly.

## Why This Methodology Matters

This methodology turns the project from “some API scripts” into a real research system.

It gives BTQ:

- a clear end goal
- explicit inclusion and exclusion logic
- traceable event-date selection
- an auditable sponsor-mapping process
- measurable QA standards
- a principled definition of model readiness
- careful boundaries around financial claims

That is exactly what makes the project stronger for:

- recruiters
- research credibility
- future productization
- eventual paper-writing
