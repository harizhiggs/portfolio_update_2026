"""Run the Chicago taxi analytics pipeline end-to-end."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paths import DEFAULT_RAW_CSV, PROJECT_ROOT, SQL_DIR, WAREHOUSE


def _run_generate() -> None:
    script = PROJECT_ROOT / "1_data" / "fixtures" / "generate_sample_data.py"
    subprocess.run([sys.executable, str(script)], check=True, cwd=script.parent)


def _execute_sql_files(conn: duckdb.DuckDBPyConnection, raw_csv: Path) -> None:
    raw_path_sql = str(raw_csv.resolve()).replace("\\", "/").replace("'", "''")

    sql_files = sorted(SQL_DIR.glob("*.sql"))
    if not sql_files:
        raise FileNotFoundError(f"No SQL files found in {SQL_DIR}")

    for sql_file in sql_files:
        print(f"Running {sql_file.name}...")
        sql = sql_file.read_text(encoding="utf-8")
        sql = sql.replace("__RAW_CSV_PATH__", raw_path_sql)
        conn.execute(sql)


def _print_sanity_checks(conn: duckdb.DuckDBPyConnection) -> None:
    checks = [
        ("chicago_taxi.trips", "raw trips"),
        ("chicago_taxi.trips_clean", "clean trips"),
        ("chicago_taxi.daily_metrics", "daily metrics"),
        ("chicago_taxi.hourly_demand", "hourly demand"),
        ("chicago_taxi.zone_performance", "zone performance"),
    ]
    print("\n--- Pipeline summary ---")
    for table, label in checks:
        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"  {label}: {count:,} rows")

    date_range = conn.execute(
        """
        SELECT MIN(trip_date), MAX(trip_date)
        FROM chicago_taxi.trips_clean
        """
    ).fetchone()
    print(f"  Date range: {date_range[0]} to {date_range[1]}")
    print(f"  Warehouse: {WAREHOUSE.resolve()}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Chicago taxi DuckDB pipeline")
    parser.add_argument(
        "--generate",
        action="store_true",
        help="Generate sample CSV before loading",
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_RAW_CSV,
        help="Path to raw taxi trips CSV",
    )
    args = parser.parse_args()

    if args.generate:
        print("Generating sample data...")
        _run_generate()

    raw_csv = args.input.resolve()
    if not raw_csv.exists():
        print(f"Raw CSV not found: {raw_csv}")
        print("Run with --generate or place your file at the path above.")
        sys.exit(1)

    WAREHOUSE.parent.mkdir(parents=True, exist_ok=True)

    print(f"Loading from: {raw_csv}")
    conn = duckdb.connect(str(WAREHOUSE))
    try:
        _execute_sql_files(conn, raw_csv)
        _print_sanity_checks(conn)
    finally:
        conn.close()

    print("\nPipeline complete.")


if __name__ == "__main__":
    main()
