"""End-to-end orchestration: extract -> load raw -> dbt (staging + marts) -> dbt test -> export.

Idempotent + incremental: each country pulls only dates after its raw watermark,
and staging de-duplicates overlapping re-pulls, so re-running never duplicates data.
Exits non-zero on any ingestion error or dbt (build/test) failure, so bad data
can't reach the dashboard.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pandas as pd
import yaml

from .ingest import extract_entsoe as extract
from .load import load_raw
from .warehouse import PROJECT_ROOT, db_path, get_connection

DEFAULT_DAYS = 30            # how much history to backfill on a fresh warehouse
CONFIG = PROJECT_ROOT / "config" / "countries.yml"
DBT_DIR = PROJECT_ROOT / "dbt"


def _countries() -> list[dict]:
    with open(CONFIG, encoding="utf-8") as f:
        return yaml.safe_load(f)["countries"]


def _window(con, country: str, now: pd.Timestamp) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Incremental window: start just after the watermark, else backfill DEFAULT_DAYS."""
    wm = load_raw.get_watermark(con, "raw_load", country)
    if wm is not None:
        start = (wm + pd.Timedelta(hours=1)).tz_convert("Europe/Berlin")
    else:
        start = (now - pd.Timedelta(days=DEFAULT_DAYS)).tz_convert("Europe/Berlin")
    return start, now.tz_convert("Europe/Berlin")


def _pull(con, code: str, kind: str, fetch, load) -> int:
    """Fetch one series and land it, tolerating ENTSO-E's 'no data yet' for the
    most recent (not-yet-published) window — a per-series skip, not a run failure."""
    try:
        df = fetch()
    except Exception as exc:  # noqa: BLE001 — entsoe-py raises on empty/late windows
        reason = type(exc).__name__ + (f": {exc}" if str(exc) else "")
        print(f"[ingest] {code} {kind}: skipped ({reason})", file=sys.stderr)
        return 0
    return load(df, con=con)


def ingest() -> int:
    """Pull + land raw for every configured country. Returns total rows written."""
    mode = "SYNTHETIC" if extract.use_synthetic() else "REAL (ENTSO-E)"
    print(f"[ingest] mode = {mode}")
    now = pd.Timestamp.now(tz="Europe/Berlin").floor("h")
    total = 0
    con = get_connection()
    try:
        load_raw.ensure_tables(con)
        for c in _countries():
            code = c["code"]
            start, end = _window(con, code, now)
            if start >= end:
                print(f"[ingest] {code}: up to date, nothing to pull.")
                continue
            n1 = _pull(con, code, "load",
                       lambda: extract.fetch_load(code, start, end), load_raw.load_raw_load)
            n2 = _pull(con, code, "generation",
                       lambda: extract.fetch_generation(code, start, end), load_raw.load_raw_generation)
            total += n1 + n2
            print(f"[ingest] {code}: +{n1} load rows, +{n2} generation rows "
                  f"({start.date()} -> {end.date()})")
    finally:
        con.close()
    print(f"[ingest] done: {total} raw rows written.")
    return total


def _dbt(*args: str) -> int:
    """Run a dbt command against our DuckDB warehouse. Returns its exit code."""
    dbt_exe = Path(sys.executable).parent / ("dbt.exe" if os.name == "nt" else "dbt")
    env = dict(os.environ)
    env["DUCKDB_PATH"] = str(db_path())
    env["DBT_PROFILES_DIR"] = str(DBT_DIR)
    cmd = [str(dbt_exe), *args, "--project-dir", str(DBT_DIR)]
    print(f"[dbt] {' '.join(args)}")
    return subprocess.run(cmd, env=env).returncode


def main() -> int:
    try:
        ingest()
    except Exception as exc:  # noqa: BLE001 — surface any ingestion failure as non-zero exit
        print(f"[FATAL] ingestion failed: {exc}", file=sys.stderr)
        return 1

    if _dbt("run") != 0:
        print("[FATAL] dbt run failed.", file=sys.stderr)
        return 2
    if _dbt("test") != 0:
        print("[FATAL] dbt test failed — a data-quality check did not pass.", file=sys.stderr)
        return 3

    # Build the dashboard + refresh the Power BI data exports from the marts.
    try:
        from .dashboard import build as build_dashboard
        print(f"[dashboard] wrote {build_dashboard()}")
    except Exception as exc:  # noqa: BLE001
        print(f"[WARN] dashboard build failed: {exc}", file=sys.stderr)
    try:
        from .export_powerbi import export as export_powerbi
        export_powerbi()
    except Exception as exc:  # noqa: BLE001
        print(f"[WARN] Power BI export failed: {exc}", file=sys.stderr)

    print("\nPipeline complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
