# Historical Event Export Workflow

This document explains how BTQ exports stored historical trial-event rows, why that export layer matters, what data it exposes, and how it fits into the larger research workflow.

## Why This Workflow Exists

BTQ does not stop at raw trial ingestion.

Its real research unit is the stored historical event row in:

- `historical_trial_events`

That row combines:

- normalized trial metadata
- sponsor-to-ticker mapping
- event-date selection
- event-date quality signals
- regulatory context counts
- market reaction outputs
- warnings
- model-readiness status

Once those rows exist, the project needs a clean way to get them back out of the database for:

- QA review
- dataset inspection
- demo outputs
- benchmark preparation
- downstream reporting
- later model and paper workflows

Without an export layer, those rows stay trapped in the database and are harder to inspect operationally.

## Where The Workflow Lives In The Codebase

The current historical-event export workflow spans three layers.

### 1. Historical event persistence

- `app/database/schemas.py`
- `app/database/repositories.py`

This layer defines the `historical_trial_events` table and the repository methods used to read stored event rows.

### 2. Historical event construction

- `app/services/historical_trial_event_service.py`

This layer builds the stored event record from the full trial-analysis payload.

### 3. Export and operational access

- `scripts/export_historical_trial_events.py`
- `run.py`

This layer exposes the stored dataset in JSON or JSONL format for operational use.

## The Current Workflow Step By Step

### Step 1. BTQ stores a historical event row

An end-to-end trial analysis is converted into a persisted historical event record.

That row includes:

- identity fields like `nct_id` and `mapped_ticker`
- event-date fields like `event_date_candidate` and `event_date_source`
- event-date quality fields like `event_date_quality_score` and `event_date_quality_tier`
- market outputs like `event_day_return` and `post_window_return`
- quality controls like `warning_count` and `is_model_ready`

### Step 2. The repository exposes queryable export filters

The repository layer supports filtered reads over stored historical events.

Current filters include:

- `limit`
- `offset`
- `is_model_ready`
- `mapped_ticker`
- `phase_label`
- `event_date_quality_tier`
- `min_event_date_quality_score`

This matters because the export layer is not meant to be just a blind dump. It should help answer practical questions like:

- show me only high-quality Phase 3 rows
- show me only model-ready rows
- show me only events mapped to one ticker

### Step 3. A standalone script can export the dataset

The standalone entrypoint is:

- `python scripts/export_historical_trial_events.py`

This script reads environment variables, loads the filtered historical event rows, and prints them as:

- `json`
- `jsonl`

### Step 4. The main runner exposes the same capability

The main project runner now supports:

- `python run.py export-historical-trial-events`

That makes historical-event export part of the official BTQ command surface instead of a one-off utility.

### Step 5. Optional summaries are attached for QA

When summary mode is enabled, the export layer also computes a lightweight QA summary including:

- exported event count
- model-ready event count
- event-date-quality-tier counts
- average event-date-quality score

That makes the export more useful for operational review and dataset snapshots.

## What A Historical Event Export Row Contains

The current export row is intentionally compact but still research-useful.

Important fields include:

- `event_id`
- `analysis_id`
- `nct_id`
- `requested_nct_id`
- `sponsor_name`
- `phase_label`
- `mapped_ticker`
- `event_date_candidate`
- `event_date_source`
- `event_date_source_rank`
- `event_date_confidence`
- `event_date_quality_score`
- `event_date_quality_tier`
- `event_day_return`
- `post_window_return`
- `is_model_ready`
- `warning_count`
- `created_at`

This is enough to support:

- export QA
- event cohort inspection
- quick benchmark slicing
- future demo views

without forcing every consumer to read the entire full analysis payload.

## Why Event-Date Quality Is Central Here

The historical-event export workflow is especially important because it carries event-date quality directly into the exported output.

That means exported rows do not just say:

- what event date was chosen

They also say:

- how strong that event-date proxy looks
- where it came from
- whether it should be trusted for cleaner historical benchmarking

This is one of the biggest reasons the export workflow matters for BTQ. It keeps the uncertainty visible instead of hiding it.

## Supported Output Modes

### `json`

This mode returns a structured payload with:

- status
- generation timestamp
- input filters
- exported rows
- optional summary

This is best for:

- QA inspection
- debugging
- reports
- demo output

### `jsonl`

This mode prints one event row per line.

This is best for:

- piping into downstream tools
- line-by-line processing
- quick machine-readable exports

## Operational Commands

### Export through the main runner

```bash
python run.py export-historical-trial-events --include-summary
```

### Export only model-ready rows

```bash
python run.py export-historical-trial-events --is-model-ready --include-summary
```

### Export only high-quality Phase 3 rows

```bash
python run.py export-historical-trial-events --phase "PHASE 3" --event-date-quality-tier high
```

### Export only one ticker as JSONL

```bash
python run.py export-historical-trial-events --mapped-ticker PFE --format jsonl
```

### Export using the standalone script

```bash
python scripts/export_historical_trial_events.py
```

## How This Fits Into The Bigger Project

This workflow helps connect the dataset-building layers to the final research and comparison layers.

It makes it easier to:

- inspect what the historical cohort actually looks like
- validate whether the stored event rows are good enough for benchmarking
- prepare slices for modeling and expected-reaction analysis
- show concrete artifacts to recruiters, collaborators, and future users

In that sense, the export layer is not just operational convenience. It is part of the project’s research transparency.

## Current Limitations

The export workflow is now implemented and tested, but it is still intentionally simple.

Current limitations include:

- there is not yet a dedicated API endpoint for historical event export
- there is not yet a richer reporting layer built on top of this export
- the summary is intentionally lightweight rather than a full audit report
- more cohort filters will likely be needed later for modeling and analog analysis

These are acceptable limitations for the current stage because the goal right now is a clean and reliable operational export path.

## What Comes Next

The next improvements that would make this workflow stronger are:

- add historical-event export metrics to published summaries
- add richer cohort filters such as therapeutic area and sponsor class
- connect the export output to benchmark and analog analysis workflows
- later expose a hosted or API-facing version for demos

That would turn the current export path into a more complete dataset-distribution layer inside BTQ.
