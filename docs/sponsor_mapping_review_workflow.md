# Sponsor Mapping Review Workflow

This document explains how sponsor-mapping review works in BTQ, why it exists, what data flows through it, and how it fits into the larger clinical-trial research pipeline.

## Why This Workflow Exists

ClinicalTrials.gov stores sponsor names as raw text.

Examples:

- `Pfizer Inc.`
- `Pfizer Inc. (Lead Sponsor)`
- `Acme Bio Holdings, LLC`
- `XYZ Therapeutics / ABC Research Group`

Financial and market analysis, however, requires a much stricter entity identity:

- public company name
- stock ticker
- CIK

That creates a difficult entity-resolution problem. A trial sponsor string is not automatically a safe public-market identity.

If the mapping is wrong, then all downstream analysis can become wrong:

- the wrong stock can be linked to the trial
- the wrong market reaction can be measured
- the wrong historical event row can be stored
- later predictive models can learn from incorrect relationships

Because of that, BTQ does not treat sponsor mapping as something that should always be fully trusted without review.

The sponsor-mapping review workflow exists to:

- capture unresolved or weak sponsor matches
- preserve the machine-generated suggestion
- preserve alternative candidate matches
- allow later human review and correction
- create an auditable record of mapping decisions

## Where The Workflow Lives In The Codebase

The current sponsor-mapping review workflow spans four layers.

### 1. Mapping logic

- `app/ingestion/sec_mapping.py`

This layer performs the raw sponsor-to-company matching using:

- normalization
- exact matching
- token overlap
- fuzzy similarity

It returns a `SponsorMatchResult` object containing:

- sponsor name
- matched company name
- ticker
- CIK
- confidence
- match type
- alternatives

### 2. Review persistence

- `app/database/schemas.py`
- `app/database/repositories.py`

This layer defines and stores review rows in the `sponsor_mapping_reviews` table.

### 3. Review decision logic

- `app/services/sponsor_mapping_review_service.py`

This layer decides whether a mapping should be queued for review and builds the review record.

### 4. Export and operational access

- `scripts/export_sponsor_mapping_reviews.py`
- `run.py`

This layer lets the project export queued reviews in JSON or JSONL format.

## The Current Workflow Step By Step

### Step 1. A sponsor name is extracted from trial data

The upstream trial-ingestion layer normalizes a ClinicalTrials.gov study into a canonical trial record. One field in that record is:

- `sponsor_name`

That is the raw sponsor identity used as the input to the SEC matching system.

### Step 2. The SEC mapping layer generates a machine match

The sponsor name is passed into the SEC mapping logic.

The matcher produces one of several possible outcomes:

- a high-confidence exact normalized match
- a token-overlap match
- a lower-confidence fuzzy match
- no confident match at all

The output includes:

- the best suggested company
- the best suggested ticker
- the best suggested CIK
- confidence score
- match type
- alternatives

### Step 3. The review service decides whether the mapping needs human review

The review service applies a review policy to the machine-generated result.

Right now, the mapping is considered review-worthy when:

- no ticker is found
- confidence falls below the configured review threshold
- the match type is weak enough to justify extra caution

The default review threshold is currently:

- `0.85`

That means not every mapping becomes a review item. Strong exact matches can pass automatically, while ambiguous mappings are queued for inspection.

### Step 4. A normalized review key is created

Before the review row is stored, the sponsor name is normalized into a canonical key.

Example:

- `Pfizer Inc.`
- `Pfizer Inc`
- `Pfizer Inc. (Lead Sponsor)`

may all normalize to:

- `pfizer`

This prevents the project from creating multiple review rows for what is really the same sponsor identity.

### Step 5. A review row is upserted into the database

The review service builds a review record and hands it to the repository layer.

The repository uses an upsert pattern keyed by:

- `normalized_sponsor_name`

That means:

- a new unresolved sponsor gets inserted once
- later refinements update the same logical review row instead of creating duplicates

This is important because sponsor review is iterative. A mapping can improve over time as:

- registry data changes
- logic improves
- a human reviewer makes a decision

### Step 6. Reviews can be exported for operational use

Once review rows exist, they can be exported through:

- `python run.py export-sponsor-mapping-reviews`

or

- `python scripts/export_sponsor_mapping_reviews.py`

Supported filters currently include:

- review status
- suggested ticker
- reviewer email
- limit
- offset

Supported output formats currently include:

- `json`
- `jsonl`

### Step 7. Approved reviews can become effective mapping overrides

Once a review row has been marked as approved, BTQ can treat it as a reusable mapping decision instead of only as stored metadata.

That matters because a human-reviewed mapping should be able to improve downstream analysis. Otherwise the system would know that the machine suggestion was wrong, but still continue to use the wrong ticker later.

The sponsor-mapping review service now supports two operational behaviors:

- saving a review decision as an approved or rejected final mapping
- applying an approved reviewed mapping back onto future sponsor-resolution calls

In practice, that means:

- if the reviewer approves the original machine suggestion, BTQ can reuse that approved mapping
- if the reviewer overrides the original machine suggestion, BTQ can reuse the override instead

This gives the project a clean path from:

- machine suggestion
- to review queue
- to reviewed final identity
- to downstream analysis reuse

That is an important step toward making sponsor mapping auditable and self-improving over time.

## What Data A Review Row Stores

The `sponsor_mapping_reviews` table is designed to preserve both the machine suggestion and the human-reviewed outcome.

Important fields include:

- `sponsor_name`
- `normalized_sponsor_name`
- `source_nct_id`
- `suggested_company_name`
- `suggested_ticker`
- `suggested_cik`
- `suggested_confidence`
- `suggested_match_type`
- `alternatives`
- `review_status`
- `reviewed_mapping_status`
- `reviewed_company_name`
- `reviewed_ticker`
- `reviewed_cik`
- `reviewer_name`
- `reviewer_email`
- `review_notes`
- `reviewed_at`

This structure is important because it preserves:

- the raw input identity
- the machine-generated suggestion
- the alternative candidates
- the final reviewed outcome

That makes the workflow auditable instead of opaque.

## What Review Status Means

The review table currently supports a `review_status` field.

Right now the core intended states are:

- `pending`
- `approved`
- `rejected`

The meaning of each state is:

### `pending`

The machine-generated mapping needs human review or confirmation.

### `approved`

The review has been accepted and a final reviewed identity can be trusted for later use.

### `rejected`

The machine-generated suggestion should not be trusted as the final mapping.

Future states could be added later if needed, but these three cover the current workflow well.

## What Reviewed Mapping Status Means

The table also stores a separate field:

- `reviewed_mapping_status`

This is different from `review_status`.

The easiest way to think about it is:

- `review_status` answers: has someone reviewed this row yet?
- `reviewed_mapping_status` answers: what was the actual mapping outcome?

That distinction matters because an approved review can still mean two different things:

- the reviewer accepted the machine-suggested mapping
- the reviewer overrode the machine suggestion and chose a different mapping

The current intended values are:

- `unreviewed`
- `approved_suggested`
- `approved_override`
- `rejected`

The meaning of each state is:

### `unreviewed`

The row is still waiting for human review, so no final mapping outcome has been accepted yet.

### `approved_suggested`

The reviewer approved the same company identity that the machine originally suggested.

This is the best-case outcome for a strong but review-worthy match because it confirms that the automated mapping was directionally correct.

### `approved_override`

The reviewer approved the row, but changed the final company identity away from the original machine suggestion.

This is especially important analytically because it lets BTQ distinguish:

- machine suggestions that were correct
- machine suggestions that needed human correction

That will matter later for sponsor-mapping evaluation and error analysis.

### `rejected`

The machine suggestion was not accepted as a valid final mapping.

In practice, this means the row should not be treated as a clean reviewed sponsor-to-ticker identity unless additional work is done later.

## Why Alternatives Matter

The `alternatives` field is especially useful.

If a sponsor cannot be matched confidently, the system still keeps a small list of plausible candidates. That makes human review much easier because the reviewer does not have to start from zero.

Instead of seeing:

- `no match`

the reviewer may see:

- candidate A with confidence 0.74
- candidate B with confidence 0.69
- candidate C with confidence 0.62

That makes the review process faster and more informed.

## Current Limitations

The sponsor-mapping review workflow is now structurally present, but it is still in an early operational stage.

Current limitations include:

- review rows are not yet automatically queued from every relevant analysis path
- there is not yet a dedicated human-review UI
- there is not yet a reviewed-mapping override path wired back into the analysis pipeline
- review metrics are not yet summarized in a dedicated sponsor-mapping evaluation report

So this workflow should currently be understood as:

- implemented
- storable
- exportable
- test-covered

but not yet fully closed-loop.

## How This Fits Into The Bigger Project

This workflow is not just an isolated data-cleaning feature. It supports the broader BTQ research thesis.

The project depends on correctly linking:

- clinical trials
- sponsors
- public companies
- historical market reactions

That means sponsor identity quality is one of the foundational controls for the whole system.

In the bigger picture, this workflow helps BTQ become:

- more auditable
- more dataset-driven
- more trustworthy for later backtests
- more credible for future modeling

Without this workflow, the sponsor-mapping layer would be a black box. With it, sponsor mapping becomes something measurable, reviewable, and eventually improvable over time.

## Operational Commands

Current useful commands:

### Export sponsor reviews through the main runner

```bash
python run.py export-sponsor-mapping-reviews --include-summary
```

### Export sponsor reviews as JSONL

```bash
python run.py export-sponsor-mapping-reviews --format jsonl
```

### Export only pending sponsor reviews

```bash
python run.py export-sponsor-mapping-reviews --review-status pending --include-summary
```

### Export only reviews associated with a suggested ticker

```bash
python run.py export-sponsor-mapping-reviews --suggested-ticker PFE
```

## What Comes Next

The next steps that would make this workflow stronger are:

- automatically queue review rows during trial analysis when mappings are weak
- add sponsor-mapping review summaries to research reports
- add reviewed-mapping overrides to the live analysis pipeline
- add a sponsor-mapping evaluation layer for benchmarking mapping quality over time

Those steps will turn the current workflow from a review queue into a full sponsor-identity quality-control system.
