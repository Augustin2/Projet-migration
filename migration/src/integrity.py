"""Tests d'intégrité des données, avant et après la migration."""
import logging

import pandas as pd

from .cleaning import EXPECTED_COLUMNS

log = logging.getLogger(__name__)

# Champs du document et type BSON attendu (alias $type de MongoDB)
FIELD_TYPES = {
    "patient.name": "string",
    "patient.age": "int",
    "patient.gender": "string",
    "patient.blood_type": "string",
    "admission.type": "string",
    "admission.admission_date": "date",
    "admission.discharge_date": "date",
    "admission.room_number": "int",
    "admission.hospital": "string",
    "admission.doctor": "string",
    "medical.condition": "string",
    "medical.medication": "string",
    "medical.test_results": "string",
    "billing.amount": "double",
    "billing.insurance_provider": "string",
}

# Correspondance colonne CSV -> champ MongoDB (pour comparer les valeurs)
CATEGORICAL_MAP = {
    "Gender": "patient.gender",
    "Blood Type": "patient.blood_type",
    "Admission Type": "admission.type",
    "Medical Condition": "medical.condition",
    "Medication": "medical.medication",
    "Test Results": "medical.test_results",
    "Insurance Provider": "billing.insurance_provider",
}


class IntegrityError(Exception):
    """Levée quand un contrôle post-migration échoue."""


def check_before(df: pd.DataFrame) -> dict:
    """Profil du CSV brut : colonnes, types, valeurs manquantes, doublons."""
    report = {
        "rows": len(df),
        "columns": list(df.columns),
        "missing_columns": sorted(set(EXPECTED_COLUMNS) - set(df.columns)),
        "extra_columns": sorted(set(df.columns) - set(EXPECTED_COLUMNS)),
        "dtypes": {c: str(t) for c, t in df.dtypes.items()},
        "missing_values": {c: int(n) for c, n in df.isna().sum().items() if n},
        "exact_duplicates": int(df.duplicated().sum()),
        "duplicates_ignoring_age": int(
            df.duplicated(subset=[c for c in df.columns if c != "Age"]).sum()
        ),
        "negative_billing": int((df["Billing Amount"] < 0).sum()),
    }
    # Cohérence des dates : la sortie ne peut pas précéder l'admission
    adm = pd.to_datetime(df["Date of Admission"], errors="coerce")
    dis = pd.to_datetime(df["Discharge Date"], errors="coerce")
    report["invalid_dates"] = int(adm.isna().sum() + dis.isna().sum())
    report["discharge_before_admission"] = int((dis < adm).sum())
    log.info("Contrôle AVANT migration : %s", report)
    return report


def check_after(collection, clean_df: pd.DataFrame) -> dict:
    """Compare le contenu de MongoDB au DataFrame nettoyé.

    Lève IntegrityError si un contrôle échoue.
    """
    errors = []
    report = {}

    # 1. Nombre de documents
    count = collection.count_documents({})
    report["documents"] = count
    if count != len(clean_df):
        errors.append(f"{count} documents en base pour {len(clean_df)} lignes attendues")

    # 2. Champs présents et correctement typés
    report["missing_fields"] = {}
    report["wrong_types"] = {}
    for field, bson_type in FIELD_TYPES.items():
        missing = collection.count_documents({field: {"$exists": False}})
        wrong = collection.count_documents(
            {field: {"$exists": True, "$not": {"$type": bson_type}}}
        )
        if missing:
            report["missing_fields"][field] = missing
            errors.append(f"{missing} documents sans le champ {field}")
        if wrong:
            report["wrong_types"][field] = wrong
            errors.append(f"{wrong} documents où {field} n'est pas de type {bson_type}")

    # 3. Aucun doublon (on ignore l'âge, comme au nettoyage)
    group_id = {f.replace(".", "_"): f"${f}" for f in FIELD_TYPES if f != "patient.age"}
    dup = list(collection.aggregate([
        {"$group": {"_id": group_id, "n": {"$sum": 1}}},
        {"$match": {"n": {"$gt": 1}}},
        {"$count": "groups"},
    ]))
    report["duplicate_groups"] = dup[0]["groups"] if dup else 0
    if report["duplicate_groups"]:
        errors.append(f"{report['duplicate_groups']} groupes de doublons en base")

    # 4. Valeurs catégorielles identiques à la source
    for col, field in CATEGORICAL_MAP.items():
        expected = set(clean_df[col].unique())
        actual = set(collection.distinct(field))
        if expected != actual:
            errors.append(f"{field} : valeurs {actual} au lieu de {expected}")

    # 5. Somme des montants (détecte une perte ou une altération de valeurs)
    agg = list(collection.aggregate([
        {"$group": {"_id": None, "total": {"$sum": "$billing.amount"}}}
    ]))
    total_db = round(agg[0]["total"], 2) if agg else 0.0
    total_src = round(float(clean_df["Billing Amount"].sum()), 2)
    report["billing_total_db"] = total_db
    report["billing_total_source"] = total_src
    if abs(total_db - total_src) > 0.01 * max(1, len(clean_df)):
        errors.append(f"Total facturé : {total_db} en base contre {total_src} attendu")

    report["status"] = "OK" if not errors else "ECHEC"
    report["errors"] = errors
    log.info("Contrôle APRÈS migration : %s", report)
    if errors:
        raise IntegrityError("; ".join(errors))
    return report
