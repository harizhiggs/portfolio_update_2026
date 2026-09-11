"""
Task 1: Standardize manufacturer names and join the master table
===============================================================

Suppliers send manufacturer names in many noisy forms ("FLEXLINE", "flexline",
"Nexa Ind.", "NexaIndustrial"). We keep a clean manufacturer master table
(the dimension) with a canonical name plus known aliases.

Goal:
  1. Build a lookup that maps any known name/alias -> canonical name.
  2. Standardize catalog.manufacturer_name_raw -> manufacturer_name_std.
  3. Join the catalog to the manufacturer master on manufacturer_id to enrich
     each row with a region / parent / status.
  4. Report the standardization match rate and the FK (join) match rate.

The match rates this prints look "fine" but are not telling the truth.
Find out why, fix it, then complete the EXTEND tasks.

EXTEND (after you have fixed the defects below):
  E1. The catalog already carries a ground-truth manufacturer_name_canonical.
      Use it to measure how accurate your standardization actually is.
  E2. Roll every row up to its top-level PARENT (group) manufacturer using
      parent_manufacturer_id, so we can later report KPIs per group.

Run from the project root:   python active/candidate/scripts/01_standardize_manufacturers.py
"""

import os
from pathlib import Path

import pandas as pd

DATA_DIR = Path(os.environ.get("DATA_DIR", "data"))
if not (DATA_DIR / "senior_data_analyst_catalog_dataset_v2.csv").exists():
    try:
        DATA_DIR = Path(__file__).resolve().parents[3] / "data"
    except NameError:
        pass

CATALOG_CSV = DATA_DIR / "senior_data_analyst_catalog_dataset_v2.csv"
MFR_CSV = DATA_DIR / "senior_data_analyst_manufacturer_dataset_v2.csv"


def build_name_lookup(manufacturers):
    """Map a manufacturer name -> canonical name."""
    lookup = {}
    for _, row in manufacturers.iterrows():
        canonical = row["canonical_manufacturer_name"]
        lookup[canonical] = canonical
        lookup[row["display_name"]] = canonical
    return lookup


def standardize_names(catalog, lookup):
    catalog = catalog.copy()
    catalog["manufacturer_name_std"] = catalog["manufacturer_name_raw"].map(lookup)
    return catalog


def enrich_with_master(catalog, manufacturers):
    """Attach master-table attributes via the manufacturer_id foreign key."""
    cols = ["manufacturer_id", "canonical_manufacturer_name", "region", "parent_manufacturer_id", "manufacturer_status"]
    merged = catalog.merge(manufacturers[cols], on="manufacturer_id", how="inner")
    return merged


def main():
    catalog = pd.read_csv(CATALOG_CSV)
    manufacturers = pd.read_csv(MFR_CSV)

    lookup = build_name_lookup(manufacturers)
    catalog = standardize_names(catalog, lookup)

    std_rate = catalog["manufacturer_name_std"].notna().mean()
    print(f"Standardization match rate: {std_rate:.1%}")

    enriched = enrich_with_master(catalog, manufacturers)
    fk_rate = enriched["canonical_manufacturer_name"].notna().mean()
    print(f"FK join match rate:         {fk_rate:.1%}")
    print(f"Rows in vs rows out:        {len(catalog)} -> {len(enriched)}")


if __name__ == "__main__":
    main()
