"""Ingestion: ENTSO-E API (or synthetic fallback) -> raw pandas DataFrames.

Two modes, same output shape:
  * REAL   — set ENTSOE_TOKEN in .env; pulls live data via entsoe-py.
  * SYNTH  — no token needed; generates realistic grid data (see synthetic.py).
             Default when no token is present, so the pipeline always runs.

Incremental by design: callers pass a per-country watermark (max datetime
already loaded) as `start`, so each run only pulls new dates.
"""
from __future__ import annotations

import argparse
import os

import pandas as pd
from dotenv import load_dotenv

from . import synthetic

load_dotenv()

# Renewable/clean fuels we expect in the generation breakdown are handled in dbt;
# here we only shape the raw extract.

RENEWABLE_HINT = None  # (kept intentionally simple; semantics live in dbt dim_fuel)


def use_synthetic() -> bool:
    """Synthetic unless a real token is present AND the user didn't force synth."""
    if os.environ.get("EU_GRID_PULSE_SYNTH", "").lower() in {"1", "true", "yes"}:
        return True
    return not bool(os.environ.get("ENTSOE_TOKEN"))


def _client():
    from entsoe import EntsoePandasClient  # imported lazily so synth mode needs no token
    token = os.environ.get("ENTSOE_TOKEN")
    if not token:
        raise RuntimeError("ENTSOE_TOKEN is not set. Copy .env.example to .env and add your token.")
    return EntsoePandasClient(api_key=token)


def smoke_test() -> None:
    """Pull one day of DE_LU load and print it. De-risks the token early."""
    start = pd.Timestamp("2024-01-01", tz="Europe/Berlin")
    end = pd.Timestamp("2024-01-02", tz="Europe/Berlin")
    if use_synthetic():
        df = synthetic.synth_load("DE_LU", start, end)
        print(df.head())
        print(f"\nOK (SYNTHETIC): generated {len(df)} rows. No token needed.")
        return
    df = _client().query_load("DE_LU", start=start, end=end)
    print(df.head())
    print(f"\nOK (REAL): pulled {len(df)} rows. Token and library are working.")


def fetch_load(country: str, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    """Actual load for one country/date-range, normalised to the raw_load shape:
    columns [country_code, datetime, resolution, load_mw]."""
    if use_synthetic():
        return synthetic.synth_load(country, start, end)

    series = _client().query_load(country, start=start, end=end)
    # entsoe-py returns a DataFrame with a DatetimeIndex and an "Actual Load" column.
    col = series.columns[0] if isinstance(series, pd.DataFrame) else series.name
    s = series[col] if isinstance(series, pd.DataFrame) else series
    out = pd.DataFrame({
        "country_code": country,
        "datetime": s.index,
        "resolution": _infer_resolution(s.index),
        "load_mw": s.values.astype("float64"),
    })
    return out


def fetch_generation(country: str, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    """Generation-by-production-type for one country, normalised to raw_generation:
    columns [country_code, datetime, resolution, production_type, generation_mw, consumption_mw]."""
    if use_synthetic():
        return synthetic.synth_generation(country, start, end)

    wide = _client().query_generation(country, start=start, end=end)
    # entsoe-py returns a wide frame: index=datetime, columns=production types
    # (sometimes a (type, 'Actual Aggregated'/'Actual Consumption') MultiIndex).
    resolution = _infer_resolution(wide.index)
    records = []
    for col in wide.columns:
        if isinstance(col, tuple):
            fuel, kind = col[0], col[1]
        else:
            fuel, kind = col, "Actual Aggregated"
        is_consumption = "Consumption" in str(kind)
        for ts, val in wide[col].items():
            if pd.isna(val):
                continue
            records.append({
                "country_code": country,
                "datetime": ts,
                "resolution": resolution,
                "production_type": fuel,
                "generation_mw": None if is_consumption else float(val),
                "consumption_mw": float(val) if is_consumption else None,
            })
    out = pd.DataFrame.from_records(records)
    if not out.empty:
        # collapse generation/consumption rows that share the same key
        out = (out.groupby(["country_code", "datetime", "resolution", "production_type"], as_index=False)
                   .agg({"generation_mw": "max", "consumption_mw": "max"}))
    return out


def _infer_resolution(index: pd.DatetimeIndex) -> str:
    """Best-effort ENTSO-E resolution label from the index spacing."""
    if len(index) < 2:
        return "PT60M"
    delta = (index[1] - index[0]).total_seconds() / 60
    return {15: "PT15M", 30: "PT30M", 60: "PT60M"}.get(int(delta), f"PT{int(delta)}M")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke-test", action="store_true", help="Pull one day of DE_LU load and exit.")
    args = parser.parse_args()
    if args.smoke_test:
        smoke_test()
