import numpy as np
import pytest

from src.cleaning import clean_dataframe, dataframe_to_documents
from src.integrity import IntegrityError, check_after, check_before


def test_check_before_profile(raw_df):
    report = check_before(raw_df)
    assert report["rows"] == 5
    assert report["missing_columns"] == []
    assert report["missing_values"] == {}
    assert report["exact_duplicates"] == 1
    assert report["duplicates_ignoring_age"] == 2
    assert report["negative_billing"] == 1
    assert report["discharge_before_admission"] == 0


def test_check_before_detects_missing_values(raw_df):
    raw_df.loc[0, "Gender"] = np.nan
    assert check_before(raw_df)["missing_values"] == {"Gender": 1}


def _load(mock_db, raw_df):
    clean, _ = clean_dataframe(raw_df)
    col = mock_db["admissions"]
    col.insert_many(dataframe_to_documents(clean))
    return col, clean


def test_check_after_ok(mock_db, raw_df):
    col, clean = _load(mock_db, raw_df)
    report = check_after(col, clean)
    assert report["status"] == "OK"
    assert report["documents"] == 3


def test_check_after_detects_missing_document(mock_db, raw_df):
    col, clean = _load(mock_db, raw_df)
    col.delete_one({})
    with pytest.raises(IntegrityError, match="documents en base"):
        check_after(col, clean)


def test_check_after_detects_wrong_type(mock_db, raw_df):
    col, clean = _load(mock_db, raw_df)
    col.update_one({}, {"$set": {"patient.age": "trente"}})
    with pytest.raises(IntegrityError, match="patient.age"):
        check_after(col, clean)


def test_check_after_detects_missing_field(mock_db, raw_df):
    col, clean = _load(mock_db, raw_df)
    col.update_one({}, {"$unset": {"billing.amount": ""}})
    with pytest.raises(IntegrityError, match="billing.amount"):
        check_after(col, clean)


def test_check_after_detects_duplicate(mock_db, raw_df):
    col, clean = _load(mock_db, raw_df)
    doc = col.find_one({}, {"_id": 0})
    col.insert_one(doc)
    col.delete_one({"patient.name": "Danny Smith"})  # garde le même total de documents
    with pytest.raises(IntegrityError, match="doublons"):
        check_after(col, clean)
