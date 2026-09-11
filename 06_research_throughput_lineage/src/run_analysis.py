from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from throughput_analysis import build_throughput, collapse_matching_candidates, coverage_summary, identifier_summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Build research throughput lineage outputs.")
    parser.add_argument("--research", type=Path, required=True)
    parser.add_argument("--matching", type=Path, required=True)
    parser.add_argument("--imports", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    research = pd.read_csv(args.research, dtype="string")
    matching = pd.read_csv(args.matching, dtype="string")
    imports = pd.read_csv(args.imports, dtype="string")
    throughput = build_throughput(research, matching, imports)
    args.output.mkdir(parents=True, exist_ok=True)
    throughput.to_csv(args.output / "throughput.csv", index=False)
    identifier_summary(throughput).to_csv(args.output / "identifier_summary.csv")
    coverage_summary(throughput, collapse_matching_candidates(matching)).to_csv(
        args.output / "coverage_summary.csv", index=False
    )


if __name__ == "__main__":
    main()
