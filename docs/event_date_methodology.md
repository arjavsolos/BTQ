# Event-Date Methodology

BTQ treats event dates as explicit catalyst-date proxies rather than assuming every stored milestone is a perfect market-moving announcement date.

The current event-date workflow stores:

- `event_date_candidate`
- `event_date_source`
- `event_date_source_rank`
- `event_date_precision`
- `event_date_confidence`
- `event_date_quality_score`
- `event_date_quality_tier`
- `event_date_quality_issues`

The next stage of this methodology is an event-date review queue for rows where the chosen proxy still needs human judgment.

That review queue is now grounded by the `event_date_reviews` table, which is intended to store:

- the currently selected event-date proxy
- the quality signals that explain why it may be weak
- a review reason
- a workflow status
- a later human-reviewed event-date override if needed

This makes event-date quality control auditable in the same spirit as sponsor-mapping review.

Approved event-date reviews can now also feed back into trial analysis, so reviewed timing corrections are no longer only stored for later export.

The current operational export path for queued event-date reviews is:

- `python scripts/export_event_date_reviews.py`
- `python run.py export-event-date-reviews`

That export layer is intended for QA, manual review, and later workflow/report integration.

The full operational workflow is documented in:

- `docs/event_date_review_workflow.md`
