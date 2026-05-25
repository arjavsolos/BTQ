# BTQ Setup On A New Computer

## Recommended Setup

Use this project with:

- local code from GitHub
- a Python virtual environment on each machine
- Neon as the shared hosted database
- local Postgres only if you want a private development database

This gives you one shared dataset across multiple computers.

## 1. Install Prerequisites

- Python `3.12`
- Git
- optional: local PostgreSQL for development

## 2. Clone The Repo

```bash
git clone <your-repo-url>
cd BTQ
```

## 3. Create The Virtual Environment

```bash
python -m venv venv
venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## 4. Create The `.env`

For a shared cross-computer setup, use Neon:

```env
DATABASE_TARGET=neon
NEON_DATABASE_URL=postgresql://...
DATABASE_POOL_ENABLED=true
DATABASE_APPLICATION_NAME=btq
```

Optional local development settings:

```env
LOCAL_DATABASE_URL=postgresql://username:password@localhost:5432/postgres
SYNC_SOURCE_DATABASE_URL=postgresql://username:password@localhost:5432/postgres
SYNC_TARGET_DATABASE_URL=postgresql://...
```

## 5. Verify The Setup

```bash
.\venv\Scripts\python.exe run.py check-readiness --skip-db
.\venv\Scripts\python.exe run.py check-readiness
```

## 6. Use The Shared Hosted Dataset

Run a trial analysis:

```bash
.\venv\Scripts\python.exe run.py analyze-trial NCT00276653 --format markdown
```

Run a benchmark:

```bash
.\venv\Scripts\python.exe run.py benchmark-event-returns --group-by therapeutic_area --format markdown
```

## 7. Sync Local Data To Neon

Preview the sync first:

```bash
.\venv\Scripts\python.exe run.py sync-hosted-database
```

Apply the sync:

```bash
.\venv\Scripts\python.exe run.py sync-hosted-database --apply
```

This copies the full BTQ dataset from your source database to the hosted target database.

## Recommended Workflow

- local Postgres for heavy backfills and experimentation
- Neon for shared demo access across machines
- sync local to Neon whenever you want the hosted copy refreshed
