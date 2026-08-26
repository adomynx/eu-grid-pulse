"""End-to-end orchestration (Step 7): extract -> load raw -> staging -> marts -> quality.

Must be idempotent (re-running doesn't duplicate data) and incremental (only new dates).
Exits non-zero on any failure or critical DQ failure.
"""
import sys


def main() -> int:
    # TODO Step 7: wire the sequence together.
    #   1. extract   (src.ingest.extract_entsoe)
    #   2. load raw  (src.load.load_raw)
    #   3. staging   (sql/02_staging.sql)
    #   4. marts     (sql/03_marts.sql)
    #   5. quality   (src.quality.checks)  -> non-zero exit on critical failure
    print("pipeline not implemented yet — see build guide Step 7")
    return 0


if __name__ == "__main__":
    sys.exit(main())
