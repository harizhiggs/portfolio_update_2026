import pandas as pd

from src.throughput_analysis import (
    build_throughput,
    collapse_matching_candidates,
    coverage_summary,
    identifier_summary,
)


def sample_frames():
    research = pd.DataFrame(
        {
            "list_id": ["10", "10", "20"],
            "material_reference": ["100.0", "101", "102"],
            "research_returned": ["yes", "no", "true"],
            "original_manufacturer": ["Acme", "", "Other"],
            "original_article": ["A-1", "B-1", "C-1"],
            "original_typecode": ["T1", "", "T3"],
            "enrichment_manufacturer": ["acme", "New", "Other"],
            "enrichment_article": ["A-1", "B-2", "C-1"],
            "enrichment_typecode": ["T1", "T2", "T3"],
        }
    )
    matching = pd.DataFrame(
        {
            "list_id": ["10", "10", "20", "99"],
            "material_reference": ["100", "100", "102", "999"],
            "is_matched": ["false", "true", "false", "true"],
        }
    )
    imports = pd.DataFrame({"material_reference": ["100.0", "102", "102"]})
    return research, matching, imports


def test_candidates_collapse_with_any_positive_match():
    pairs = collapse_matching_candidates(sample_frames()[1])
    row = pairs[(pairs.list_id == "10") & (pairs.material_reference == "100")].iloc[0]
    assert row.n_candidates == 2
    assert row.n_positive == 1
    assert row.match_status == "green"


def test_lineage_preserves_research_grain_and_stage_flags():
    research, matching, imports = sample_frames()
    throughput = build_throughput(research, matching, imports)
    assert len(throughput) == 3
    assert throughput.loc[0, "match_status"] == "green"
    assert throughput.loc[1, "match_status"] == "no matching row"
    assert throughput["imported"].tolist() == [True, False, True]
    assert throughput.loc[0, "manufacturer_match"] == "match"
    assert throughput.loc[1, "manufacturer_match"] == "original_blank"


def test_coverage_and_identifier_summaries_are_reproducible():
    research, matching, imports = sample_frames()
    throughput = build_throughput(research, matching, imports)
    summary = coverage_summary(throughput, collapse_matching_candidates(matching)).set_index("metric")
    assert summary.loc["research_rows", "value"] == 3
    assert summary.loc["research_green", "value"] == 1
    assert summary.loc["pairs_in_matching_not_research", "value"] == 1
    identifiers = identifier_summary(throughput)
    assert identifiers.loc["match", "article"] == 2
