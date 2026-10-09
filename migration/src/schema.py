"""Schéma de validation ($jsonSchema) et index de la collection `admissions`.

Le validateur est appliqué côté serveur : MongoDB refuse tout document
dont un champ manque ou n'a pas le bon type BSON. C'est une garantie de
typage qui ne dépend pas du script Python.
"""
from pymongo import ASCENDING, IndexModel

_str = {"bsonType": "string"}
_int = {"bsonType": "int"}
_date = {"bsonType": "date"}
_double = {"bsonType": "double"}


def _obj(props: dict) -> dict:
    return {
        "bsonType": "object",
        "required": list(props),
        "properties": props,
    }


ADMISSION_VALIDATOR = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["patient", "admission", "medical", "billing"],
        "properties": {
            "patient": _obj({
                "name": _str,
                "age": {"bsonType": "int", "minimum": 0, "maximum": 120},
                "gender": {"enum": ["Male", "Female"]},
                "blood_type": {"enum": ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]},
            }),
            "admission": _obj({
                "type": {"enum": ["Emergency", "Elective", "Urgent"]},
                "admission_date": _date,
                "discharge_date": _date,
                "room_number": _int,
                "hospital": _str,
                "doctor": _str,
            }),
            "medical": _obj({
                "condition": _str,
                "medication": _str,
                "test_results": {"enum": ["Normal", "Abnormal", "Inconclusive"]},
            }),
            "billing": _obj({
                "amount": _double,
                "insurance_provider": _str,
            }),
        },
    }
}

# Index choisis d'après les requêtes métier attendues
INDEXES = [
    # Retrouver les séjours d'un patient par son nom
    IndexModel([("patient.name", ASCENDING)], name="idx_patient_name"),
    # Statistiques par pathologie sur une période (index composé)
    IndexModel(
        [("medical.condition", ASCENDING), ("admission.admission_date", ASCENDING)],
        name="idx_condition_date",
    ),
    # Requêtes par période seule (activité mensuelle, etc.)
    IndexModel([("admission.admission_date", ASCENDING)], name="idx_admission_date"),
    # Activité par établissement
    IndexModel([("admission.hospital", ASCENDING)], name="idx_hospital"),
    # Facturation par assureur
    IndexModel([("billing.insurance_provider", ASCENDING)], name="idx_insurance"),
]
