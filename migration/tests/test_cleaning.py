from datetime import datetime

import pandas as pd
import pytest

from src.cleaning import clean_dataframe, clean_hospital, load_csv, row_to_document


@pytest.mark.parametrize("raw, expected", [
    ("Hernandez Rogers and Vang,", "Hernandez Rogers and Vang"),
    ("and Garcia Morris Cunningham,", "Garcia Morris Cunningham"),
    ("Smith Jones and", "Smith Jones"),
    ("  Cook PLC  ", "Cook PLC"),
])
def test_clean_hospital(raw, expected):
    assert clean_hospital(raw) == expected


def test_load_csv_rejects_missing_columns(tmp_path, raw_df):
    path = tmp_path / "bad.csv"
    raw_df.drop(columns=["Age"]).to_csv(path, index=False)
    with pytest.raises(ValueError, match="Age"):
        load_csv(str(path))


def test_duplicates_removed(raw_df):
    clean, report = clean_dataframe(raw_df)
    assert report["exact_duplicates_removed"] == 1
    assert report["age_only_duplicates_removed"] == 1
    assert len(clean) == 3 == report["rows_out"]


def test_names_normalized(raw_df):
    clean, _ = clean_dataframe(raw_df)
    assert "Bobby Jackson" in clean["Name"].tolist()
    assert "Matthew Smith" in clean["Doctor"].tolist()


def test_types(raw_df):
    clean, _ = clean_dataframe(raw_df)
    assert pd.api.types.is_datetime64_any_dtype(clean["Date of Admission"])
    assert pd.api.types.is_datetime64_any_dtype(clean["Discharge Date"])
    assert clean["Age"].dtype == "int64"
    assert clean["Billing Amount"].tolist()[0] == 18856.28  # arrondi à 2 décimales


def test_negative_billing_kept(raw_df):
    clean, report = clean_dataframe(raw_df)
    assert report["negative_billing_kept"] == 1
    assert (clean["Billing Amount"] < 0).sum() == 1


def test_source_not_modified(raw_df):
    before = raw_df.copy()
    clean_dataframe(raw_df)
    pd.testing.assert_frame_equal(raw_df, before)


def test_row_to_document_structure_and_types(raw_df):
    clean, _ = clean_dataframe(raw_df)
    doc = row_to_document(clean.to_dict(orient="records")[0])
    assert set(doc) == {"patient", "admission", "medical", "billing"}
    assert type(doc["patient"]["age"]) is int
    assert type(doc["admission"]["room_number"]) is int
    assert type(doc["billing"]["amount"]) is float
    assert type(doc["admission"]["admission_date"]) is datetime
    assert doc["admission"]["admission_date"] == datetime(2024, 1, 31)
