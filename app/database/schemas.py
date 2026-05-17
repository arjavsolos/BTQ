CLINICAL_TRIALS_TABLE_SQL = """
create table if not exists clinical_trials (
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
  event_date_source text,
  event_date_source_rank integer,
  event_date_precision text,
  event_date_confidence text,
  event_date_quality_score integer,
  event_date_quality_tier text,
  event_date_quality_issues jsonb,
  locations jsonb,
  location_count integer,
  country_counts jsonb,
  us_site_count integer,
  trial_references jsonb,
  reference_count integer,
  see_also_links jsonb,
  keyword_hits jsonb,
  derived_misc_info jsonb,
  central_contacts jsonb,
  overall_officials jsonb,
  ipd_sharing text,
  source_system text default 'clinicaltrials.gov',
  source_api_version text default 'v2',
  has_sponsor boolean,
  has_primary_outcomes boolean,
  has_secondary_outcomes boolean,
  has_locations boolean,
  has_interventions boolean,
  has_reference_support boolean,
  has_eligibility boolean,
  has_event_date boolean,
  has_results_flag boolean,
  data_completeness_score integer,
  data_completeness_ratio double precision,
  ingested_at timestamptz default now(),
  updated_at timestamptz default now()
);
"""


CLINICAL_TRIALS_INDEX_SQL = [
    "create index if not exists clinical_trials_sponsor_name_idx on clinical_trials (sponsor_name);",
    "create index if not exists clinical_trials_overall_status_idx on clinical_trials (overall_status);",
    "create index if not exists clinical_trials_phase_score_idx on clinical_trials (phase_score);",
    "create index if not exists clinical_trials_therapeutic_area_idx on clinical_trials (therapeutic_area);",
    "create index if not exists clinical_trials_event_date_candidate_idx on clinical_trials (event_date_candidate);",
    (
        "create index if not exists clinical_trials_event_date_source_rank_idx "
        "on clinical_trials (event_date_source_rank);"
    ),
    (
        "create index if not exists clinical_trials_event_date_quality_score_idx "
        "on clinical_trials (event_date_quality_score);"
    ),
    "create index if not exists clinical_trials_has_results_idx on clinical_trials (has_results);",
]


CLINICAL_TRIALS_MIGRATION_SQL = [
    "alter table clinical_trials add column if not exists event_date_source_rank integer;",
    "alter table clinical_trials add column if not exists event_date_confidence text;",
    "alter table clinical_trials add column if not exists event_date_quality_score integer;",
    "alter table clinical_trials add column if not exists event_date_quality_tier text;",
    "alter table clinical_trials add column if not exists event_date_quality_issues jsonb;",
]


TRIAL_ANALYSES_TABLE_SQL = """
create table if not exists trial_analyses (
  analysis_id bigserial primary key,
  nct_id text not null references clinical_trials (nct_id) on delete cascade,
  requested_nct_id text,
  mapped_ticker text,
  mapped_cik text,
  sponsor_name text,
  event_date_candidate text,
  event_date_source text,
  overall_status text,
  phase_label text,
  therapeutic_area text,
  approval_record_count integer,
  market_record_count integer,
  event_day_return double precision,
  post_window_return double precision,
  warning_count integer not null default 0,
  analysis_version text not null default '1.0',
  analysis_payload jsonb not null,
  created_at timestamptz default now()
);
"""


TRIAL_ANALYSES_INDEX_SQL = [
    "create index if not exists trial_analyses_nct_id_idx on trial_analyses (nct_id);",
    "create index if not exists trial_analyses_mapped_ticker_idx on trial_analyses (mapped_ticker);",
    "create index if not exists trial_analyses_created_at_idx on trial_analyses (created_at desc);",
]


HISTORICAL_TRIAL_EVENTS_TABLE_SQL = """
create table if not exists historical_trial_events (
  event_id bigserial primary key,
  analysis_id bigint references trial_analyses (analysis_id) on delete set null,
  nct_id text not null references clinical_trials (nct_id) on delete cascade,
  requested_nct_id text,
  brief_title text,
  sponsor_name text,
  sponsor_class text,
  overall_status text,
  phase_label text,
  phase_score integer,
  study_type text,
  therapeutic_area text,
  enrollment_count integer,
  has_results boolean,
  data_completeness_score integer,
  data_completeness_ratio double precision,
  event_date_candidate text,
  event_date_source text,
  event_date_source_rank integer,
  event_date_precision text,
  event_date_confidence text,
  event_date_quality_score integer,
  event_date_quality_tier text,
  mapped_ticker text,
  mapped_cik text,
  matched_company_name text,
  mapping_confidence double precision,
  mapping_match_type text,
  approval_record_count integer not null default 0,
  approval_application_numbers jsonb,
  approval_brand_names jsonb,
  approval_sponsor_names jsonb,
  market_record_count integer,
  trade_start text,
  trade_end text,
  prior_close double precision,
  event_close double precision,
  latest_close double precision,
  event_day_return double precision,
  post_window_return double precision,
  warning_count integer not null default 0,
  warnings jsonb not null default '[]'::jsonb,
  is_model_ready boolean not null default false,
  dataset_version text not null default '1.0',
  source_analysis_version text,
  feature_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz default now(),
  updated_at timestamptz default now(),
  unique (nct_id, event_date_candidate, mapped_ticker)
);
"""


HISTORICAL_TRIAL_EVENTS_INDEX_SQL = [
    "create index if not exists historical_trial_events_nct_id_idx on historical_trial_events (nct_id);",
    "create index if not exists historical_trial_events_ticker_idx on historical_trial_events (mapped_ticker);",
    (
        "create index if not exists historical_trial_events_event_date_idx "
        "on historical_trial_events (event_date_candidate);"
    ),
    (
        "create index if not exists historical_trial_events_event_date_source_rank_idx "
        "on historical_trial_events (event_date_source_rank);"
    ),
    (
        "create index if not exists historical_trial_events_event_date_confidence_idx "
        "on historical_trial_events (event_date_confidence);"
    ),
    (
        "create index if not exists historical_trial_events_event_date_quality_score_idx "
        "on historical_trial_events (event_date_quality_score);"
    ),
    (
        "create index if not exists historical_trial_events_model_ready_idx "
        "on historical_trial_events (is_model_ready);"
    ),
    "create index if not exists historical_trial_events_created_at_idx on historical_trial_events (created_at desc);",
]


HISTORICAL_TRIAL_EVENTS_MIGRATION_SQL = [
    "alter table historical_trial_events add column if not exists event_date_source_rank integer;",
    "alter table historical_trial_events add column if not exists event_date_confidence text;",
    "alter table historical_trial_events add column if not exists event_date_quality_score integer;",
    "alter table historical_trial_events add column if not exists event_date_quality_tier text;",
]


SPONSOR_MAPPING_REVIEWS_TABLE_SQL = """
create table if not exists sponsor_mapping_reviews (
  review_id bigserial primary key,
  sponsor_name text not null,
  normalized_sponsor_name text not null,
  source_nct_id text references clinical_trials (nct_id) on delete set null,
  suggested_company_name text,
  suggested_ticker text,
  suggested_cik text,
  suggested_confidence double precision,
  suggested_match_type text,
  alternatives jsonb not null default '[]'::jsonb,
  review_status text not null default 'pending',
  reviewed_mapping_status text not null default 'unreviewed',
  reviewed_company_name text,
  reviewed_ticker text,
  reviewed_cik text,
  reviewer_name text,
  reviewer_email text,
  review_notes text,
  reviewed_at timestamptz,
  created_at timestamptz default now(),
  updated_at timestamptz default now(),
  unique (normalized_sponsor_name)
);
"""


SPONSOR_MAPPING_REVIEWS_INDEX_SQL = [
    (
        "create index if not exists sponsor_mapping_reviews_review_status_idx "
        "on sponsor_mapping_reviews (review_status);"
    ),
    (
        "create index if not exists sponsor_mapping_reviews_suggested_ticker_idx "
        "on sponsor_mapping_reviews (suggested_ticker);"
    ),
    (
        "create index if not exists sponsor_mapping_reviews_reviewed_mapping_status_idx "
        "on sponsor_mapping_reviews (reviewed_mapping_status);"
    ),
    (
        "create index if not exists sponsor_mapping_reviews_source_nct_id_idx "
        "on sponsor_mapping_reviews (source_nct_id);"
    ),
    (
        "create index if not exists sponsor_mapping_reviews_reviewed_ticker_idx "
        "on sponsor_mapping_reviews (reviewed_ticker);"
    ),
    (
        "create index if not exists sponsor_mapping_reviews_created_at_idx "
        "on sponsor_mapping_reviews (created_at desc);"
    ),
]


SPONSOR_MAPPING_REVIEWS_MIGRATION_SQL = [
    (
        "alter table sponsor_mapping_reviews add column if not exists "
        "reviewed_mapping_status text not null default 'unreviewed';"
    ),
]
