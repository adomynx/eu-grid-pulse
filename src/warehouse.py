"""DuckDB warehouse connection helper.

We use DuckDB as the local warehouse: a single file on disk, no server, no
Docker. The dbt models are written in plain SQL and stay portable to Postgres
or BigQuery later — only this connection layer is DuckDB-specific.
"""
from __future__ import annotations

import os
from pathlib import Path

import duckdb

# Project root = two levels up from this file (src/warehouse.py -> project/).
PROJECT_ROOT = Path(__file__).resolve().parents[1]

# The warehouse file lives under data/ (gitignored), so the DB never gets committed.
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "eu_grid_pulse.duckdb"


def db_path() -> Path:
    """Resolve the warehouse path (env override wins, else the default under data/)."""
    override = os.environ.get("DUCKDB_PATH")
    path = Path(override) if override else DEFAULT_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def get_connection() -> duckdb.DuckDBPyConnection:
    """Open (or create) the DuckDB warehouse and return a connection."""
    return duckdb.connect(str(db_path()))
