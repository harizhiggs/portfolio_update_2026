# Research throughput lineage

A privacy-safe version of a research-throughput analysis that traces each submitted item through a multi-stage data pipeline:

```text
submitted -> enrichment returned -> candidate matching -> imported
```

The central output remains at **submitted-row grain**. Duplicate submitted rows are retained so that throughput counts describe the actual workload, while matching candidates are collapsed to one row per list-item pair before joining.

This is a coverage and lineage analysis, not a binary success score. It makes missing-stage rows visible and separates operational throughput from identifier agreement.

## Analytical questions

- How many submitted rows received any enrichment payload?
- Which submitted list-item pairs have matching candidates, and which have a positive match?
- Which material identifiers reached the import stage?
- Where do submitted and enriched manufacturer, article, and typecode values agree?
- Which join-key populations exist in one stage but not another?

## Input contract

The implementation accepts three normalized CSV inputs:

### `research.csv`

One row per submitted research line. Required columns:

- `list_id`
- `material_reference`
- `research_returned` (`true`/`false`)
- `original_manufacturer`, `original_article`, `original_typecode`
- `enrichment_manufacturer`, `enrichment_article`, `enrichment_typecode`

### `matching.csv`

One row per candidate match. Required columns:

- `list_id`
- `material_reference`
- `is_matched` (`true`/`false`)

Optional descriptive columns are aggregated when present. Multiple candidates collapse to one pair; a pair is `green` when any candidate is positive, otherwise `yellow`.

### `imports.csv`

One row per imported material. Required column: `material_reference`. Repeated materials are aggregated rather than duplicated in the lineage output.

Identifiers are normalized as strings, including removal of spreadsheet-style `.0` suffixes. The original workbook parser and source-system group labels are intentionally excluded.

## Outputs

The pipeline writes:

- `throughput.csv`: one row per submitted research line with stage flags and match counts.
- `identifier_summary.csv`: match, mismatch, and blank statuses for each compared field.
- `coverage_summary.csv`: stage counts and pair-key overlap diagnostics.

## Run

```powershell
python -m venv .venv
.\\.venv\\Scripts\\Activate.ps1
pip install -r requirements.txt
python src/run_analysis.py --research data/research.csv --matching data/matching.csv --imports data/imports.csv --output output
```

## Privacy boundary

The private notebook, research workbooks, candidate exports, imported files, generated outputs, customer/list identifiers, and source-system names are excluded. The code uses generic stage names and synthetic-fixture tests only.
