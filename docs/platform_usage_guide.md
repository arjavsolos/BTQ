# BTQ Usage Guide

## What BTQ Does

BTQ is a biotech event-intelligence platform for analyzing one clinical-trial catalyst at a time or building a historical event dataset for research.

Its final output is not "the stock will be exactly X."

It produces:

- baseline success probability
- Bayesian posterior probability
- Monte Carlo event-risk simulation
- historical expected-reaction context
- market-view comparison
- final research conclusion

## Core Workflow

### 1. Check the environment

```bash
python run.py check-readiness --skip-db
```

Use this first to confirm the local Python environment is ready.

### 2. Run one full trial analysis

```bash
python run.py analyze-trial NCT00000001 --format markdown --output-path reports/NCT00000001.md
```

This is the main product workflow.

It will:

- fetch and normalize the trial
- map the sponsor to a ticker
- pull regulatory context
- align market data
- compute baseline probability
- update that probability with Bayesian evidence
- run Monte Carlo event-risk simulation
- compare modeled move versus market move proxy
- save a recruiter/demo-ready Markdown report

### 3. Inspect historical benchmark context

```bash
python run.py benchmark-event-returns --group-by therapeutic_area --format markdown
```

Use this to understand the analog cohort behind expected-reaction estimates.

### 4. Build or refresh the historical dataset

```bash
python run.py build-historical-dataset --limit 50 --event-date-quality-tier high
```

This constructs historical catalyst-event rows for benchmarking and audit work.

### 5. Publish a demo dataset

```bash
python run.py publish-demo-dataset
```

This runs as a dry run by default. Add `--apply` only when you want to push the curated subset to the hosted demo database.

## How To Read The Final Report

### Modeled Success Probability

- `modeled_success_probability` is the interpretable baseline estimate.
- `bayesian_probability` is the adjusted posterior after accounting for evidence quality.

### Event Risk

- `event_risk_simulation` shows expected event-day return, downside probability, and bear/base/bull scenarios.

### Historical Context

- `expected_reaction_profile` tells you what similar historical events tended to do.
- `market_expected_reaction_comparison` tells you whether the realized event reaction was weaker, stronger, or aligned versus history.

### Market View

- `market_view_comparison` compares the modeled event-risk move to a volatility-based market move proxy.
- `potentially_underpriced` means modeled event risk looks wider than the market move proxy.
- `potentially_overpriced` means the market move proxy looks richer than the modeled view.
- `aligned` means they are broadly consistent.

## Best Daily Commands

```bash
python run.py project-status --format markdown
python run.py describe-methodology --format markdown
python run.py analyze-trial NCT00000001 --format markdown
```
