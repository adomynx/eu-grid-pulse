# EU Grid Pulse — Power BI build guide

This turns the dbt marts into a Power BI report with a proper star-schema model
and the DAX measures in [`powerbi/measures.dax`](../powerbi/measures.dax).

**Two ways to use it:**
- **Path A — open the pre-built project (fastest).** A Power BI Project (PBIP,
  "model as code") is already authored under `powerbi/`. See §0 — open it and the
  model, relationships, and all 21 measures load ready to use; you just add
  visuals.
- **Path B — build it by hand (guaranteed, good for learning).** §2–§5 below walk
  you through importing the data, creating the model, and pasting the measures.
  Use this if the PBIP needs a tweak on your Power BI version, or if you want to
  learn the model by assembling it.

---

## 0. Path A — open the pre-built PBIP

```
powerbi/
├── EUGridPulse.pbip                 ← open THIS in Power BI Desktop
├── EUGridPulse.SemanticModel/       ← tables, relationships, 21 DAX measures (TMDL)
└── EUGridPulse.Report/              ← report shell with an empty "Overview" page
```

1. Make sure the CSVs exist in `powerbi/data/` (run `python -m src.export_powerbi`
   if not).
2. Open `EUGridPulse.pbip` in **Power BI Desktop** (needs a recent version with
   the TMDL/PBIR formats — 2024 or later; enable *Preview features → Power BI
   Project (.pbip) save option* if prompted).
3. Set the data-source path: **Transform data → Edit Parameters → `DataFolder`**
   and point it at your absolute `...\eu-grid-pulse\powerbi\data\` path (keep the
   trailing backslash). It's pre-filled with `F:\Project\eu-grid-pulse\powerbi\data\`
   — change it if your path differs. Then **Refresh**.
4. The model + measures are loaded. Build visuals per §5, or drag from the
   `fact_load` measures straight onto the Overview page.

> The DAX measures live on the `fact_load` table (functionally identical to a
> dedicated measures table). Move them to a `_Measures` table later if you like.
>
> If your Power BI version rejects any PBIP file on open, fall back to Path B —
> the data and DAX are the same, you just assemble the model in the GUI.

---

---

## 1. Data

The pipeline exports every mart to `powerbi/data/` in two formats:

| File | Grain | Rows |
|------|-------|------|
| `dim_date.*`        | one row per hour        | 720 |
| `dim_country.*`     | one row per bidding zone | 5 |
| `dim_fuel.*`        | one row per fuel (+ `is_renewable`) | 8 |
| `fact_load.*`       | country × hour          | 3,600 |
| `fact_generation.*` | country × hour × fuel   | 28,800 |

`.parquet` is preferred (typed, compact); `.csv` is the universal fallback.
Regenerate anytime with:

```bash
.venv/Scripts/python -m src.run_pipeline        # full refresh
.venv/Scripts/python -m src.export_powerbi       # just re-export the files
```

---

## 2. Load the data

Power BI Desktop → **Get Data**:

- **Parquet route:** Get Data → *Parquet* → load each of the 5 files; or Get Data →
  *Folder* → point at `powerbi/data` → keep the `.parquet` files.
- **CSV route:** Get Data → *Text/CSV* → load each of the 5 `.csv` files.

Rename the queries to `dim_date`, `dim_country`, `dim_fuel`, `fact_load`,
`fact_generation` if the import didn't.

---

## 3. Build the star-schema model (Model view)

Create these relationships — all **one-to-many**, **single** cross-filter
direction (dimension filters fact). This is a clean star; no dim-to-dim links.

| From (one) | To (many) | Key |
|------------|-----------|-----|
| `dim_date[date_key]`       | `fact_load[date_key]`        | date_key |
| `dim_date[date_key]`       | `fact_generation[date_key]`  | date_key |
| `dim_country[country_key]` | `fact_load[country_key]`     | country_key |
| `dim_country[country_key]` | `fact_generation[country_key]` | country_key |
| `dim_fuel[fuel_key]`       | `fact_generation[fuel_key]`  | fuel_key |

> `dim_fuel` connects only to `fact_generation` (load has no fuel) — that's
> correct, not a mistake.

*(Optional, for time-intelligence DAX)* Table tools → **Mark as date table** on
`dim_date`, using the `date` column.

---

## 4. Add the measures

1. Home → **Enter data** → create an empty table named `_Measures` (one throwaway
   column; you can hide it later). This keeps all measures in one tidy home.
2. For each measure in [`powerbi/measures.dax`](../powerbi/measures.dax):
   **New measure** → paste the definition (the `Name = …` block). ~20 measures.
3. Hide the raw numeric key/measure columns on the facts so report builders use
   the measures, not the columns.

---

## 5. Suggested report pages

**Page 1 — Overview**
- KPI cards: `Renewable Share %`, `Peak Load (MW)`, `Self-Sufficiency %`,
  `Total Generation (GWh)`.
- Bar: `Renewable Share %` by `dim_country[country_name]`.
- Stacked column: `Total Generation (GWh)` by `country_name`, legend `fuel_type`.
- Line: `Total Load (GWh)` vs `Total Generation (GWh)` by `dim_date[date]`.

**Page 2 — Demand profile**
- Area/line: `Avg Load (MW)` by `dim_date[hour]` (the diurnal curve).
- Card: `Peak Hour (UTC)`, `Weekend Load Ratio %`, `Load Factor %`.
- Line: `7D Avg Load (MW)` by `date`.

**Page 3 — Country league table**
- Table: `country_name`, `Renewable Share %`, `Low-Carbon Share %`,
  `Country Share of Generation %`, `Top Fuel`, `Country Rank by Renewable`.

Add a slicer on `country_name` and one on `date` to every page.

---

## 6. Refresh cycle

1. Re-run the pipeline (`src.run_pipeline`) — new data lands in the marts and the
   `powerbi/data` files are rewritten to the same paths.
2. In Power BI Desktop: **Home → Refresh**. Model, measures, and visuals all
   update; nothing needs rebuilding.

---

## 7. Going to production data

Swap synthetic for real by adding your `ENTSOE_TOKEN` to `.env` (see
[KT.md](KT.md) §6), delete `data/eu_grid_pulse.duckdb`, re-run, re-export, refresh.
For a server-based source, repoint the dbt `profiles.yml` at Postgres and connect
Power BI to Postgres directly instead of the file export.
