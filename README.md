# Analytics Portfolio Export

A curated, data-free portfolio export from a private analysis workspace.

The projects are presented as reusable analytical artefacts: source code, SQL, dependency files, and portfolio-facing documentation. Proprietary source exports, customer names, internal identifiers, generated workbooks, notebooks containing private data, and operational notes are intentionally excluded.

## Featured work

### 1. Supplier-client prioritization report
The flagship project. A reproducible Python pipeline that combines supplier reference data, matched and unmatched product counts, client/entity metadata, product totals, import metadata, and prior-period tracking into a decision-ready Excel report.

Key techniques: schema-tolerant loading, Unicode normalization, mojibake repair, alias-based joins, exclusion rules, aggregation, pivoted reporting, diagnostics, and Excel formatting.

### 2. Local analytics pipeline
An end-to-end DuckDB example showing fixture generation, SQL modeling, Python orchestration, validation, Parquet export, and BI-ready outputs. It uses synthetic/open-data-compatible inputs only.

### 3. Catalog quality case
A focused data-quality exercise covering manufacturer-name standardization, foreign-key enrichment, and catalog deduplication. The original challenge data is not included in this export.

### 4. Supplier-source coverage
A reusable pandas workflow for loading source batches, enriching source labels, measuring source share, and comparing list-level coverage with weighted portfolio coverage. It uses generic input contracts and synthetic-fixture tests.

### 5. Auditable catalog transformation
An anonymized version of a large-scale Python cleaning workflow. It demonstrates normalized business-key deduplication, supplier-to-manufacturer transplantation, reviewed name mappings, role-based output partitioning, and row-level audit events.

### 6. Research throughput lineage
A row-grain pipeline analysis that traces submitted items through enrichment, candidate matching, and import stages. It separates throughput coverage from identifier agreement and preserves diagnostics for missing or asymmetric join-key populations.

## Privacy boundary

This folder contains no source data. The prioritization report expects a `sample_inputs/` directory if someone wants to run it, but no sample inputs are supplied. The local analytics pipeline's raw and generated data are also omitted. The catalog-quality scripts are included as reusable code only.

## Export inventory

```text
portfolio-export/
├── README.md
├── PRIVACY_MANIFEST.md
├── .gitignore
├── 01_supplier-client-prioritization/
│   ├── README.md
│   ├── requirements.txt
│   └── src/supplier_client_priority_report.py
├── 02_local_analytics_pipeline/
│   ├── README.md
│   ├── requirements.txt
│   ├── 01_schema.sql
│   ├── 02_analytics.sql
│   └── src/
└── 03_catalog_quality_case/
    ├── README.md
    ├── pyproject.toml
    └── src/
├── 04_supplier_source_coverage/
│   ├── README.md
│   ├── requirements.txt
│   ├── src/
│   └── tests/
└── 05_auditable_catalog_transformation/
    ├── README.md
    ├── requirements.txt
    ├── src/
    └── tests/
└── 06_research_throughput_lineage/
    ├── README.md
    ├── requirements.txt
    ├── src/
    └── tests/
```
