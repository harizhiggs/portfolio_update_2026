import pandas as pd

from src.coverage_analysis import (
    annotate_source_status,
    list_coverage,
    normalize_columns,
    source_share,
    summarize_coverage,
)


def test_normalize_columns_and_union_safe_headers():
    frame = normalize_columns(pd.DataFrame({"Source ID": ["s1"], "Item-ID": ["i1"]}))
    assert list(frame.columns) == ["source_id", "item_id"]


def test_unmatched_sources_are_explicit():
    observed = pd.DataFrame(
        {"list_id": ["l1", "l1"], "item_id": ["i1", "i2"], "source_id": ["s1", "unknown"]}
    )
    lookup = pd.DataFrame({"source_id": ["s1"], "source_name": ["Source A"]})
    result = annotate_source_status(observed, lookup)
    assert result["source_name"].tolist() == ["Source A", "no-source-found"]


def test_coverage_deduplicates_and_calculates_weighted_metric():
    candidates = pd.DataFrame({"list_id": ["l1", "l1", "l2"], "item_id": ["i1", "i2", "i3"]})
    observed = pd.DataFrame(
        {
            "list_id": ["l1", "l1", "l1", "l2"],
            "item_id": ["i1", "i1", "i2", "i3"],
            "source_id": ["s1", "s1", "s2", "s1"],
            "source_name": ["Source A", "Source A", "Source B", "Source A"],
        }
    )
    coverage = list_coverage(candidates, observed)
    summary = summarize_coverage(coverage).set_index("source_name")
    assert summary.loc["Source A", "weighted_coverage"] == 2 / 3
    assert summary.loc["Source B", "weighted_coverage"] == 1 / 2
    assert source_share(observed).set_index("source_name").loc["Source A", "observed_records"] == 2
