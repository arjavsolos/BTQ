# Architecture

## Current State

The project now has a dedicated ClinicalTrials.gov ingestion module in:

- `app/ingestion/clinical_trials.py`

That module is responsible only for:

- pulling trial data from the ClinicalTrials.gov v2 API
- flattening nested trial payloads
- returning storage-ready records
- supporting single-trial fetch and paginated search

It is not responsible for:

- sponsor-to-ticker mapping
- OpenFDA ingestion
- historical equity ingestion
- options pricing
- Bayesian or Monte Carlo modeling

## High-Level Data Flow

1. `clinical_trials.py`
- ingest trial metadata
- normalize into one canonical record per `nct_id`

2. `sec_mapping.py`
- map `sponsor_name` to a public company identity
- output a ticker and confidence score

3. `openfda.py`
- gather approval and labeling context
- produce empirical priors by therapeutic area or drug class

4. `market_data.py`
- retrieve historical equity and eventually options data
- align event windows to trial catalyst dates

5. Database layer
- persist trial records
- persist mappings
- persist market event windows

6. Modeling layer
- use trial features, sponsor context, and prior data to estimate success probability
- estimate event risk and expected reaction context from historical analogs
- compare that modeled view to observed or market-implied event pricing

## Core System Principle

Each layer should produce a clean artifact for the next layer.

Examples:

- `clinical_trials.py` produces canonical trial records
- `sec_mapping.py` produces canonical sponsor-to-ticker links
- `market_data.py` produces event-window price records

This keeps the system modular and avoids hidden coupling.

## Canonical Trial Record

The canonical trial record should be the output of `extract_trial_record()` in `clinical_trials.py`.

That record should:

- be stable in shape
- be database-ready
- preserve raw nested structures only when useful
- be keyed by canonical `nct_id`

## Immediate Next Build Targets

1. Finish the storage contract
- align the `clinical_trials` table to the current ingestor output

2. Build sponsor mapping
- use `sponsor_name` from trial records
- store mappings separately from the raw trial table

3. Add ingestion scripts
- fetch trials and upsert them into the database

4. Build event alignment
- connect trial records to public tickers and event dates

5. Build the modeling layer last
- after the data pipeline is stable

## Target Analytical Output

The desired final system output is not an exact point-price target.

The stronger architecture target is a comparison engine that produces:

- modeled success probability
- event-risk or catalyst-risk context
- historical expected-reaction benchmarks
- comparison against the observed or market-implied event setup

In other words, the end of the architecture should answer:

- what does the historical and modeled evidence suggest?
- how uncertain is that estimate?
- how does that compare with what the market appears to be pricing?
