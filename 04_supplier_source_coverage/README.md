# Supplier-source coverage analysis

A reusable pandas workflow for understanding how consistently external sources cover a set of candidate item lists.

The case study answers two related questions:

1. What share of observed item records comes from each source?
2. How much of each candidate list is covered by each source?

It demonstrates batch ingestion, schema normalization, source enrichment, duplicate-safe counting, unmatched-ID diagnostics, and both list-level and weighted portfolio KPIs. The implementation uses generic fields and synthetic fixtures only.

## Workflow

```text
CSV batches -> normalized schema -> source labels -> source shares
candidate lists + observed records -> list coverage -> weighted summary
```

## Input contract

Batch CSV files in `data/source_batches/` should contain:

- `list_id`: candidate-list identifier
- `item_id`: item identifier
- `source_id`: source identifier

The candidate-list CSV should contain `list_id` and `item_id`. An optional lookup CSV can contain `source_id` and `source_name`. All identifiers are treated as strings.

Files may use minor naming differences such as `Source ID` or `item-id`; headers are normalized to lowercase `snake_case` before validation. Every batch contributes to the union of available columns.

## Metrics

- **Source share**: distinct observed item records attributed to a source divided by all distinct observed records.
- **List coverage**: distinct items observed for a source in a list divided by the candidate-item total for that list.
- **Weighted coverage**: total distinct covered candidate items divided by total candidate items, so larger lists contribute proportionally more.
- **Unmatched-source rate**: observed records whose source ID is absent from the lookup divided by all observed records.

The report also retains the unweighted mean of list-level coverage because it answers a different question: the typical-list experience.

## Data-quality safeguards

- Batch schemas are unioned instead of trusting the first file's columns.
- Duplicate observations are removed before counting.
- Missing lookup matches are labeled `no-source-found`.
- Empty groups and zero denominators produce zero percentages rather than errors.
- Required columns are validated at the boundary.

## Run

```powershell
python -m venv .venv
.\\.venv\\Scripts\\Activate.ps1
pip install -r requirements.txt
python src/run_analysis.py --batches data/source_batches --candidates data/candidate_lists.csv --lookup data/source_lookup.csv --output output
```

The command writes CSV summaries for source share, list coverage, and portfolio KPIs. No input data or generated output is included in this export.

## Portfolio boundary

The original notebook, supplier names, internal IDs, URLs, row counts, and generated workbook are excluded. To reproduce the workflow, supply synthetic or public-compatible CSVs following the contract above.
