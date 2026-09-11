from __future__ import annotations

import re

import pandas as pd


RESEARCH_REQUIRED = {
    "list_id",
    "material_reference",
    "research_returned",
    "original_manufacturer",
    "original_article",
    "original_typecode",
    "enrichment_manufacturer",
    "enrichment_article",
    "enrichment_typecode",
}
MATCHING_REQUIRED = {"list_id", "material_reference", "is_matched"}
IMPORT_REQUIRED = {"material_reference"}


def normalize_identifier(value: object) -> str | None:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "null", "nat"}:
        return None
    if re.fullmatch(r"-?\d+\.0", text):
        return text[:-2]
    return text


def normalize_bool(value: object) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def validate(frame: pd.DataFrame, required: set[str], label: str) -> None:
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"{label} is missing required columns: {', '.join(missing)}")


def _normalize_keys(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    for column in ("list_id", "material_reference"):
        if column in result:
            result[column] = result[column].map(normalize_identifier)
    return result


def collapse_matching_candidates(matching: pd.DataFrame) -> pd.DataFrame:
    validate(matching, MATCHING_REQUIRED, "matching candidates")
    frame = _normalize_keys(matching)
    frame["is_matched"] = frame["is_matched"].map(normalize_bool)
    frame = frame.dropna(subset=["list_id", "material_reference"])
    grouped = frame.groupby(["list_id", "material_reference"], as_index=False).agg(
        n_candidates=("is_matched", "size"),
        n_positive=("is_matched", "sum"),
    )
    grouped["n_positive"] = grouped["n_positive"].astype(int)
    grouped["n_negative"] = grouped["n_candidates"] - grouped["n_positive"]
    grouped["match_status"] = grouped["n_positive"].gt(0).map({True: "green", False: "yellow"})
    return grouped


def compare_values(original: object, enriched: object, matcher=None) -> str:
    original_blank = normalize_identifier(original) is None
    enriched_blank = normalize_identifier(enriched) is None
    if original_blank and enriched_blank:
        return "both_blank"
    if original_blank:
        return "original_blank"
    if enriched_blank:
        return "enrichment_blank"
    if matcher is None:
        same = normalize_identifier(original).casefold() == normalize_identifier(enriched).casefold()
    else:
        same = matcher(original, enriched)
    return "match" if same else "mismatch"


def compare_identifiers(throughput: pd.DataFrame) -> pd.DataFrame:
    result = throughput.copy()
    for field in ("manufacturer", "article", "typecode"):
        result[f"{field}_match"] = result.apply(
            lambda row: compare_values(row[f"original_{field}"], row[f"enrichment_{field}"]), axis=1
        )

    statuses = result[["manufacturer_match", "article_match", "typecode_match"]]
    comparable = statuses.isin({"match", "mismatch"})
    result["identifier_agreement"] = "no_comparable_field"
    result.loc[comparable.any(axis=1), "identifier_agreement"] = "partial_match"
    result.loc[comparable.all(axis=1) & statuses.eq("match").all(axis=1), "identifier_agreement"] = "all_match"
    result.loc[comparable.all(axis=1) & statuses.eq("mismatch").all(axis=1), "identifier_agreement"] = "all_mismatch"
    return result


def build_throughput(
    research: pd.DataFrame,
    matching: pd.DataFrame,
    imports: pd.DataFrame,
) -> pd.DataFrame:
    validate(research, RESEARCH_REQUIRED, "research rows")
    validate(imports, IMPORT_REQUIRED, "imports")
    research = _normalize_keys(research)
    research["research_returned"] = research["research_returned"].map(normalize_bool)
    matching_pairs = collapse_matching_candidates(matching)
    imported = _normalize_keys(imports).dropna(subset=["material_reference"]).drop_duplicates("material_reference")
    imported["imported"] = True
    result = research.merge(matching_pairs, on=["list_id", "material_reference"], how="left")
    result = result.merge(imported[["material_reference", "imported"]], on="material_reference", how="left")
    result["in_matching"] = result["match_status"].notna()
    result["match_status"] = result["match_status"].fillna("no matching row")
    result["n_candidates"] = result["n_candidates"].fillna(0).astype(int)
    result["n_positive"] = result["n_positive"].fillna(0).astype(int)
    result["n_negative"] = result["n_negative"].fillna(0).astype(int)
    result["imported"] = result["imported"].eq(True)
    return compare_identifiers(result)


def coverage_summary(throughput: pd.DataFrame, matching: pd.DataFrame) -> pd.DataFrame:
    research_pairs = set(zip(throughput["list_id"], throughput["material_reference"]))
    matching_pairs = set(zip(matching["list_id"], matching["material_reference"]))
    metrics = {
        "research_rows": len(throughput),
        "research_distinct_materials": throughput["material_reference"].nunique(dropna=True),
        "research_returned": int(throughput["research_returned"].sum()),
        "research_with_matching": int(throughput["in_matching"].sum()),
        "research_green": int(throughput["match_status"].eq("green").sum()),
        "research_yellow": int(throughput["match_status"].eq("yellow").sum()),
        "research_no_matching_row": int(throughput["match_status"].eq("no matching row").sum()),
        "research_imported": int(throughput["imported"].sum()),
        "pairs_in_research_not_matching": len(research_pairs - matching_pairs),
        "pairs_in_matching_not_research": len(matching_pairs - research_pairs),
    }
    return pd.DataFrame({"metric": list(metrics), "value": list(metrics.values())})


def identifier_summary(throughput: pd.DataFrame) -> pd.DataFrame:
    statuses = ["match", "mismatch", "original_blank", "enrichment_blank", "both_blank"]
    result = pd.DataFrame(
        {
            field: throughput[f"{field}_match"].value_counts()
            for field in ("manufacturer", "article", "typecode")
        }
    )
    return result.reindex(statuses).fillna(0).astype(int)
