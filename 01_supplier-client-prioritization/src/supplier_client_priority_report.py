#!/usr/bin/env python3
"""
Supplier-Client Prioritization Report Builder

Builds a supplier-client prioritization report from structured CSV/XLSX
exports under a configurable ``data_root``.

Pipeline overview:
  1. Load raw CSV/XLSX inputs from nine folders (dual-format where needed).
  2. Normalize names (Unicode NFKC, mojibake repair) and join via manufacturer aliases.
  3. Aggregate matched/unmatched counts, products-in-DB (MAX), and dataset metadata.
    4. Pivot per client/entity and write a single formatted Excel sheet.

Input note:
  ``products_per_supplier`` is expected as XLSX so Unicode supplier names are preserved
  (CSV exports previously mangled non-ASCII characters). Some folders accept CSV or XLSX
  so older and newer monthly exports both load without config changes.

Output: ``YYYYMMDD_supplier_client_priority_report.xlsx`` plus optional
    ``unmapped_suppliers.csv`` when product suppliers cannot be mapped.
"""

from __future__ import annotations

import os
import glob
import unicodedata
from typing import Dict, List, Tuple
import pandas as pd
import numpy as np

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# formats: preferred order. If any files of the first listed format exist in the
# folder, only that format is loaded; otherwise the next format is tried.
CONFIG = {
    "data_root": "./sample_inputs",
    "folders": {
        "prio_list_manufacturer_abbreviations": {
            "dir": "supplier_reference",
            "formats": ["xlsx", "csv"],
        },
        "unmatched_per_supplier_per_client": {
            "dir": "unmatched_by_supplier_entity",
            "formats": ["xlsx", "csv"],
        },
        "matched_per_supplier_per_client": {
            "dir": "matched_by_supplier_entity",
            "formats": ["csv"],
        },
        "all_datasets": {
            "dir": "dataset_metadata",
            "formats": ["csv"],
        },
        "products_per_supplier": {
            "dir": "products_by_supplier",
            "formats": ["xlsx", "csv"],
        },
        "client_entities": {
            "dir": "client_entities",
            "formats": ["csv"],
        },
        "partnership_details": {
            "dir": "relationship_rules",
            "formats": ["xlsx"],
        },
        "prev_month_list": {
            "dir": "prior_period_report",
            "formats": ["xlsx"],
        },
        "matching_details": {
            "dir": "match_timestamps",
            "formats": ["csv"],
        },
    },
    "output_path": None,  # Set in main() from data_root date prefix
    "sheet_name": "Supplier Client Priority Report",
    "col_hints": {
        "manufacturer_name": [
            "manufacturermatchingcandidates - materialreference → manufacturername",
            "manufacturername",
            "manufacturer",
            "name",
        ],
        "manufacturer_abbrev": ["spt id abbreviation", "manufacturerabbreviation", "abbreviation", "abbr"],
        "client_name": ["clients->name", "clients→name", "clients â†’ name", "clients -> name", "client", "clientname"],
        "be_name": [
            "businessentities->name",
            "businessentities → name",
            "businessentities â†’ name",
            "businessentities - businessentityid â†’ name",
            "businessentities -> name",
        ],
        "be_id": ["businessentities->id", "businessentities → id", "businessentities - businessentityid â†' id", "id"],
        "sparepartlist_id": ["matchingcandidates - matchingcandidateid → sparepartlistid", "sparepartlistid"],
        "count": ["count", "rows", "qty"],
        "display_name": ["displayname"],
        "legal_name": ["legalname"],
        # products_per_supplier XLSX uses "Manufacturer: Name"; older CSV used "Name"
        "top_name": ["manufacturer: name", "name"],
        "products_count": ["count"],
        "source_format": ["sourceformat"],
        "company_source": ["company source", "company_source"],
        "import_done": ["importdone"],
        "source_origin": ["sourceorigin"],
        "mm_total_rows": ["totalnumberofrows"],
        "matched_at": ["matchedat"],
        "prev_abbr": ["abbreviation"],
        "prev_matching_rate": ["matching rate"],
        "prev_research": ["research"],
        "prev_crawlability": ["crawlability"],
        "prev_crawler_status": ["crawler status"],
        "prev_partner_status": ["partner status"],
        "prev_stage_in_sf": ["crm stage"],
        "prev_acqu_method": ["acquisition method"],
        "prev_wrong_match": ["wrong match"],
    },
    "diagnostics_path": "./unmapped_suppliers.csv",
}

# ---------------------------------------------------------------------------
# String / column helpers
# ---------------------------------------------------------------------------

def _norm_col(s: str) -> str:
    """Normalize a column header for case-insensitive matching."""
    s = (s or "").strip()
    s = s.replace("â†’", "->").replace("→", "->").replace("—", "-").replace("–", "-").replace("’", "'")
    s = " ".join(s.split())
    return s.lower()

def _try_fix_mojibake(s: str) -> str:
    """Repair common UTF-8-as-Latin-1 mojibake, then apply NFKC normalization."""
    if s is None:
        return s
    s0 = " ".join(str(s).split())
    try:
        fixed = s0.encode("latin-1").decode("utf-8")
        if fixed != s0 and ("Ã" not in fixed and "�" not in fixed):
            s0 = fixed
    except Exception:
        pass
    s0 = unicodedata.normalize("NFKC", s0)
    return s0

def canonical_key(s: str) -> str:
    """Lowercased, whitespace-collapsed join key after mojibake repair."""
    if s is None:
        return ""
    s = _try_fix_mojibake(s)
    s = s.strip().lower()
    s = " ".join(s.split())
    return s

def to_int(series: pd.Series) -> pd.Series:
    """Parse count-like strings (including thousands separators) to int."""
    s = series.astype(str).str.replace(",", "", regex=False).str.replace("\u202f", "", regex=False).str.strip()
    return pd.to_numeric(s, errors="coerce").fillna(0).astype(int)

def normalize_id_key(val) -> str:
    """Normalize identifier-like values to a stable string key for joins/lookups."""
    if val is None or pd.isna(val):
        return ""
    s = str(val).strip().replace(",", "").replace("\u202f", "")
    if s == "":
        return ""
    try:
        n = float(s)
        if np.isfinite(n) and n.is_integer():
            return str(int(n))
    except Exception:
        pass
    return s

def parse_date_to_str(val) -> str:
    """Parse various date formats (e.g., 'May 11, 2021') to 'YYYY-MM-DD'.
    Returns empty string if parsing fails or value is empty/NaN.
    """
    if pd.isna(val) or str(val).strip() == "":
        return ""
    try:
        dt = pd.to_datetime(str(val).strip(), errors="coerce")
        if pd.isna(dt):
            return ""
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return ""

def coalesce_col(df: pd.DataFrame, candidates: List[str]) -> str | None:
    """Return the first df column matching any candidate (exact, then substring)."""
    cand_norm = [_norm_col(c) for c in candidates]
    for c in df.columns:
        if c in cand_norm:
            return c
    for c in df.columns:
        for k in cand_norm:
            if k in c:
                return c
    return None

# ---------------------------------------------------------------------------
# File loading
# ---------------------------------------------------------------------------

def read_all_csvs(folder_glob: str) -> pd.DataFrame:
    """Read and concatenate all CSV files matching a glob pattern."""
    paths = glob.glob(folder_glob)
    if not paths:
        return pd.DataFrame()
    dfs = []
    for p in paths:
        try:
            df = pd.read_csv(p, dtype=str, encoding="utf-8", keep_default_na=False, na_values=[""])
        except UnicodeDecodeError:
            df = pd.read_csv(p, dtype=str, encoding="latin-1", keep_default_na=False, na_values=[""])
        df.columns = [_norm_col(c) for c in df.columns]
        dfs.append(df)
    return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()

def read_excel_files(folder_glob: str) -> pd.DataFrame:
    """Read and concatenate all Excel files matching a glob pattern."""
    paths = glob.glob(folder_glob)
    if not paths:
        return pd.DataFrame()
    dfs = []
    for p in paths:
        df = pd.read_excel(p, dtype=str, keep_default_na=False, na_values=[""])
        df.columns = [_norm_col(c) for c in df.columns]
        dfs.append(df)
    return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()

def _folder_glob(root: str, folder_dir: str, ext: str) -> str:
    return os.path.join(root, folder_dir, f"*.{ext}")

def read_folder(root: str, folder_dir: str, formats: List[str]) -> pd.DataFrame:
    """Load a data folder using preferred format order (xlsx before csv when both listed).

    If any files exist for the first format in ``formats``, only that format is read.
    Otherwise the next format is tried. Returns an empty DataFrame if nothing matches.
    """
    for ext in formats:
        pattern = _folder_glob(root, folder_dir, ext)
        paths = glob.glob(pattern)
        if not paths:
            continue
        if ext == "xlsx":
            return read_excel_files(pattern)
        if ext == "csv":
            return read_all_csvs(pattern)
        raise ValueError(f"Unsupported format '{ext}' for folder {folder_dir}")
    return pd.DataFrame()

def load_inputs(cfg: Dict) -> Dict[str, pd.DataFrame]:
    """Load all configured input folders into a dict of DataFrames."""
    root = cfg["data_root"]
    result = {}
    for key, spec in cfg["folders"].items():
        result[key] = read_folder(root, spec["dir"], spec["formats"])
    return result

def load_prev_month_matching_rate(cfg: Dict) -> pd.DataFrame:
    """Load previous month's priority list Excel and extract Abbreviation + tracking columns.

    Expects exactly one Excel file in prev_month_list.
    Tries header row 4, then falls back to row 3 (0-indexed multi-row headers).

    Returns DataFrame with columns: abbr, last_month_mr, and optionally research,
    crawlability, crawler_status, partner_status, stage_in_sf, acqu_method, wrong_match.
    """
    root = cfg["data_root"]
    folder_dir = cfg["folders"]["prev_month_list"]["dir"]
    pattern = _folder_glob(root, folder_dir, "xlsx")
    paths = glob.glob(pattern)

    if len(paths) == 0:
        raise ValueError(f"No Excel file found in prev_month_list folder: {pattern}")
    if len(paths) > 1:
        raise ValueError(f"Multiple Excel files found in prev_month_list folder (expected exactly 1): {paths}")

    try:
        df = pd.read_excel(paths[0], header=4, dtype=str, keep_default_na=False, na_values=[""])
        df.columns = [_norm_col(c) for c in df.columns]
        c_abbr = coalesce_col(df, cfg["col_hints"]["prev_abbr"])
        c_mr = coalesce_col(df, cfg["col_hints"]["prev_matching_rate"])

        if c_abbr is None or c_mr is None:
            df = pd.read_excel(paths[0], header=3, dtype=str, keep_default_na=False, na_values=[""])
            df.columns = [_norm_col(c) for c in df.columns]
            c_abbr = coalesce_col(df, cfg["col_hints"]["prev_abbr"])
            c_mr = coalesce_col(df, cfg["col_hints"]["prev_matching_rate"])
    except Exception as e:
        raise ValueError(f"Failed to read prev_month Excel file {paths[0]}: {e}")

    if c_abbr is None or c_mr is None:
        raise ValueError(f"prev_month file missing Abbreviation or Matching Rate columns. Found: {list(df.columns)}")

    c_research = coalesce_col(df, cfg["col_hints"]["prev_research"])
    c_crawl = coalesce_col(df, cfg["col_hints"]["prev_crawlability"])
    c_crawl_status = coalesce_col(df, cfg["col_hints"]["prev_crawler_status"])
    c_partner = coalesce_col(df, cfg["col_hints"]["prev_partner_status"])
    c_stage = coalesce_col(df, cfg["col_hints"]["prev_stage_in_sf"])
    c_acqu = coalesce_col(df, cfg["col_hints"]["prev_acqu_method"])
    c_wrong = coalesce_col(df, cfg["col_hints"]["prev_wrong_match"])

    cols_to_extract = [c_abbr, c_mr]
    col_names = ["abbr", "last_month_mr"]

    for col, name in [
        (c_research, "research"),
        (c_crawl, "crawlability"),
        (c_crawl_status, "crawler_status"),
        (c_partner, "partner_status"),
        (c_stage, "stage_in_sf"),
        (c_acqu, "acqu_method"),
        (c_wrong, "wrong_match"),
    ]:
        if col is not None:
            cols_to_extract.append(col)
            col_names.append(name)

    result = df[cols_to_extract].copy()
    result.columns = col_names
    result["abbr"] = result["abbr"].astype(str).str.strip()
    if "last_month_mr" in result.columns:
        result["last_month_mr"] = pd.to_numeric(result["last_month_mr"], errors="coerce")
    result = result[result["abbr"].str.len() > 0]
    result = result.drop_duplicates(subset=["abbr"])
    return result

def load_matching_details(cfg: Dict) -> Dict[str, str]:
    """Load matching-details and return {be_id: matched_at} as YYYY-MM-DD or 'N/A'."""
    root = cfg["data_root"]
    folder_dir = cfg["folders"]["matching_details"]["dir"]
    df = read_folder(root, folder_dir, cfg["folders"]["matching_details"]["formats"])

    if df.empty:
        return {}

    c_splist = coalesce_col(df, [
        "matchingcandidates - matchingcandidateid -> sparepartlistid",
        "client entities - entityid -> sparepartlistid",
        "sparepartlistid",
        "sparepartlist_id",
    ])
    if c_splist is None:
        for c in df.columns:
            if "sparepartlistid" in c:
                c_splist = c
                break
    if c_splist is None:
        c_splist = coalesce_col(df, ["id"])

    c_matched_at = coalesce_col(df, cfg["col_hints"]["matched_at"])

    if c_splist is None or c_matched_at is None:
        return {}

    tmp = df[[c_splist, c_matched_at]].copy()
    tmp["be_id"] = tmp[c_splist].map(normalize_id_key)
    try:
        tmp["matched_at_dt"] = pd.to_datetime(tmp[c_matched_at], errors="coerce", format="mixed")
    except TypeError:
        tmp["matched_at_dt"] = pd.to_datetime(tmp[c_matched_at], errors="coerce")
    tmp = tmp[tmp["be_id"] != ""]

    with_dates = tmp[tmp["matched_at_dt"].notna()].copy()
    result: Dict[str, str] = {}
    if not with_dates.empty:
        latest = with_dates.sort_values(["be_id", "matched_at_dt"], ascending=[True, False]).drop_duplicates(
            subset=["be_id"], keep="first"
        )
        result.update({
            r["be_id"]: r["matched_at_dt"].strftime("%Y-%m-%d")
            for _, r in latest.iterrows()
        })

    for be_id in tmp["be_id"].drop_duplicates().tolist():
        if be_id not in result:
            result[be_id] = "N/A"

    return result

# ---------------------------------------------------------------------------
# Manufacturer dimension and exclusions
# ---------------------------------------------------------------------------

def get_excluded_manufacturers(df_partnership: pd.DataFrame) -> set:
    """Manufacturer canonical keys flagged 'y' under 'exclude due to bad name'."""
    if df_partnership.empty:
        return set()
    c_manu = coalesce_col(df_partnership, ["manufacturer"])
    c_exclude = coalesce_col(df_partnership, ["exclude due to bad name"])
    if c_manu is None or c_exclude is None:
        return set()
    df = df_partnership[[c_manu, c_exclude]].copy()
    df[c_exclude] = df[c_exclude].astype(str).str.strip().str.lower()
    excluded = df[df[c_exclude] == "y"][c_manu].unique()
    return {canonical_key(m) for m in excluded if pd.notna(m) and str(m).strip()}

def build_manufacturer_dim(df_abbrev: pd.DataFrame, excluded_manufacturers: set = None) -> pd.DataFrame:
    """Build manufacturer dimension (manufacturer, legal_name, abbr), applying exclusions."""
    if df_abbrev.empty:
        raise ValueError("Abbreviations file is required.")
    c_name = coalesce_col(df_abbrev, ["name"])
    c_legal = coalesce_col(df_abbrev, ["legalname"])
    c_abbr = coalesce_col(df_abbrev, ["abbreviation"])
    for c in [c_name, c_legal, c_abbr]:
        if c is None:
            raise ValueError("Abbreviations file is missing Name/LegalName/Abbreviation.")
    dim = df_abbrev[[c_name, c_legal, c_abbr]].copy()
    dim.columns = ["manufacturer", "legal_name", "abbr"]
    dim = dim.drop_duplicates(subset=["abbr"]).reset_index(drop=True)

    initial_count = len(dim)
    if excluded_manufacturers and len(excluded_manufacturers) > 0:
        dim["manu_key"] = dim["manufacturer"].map(canonical_key)
        dim = dim[~dim["manu_key"].isin(excluded_manufacturers)]
        dim = dim.drop(columns=["manu_key"]).reset_index(drop=True)
        print(f"Exclusions applied: {initial_count} -> {len(dim)} manufacturers ({initial_count - len(dim)} excluded)")

    return dim

def manufacturer_alias_table(dim_m: pd.DataFrame) -> pd.DataFrame:
    """Map display and legal names to abbreviations via canonical keys."""
    recs = []
    for _, r in dim_m.iterrows():
        for alias in [r["manufacturer"], r["legal_name"]]:
            if pd.notna(alias) and str(alias).strip():
                recs.append({"abbr": r["abbr"], "alias_key": canonical_key(alias)})
    return pd.DataFrame(recs).drop_duplicates(subset=["alias_key"])

# ---------------------------------------------------------------------------
# Aggregations
# ---------------------------------------------------------------------------

def aggregate_unmatched_per_client(df_u, dim_m, aliases, cfg, df_focus_map):
    """Aggregate unmatched counts joined to client/BE via SparepartListId."""
    if df_u.empty:
        return pd.DataFrame(columns=["abbr", "manufacturer", "client", "client_key", "be_name", "be_key", "count"])
    c_splist = coalesce_col(df_u, ["sparepartlistid"])
    c_mname = coalesce_col(df_u, cfg["col_hints"]["manufacturer_name"])
    c_count = coalesce_col(df_u, cfg["col_hints"]["count"])
    for c in [c_splist, c_mname, c_count]:
        if c is None:
            raise ValueError("Unmatched-per-client file missing a required column (SparepartListId, ManufacturerName, Count).")
    tmp = df_u[[c_splist, c_mname, c_count]].copy()
    tmp.columns = ["splist_id", "manu_name", "count"]
    tmp["count"] = to_int(tmp["count"])
    tmp["splist_id"] = tmp["splist_id"].map(normalize_id_key)
    tmp = tmp.merge(df_focus_map, left_on="splist_id", right_on="be_id", how="left")
    tmp["manu_key"] = tmp["manu_name"].map(canonical_key)
    tmp = tmp.merge(aliases, left_on="manu_key", right_on="alias_key", how="left")
    tmp = tmp.merge(dim_m[["abbr", "manufacturer"]], on="abbr", how="left")
    tmp["abbr"] = tmp["abbr"].fillna("")
    tmp["manufacturer"] = tmp["manufacturer"].fillna(tmp["manu_name"].map(_try_fix_mojibake))
    return tmp[["abbr", "manufacturer", "client", "client_key", "be_name", "be_key", "count"]].dropna(subset=["client"])

def aggregate_matched_per_client(df_m, dim_m, aliases, cfg, df_focus_map):
    """Aggregate matched counts joined to client/BE via SparepartListId + Abbreviation."""
    if df_m.empty:
        return pd.DataFrame(columns=["abbr", "manufacturer", "legal_name", "client", "client_key", "be_name", "be_key", "be_id", "count"])
    c_splist = coalesce_col(df_m, cfg["col_hints"]["sparepartlist_id"])
    c_abbr = coalesce_col(df_m, cfg["col_hints"]["manufacturer_abbrev"])
    c_count = coalesce_col(df_m, cfg["col_hints"]["count"])
    for c in [c_splist, c_abbr, c_count]:
        if c is None:
            raise ValueError("Matched-per-client file missing a required column (SparepartListId, Abbreviation, Count).")
    tmp = df_m[[c_splist, c_abbr, c_count]].copy()
    tmp.columns = ["splist_id", "abbr", "count"]
    tmp["count"] = to_int(tmp["count"])
    tmp["abbr"] = tmp["abbr"].astype(str).str.strip()
    tmp["splist_id"] = tmp["splist_id"].map(normalize_id_key)
    tmp = tmp.merge(df_focus_map, left_on="splist_id", right_on="be_id", how="left")
    tmp = tmp.merge(dim_m[["abbr", "manufacturer", "legal_name"]], on="abbr", how="left")
    return tmp[["abbr", "manufacturer", "legal_name", "client", "client_key", "be_name", "be_key", "be_id", "count"]].dropna(subset=["client"])

def products_per_supplier(df_p, dim_m, aliases, cfg):
    """Map supplier product counts to abbreviations using MAX across batch duplicates.

    Returns (products_df, unmapped_df) where unmapped_df lists supplier keys with no abbr.
    """
    if df_p.empty:
        return dim_m[["abbr", "manufacturer"]].assign(products_in_db=0), pd.DataFrame(columns=["unmapped_supplier_key"])
    c_name = coalesce_col(df_p, cfg["col_hints"]["top_name"])
    c_cnt = coalesce_col(df_p, cfg["col_hints"]["products_count"])
    if c_name is None or c_cnt is None:
        raise ValueError("Products-per-supplier missing (Name / Manufacturer: Name, Count).")
    tmp = df_p[[c_name, c_cnt]].copy()
    tmp.columns = ["name", "count"]
    tmp["name"] = tmp["name"].map(_try_fix_mojibake)
    tmp["name_key"] = tmp["name"].map(canonical_key)
    tmp["count"] = to_int(tmp["count"])
    tmp = tmp.groupby("name_key", as_index=False)["count"].max()
    tmp = tmp.merge(aliases.rename(columns={"alias_key": "name_key"}), on="name_key", how="left")
    agg = tmp.groupby("abbr", dropna=False, as_index=False)["count"].max().rename(columns={"count": "products_in_db"})
    out = dim_m[["abbr", "manufacturer"]].merge(agg, on="abbr", how="left").fillna({"products_in_db": 0})
    out["products_in_db"] = out["products_in_db"].astype(int)
    unmapped = tmp[tmp["abbr"].isna()][["name_key"]].drop_duplicates().rename(columns={"name_key": "unmapped_supplier_key"})
    return out[["abbr", "manufacturer", "products_in_db"]], unmapped

def latest_dataset_info(df_all, dim_m, aliases, cfg):
    """Latest ImportDone date per manufacturer with SourceFormat, SourceOrigin, and row counts."""
    if df_all.empty:
        return dim_m[["abbr", "manufacturer"]].assign(
            import_done="", source_format="", source_origin="", datasets_imported=0
        )

    c_srcfmt = coalesce_col(df_all, cfg["col_hints"]["source_format"])
    c_company = coalesce_col(df_all, cfg["col_hints"]["company_source"])
    c_import = coalesce_col(df_all, cfg["col_hints"]["import_done"])
    c_origin = coalesce_col(df_all, cfg["col_hints"]["source_origin"])

    if c_srcfmt is None or c_company is None:
        raise ValueError("all_datasets needs SourceFormat and Company Source.")

    df = df_all.copy()
    df["company_key"] = df[c_company].map(canonical_key)
    df = df.merge(aliases.rename(columns={"alias_key": "company_key"}), on="company_key", how="left")

    imported = df.groupby("abbr", dropna=False, as_index=False).size().rename(columns={"size": "datasets_imported"})

    df["_import_date"] = df[c_import].apply(
        lambda x: pd.to_datetime(x, errors="coerce") if pd.notna(x) and str(x).strip() else pd.NaT
    )
    df_with_dates = df[df["_import_date"].notna()].copy()

    if df_with_dates.empty:
        out = dim_m[["abbr", "manufacturer"]].copy()
        out["import_done"] = ""
        out["source_format"] = ""
        out["source_origin"] = ""
    else:
        df_with_dates = df_with_dates.sort_values(["abbr", "_import_date"], ascending=[True, False])
        latest = df_with_dates.groupby("abbr", as_index=False).first()
        latest["import_done"] = latest["_import_date"].apply(
            lambda x: x.strftime("%Y-%m-%d") if pd.notna(x) else ""
        )
        latest["source_format"] = latest[c_srcfmt].fillna("") if c_srcfmt else ""
        latest["source_origin"] = latest[c_origin].fillna("") if c_origin else ""
        out = dim_m[["abbr", "manufacturer"]].merge(
            latest[["abbr", "import_done", "source_format", "source_origin"]],
            on="abbr", how="left",
        )
        out["import_done"] = out["import_done"].fillna("")
        out["source_format"] = out["source_format"].fillna("")
        out["source_origin"] = out["source_origin"].fillna("")

    out = out.merge(imported, on="abbr", how="left")
    out["datasets_imported"] = out["datasets_imported"].fillna(0).astype(int)

    return out[["abbr", "manufacturer", "import_done", "source_format", "source_origin", "datasets_imported"]]

def mm_rows_from_focus(df_focus, cfg):
    """Extract client/entity mapping and total rows from the entity reference table."""
    if df_focus.empty:
        return pd.DataFrame(columns=["client", "client_key", "be_name", "be_key", "be_id", "mm_total_rows"])
    c_client = coalesce_col(df_focus, cfg["col_hints"]["client_name"])
    c_be_name = coalesce_col(df_focus, cfg["col_hints"]["be_name"])
    c_id = coalesce_col(df_focus, ["id"])
    c_total = coalesce_col(df_focus, cfg["col_hints"]["mm_total_rows"])
    for c in [c_client, c_be_name, c_id, c_total]:
        if c is None:
            raise ValueError("client_entities missing (client, entity name, id, total rows).")
    df = df_focus[[c_client, c_be_name, c_id, c_total]].copy()
    df.columns = ["client", "be_name", "be_id", "mm_total_rows"]
    df["client"] = df["client"].map(_try_fix_mojibake)
    df["be_name"] = df["be_name"].map(_try_fix_mojibake)
    df["client_key"] = df["client"].map(canonical_key)
    df["be_key"] = df["be_name"].map(canonical_key)
    df["be_id"] = df["be_id"].map(normalize_id_key)
    df["mm_total_rows"] = to_int(df["mm_total_rows"])
    return df

# ---------------------------------------------------------------------------
# Report assembly
# ---------------------------------------------------------------------------

def build_report(cfg: Dict) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Assemble the full priority-list DataFrame and unmapped-products diagnostics.

    Returns (final_df, unmapped_prod).
    """
    data = load_inputs(cfg)

    excluded_manufacturers = get_excluded_manufacturers(data.get("partnership_details", pd.DataFrame()))

    dim_m = build_manufacturer_dim(data["prio_list_manufacturer_abbreviations"], excluded_manufacturers)
    aliases = manufacturer_alias_table(dim_m)

    df_focus = mm_rows_from_focus(data["client_entities"], cfg)
    df_focus_map = df_focus[["be_id", "client", "client_key", "be_name", "be_key"]].copy()

    df_u = aggregate_unmatched_per_client(data["unmatched_per_supplier_per_client"], dim_m, aliases, cfg, df_focus_map)
    df_m = aggregate_matched_per_client(data["matched_per_supplier_per_client"], dim_m, aliases, cfg, df_focus_map)
    df_prod, unmapped_prod = products_per_supplier(data["products_per_supplier"], dim_m, aliases, cfg)
    df_all = latest_dataset_info(data["all_datasets"], dim_m, aliases, cfg)

    df_prev_mr = load_prev_month_matching_rate(cfg)
    matching_details = load_matching_details(cfg)

    display_map = {}
    for _, r in df_focus[["client_key", "client"]].drop_duplicates().iterrows():
        display_map[("client", r["client_key"])] = r["client"]
    for _, r in df_focus[["be_key", "be_name"]].drop_duplicates().iterrows():
        display_map[("be", r["be_key"])] = r["be_name"]

    def disp(kind, key):
        return display_map.get((kind, key), key)

    unmatched_pivot = (
        df_u.pivot_table(index=["abbr", "manufacturer"], columns=["client_key", "be_key"], values="count", aggfunc="sum", fill_value=0)
        if not df_u.empty else pd.DataFrame()
    )
    matched_pivot = (
        df_m.pivot_table(index=["abbr", "manufacturer"], columns=["client_key", "be_key"], values="count", aggfunc="sum", fill_value=0)
        if not df_m.empty else pd.DataFrame()
    )

    all_cols = sorted(set(unmatched_pivot.columns).union(set(matched_pivot.columns)))
    unmatched_pivot = unmatched_pivot.reindex(columns=all_cols, fill_value=0)
    matched_pivot = matched_pivot.reindex(columns=all_cols, fill_value=0)

    idx_from_dim = pd.MultiIndex.from_frame(dim_m[["abbr", "manufacturer"]])
    if not unmatched_pivot.empty:
        unmatched_row_sum = unmatched_pivot.sum(axis=1).reindex(idx_from_dim, fill_value=0)
    else:
        unmatched_row_sum = pd.Series(0, index=idx_from_dim)

    if not matched_pivot.empty:
        matched_row_sum = matched_pivot.sum(axis=1).reindex(idx_from_dim, fill_value=0)
    else:
        matched_row_sum = pd.Series(0, index=idx_from_dim)

    base = dim_m.set_index(["abbr", "manufacturer"]).copy()
    base = base.join(df_prod.set_index(["abbr", "manufacturer"]), how="left")
    base = base.join(df_all.set_index(["abbr", "manufacturer"]), how="left")

    prev_cols = [c for c in df_prev_mr.columns if c != "abbr"]
    df_prev_indexed = df_prev_mr.set_index("abbr")[prev_cols]
    base = base.join(df_prev_indexed, on="abbr", how="left")

    base["unmatched_rows_mm_signed_clients"] = unmatched_row_sum
    base["matched_rows_mm_signed_clients"] = matched_row_sum
    base["total_rows_mm_signed_clients"] = base["unmatched_rows_mm_signed_clients"] + base["matched_rows_mm_signed_clients"]
    base["matching_rate"] = np.where(
        base["total_rows_mm_signed_clients"] > 0,
        base["matched_rows_mm_signed_clients"] / base["total_rows_mm_signed_clients"],
        np.nan,
    )

    def build_header_block(cols: List[Tuple[str, str]], label: str, matching_details_dict: Dict[str, str]) -> pd.MultiIndex:
        """Build 5-row MultiIndex header: label, BE ID, MatchedAt, Client Name, BE Name."""
        tuples = []
        for ck, bk in cols:
            client_disp = disp("client", ck)
            be_disp = disp("be", bk)
            row = df_focus[(df_focus["client_key"] == ck) & (df_focus["be_key"] == bk)]
            be_id = normalize_id_key(row["be_id"].iloc[0]) if not row.empty else ""
            matched_at = matching_details_dict.get(be_id, "N/A")
            tuples.append((label, be_id, matched_at, client_disp, be_disp))
        return pd.MultiIndex.from_tuples(tuples, names=["", "", "", "", ""])

    unmatched_hdr = build_header_block(list(unmatched_pivot.columns), "Unmatched", matching_details)
    matched_hdr = build_header_block(list(matched_pivot.columns), "Matched Rows", matching_details)

    unmatched_block = pd.DataFrame(unmatched_pivot.to_numpy(), index=unmatched_pivot.index, columns=unmatched_hdr)
    matched_block = pd.DataFrame(matched_pivot.to_numpy(), index=matched_pivot.index, columns=matched_hdr)

    left_cols = ["legal_name", "import_done", "source_format", "source_origin", "products_in_db", "datasets_imported"]
    for col in ["research", "crawlability", "crawler_status", "partner_status", "stage_in_sf", "acqu_method", "wrong_match"]:
        if col in base.columns:
            left_cols.append(col)
    left_cols.extend([
        "total_rows_mm_signed_clients",
        "unmatched_rows_mm_signed_clients",
        "matched_rows_mm_signed_clients",
        "matching_rate",
        "last_month_mr",
    ])

    left_block = base[left_cols]
    left_block = left_block.reindex(dim_m.set_index(["abbr", "manufacturer"]).index)

    final_df = pd.concat([left_block, unmatched_block, matched_block], axis=1)
    final_df = final_df.fillna(0)

    final_df = final_df.reset_index().rename(columns={
        "abbr": "Abbreviation",
        "manufacturer": "Manufacturer",
        "legal_name": "Legal Name",
        "import_done": "Import Done",
        "source_format": "Source Format",
        "source_origin": "Source Origin",
        "products_in_db": "Products in DB",
        "datasets_imported": "Datasets imported",
        "research": "Research",
        "crawlability": "Crawlability",
        "crawler_status": "Crawler Status",
        "partner_status": "Partner status",
        "stage_in_sf": "CRM stage",
        "acqu_method": "Acquisition Method",
        "wrong_match": "wrong match",
        "total_rows_mm_signed_clients": "Total Rows MM signed clients",
        "unmatched_rows_mm_signed_clients": "Unmatched Rows MM Signed Clients",
        "matched_rows_mm_signed_clients": "Matched Rows MM Signed Clients",
        "matching_rate": "Matching Rate",
        "last_month_mr": "Last Month MR",
    })
    return final_df, unmapped_prod

def write_excel_single_sheet(df: pd.DataFrame, path: str, sheet_name: str):
    """Write DataFrame to Excel with percentage formatting for Matching Rate columns."""
    try:
        import xlsxwriter  # noqa: F401
        engine = "xlsxwriter"
    except ImportError:
        engine = "openpyxl"

    rate_column_names = ["Matching Rate", "Last Month MR"]

    with pd.ExcelWriter(path, engine=engine) as writer:
        df2 = df.copy()

        rate_col_indices = []
        for i, col in enumerate(df2.columns):
            col_name = col[0] if isinstance(col, tuple) else col
            if col_name in rate_column_names:
                rate_col_indices.append(i)
                df2.iloc[:, i] = pd.to_numeric(df2.iloc[:, i], errors="coerce")

        df2.to_excel(writer, index=False, sheet_name=sheet_name)

        if engine == "xlsxwriter":
            ws = writer.sheets[sheet_name]
            percent_fmt = writer.book.add_format({"num_format": "0.00%"})
            for col_idx in rate_col_indices:
                ws.set_column(col_idx, col_idx, None, percent_fmt)
        else:
            from openpyxl.utils import get_column_letter
            ws = writer.sheets[sheet_name]
            for col_idx in rate_col_indices:
                col_letter = get_column_letter(col_idx + 1)
                for cell in ws[col_letter]:
                    cell.number_format = "0.00%"

def write_unmapped_diagnostics(unmapped: pd.DataFrame, path: str) -> None:
    """Write unmapped product-supplier keys to CSV when non-empty."""
    if unmapped is None or unmapped.empty:
        return
    unmapped.to_csv(path, index=False)
    print(f"Unmapped product suppliers written to: {path} | Rows: {len(unmapped)}")

# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

def main():
    cfg = CONFIG
    folder_name = os.path.basename(cfg["data_root"].rstrip("/").rstrip("\\"))
    date_prefix = folder_name[:6] if len(folder_name) >= 6 else folder_name
    output_path = f"./{date_prefix}_supplier_client_priority_report.xlsx"
    cfg["output_path"] = output_path

    final_df, unmapped_prod = build_report(cfg)
    write_excel_single_sheet(final_df, cfg["output_path"], cfg["sheet_name"])
    write_unmapped_diagnostics(unmapped_prod, cfg["diagnostics_path"])
    print(f"Report written to: {cfg['output_path']} | Rows: {len(final_df)} | Cols: {len(final_df.columns)}")

if __name__ == "__main__":
    main()
