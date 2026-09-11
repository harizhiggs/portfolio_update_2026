"""
Task 2: De-duplicate the catalog
==================================

The feed contains duplicates: byte-for-byte repeats, near-duplicates with tiny
text variations, and the same part re-sent by a different supplier.

Goal:
  1. Decide what makes two catalog rows "the same part".
  2. Count and remove duplicates, keeping one record per part.
  3. Report how many were removed and the final unique count.

This script claims it removed duplicates, but the numbers do not add up.
Find the defects, fix them, then complete the EXTEND tasks.

EXTEND (after you have fixed the defects below):
  E1. Choose and justify a business key for "same part". Why should (or
      should not) catalog_row_id be part of it?
  E2. Near-duplicates differ by case / whitespace / punctuation in the text
      fields. Normalize before comparing so they actually collapse.
  E3. Instead of silently dropping, flag duplicate groups (assign a group id
      and a keep/drop reason) so the decision is auditable. Cross-check your
      counts against the duplicate-related values in quality_issue_hint.

Run from the project root:   python active/candidate/scripts/02_deduplicate_catalog.py
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

# What we consider the identity of a "part".
DEDUP_KEYS = ["catalog_row_id", "manufacturer_name_canonical", "article_number_clean"]


def remove_duplicates(df):
    before = len(df)

    # full-row de-duplication
    df = df.drop_duplicates()

    # business-key de-duplication
    df = df.drop_duplicates(subset=DEDUP_KEYS, keep=False)

    removed = before - len(df)
    return df, removed


def find_near_duplicates(df):
    """Rows that share a manufacturer + identical short_text are likely near-dupes."""
    dupe_mask = df.duplicated(subset=["manufacturer_name_canonical", "short_text"], keep=False)
    return df[dupe_mask]


def main():
    df = pd.read_csv(CATALOG_CSV)

    deduped, removed = remove_duplicates(df)
    print(f"Rows before:        {len(df)}")
    print(f"Duplicates removed: {removed}")
    print(f"Rows after:         {len(deduped)}")

    near = find_near_duplicates(df)
    print(f"\nPotential near-duplicate rows: {len(near)}")


if __name__ == "__main__":
    main()
