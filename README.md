# EU Grid Pulse

An end-to-end batch pipeline for European electricity data. It pulls real
**demand** and **generation-by-fuel-type** for several European countries from
the ENTSO-E Transparency API, lands it raw, cleans and harmonises it, models it
into a star schema, runs data-quality checks on every load, and serves it in a
Power BI dashboard. The whole thing is containerised and scheduled.

## Architecture

```
ENTSO-E API
   |  (Python extract, incremental by date)
   v
RAW layer      unprocessed load + generation, as pulled
   |  (SQL: timezone->UTC, units->MW, country codes, dedup, nulls)
   v
STAGING layer  cleaned + harmonised, one clean grain
   |  (SQL: build dimensions + facts)
   v
MARTS layer    star schema: fact_load, fact_generation + dims
   |
   +--> DATA QUALITY  freshness / nulls / plausibility / referential -> dq_results
   |
   v
Power BI       renewable share, demand vs generation, fuel mix, peak load
```

## Stack

Python (pandas, entsoe-py, SQLAlchemy) · PostgreSQL (Docker) · Power BI · Docker · Jenkins · Git

## Getting started

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env          # then add your ENTSOE_TOKEN
docker compose up -d          # stand up Postgres
make test-token               # Step 1: confirm token + library work
```

## Build status

Scaffolded (Step 0). Building out ingestion -> raw -> staging -> marts -> DQ -> dashboard.

## Data quality

Checks run after every load and write pass/fail rows to `dq_results`:
freshness, null-rate, plausibility, referential integrity, row-count. A critical
failure exits non-zero so bad data can't reach the dashboard.

## What was hard

- Timezone / DST harmonisation across countries (resolution differs: 15-min vs hourly).
- Incremental de-duplication of overlapping rows on re-pull (idempotency).

## License

MIT
