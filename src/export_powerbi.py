"""Export the dbt marts to Power BI-ready files.

Writes each mart to powerbi/data/ as both Parquet (compact, typed — preferred
connector) and CSV (universal fallback). Uses DuckDB's COPY, so every export is
a single set-based scan — O(rows), no Python row loops.
"""
from __future__ import annotations

from pathlib import Path

from .warehouse import PROJECT_ROOT, get_connection

OUT_DIR = PROJECT_ROOT / "powerbi" / "data"
MARTS = ["dim_date", "dim_country", "dim_fuel", "fact_load", "fact_generation"]


def export() -> list[Path]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    con = get_connection()
    try:
        for mart in MARTS:
            pq = OUT_DIR / f"{mart}.parquet"
            csv = OUT_DIR / f"{mart}.csv"
            con.execute(f"COPY {mart} TO '{pq.as_posix()}' (FORMAT PARQUET)")
            con.execute(f"COPY {mart} TO '{csv.as_posix()}' (FORMAT CSV, HEADER)")
            n = con.execute(f"SELECT count(*) FROM {mart}").fetchone()[0]
            written += [pq, csv]
            print(f"[export] {mart}: {n} rows -> parquet + csv")
    finally:
        con.close()
    print(f"[export] done -> {OUT_DIR}")
    return written


if __name__ == "__main__":
    export()
