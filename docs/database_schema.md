# Clinical Trials Schema

This document defines the target storage schema for the ClinicalTrials.gov ingestion layer in `app/ingestion/clinical_trials.py`.

## Purpose

The `clinical_trials` table is the canonical storage layer for normalized trial metadata. It should:

- preserve one row per canonical `nct_id`
- keep the most queryable fields as normal SQL columns
- keep deeply nested source structures as JSONB
- support joins into sponsor mapping, FDA priors, and market-event backtests

## Primary Rule

- Use `nct_id` as the true primary key.
- Keep `requested_nct_id` for traceability.
- Do not create duplicate rows when an alias resolves to the same canonical `nct_id`.

## Recommended Table: `clinical_trials`

### Core identifiers

- `nct_id` `TEXT PRIMARY KEY`
- `requested_nct_id` `TEXT`
- `org_study_id` `TEXT`
- `acronym` `TEXT`
- `nct_aliases` `JSONB`
- `secondary_ids` `JSONB`

### Titles and sponsor

- `brief_title` `TEXT`
- `official_title` `TEXT`
- `sponsor_name` `TEXT`
- `sponsor_class` `TEXT`
- `collaborators` `JSONB`
- `responsible_party` `JSONB`

### Trial status and design

- `overall_status` `TEXT`
- `why_stopped` `TEXT`
- `status_verified_date` `TEXT`
- `has_results` `BOOLEAN`
- `expanded_access` `BOOLEAN`
- `study_type` `TEXT`
- `phases` `JSONB`
- `phase_label` `TEXT`
- `phase_score` `INTEGER`
- `allocation` `TEXT`
- `intervention_model` `TEXT`
- `primary_purpose` `TEXT`
- `masking` `TEXT`

### Enrollment and population

- `enrollment_count` `INTEGER`
- `enrollment_type` `TEXT`
- `healthy_volunteers` `BOOLEAN`
- `sex` `TEXT`
- `minimum_age` `TEXT`
- `maximum_age` `TEXT`
- `std_ages` `JSONB`
- `eligibility_criteria` `TEXT`

### Disease and intervention metadata

- `therapeutic_area` `TEXT`
- `conditions` `JSONB`
- `condition_keywords` `JSONB`
- `interventions` `JSONB`
- `intervention_names` `JSONB`
- `intervention_types` `JSONB`
- `arm_groups` `JSONB`

### Endpoint and catalyst metadata

- `primary_outcomes` `JSONB`
- `secondary_outcomes` `JSONB`
- `other_outcomes` `JSONB`
- `primary_endpoint_measures` `JSONB`
- `secondary_endpoint_measures` `JSONB`
- `brief_summary` `TEXT`
- `detailed_description` `TEXT`
- `keyword_hits` `JSONB`

### Regulatory and oversight flags

- `fda_regulated_drug` `BOOLEAN`
- `fda_regulated_device` `BOOLEAN`
- `has_dmc` `BOOLEAN`
- `ipd_sharing` `TEXT`

### Date fields

- `start_date` `TEXT`
- `primary_completion_date` `TEXT`
- `completion_date` `TEXT`
- `study_first_posted` `TEXT`
- `results_first_posted` `TEXT`
- `last_update_posted` `TEXT`
- `event_date_candidate` `TEXT`
- `event_date_source` `TEXT`
- `event_date_precision` `TEXT`
- `event_date_confidence` `TEXT`
- `event_date_precision` `TEXT`
- `event_date_confidence` `TEXT`

### Site and geography data

- `locations` `JSONB`
- `location_count` `INTEGER`
- `country_counts` `JSONB`
- `us_site_count` `INTEGER`
- `central_contacts` `JSONB`
- `overall_officials` `JSONB`

### Literature and provenance

- `references` `JSONB`
- `reference_count` `INTEGER`
- `see_also_links` `JSONB`
- `derived_misc_info` `JSONB`

### Audit fields

- `source_system` `TEXT DEFAULT 'clinicaltrials.gov'`
- `source_api_version` `TEXT DEFAULT 'v2'`
- `ingested_at` `TIMESTAMPTZ DEFAULT now()`
- `updated_at` `TIMESTAMPTZ DEFAULT now()`

## Recommended Indexes

- `INDEX clinical_trials_sponsor_name_idx ON clinical_trials (sponsor_name)`
- `INDEX clinical_trials_overall_status_idx ON clinical_trials (overall_status)`
- `INDEX clinical_trials_phase_score_idx ON clinical_trials (phase_score)`
- `INDEX clinical_trials_therapeutic_area_idx ON clinical_trials (therapeutic_area)`
- `INDEX clinical_trials_event_date_candidate_idx ON clinical_trials (event_date_candidate)`
- `INDEX clinical_trials_has_results_idx ON clinical_trials (has_results)`

## Recommended JSONB Index Targets

If query volume grows, add GIN indexes for:

- `conditions`
- `intervention_names`
- `intervention_types`
- `keyword_hits`

## Suggested Follow-On Tables

### `companies`

Purpose:
- maps sponsor names to public-market entities

Core fields:
- `ticker`
- `company_name`
- `normalized_company_name`
- `cik`
- `exchange`
- `market_cap`

### `trial_company_links`

Purpose:
- stores the sponsor-to-ticker mapping separately from raw trial ingestion

Core fields:
- `nct_id`
- `sponsor_name`
- `ticker`
- `mapping_method`
- `mapping_confidence`
- `is_primary_match`

### `trial_market_events`

Purpose:
- stores event-study pricing windows around trial catalysts

Core fields:
- `nct_id`
- `ticker`
- `event_date`
- `event_date_source`
- `event_date_confidence`
- `pre_event_close`
- `event_close`
- `post_1d_return`
- `post_3d_return`
- `volume_change`

## Data Contract Notes

- `nct_id` is canonical and should be unique.
- `requested_nct_id` may differ from `nct_id` because alias IDs can resolve to the same study.
- Date fields are currently stored as strings because ClinicalTrials.gov sometimes returns partial dates like `2008-10`.
- `event_date_confidence` captures the current heuristic confidence level of the chosen catalyst-date proxy.
- Nested arrays and source-rich objects should remain JSONB until there is a proven need to normalize them further.

## Minimal SQL Shape

```sql
create table clinical_trials (
  nct_id text primary key,
  requested_nct_id text,
  org_study_id text,
  acronym text,
  nct_aliases jsonb,
  secondary_ids jsonb,
  brief_title text,
  official_title text,
  sponsor_name text,
  sponsor_class text,
  collaborators jsonb,
  responsible_party jsonb,
  overall_status text,
  why_stopped text,
  status_verified_date text,
  has_results boolean,
  expanded_access boolean,
  study_type text,
  phases jsonb,
  phase_label text,
  phase_score integer,
  allocation text,
  intervention_model text,
  primary_purpose text,
  masking text,
  enrollment_count integer,
  enrollment_type text,
  therapeutic_area text,
  conditions jsonb,
  condition_keywords jsonb,
  interventions jsonb,
  intervention_names jsonb,
  intervention_types jsonb,
  arm_groups jsonb,
  primary_outcomes jsonb,
  secondary_outcomes jsonb,
  other_outcomes jsonb,
  primary_endpoint_measures jsonb,
  secondary_endpoint_measures jsonb,
  brief_summary text,
  detailed_description text,
  eligibility_criteria text,
  healthy_volunteers boolean,
  sex text,
  minimum_age text,
  maximum_age text,
  std_ages jsonb,
  fda_regulated_drug boolean,
  fda_regulated_device boolean,
  has_dmc boolean,
  start_date text,
  primary_completion_date text,
  completion_date text,
  study_first_posted text,
  results_first_posted text,
  last_update_posted text,
  event_date_candidate text,
  locations jsonb,
  location_count integer,
  country_counts jsonb,
  us_site_count integer,
  references jsonb,
  reference_count integer,
  see_also_links jsonb,
  keyword_hits jsonb,
  derived_misc_info jsonb,
  central_contacts jsonb,
  overall_officials jsonb,
  ipd_sharing text,
  source_system text default 'clinicaltrials.gov',
  source_api_version text default 'v2',
  ingested_at timestamptz default now(),
  updated_at timestamptz default now()
);
```
