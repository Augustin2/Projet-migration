"""Démonstration des opérations CRUD sur la collection `admissions`.

Le document de démonstration est marqué `demo: True` et supprimé à la fin :
les données migrées ne sont pas modifiées.

Usage :
    python -m src.crud_demo
"""
import logging
from datetime import datetime
from pprint import pformat

from pymongo import MongoClient

from . import config

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("crud")

DEMO_DOC = {
    "patient": {"name": "Jean Dupont", "age": 45, "gender": "Male", "blood_type": "O+"},
    "admission": {
        "type": "Elective",
        "admission_date": datetime(2024, 3, 1),
        "discharge_date": datetime(2024, 3, 5),
        "room_number": 101,
        "hospital": "Hopital Demo",
        "doctor": "Marie Curie",
    },
    "medical": {"condition": "Asthma", "medication": "Ibuprofen", "test_results": "Normal"},
    "billing": {"amount": 1234.56, "insurance_provider": "Aetna"},
    "demo": True,
}


def run_crud(col) -> None:
    # CREATE
    inserted_id = col.insert_one(dict(DEMO_DOC)).inserted_id
    log.info("CREATE  -> document inséré : %s", inserted_id)

    # READ : le document créé, puis une requête sur les données migrées
    doc = col.find_one({"_id": inserted_id}, {"_id": 0, "patient": 1, "billing": 1})
    log.info("READ    -> %s", pformat(doc))
    n = col.count_documents({"medical.condition": "Diabetes",
                             "admission.admission_date": {"$gte": datetime(2023, 1, 1)}})
    log.info("READ    -> séjours pour diabète depuis 2023 : %d", n)
    for d in col.find({"patient.age": {"$gte": 85}}, {"_id": 0, "patient.name": 1,
                      "patient.age": 1}).sort("patient.age", -1).limit(3):
        log.info("           %s", d)

    # UPDATE
    res = col.update_one({"_id": inserted_id},
                         {"$set": {"medical.test_results": "Abnormal",
                                   "billing.amount": 1500.00}})
    log.info("UPDATE  -> %d document modifié : %s", res.modified_count,
             col.find_one({"_id": inserted_id}, {"_id": 0, "medical.test_results": 1}))

    # Agrégation : coût moyen par pathologie
    pipeline = [
        {"$match": {"demo": {"$ne": True}}},
        {"$group": {"_id": "$medical.condition", "avg": {"$avg": "$billing.amount"},
                    "n": {"$sum": 1}}},
        {"$sort": {"avg": -1}},
    ]
    log.info("AGGREGATE -> coût moyen par pathologie :")
    for r in col.aggregate(pipeline):
        log.info("           %-13s %6d séjours  %9.2f $", r["_id"], r["n"], r["avg"])

    # DELETE
    res = col.delete_one({"_id": inserted_id})
    log.info("DELETE  -> %d document supprimé", res.deleted_count)


def main() -> None:
    client = MongoClient(config.mongo_uri(), serverSelectionTimeoutMS=10000)
    try:
        run_crud(client[config.MONGO_DB][config.COLLECTION])
    finally:
        client.close()


if __name__ == "__main__":
    main()
