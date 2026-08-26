"""Ingestion: ENTSO-E API -> raw pandas DataFrames.

Step 1 gives you a --smoke-test that pulls one day of German load, so you can
confirm your token + library work the moment the token arrives.
Step 2 fills in fetch_load / fetch_generation with incremental (watermark) logic.
"""
import argparse
import os

import pandas as pd
from dotenv import load_dotenv
from entsoe import EntsoePandasClient

load_dotenv()


def _client() -> EntsoePandasClient:
    token = os.environ.get("ENTSOE_TOKEN")
    if not token:
        raise RuntimeError("ENTSOE_TOKEN is not set. Copy .env.example to .env and add your token.")
    return EntsoePandasClient(api_key=token)


def smoke_test() -> None:
    """Step 1: pull one day of DE_LU load and print it. De-risks the token early."""
    client = _client()
    start = pd.Timestamp("2024-01-01", tz="Europe/Berlin")
    end = pd.Timestamp("2024-01-02", tz="Europe/Berlin")
    df = client.query_load("DE_LU", start=start, end=end)
    print(df.head())
    print(f"\nOK: pulled {len(df)} rows. Token and library are working.")


def fetch_load(country: str, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    """Step 2: pull actual load for one country/date-range. TODO: implement + watermark."""
    raise NotImplementedError("Implement in Step 2")


def fetch_generation(country: str, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    """Step 2: pull generation-by-production-type. TODO: implement + watermark.

    query_generation returns generation broken out per production type
    (solar, wind onshore/offshore, nuclear, fossil gas, ...). That fuel
    breakdown is what powers the renewable-share story later.
    """
    raise NotImplementedError("Implement in Step 2")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke-test", action="store_true", help="Pull one day of DE_LU load and exit.")
    args = parser.parse_args()
    if args.smoke_test:
        smoke_test()
