# Event-Date Review Workflow

This document explains how event-date review works in BTQ, why it exists, what data flows through it, and how it fits into the broader trial-event research pipeline.

## Why This Workflow Exists

ClinicalTrials.gov exposes milestone dates, but those dates are not always the exact public market-moving catalyst date.

Examples of potential proxy issues include:

- month-only completion dates
- low-ranked fallback sources such as `last_update_posted`
- records with weak timing confidence
- rows where the stored event date is usable for normalization but still questionable for market analysis

If BTQ silently treats every stored event date as equally trustworthy, then downstream work can become weaker:

- market event windows can be misaligned
- historical event rows can overstate their quality
- benchmark outputs can mix strong catalyst dates with weak proxy dates
- later models can learn from noisy timing labels

Because of that, BTQ treats event-date quality as something measurable and reviewable, not something that should always be blindly trusted.

The event-date review workflow exists to:

- capture weak or ambiguous event-date proxies
- preserve the current chosen event date and why it looks weak
- support later human-reviewed event-date overrides
- create an auditable record of timing-quality decisions

## Where The Workflow Lives In The Codebase

The current event-date review workflow spans four layers.

### 1. Event-date quality logic

- `app/services/event_date_quality_service.py`

This layer scores event-date strength using:

- source rank
- date precision
- confidence heuristics
- quality score and tier
- issue flags

### 2. Review persistence

- `app/database/schemas.py`
- `app/database/repositories.py`

This layer defines and stores review rows in the `event_date_reviews` table.

### 3. Review decision logic

- `app/services/event_date_review_service.py`

This layer decides whether an event date needs review, derives review reasons, builds review records, and handles review decisions.

### 4. Operational access

- `scripts/export_event_date_reviews.py`
- `run.py`

This layer lets the project export queued event-date reviews in JSON or JSONL format.

## The Current Workflow Step By Step

### Step 1. BTQ selects an event-date proxy

During trial normalization, BTQ chooses an `event_date_candidate` from the available milestone fields.

That selection is stored together with:

- `event_date_source`
- `event_date_source_rank`
- `event_date_precision`
- `event_date_confidence`
- `event_date_quality_score`
- `event_date_quality_tier`
- `event_date_quality_issues`

This means event-date review starts from a concrete and auditable proxy rather than from raw unstructured metadata.

### Step 2. Trial analysis evaluates whether the proxy needs review

During end-to-end trial analysis, BTQ now passes the normalized trial record into the event-date review service.

The review service currently treats an event date as review-worthy when:

- no event-date candidate exists
- the date is not day precision
- the quality tier is `low` or `unknown`
- the quality score falls below the configured threshold

The default quality-score threshold is currently:

- `70`

That means strong day-precision catalyst-date proxies can pass without review, while weaker timing proxies are queued.

### Step 3. The service derives a review reason

When review is needed, the service stores a concrete reason explaining why.

Current reasons include:

- `missing_event_date_candidate`
- `non_day_precision_event_date`
- `low_event_date_quality_score`
- `low_event_date_quality`
- `unknown_event_date_quality`
- `low_rank_event_date_source`
- `low_confidence_event_date`

This is important because a queue without reasons is much harder to interpret operationally.

### Step 4. A review row is upserted into the database

The event-date review service builds a review record and passes it to the repository.

The repository upserts by:

- `nct_id`

That means:

- one trial has one canonical event-date review row
- later re-analysis updates the same logical review entry instead of creating duplicates

This is the right pattern because event-date review is iterative, not one-shot.

### Step 5. The queue result is attached back onto trial analysis

When an event date is queued for review, the analysis result now includes:

- `event_date_review`

and also adds a warning explaining that the event date was queued because the catalyst-date proxy looks weak or ambiguous.

That makes the workflow visible during normal use instead of hiding it entirely inside the database.

### Step 6. Human review decisions can be submitted later

The event-date review service also supports review decisions.

An approved decision can:

- keep the original event date
- or explicitly store a reviewed override event date and source

This creates a clean path from:

- machine-selected proxy
- to review queue
- to reviewed final event date

## What Data A Review Row Stores

The `event_date_reviews` table is designed to preserve both the current proxy and the later reviewed outcome.

Important fields include:

- `nct_id`
- `requested_nct_id`
- `sponsor_name`
- `mapped_ticker`
- `event_date_candidate`
- `event_date_source`
- `event_date_source_rank`
- `event_date_precision`
- `event_date_confidence`
- `event_date_quality_score`
- `event_date_quality_tier`
- `event_date_quality_issues`
- `review_reason`
- `review_status`
- `reviewed_event_date`
- `reviewed_event_date_source`
- `reviewer_name`
- `reviewer_email`
- `review_notes`
- `reviewed_at`

This structure is important because it preserves:

- the machine-selected event-date proxy
- the quality signals behind that proxy
- the reason it was queued
- the final reviewed outcome

That makes the timing workflow auditable instead of opaque.

## How Reviewer Notes Work

Reviewer notes are intended to capture the rationale behind accepting or overriding an event-date proxy.

Examples of useful notes include:

- why the original milestone date looked too weak
- what public source supported the override
- whether the date came from company guidance, a press release, or another confirmed source

BTQ treats event-date reviewer notes as a running audit trail rather than a disposable text field.

In practice, that means:

- note text is normalized
- new note entries are appended instead of overwriting old ones
- note entries carry decision context such as status and reviewer identity when available

That makes later QA and methodology writing much easier.

## What Review Status Means

The event-date review table currently supports:

- `pending`
- `approved`
- `rejected`

The meaning of each state is:

### `pending`

The event-date proxy still needs human review or confirmation.

### `approved`

The event-date proxy or reviewed override has been accepted as the best current event-date choice.

### `rejected`

The current proxy should not be treated as an accepted final event-date choice without more work.

## Why This Workflow Matters For BTQ

This workflow is not just a side utility. It supports one of the core research-quality controls in the project.

BTQ depends on correctly linking:

- trials
- companies
- event dates
- market reactions

That means event-date quality is one of the foundational controls for the entire research dataset.

In the bigger picture, this workflow helps BTQ become:

- more auditable
- more honest about timing uncertainty
- more credible for historical benchmarking
- more trustworthy for later probability and expected-reaction modeling

Without this workflow, event dates risk becoming a hidden source of label noise. With it, timing quality becomes something explicit and improvable.

## Operational Commands

Current useful commands:

### Export event-date reviews through the main runner

```bash
python run.py export-event-date-reviews --include-summary
```

### Export event-date reviews as JSONL

```bash
python run.py export-event-date-reviews --format jsonl
```

### Export only pending event-date reviews

```bash
python run.py export-event-date-reviews --review-status pending --include-summary
```

### Export only low-tier event-date reviews for one ticker

```bash
python run.py export-event-date-reviews --mapped-ticker PFE --event-date-quality-tier low
```

### Export using the standalone script

```bash
python scripts/export_event_date_reviews.py
```

## Current Limitations

The event-date review workflow is now structurally present, but it is still in an early operational stage.

Current limitations include:

- there is not yet a dedicated human-review UI
- reviewed event-date overrides are not yet applied back into all downstream analysis paths
- event-date review metrics are not yet summarized in a dedicated timing-quality evaluation report
- the workflow currently focuses on queueing and export, not full review analytics

So this workflow should currently be understood as:

- implemented
- storable
- queueable during analysis
- exportable
- test-covered

but not yet fully closed-loop.

## What Comes Next

The next steps that would make this workflow stronger are:

- apply approved reviewed event dates back into trial analysis and historical event construction
- add event-date review summaries to dataset audits and reports
- add timing-quality evaluation metrics over reviewed examples
- later expose the review queue through an API or hosted workflow

Those steps will turn the current queue into a fuller event-date quality-control system inside BTQ.
