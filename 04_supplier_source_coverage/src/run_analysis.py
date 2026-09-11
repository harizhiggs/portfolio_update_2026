from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from coverage_analysis import (
    annotate_source_status,
    list_coverage,
    load_batches,
    source_share,
    summarize_coverage,
    unmatched_source_rate,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build supplier-source coverage summaries.")
    parser.add_argument("--batches", type=Path, required=True)
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--lookup", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    observed = load_batches(args.batches)
    lookup = pd.read_csv(args.lookup, dtype="string") if args.lookup else None
    observed = annotate_source_status(observed, lookup)
    candidates = pd.read_csv(args.candidates, dtype="string")
    coverage = list_coverage(candidates, observed)

    args.output.mkdir(parents=True, exist_ok=True)
    source_share(observed).to_csv(args.output / "source_share.csv", index=False)
    coverage.to_csv(args.output / "list_coverage.csv", index=False)
    summarize_coverage(coverage).to_csv(args.output / "coverage_summary.csv", index=False)
    pd.DataFrame({"unmatched_source_rate": [unmatched_source_rate(observed)]}).to_csv(
        args.output / "diagnostics.csv", index=False
    )


if __name__ == "__main__":
    main()
