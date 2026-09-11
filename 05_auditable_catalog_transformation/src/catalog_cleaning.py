from __future__ import annotations

import re
from typing import Mapping

import pandas as pd


OPTIONAL_COLUMNS = [
    "proper_identification",
    "manufacturer_name",
    "manufacturer_article",
    "manufacturer_typecode",
    "manufacturer_url",
    "supplier_name",
    "supplier_article",
    "supplier_url",
]


def normalize_text(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    value = str(value).strip()
    if value.lower() in {"nan", "none", "null"}:
        return ""
    return value


def comparison_key(value: object) -> str:
    return re.sub(r"\s+", " ", normalize_text(value).casefold())


def prepare_catalog(catalog: pd.DataFrame) -> pd.DataFrame:
    result = catalog.copy().reset_index(drop=True)
    for column in OPTIONAL_COLUMNS:
        if column not in result:
            result[column] = ""
        result[column] = result[column].map(normalize_text)
    result["_source_row"] = result.index + 1
    return result


def _event(row_number: int, action: str, details: str) -> dict[str, object]:
    return {"row_number": row_number, "action": action, "details": details}


def clean_catalog(
    catalog: pd.DataFrame,
    mappings: Mapping[str, str] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    frame = prepare_catalog(catalog)
    audit: list[dict[str, object]] = []

    not_identified = frame["proper_identification"].map(comparison_key).eq("no")
    for row_number in frame.loc[not_identified, "_source_row"]:
        audit.append(_event(int(row_number), "drop_not_identified", "proper_identification is no"))
    frame = frame.loc[~not_identified].copy()

    for index, row in frame.iterrows():
        if not row["manufacturer_name"] and any(row[column] for column in ("supplier_name", "supplier_article", "supplier_url")):
            for source, target in (
                ("supplier_name", "manufacturer_name"),
                ("supplier_article", "manufacturer_article"),
                ("supplier_url", "manufacturer_url"),
            ):
                if row[source]:
                    frame.at[index, target] = row[source]
            frame.loc[index, ["supplier_name", "supplier_article", "supplier_url"]] = ""
            audit.append(_event(int(row["_source_row"]), "transplant_supplier_to_manufacturer", "manufacturer fields were blank"))

    key_columns = ["manufacturer_name", "manufacturer_article", "manufacturer_typecode"]
    keys = frame[key_columns].map(comparison_key).agg("|".join, axis=1)
    duplicate = keys.duplicated(keep="first")
    for row_number in frame.loc[duplicate, "_source_row"]:
        audit.append(_event(int(row_number), "drop_duplicate", "duplicate normalized manufacturer business key"))
    frame = frame.loc[~duplicate].copy()

    for index, row in frame.iterrows():
        if mappings:
            mapped = mappings.get(comparison_key(row["manufacturer_name"]))
            if mapped and mapped != row["manufacturer_name"]:
                frame.at[index, "manufacturer_name"] = normalize_text(mapped)
                audit.append(_event(int(row["_source_row"]), "map_manufacturer_name", f"mapped to {mapped}"))

    cleaned = frame.drop(columns="_source_row").reset_index(drop=True)
    audit_log = pd.DataFrame(audit, columns=["row_number", "action", "details"])
    return cleaned, audit_log


def split_by_role(cleaned: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    supplier_fields = ["supplier_name", "supplier_article", "supplier_url"]
    has_supplier = cleaned[supplier_fields].replace("", pd.NA).notna().any(axis=1)
    manufacturer = cleaned.loc[~has_supplier].reset_index(drop=True)
    supplier = cleaned.loc[has_supplier].reset_index(drop=True)
    return manufacturer, supplier
