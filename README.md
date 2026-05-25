# BTQ

BTQ is a biotech event intelligence platform that turns public clinical-trial, regulatory, and market data into an auditable historical catalyst dataset for probability, event-risk, and expected-reaction analysis.

The project is being built toward a final system that:

- constructs an auditable historical dataset of clinical trial catalysts
- links those events to public-market entities
- measures biological and data uncertainty explicitly
- models trial success probability and event risk
- compares that modeled view to observed market behavior

The intended final output is not an exact point-price prediction.

The stronger end-state is a comparison engine that produces:

- modeled success probability
- event-risk context
- historically grounded expected reaction
- comparison against the observed or market-implied market setup

The canonical project definition lives in:

- `docs/final_product_definition.md`
- `docs/methodology.md`
- `app/research/methodology.py`

Print the current capability and production-readiness snapshot:

```bash
python run.py project-status --format markdown
```

## Readiness Check

Before running backfills or analysis workflows, verify the local environment:

```bash
python run.py check-readiness
```

For a quick dependency and configuration check without opening a database connection:

```bash
python run.py check-readiness --skip-db
```

The API registry also exposes a lightweight health route that runs the same fast readiness check without touching the database by default.

Set `BTQ_DEPLOYMENT_PROFILE` to `local`, `demo`, or `ci` so readiness checks validate the right environment requirements for the run.

## Demo Publishing

Preview the curated model-ready subset that would be published to a hosted demo database:

```bash
python run.py publish-demo-dataset
```

Apply the copy to the configured demo database:

```bash
python run.py publish-demo-dataset --apply
```

## Analysis Reports

Generate a shareable Markdown report for a trial analysis:

```bash
python run.py analyze-trial NCT00000001 --format markdown --output-path reports/NCT00000001.md
```
