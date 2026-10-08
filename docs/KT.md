# EU Grid Pulse — Knowledge Transfer

This is the hand-off doc for the working pipeline. It explains **what runs, how
it runs, the data model, and how to extend it.** Read top to bottom once; after
that it's a reference.

---

## 1. Current status — it runs end to end

As of this build, the pipeline is **fully runnable on this machine with no API
token and no Docker**:

```
ingest (synthetic or real)  →  DuckDB raw tables  →  dbt staging (views)
   →  dbt marts (star schema, tables)  →  dbt tests (31)  →  HTML dashboard
```

One command runs the whole thing:

```bash
.venv/Scripts/python -m src.run_pipeline
```

Last verified run: **32,400 raw rows → 7 dbt models → 31/31 tests passed → dashboard → exit 0.**
Re-running pulls 0 new rows (idempotent + incremental).

---

## 2. The stack we actually built (and why it differs from the README)

The original README described **Postgres-in-Docker + hand-written SQL + Jenkins +
Power BI**. This machine has no Docker, so we built the modern, equivalent stack
that runs here natively. Every swap is deliberate and defensible:

| README's original plan | What we built | Why |
|---|---|---|
| PostgreSQL in Docker | **DuckDB** (one file: `data/eu_grid_pulse.duckdb`) | No Docker needed. DuckDB is a modern analytics engine; the dbt SQL stays portable to Postgres/BigQuery later. |
| Hand-written `02_staging.sql` / `03_marts.sql` | **dbt** (`dbt/` project) | Version-controlled models, lineage, and built-in tests — the modern transformation layer. |
| `checks.py` DQ module | **dbt tests** (31) | `not_null`, `unique`, `relationships`, `accepted_values` + 2 custom plausibility tests. |
| Live ENTSO-E pull | **Synthetic data by default**, real API path kept wired | Runs today with no token. Add a token and the real path activates automatically. |
| Power BI (`.pbix`) | **PBIP project as code** (`powerbi/`, TMDL model + 21 DAX measures) **+ HTML dashboard** | PBIP is Git-friendly and opens in Power BI Desktop; the HTML dashboard needs no extra software. |
| Jenkins | **Dagster** (`src/dagster_defs.py`) — asset graph + daily schedule; `src/run_pipeline.py` as a no-UI fallback | Dagster runs natively on Windows (pip-installed, no WSL), with first-class dbt integration — the 31 tests surface as asset checks. Supersedes the earlier Airflow-via-WSL plan. |

> The `README.md` has been rewritten to match this DuckDB + dbt + Dagster + Power BI
> stack.

---

## 3. Repository map

```
eu-grid-pulse/
├── .venv/                        # Python 3.10 env (gitignored) — the toolchain
├── config/countries.yml          # which bidding zones to pull (DE_LU, FR, NL, ES, PL)
├── data/eu_grid_pulse.duckdb      # the warehouse file (gitignored)
├── src/
│   ├── warehouse.py               # DuckDB connection helper (+ DUCKDB_PATH override)
│   ├── ingest/
│   │   ├── extract_entsoe.py      # real ENTSO-E pull OR synthetic; same output shape
│   │   └── synthetic.py           # realistic fake grid data (no token needed)
│   ├── load/load_raw.py           # DataFrames → raw_load / raw_generation (+ watermark)
│   ├── dashboard.py               # marts → dashboards/index.html
│   ├── export_powerbi.py          # marts → Parquet/CSV for Power BI
│   ├── run_pipeline.py            # no-UI orchestrator (ingest→dbt build→dashboard→export)
│   ├── dagster_defs.py            # Dagster asset graph + daily schedule (primary orchestrator)
│   └── pipeline.py                # thin wrapper so `python -m src.pipeline` still works
├── dbt/
│   ├── dbt_project.yml            # dbt config (staging=views, marts=tables)
│   ├── profiles.yml               # points dbt at the DuckDB file via DUCKDB_PATH
│   ├── models/
│   │   ├── sources.yml            # declares raw_load / raw_generation as sources
│   │   ├── staging/               # stg_load, stg_generation (+ _staging.yml tests)
│   │   └── marts/                 # dim_* , fact_* (+ _marts.yml tests)
│   └── tests/                     # custom plausibility checks
├── powerbi/                       # PBIP (TMDL model + 21 DAX measures) + measures.dax
└── dashboards/index.html          # the generated dashboard
```

---

## 4. The data model (star schema)

```
            dim_date (hourly)                  dim_country
                  │                                 │
                  │        ┌────────────────────────┤
                  ▼        ▼                         ▼
              fact_load (country × hour)      fact_generation (country × hour × fuel)
                                                     ▲
                                                     │
                                                 dim_fuel (is_renewable)
```

- **Grain**: `fact_load` = one row per country per hour. `fact_generation` = one
  row per country per hour per fuel.
- **Keys**: surrogate keys are `md5(...)` of the natural key (country_code,
  production_type, hourly timestamp). Facts join to dims on these; the
  `relationships` tests prove every fact key exists in its dim.
- **Renewable flag** lives in `dim_fuel.is_renewable` — Solar/Wind/Hydro/Biomass =
  true; Nuclear/Fossil = false (nuclear is low-carbon but not *renewable*, by
  convention). This single flag drives the renewable-share metric.

---

## 5. How to run

```bash
# full pipeline (ingest → dbt → tests → dashboard)
.venv/Scripts/python -m src.run_pipeline

# just confirm ingestion works
.venv/Scripts/python -m src.ingest.extract_entsoe --smoke-test

# run dbt on its own (from the dbt/ folder, or let the runner set env vars)
cd dbt
set DUCKDB_PATH=..\data\eu_grid_pulse.duckdb   # PowerShell: $env:DUCKDB_PATH=...
..\.venv\Scripts\dbt run
..\.venv\Scripts\dbt test
..\.venv\Scripts\dbt docs generate   # optional: lineage docs

# rebuild only the dashboard from existing marts
.venv/Scripts/python -c "from src.dashboard import build; print(build())"
```

Inspect the warehouse directly:

```bash
.venv/Scripts/python -c "import duckdb; c=duckdb.connect('data/eu_grid_pulse.duckdb'); print(c.sql('select * from dim_fuel'))"
```

---

## 6. Synthetic vs. real data

Controlled entirely by environment variables (in `.env`):

- **No `ENTSOE_TOKEN`** → synthetic mode (default). Generates 30 days of realistic
  hourly data for all 5 countries.
- **`ENTSOE_TOKEN=<your token>`** → real mode. The same `fetch_load` /
  `fetch_generation` functions call the live ENTSO-E API via `entsoe-py`.
- **`EU_GRID_PULSE_SYNTH=1`** → force synthetic even if a token is present (handy
  for offline dev/CI).

Nothing downstream (dbt, dashboard) changes between modes — the extract functions
normalise both to the same DataFrame shape. To go live: get a free token from the
ENTSO-E Transparency Platform, put it in `.env`, delete `data/eu_grid_pulse.duckdb`
(to backfill fresh), and re-run.

---

## 7. Data quality (the DQ gate)

`dbt test` is the quality gate. If any test fails, `run_pipeline` exits non-zero
and the dashboard is **not** considered trustworthy. Current 31 tests:

- **Schema tests** — `not_null` on all keys/measures, `unique` on dim keys,
  `relationships` (every fact key exists in its dim), `accepted_values` on the
  renewable flag.
- **Custom plausibility** (`dbt/tests/`) — load must be positive and < 200 GW;
  generation non-negative and < 150 GW per fuel-hour.

Add a freshness check later with dbt's `source freshness` feature once real data
with recent timestamps is flowing.

---

## 8. The dashboard

`src/dashboard.py` queries the marts and writes a self-contained
`dashboards/index.html` (Chart.js from CDN). Panels: renewable share by country,
peak load by country, fuel mix (stacked), daily demand vs generation, and the
average demand-by-hour curve. Open the file in any browser, or publish it.

---

## 9. Done since the original scaffold

- ✅ **Orchestration — Dagster** (`src/dagster_defs.py`): asset graph (ingest → dbt →
  dashboard/export) + daily 06:00 schedule; 31 dbt tests run as asset checks.
  `dagster dev -m src.dagster_defs` → UI at http://localhost:3000. Supersedes the
  earlier Airflow-via-WSL idea (Dagster runs natively on Windows and is dbt-native).
- ✅ **Power BI** — PBIP project as code (`powerbi/`) + 21 DAX measures; see
  [POWERBI.md](POWERBI.md).
- ✅ **README** rewritten for the real stack (Mermaid architecture + star-schema
  diagrams, no broken images).

### Still to do — the roadmap

1. **Go live** — add your ENTSO-E token (§6). The real path is already wired; the
   first live run may need a small `entsoe-py` column-shape tweak.
2. **GitHub Actions CI** — a workflow that installs the venv, runs the pipeline in
   `EU_GRID_PULSE_SYNTH=1` mode, and asserts `dbt build` passes. Highly visible to
   reviewers; the last "bulletproof" item.
3. **Optional — cloud warehouse** — swap DuckDB for Postgres/BigQuery (only
   `dbt/profiles.yml` and `src/warehouse.py` change; the dbt models are portable).
4. **Optional — source freshness** — add dbt `source freshness` once live data with
   recent timestamps is flowing.

---

## 10. Troubleshooting

| Symptom | Fix |
|---|---|
| `ENTSOE_TOKEN is not set` | You're in real mode without a token. Add one to `.env`, or set `EU_GRID_PULSE_SYNTH=1`. |
| dbt can't find the warehouse | Ensure `DUCKDB_PATH` is set (the runner does this automatically). |
| Want a clean re-parse / stale dbt warnings | Delete `dbt/target/` and re-run. |
| Dashboard charts blank | Needs internet for the Chart.js CDN; or publish it as an artifact. |
| Start fresh | Delete `data/eu_grid_pulse.duckdb` and re-run the pipeline. |
| dbt deprecation warnings | Cosmetic (dbt 1.12 notices); safe to ignore. |
