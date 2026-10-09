import os

import mongomock
import pandas as pd
import pytest
from pymongo import MongoClient
from pymongo.errors import PyMongoError

from src import config

HEADER = ["Name", "Age", "Gender", "Blood Type", "Medical Condition", "Date of Admission",
          "Doctor", "Hospital", "Insurance Provider", "Billing Amount", "Room Number",
          "Admission Type", "Discharge Date", "Medication", "Test Results"]

ROWS = [
    # ligne normale, casse aléatoire
    ["bOBby JacksOn", 30, "Male", "B-", "Cancer", "2024-01-31", "matthew smith",
     "Sons and Miller", "Blue Cross", 18856.281306, 328, "Urgent", "2024-02-02",
     "Paracetamol", "Normal"],
    # doublon exact de la ligne 1
    ["bOBby JacksOn", 30, "Male", "B-", "Cancer", "2024-01-31", "matthew smith",
     "Sons and Miller", "Blue Cross", 18856.281306, 328, "Urgent", "2024-02-02",
     "Paracetamol", "Normal"],
    # quasi-doublon : seul l'âge change
    ["bOBby JacksOn", 31, "Male", "B-", "Cancer", "2024-01-31", "matthew smith",
     "Sons and Miller", "Blue Cross", 18856.281306, 328, "Urgent", "2024-02-02",
     "Paracetamol", "Normal"],
    # hôpital mal formé + montant négatif
    ["LesLie TErRy", 62, "Female", "A+", "Obesity", "2019-08-20", "Samantha Davies",
     "and Garcia Morris Cunningham,", "Medicare", -1200.5, 265, "Emergency",
     "2019-08-26", "Ibuprofen", "Inconclusive"],
    ["DaNnY sMitH", 76, "Female", "O-", "Diabetes", "2022-09-22", "Tiffany Mitchell",
     "Cook PLC", "Aetna", 27955.096078, 205, "Elective", "2022-10-07", "Aspirin",
     "Abnormal"],
]


@pytest.fixture
def raw_df():
    return pd.DataFrame(ROWS, columns=HEADER)


@pytest.fixture
def csv_file(tmp_path, raw_df):
    path = tmp_path / "sample.csv"
    raw_df.to_csv(path, index=False)
    return str(path)


@pytest.fixture
def mock_db():
    return mongomock.MongoClient()["healthcare_test"]


# --- Vrai serveur MongoDB (conteneur Docker) ---------------------------------

# Collection dédiée aux tests : les 50 000 documents de `admissions` ne sont
# jamais touchés. Elle est créée dans la base `healthcare`, car migration_user
# n'a de droits que sur cette base.
TEST_COLLECTION = "admissions_test"


@pytest.fixture(scope="session")
def real_db():
    """Connexion au MongoDB du docker-compose, avec le compte migration_user.

    Si le serveur n'est pas joignable, les tests qui en dépendent sont ignorés
    (ou en échec si REQUIRE_MONGO=1, utile pour une CI).
    """
    try:
        client = MongoClient(config.mongo_uri(), serverSelectionTimeoutMS=3000)
        client.admin.command("ping")
    except PyMongoError as exc:
        if os.getenv("REQUIRE_MONGO") == "1":
            pytest.fail(f"MongoDB requis mais non joignable : {exc}")
        pytest.skip("MongoDB non joignable : tests sur serveur réel ignorés")
    yield client[config.MONGO_DB]
    client.close()


@pytest.fixture
def test_collection(real_db):
    """Nom de la collection de test, supprimée après chaque test."""
    real_db.drop_collection(TEST_COLLECTION)
    yield TEST_COLLECTION
    real_db.drop_collection(TEST_COLLECTION)
