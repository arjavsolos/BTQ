# Methodology

## What The Clinical Trials Ingestor Does

The ClinicalTrials.gov ingestion layer converts the raw v2 API payload into a normalized trial record for downstream analytics.

The normalized record contains:

- identifier metadata
- sponsor metadata
- trial design metadata
- enrollment and eligibility metadata
- condition and intervention metadata
- endpoint metadata
- date and catalyst metadata
- geography and site metadata
- literature and signal metadata

## Why This Matters

ClinicalTrials.gov returns deeply nested JSON that is hard to store and hard to model against directly.

The ingestor solves that by translating one raw study object into a row-like structure that can feed:

- database storage
- sponsor resolution
- prior estimation
- event-study backtesting
- later probability models

## Event Modeling Relevance

The most important fields for the broader project are:

- `nct_id`
- `sponsor_name`
- `overall_status`
- `study_type`
- `phases`
- `enrollment_count`
- `therapeutic_area`
- `intervention_types`
- `primary_endpoint_measures`
- `has_results`
- `event_date_candidate`
- `us_site_count`
- `keyword_hits`

These fields help approximate:

- trial maturity
- trial complexity
- sponsor context
- potential catalyst timing
- disease-area grouping
- operational footprint
- likely market relevance

## What To Finish Next

### 1. Stabilize the schema

Make sure the output of `extract_trial_record()` is treated as a formal contract.

Do this by:

- keeping field names stable
- deciding which fields are mandatory
- documenting which fields are nullable

### 2. Improve event-date logic

`event_date_candidate` is useful, but it is still heuristic.

Add:

- `event_date_source`
- clearer precedence rules

Recommended precedence:

1. `primary_completion_date`
2. `completion_date`
3. `results_first_posted`
4. `last_update_posted`

### 3. Add completeness flags

Examples:

- `has_primary_outcomes`
- `has_locations`
- `has_sponsor`
- `has_interventions`
- `has_reference_support`

These make later filtering much easier.

### 4. Add targeted search filters

Extend the trial query object to support:

- sponsor filters
- condition filters
- intervention filters
- result availability filters

### 5. Persist records into the database

Once the shape is stable, stop thinking of the ingestor as terminal output and start treating it as a real data source.

That means:

- fetch
- normalize
- upsert into `clinical_trials`

### 6. Build sponsor mapping after that

Use `sponsor_name` from the normalized trial record as the input to the mapping layer.

## Completion Standard

The ClinicalTrials ingestion layer is "finished enough" when:

- it reliably fetches and paginates studies
- the normalized output schema is stable
- canonical `nct_id` handling is clear
- event-date logic is explicit
- missing fields do not break extraction
- the records can be inserted into the database without manual cleanup
