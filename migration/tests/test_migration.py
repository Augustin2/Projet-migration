"""Migration complète sur le vrai serveur MongoDB (conteneur Docker).

Les tests travaillent sur la collection `admissions_test`, recréée puis
supprimée à chaque test : les données migrées (`admissions`) ne sont pas
touchées. Le validateur $jsonSchema est actif, comme en production.
"""
import json

import pandas as pd
import pytest
from pymongo.errors import WriteError

from src.crud_demo import run_crud
from src.export_data import export_collection
from src.migrate import run_migration

pytestmark = pytest.mark.integration


def _run(db, csv_file, collection):
    return run_migration(db, csv_file, collection, batch_size=2, use_validator=True)


def test_full_migration(real_db, csv_file, test_collection):
    report = _run(real_db, csv_file, test_collection)
    assert report["inserted"] == 3
    assert report["after"]["status"] == "OK"
    assert real_db[test_collection].count_documents({}) == 3


def test_migration_is_idempotent(real_db, csv_file, test_collection):
    _run(real_db, csv_file, test_collection)
    _run(real_db, csv_file, test_collection)
    assert real_db[test_collection].count_documents({}) == 3


def test_indexes_created(real_db, csv_file, test_collection):
    _run(real_db, csv_file, test_collection)
    names = set(real_db[test_collection].index_information())
    assert {"idx_patient_name", "idx_condition_date", "idx_admission_date",
            "idx_hospital", "idx_insurance"} <= names


def test_validator_is_active(real_db, csv_file, test_collection):
    _run(real_db, csv_file, test_collection)
    options = real_db[test_collection].options()
    assert "$jsonSchema" in options["validator"]


def test_validator_rejects_bad_type(real_db, csv_file, test_collection):
    _run(real_db, csv_file, test_collection)
    doc = real_db[test_collection].find_one({}, {"_id": 0})
    doc["patient"]["age"] = "trente"
    with pytest.raises(WriteError):
        real_db[test_collection].insert_one(doc)


def test_validator_rejects_missing_field(real_db, csv_file, test_collection):
    _run(real_db, csv_file, test_collection)
    doc = real_db[test_collection].find_one({}, {"_id": 0})
    del doc["billing"]
    with pytest.raises(WriteError):
        real_db[test_collection].insert_one(doc)


def test_crud(real_db, csv_file, test_collection):
    _run(real_db, csv_file, test_collection)
    run_crud(real_db[test_collection])
    # le document de démo est supprimé : les données migrées sont intactes
    assert real_db[test_collection].count_documents({}) == 3
    assert real_db[test_collection].count_documents({"demo": True}) == 0


def test_export(real_db, csv_file, test_collection, tmp_path):
    _run(real_db, csv_file, test_collection)
    json_path, csv_path = export_collection(real_db[test_collection], str(tmp_path))
    with open(json_path, encoding="utf-8") as f:
        assert len(json.load(f)) == 3
    exported = pd.read_csv(csv_path)
    assert len(exported) == 3
    assert "patient.name" in exported.columns
