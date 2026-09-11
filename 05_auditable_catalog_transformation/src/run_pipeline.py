from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from catalog_cleaning import clean_catalog, split_by_role


def main() -> None:
    parser = argparse.ArgumentParser(description="Clean a catalog with an audit log.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mappings", type=Path)
    args = parser.parse_args()

    catalog = pd.read_excel(args.input, dtype=object)
    mappings = {}
    if args.mappings:
        mappings = json.loads(args.mappings.read_text(encoding="utf-8"))
    cleaned, audit_log = clean_catalog(catalog, mappings)
    manufacturer, supplier = split_by_role(cleaned)

    args.output.mkdir(parents=True, exist_ok=True)
    cleaned.to_csv(args.output / "cleaned_catalog.csv", index=False)
    audit_log.to_csv(args.output / "audit_log.csv", index=False)
    manufacturer.to_csv(args.output / "manufacturer_records.csv", index=False)
    supplier.to_csv(args.output / "supplier_records.csv", index=False)


if __name__ == "__main__":
    main()
