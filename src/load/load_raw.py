"""Load raw DataFrames into the DuckDB warehouse raw tables.

Land data AS-IS here. No cleaning at this layer — raw is an honest, replayable
copy of the source. Every row gets an ingested_at stamp so staging can keep the
latest pull and de-duplicate overlapping incremental re-pulls.
"""
from __future__ import annotations

import datetime as dt

import pandas as pd

from ..warehouse import get_connection

_DDL = """
CREATE TABLE IF NOT EXISTS raw_load (
    country_code TEXT        NOT NULL,
    datetime     TIMESTAMPTZ NOT NULL,
    resolution   TEXT,
    load_mw      DOUBLE,
    ingested_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS raw_generation (
    country_code    TEXT        NOT NULL,
    datetime        TIMESTAMPTZ NOT NULL,
    resolution      TEXT,
    production_type TEXT        NOT NULL,
    generation_mw   DOUBLE,
    consumption_mw  DOUBLE,
    ingested_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""


def ensure_tables(con) -> None:
    con.execute(_DDL)


def _append(con, table: str, df: pd.DataFrame) -> int:
    if df is None or df.empty:
        return 0
    df = df.copy()
    df["ingested_at"] = dt.datetime.now(dt.timezone.utc)
    con.register("_incoming", df)
    cols = ", ".join(df.columns)
    con.execute(f"INSERT INTO {table} ({cols}) SELECT {cols} FROM _incoming")
    con.unregister("_incoming")
    return len(df)


def load_raw_load(df: pd.DataFrame, con=None) -> int:
    """Append a load DataFrame to raw_load. Returns rows written."""
    own = con is None
    con = con or get_connection()
    try:
        ensure_tables(con)
        return _append(con, "raw_load", df)
    finally:
        if own:
            con.close()


def load_raw_generation(df: pd.DataFrame, con=None) -> int:
    """Append a generation DataFrame to raw_generation. Returns rows written."""
    own = con is None
    con = con or get_connection()
    try:
        ensure_tables(con)
        return _append(con, "raw_generation", df)
    finally:
        if own:
            con.close()


def get_watermark(con, table: str, country: str) -> pd.Timestamp | None:
    """Max datetime already loaded for a country — the incremental watermark."""
    row = con.execute(
        f"SELECT max(datetime) FROM {table} WHERE country_code = ?", [country]
    ).fetchone()
    return pd.Timestamp(row[0]) if row and row[0] is not None else None
