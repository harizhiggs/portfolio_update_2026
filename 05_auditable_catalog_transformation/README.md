# Auditable catalog transformation

A generalized version of a large-scale Python cleaning workflow for supplier and manufacturer catalog records.

The case study focuses on a recurring master-data problem: names arrive with inconsistent casing and whitespace, the same business item appears more than once, and supplier records sometimes need to be reclassified. Instead of silently mutating rows, the pipeline returns a cleaned frame plus an action-level audit log.

## Staged workflow

```text
validate -> normalize -> transplant incomplete manufacturer rows
         -> deduplicate by business key -> apply reviewed mappings
         -> partition manufacturer and supplier outputs
```

### Business identity

Rows are deduplicated by normalized `manufacturer_name`, `manufacturer_article`, and `manufacturer_typecode`. This is intentionally different from dropping identical rows: formatting differences should not create a second business item, while changes to the article or typecode should remain visible for review.

### Reviewed mappings

Mappings are supplied as a small, explicit dictionary from an original name to a canonical name. This represents a reviewed mapping library without publishing the private library itself. A mapping is applied only after normalization, and every changed row receives an audit event.

### Audit events

The audit output contains `row_number`, `action`, and `details`. Typical actions include `drop_not_identified`, `transplant_supplier_to_manufacturer`, `drop_duplicate`, and `map_manufacturer_name`. This makes the transformation explainable and lets a reviewer quantify why rows changed.

## Input contract

The reusable functions expect generic columns such as:

- `proper_identification`
- `manufacturer_name`, `manufacturer_article`, `manufacturer_typecode`, `manufacturer_url`
- `supplier_name`, `supplier_article`, `supplier_url`

Missing optional columns are created as blank values. Blank values include empty strings and common null markers. The command-line example accepts Excel input because that reflects the original workflow; CSV input can be adapted at the boundary without changing the transformations.

## Run

```powershell
python -m venv .venv
.\\.venv\\Scripts\\Activate.ps1
pip install -r requirements.txt
python src/run_pipeline.py --input data/catalog.xlsx --output output
```

The command writes `cleaned_catalog.csv`, `audit_log.csv`, `manufacturer_records.csv`, and `supplier_records.csv`. No workbook, mapping library, internal identifier, URL, or proprietary row is included in this export.

## Skills demonstrated

Pandas data contracts, null handling, Unicode-safe normalization, business-key deduplication, reviewed entity resolution, role-based partitioning, auditability, and testable pipeline design.
