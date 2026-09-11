from __future__ import annotations

from pathlib import Path
import re

import pandas as pd


REQUIRED_OBSERVED = {"list_id", "item_id", "source_id"}
REQUIRED_CANDIDATES = {"list_id", "item_id"}


def normalize_column_name(name: object) -> str:
    value = re.sub(r"[^a-z0-9]+", "_", str(name).strip().lower())
    return value.strip("_")


def normalize_columns(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    result.columns = [normalize_column_name(column) for column in result.columns]
    return result


def _validate(frame: pd.DataFrame, required: set[str], label: str) -> None:
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"{label} is missing required columns: {', '.join(missing)}")


def load_batches(folder: str | Path) -> pd.DataFrame:
    paths = sorted(Path(folder).glob("*.csv"))
    if not paths:
        raise FileNotFoundError(f"No CSV batches found in {folder}")

    batches = []
    for path in paths:
        batch = normalize_columns(pd.read_csv(path, dtype="string"))
        _validate(batch, REQUIRED_OBSERVED, path.name)
        batch["batch_name"] = path.name
        batches.append(batch)

    combined = pd.concat(batches, ignore_index=True, sort=False)
    for column in REQUIRED_OBSERVED:
        combined[column] = combined[column].fillna("").str.strip()
    return combined


def annotate_source_status(
    observed: pd.DataFrame,
    lookup: pd.DataFrame | None = None,
) -> pd.DataFrame:
    result = observed.copy()
    if lookup is None:
        result["source_name"] = result["source_id"].where(result["source_id"].ne(""), "no-source-found")
        result.loc[result["source_id"].ne(""), "source_name"] = "no-source-found"
        return result

    lookup = normalize_columns(lookup)
    _validate(lookup, {"source_id", "source_name"}, "source lookup")
    lookup = lookup[["source_id", "source_name"]].drop_duplicates("source_id")
    result = result.merge(lookup, on="source_id", how="left", validate="many_to_one")
    result["source_name"] = result["source_name"].fillna("no-source-found").replace("", "no-source-found")
    return result


def source_share(observed: pd.DataFrame) -> pd.DataFrame:
    unique = observed.drop_duplicates(["list_id", "item_id", "source_id"])
    result = unique.groupby("source_name", dropna=False).size().rename("observed_records").reset_index()
    total = result["observed_records"].sum()
    result["share"] = result["observed_records"].div(total).fillna(0)
    return result.sort_values(["observed_records", "source_name"], ascending=[False, True]).reset_index(drop=True)


def list_coverage(candidates: pd.DataFrame, observed: pd.DataFrame) -> pd.DataFrame:
    candidates = normalize_columns(candidates)
    _validate(candidates, REQUIRED_CANDIDATES, "candidate lists")
    _validate(observed, REQUIRED_OBSERVED | {"source_name"}, "observed records")

    candidate_totals = candidates.drop_duplicates(["list_id", "item_id"]).groupby("list_id").size().rename("candidate_items")
    observed_unique = observed.drop_duplicates(["list_id", "item_id", "source_name"])
    covered = observed_unique.groupby(["list_id", "source_name"]).size().rename("covered_items")
    result = covered.reset_index().merge(candidate_totals.reset_index(), on="list_id", how="right")
    result["covered_items"] = result["covered_items"].fillna(0).astype(int)
    result["coverage"] = result["covered_items"].div(result["candidate_items"]).fillna(0)
    return result.sort_values(["list_id", "source_name"], na_position="last").reset_index(drop=True)


def summarize_coverage(coverage: pd.DataFrame) -> pd.DataFrame:
    if coverage.empty:
        return pd.DataFrame(columns=["source_name", "lists", "unweighted_coverage", "weighted_coverage"])

    grouped = coverage.groupby("source_name", dropna=False)
    summary = grouped.agg(
        lists=("list_id", "nunique"),
        unweighted_coverage=("coverage", "mean"),
        covered_items=("covered_items", "sum"),
        candidate_items=("candidate_items", "sum"),
    ).reset_index()
    summary["weighted_coverage"] = summary["covered_items"].div(summary["candidate_items"]).fillna(0)
    return summary[["source_name", "lists", "unweighted_coverage", "weighted_coverage"]].sort_values("source_name").reset_index(drop=True)


def unmatched_source_rate(observed: pd.DataFrame) -> float:
    if observed.empty:
        return 0.0
    return observed["source_name"].eq("no-source-found").mean()
