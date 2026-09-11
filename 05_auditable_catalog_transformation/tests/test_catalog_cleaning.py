import pandas as pd

from src.catalog_cleaning import clean_catalog, split_by_role


def test_clean_catalog_records_decisions_and_deduplicates_business_keys():
    catalog = pd.DataFrame(
        {
            "proper_identification": ["Yes", "Yes", "No", "Yes"],
            "manufacturer_name": [" Acme ", "acme", "Ignored", ""],
            "manufacturer_article": ["A-1", " A-1 ", "X", "B-1"],
            "manufacturer_typecode": ["T", "t", "X", "T"],
            "supplier_name": ["", "", "", "Source Co"],
            "supplier_article": ["", "", "", "B-1"],
            "supplier_url": ["", "", "", "https://example.test/item"],
        }
    )
    cleaned, audit = clean_catalog(catalog, {"acme": "Acme Corporation"})

    assert len(cleaned) == 2
    assert cleaned.loc[0, "manufacturer_name"] == "Acme Corporation"
    assert cleaned.loc[1, "manufacturer_name"] == "Source Co"
    assert set(audit["action"]) == {
        "drop_duplicate",
        "drop_not_identified",
        "map_manufacturer_name",
        "transplant_supplier_to_manufacturer",
    }


def test_split_by_role_keeps_supplier_records_separate():
    cleaned = pd.DataFrame(
        {
            "manufacturer_name": ["A", "B"],
            "supplier_name": ["", "Supplier"],
            "supplier_article": ["", "B-1"],
            "supplier_url": ["", "url"],
        }
    )
    manufacturer, supplier = split_by_role(cleaned)
    assert len(manufacturer) == 1
    assert len(supplier) == 1
