"""Export analytics tables to Parquet for Metabase / other BI tools."""

from __future__ import annotations

import sys
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paths import PROCESSED_DIR, WAREHOUSE

TABLES = [
    "chicago_taxi.daily_metrics",
    "chicago_taxi.hourly_demand",
    "chicago_taxi.zone_performance",
    "chicago_taxi.trips_clean",
]


def main() -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(str(WAREHOUSE), read_only=True)
    try:
        for table in TABLES:
            name = table.split(".")[-1]
            out_path = PROCESSED_DIR / f"{name}.parquet"
            conn.execute(
                f"COPY (SELECT * FROM {table}) TO '{out_path.as_posix()}' (FORMAT PARQUET)"
            )
            print(f"Exported {table} -> {out_path}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
