-- sql/01_raw.sql
-- RAW layer: land ENTSO-E extracts AS-IS. No cleaning happens here.
-- The raw layer is an honest, replayable copy of the source, so by design:
--   * we keep whatever timestamps/units the API returned,
--   * we ALLOW duplicate rows from overlapping incremental re-pulls
--     (de-duplication happens later, in staging), and
--   * every row records ingested_at, so staging can keep the latest pull.

-- Actual electricity demand (load): one row per country x timestamp, per pull.
CREATE TABLE IF NOT EXISTS raw_load (
    country_code   TEXT             NOT NULL,             -- ENTSO-E bidding-zone code, e.g. 'DE_LU', 'FR'
    datetime       TIMESTAMPTZ      NOT NULL,             -- timestamp as returned by the API (instant preserved)
    resolution     TEXT,                                  -- 'PT15M' / 'PT60M' — resolution differs by country
    load_mw        DOUBLE PRECISION,                      -- actual load in MW (nullable: the API returns gaps)
    ingested_at    TIMESTAMPTZ      NOT NULL DEFAULT now()  -- when this row was pulled (audit + dedup key)
);

-- Actual generation broken out by production type:
-- one row per country x timestamp x fuel, per pull.
-- This per-fuel breakdown is what powers the renewable-share story downstream.
CREATE TABLE IF NOT EXISTS raw_generation (
    country_code     TEXT             NOT NULL,
    datetime         TIMESTAMPTZ      NOT NULL,
    resolution       TEXT,
    production_type  TEXT             NOT NULL,           -- raw ENTSO-E label: 'Solar', 'Wind Onshore', 'Fossil Gas', 'Nuclear', ...
    generation_mw    DOUBLE PRECISION,                    -- actual aggregated generation in MW
    consumption_mw   DOUBLE PRECISION,                    -- some types (e.g. pumped storage) also report consumption
    ingested_at      TIMESTAMPTZ      NOT NULL DEFAULT now()
);

-- Supports the incremental watermark ("max datetime already loaded per country")
-- and staging reads. Deliberately NOT unique: raw tolerates duplicate re-pulls.
CREATE INDEX IF NOT EXISTS ix_raw_load_country_dt
    ON raw_load (country_code, datetime);

CREATE INDEX IF NOT EXISTS ix_raw_generation_country_dt
    ON raw_generation (country_code, datetime);
