# Final Product Definition

This document defines the final product that BTQ is being built toward.

## North Star

BTQ is a research-grade system for quantifying biological uncertainty in public biotech markets by building an auditable historical trial-event dataset and comparing modeled event risk to observed market behavior.

## Final Product Definition

BTQ should become a research-grade biotech event intelligence platform that:

- constructs an auditable historical dataset of clinical trial catalysts
- links those events to public-market entities
- measures biological and data uncertainty explicitly
- models trial success probability and event risk
- compares that modeled view to observed market behavior

The final system should not be framed as an exact point-price prediction engine.

The stronger and more defensible output is a comparison between:

- modeled success probability
- modeled event risk
- historically grounded expected reaction
- observed or market-implied market setup

## What The Final Product Should Output

For one analyzed trial or historical event, the ideal final output should include:

- trial summary
- sponsor mapping result and confidence
- event-date source and confidence
- regulatory context summary
- historical analog cohort summary
- modeled success probability
- confidence tier for that estimate
- event-risk score
- expected event-day reaction range
- expected post-window context
- market-view proxy
- final comparison summary

The final comparison summary should use clear research language such as:

- `aligned`
- `potentially underpriced`
- `potentially overpriced`
- `indeterminate`

## Why This Is The Right End State

Biotech catalyst events are:

- noisy
- expectation-driven
- often discontinuous
- difficult to reduce to a single exact price target

Because of that, the project is strongest when it compares modeled uncertainty and expected reaction to observed market setup rather than pretending it can always predict one exact future price.

## What BTQ Is Building Right Now

The current project phase is building the foundation for that final system:

- ingestion and normalization
- sponsor mapping and review
- event-date methodology
- historical event construction
- market reaction alignment
- dataset QA and auditability

Those layers are necessary because the final comparison engine is only as good as the dataset and methodology underneath it.

## Positioning Summaries

### README summary

BTQ is a biotech event intelligence platform that turns public clinical-trial, regulatory, and market data into an auditable historical catalyst dataset for probability, event-risk, and expected-reaction analysis.

### Recruiter summary

BTQ demonstrates full-stack data engineering, entity resolution, workflow automation, event-study design, and uncertainty-aware research modeling in a difficult biotech finance setting.

### Paper-style summary

BTQ is a research pipeline for constructing and auditing a historical dataset of clinical trial catalysts linked to public biotech equities, with the goal of comparing modeled biological uncertainty and expected market reaction to observed market behavior.
