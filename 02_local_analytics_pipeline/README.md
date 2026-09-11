# Local Analytics Pipeline

An offline end-to-end analytics pipeline using synthetic/open-data-compatible trip records. It demonstrates a production-shaped flow without requiring private data:

1. Inspect raw input.
2. Load and type data in DuckDB.
3. Transform it with version-controlled SQL.
4. Run the stages through Python orchestration.
5. Validate row counts and date ranges.
6. Export analytics tables for BI or downstream use.

Included artefacts are the orchestration scripts and representative SQL models. Raw data, generated warehouse files, notebooks, and dashboard state are intentionally omitted.

## Run

Install the dependencies, provide a compatible CSV, then run:

```powershell
pip install -r requirements.txt
python src/run_pipeline.py --input path\to\trips.csv
python src/export_for_bi.py
```

The design emphasizes inspectability: each SQL stage is explicit, the runner reports sanity checks, and the export boundary is separate from transformation logic.
