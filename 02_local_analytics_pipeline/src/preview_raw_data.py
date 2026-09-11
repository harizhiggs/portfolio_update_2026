"""Preview a raw CSV before writing SQL against it.

This is the bridge between "plug-and-play" data (the synthetic fixture in
1_data/fixtures/, or any real CSV you drop into 1_data/raw/) and the SQL
models in 2_sql/. Different data sources have different column names and
types, so instead of guessing, this script loads the file with DuckDB's
read_csv_auto and prints exactly what it sees: column names, inferred types,
row count, and a small sample. Use that output to confirm or edit
2_sql/01_schema.sql so it matches your actual data.

Usage:
    python 3_pipeline/preview_raw_data.py
    python 3_pipeline/preview_raw_data.py --input 1_data/raw/my_export.csv --rows 10
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paths import DEFAULT_RAW_CSV


def main() -> None:
    parser = argparse.ArgumentParser(description="Preview a raw CSV's headers, types, and sample rows.")
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_RAW_CSV,
        help="Path to the CSV to preview (default: the fixture path used by --generate)",
    )
    parser.add_argument("--rows", type=int, default=5, help="Number of sample rows to print")
    args = parser.parse_args()

    csv_path = args.input.resolve()
    if not csv_path.exists():
        print(f"File not found: {csv_path}")
        print("Generate the plug-and-play test fixture first:")
        print("  python 1_data/fixtures/generate_sample_data.py")
        print("...or point --input at your own CSV.")
        sys.exit(1)

    csv_literal = str(csv_path).replace("\\", "/").replace("'", "''")
    conn = duckdb.connect()
    try:
        print(f"Previewing: {csv_path}\n")

        print("--- Columns & inferred types (DESCRIBE) ---")
        described = conn.execute(f"DESCRIBE SELECT * FROM read_csv_auto('{csv_literal}')").fetchall()
        for column_name, column_type, *_ in described:
            print(f"  {column_name:<28} {column_type}")

        row_count = conn.execute(
            f"SELECT COUNT(*) FROM read_csv_auto('{csv_literal}')"
        ).fetchone()[0]
        print(f"\nTotal rows: {row_count:,}")

        print(f"\n--- Sample rows (first {args.rows}) ---")
        sample = conn.execute(
            f"SELECT * FROM read_csv_auto('{csv_literal}') LIMIT {args.rows}"
        ).df()
        print(sample.to_string(index=False))
    finally:
        conn.close()

    print(
        "\nNext step: open 2_sql/01_schema.sql and confirm the column names/types "
        "above match what that file expects. Adjust it if your source differs, "
        "then run: python 3_pipeline/run_pipeline.py --input "
        f"{csv_path}"
    )


if __name__ == "__main__":
    main()
