"""Nettoyage du CSV et transformation des lignes en documents MongoDB."""
import logging
from datetime import datetime

import pandas as pd

log = logging.getLogger(__name__)

# Colonnes attendues dans le CSV source et leur type pandas cible
EXPECTED_COLUMNS = {
    "Name": "str",
    "Age": "int",
    "Gender": "str",
    "Blood Type": "str",
    "Medical Condition": "str",
    "Date of Admission": "date",
    "Doctor": "str",
    "Hospital": "str",
    "Insurance Provider": "str",
    "Billing Amount": "float",
    "Room Number": "int",
    "Admission Type": "str",
    "Discharge Date": "date",
    "Medication": "str",
    "Test Results": "str",
}
TEXT_COLUMNS = [c for c, t in EXPECTED_COLUMNS.items() if t == "str"]
DATE_COLUMNS = [c for c, t in EXPECTED_COLUMNS.items() if t == "date"]


def load_csv(path: str) -> pd.DataFrame:
    """Charge le CSV brut et vérifie la présence des colonnes attendues."""
    df = pd.read_csv(path)
    missing = set(EXPECTED_COLUMNS) - set(df.columns)
    if missing:
        raise ValueError(f"Colonnes manquantes dans le CSV : {sorted(missing)}")
    log.info("CSV chargé : %d lignes, %d colonnes", len(df), df.shape[1])
    return df


def clean_hospital(name: str) -> str:
    """'and Garcia Morris Cunningham,' -> 'Garcia Morris Cunningham'."""
    name = name.strip().rstrip(",").strip()
    if name.lower().startswith("and "):
        name = name[4:]
    if name.lower().endswith(" and"):
        name = name[:-4]
    return name.strip()


def clean_dataframe(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Nettoie le DataFrame et renvoie (df_propre, rapport_de_nettoyage)."""
    report = {"rows_in": len(df)}
    df = df.copy()

    # 1. Espaces parasites sur toutes les colonnes texte
    for col in TEXT_COLUMNS:
        df[col] = df[col].astype(str).str.strip()

    # 2. Normalisation de la casse ("bOBby JacksOn" -> "Bobby Jackson")
    df["Name"] = df["Name"].str.title()
    df["Doctor"] = df["Doctor"].str.title()

    # 3. Noms d'hôpitaux mal formés (virgule finale, "and" orphelin)
    df["Hospital"] = df["Hospital"].map(clean_hospital)

    # 4. Typage explicite
    for col in DATE_COLUMNS:
        df[col] = pd.to_datetime(df[col], format="%Y-%m-%d")
    df["Age"] = df["Age"].astype("int64")
    df["Room Number"] = df["Room Number"].astype("int64")
    df["Billing Amount"] = df["Billing Amount"].astype("float64").round(2)

    # 5. Doublons exacts
    before = len(df)
    df = df.drop_duplicates()
    report["exact_duplicates_removed"] = before - len(df)

    # 6. Quasi-doublons : identiques sur tout sauf l'âge -> on garde le 1er
    before = len(df)
    subset = [c for c in df.columns if c != "Age"]
    df = df.drop_duplicates(subset=subset, keep="first")
    report["age_only_duplicates_removed"] = before - len(df)

    # 7. Montants négatifs : conservés (remboursements possibles) mais comptés
    report["negative_billing_kept"] = int((df["Billing Amount"] < 0).sum())

    df = df.reset_index(drop=True)
    report["rows_out"] = len(df)
    log.info("Nettoyage : %s", report)
    return df, report


def row_to_document(row: dict) -> dict:
    """Transforme une ligne du CSV en document MongoDB imbriqué."""

    def to_dt(value) -> datetime:
        return pd.Timestamp(value).to_pydatetime()

    return {
        "patient": {
            "name": str(row["Name"]),
            "age": int(row["Age"]),
            "gender": str(row["Gender"]),
            "blood_type": str(row["Blood Type"]),
        },
        "admission": {
            "type": str(row["Admission Type"]),
            "admission_date": to_dt(row["Date of Admission"]),
            "discharge_date": to_dt(row["Discharge Date"]),
            "room_number": int(row["Room Number"]),
            "hospital": str(row["Hospital"]),
            "doctor": str(row["Doctor"]),
        },
        "medical": {
            "condition": str(row["Medical Condition"]),
            "medication": str(row["Medication"]),
            "test_results": str(row["Test Results"]),
        },
        "billing": {
            "amount": float(row["Billing Amount"]),
            "insurance_provider": str(row["Insurance Provider"]),
        },
    }


def dataframe_to_documents(df: pd.DataFrame) -> list[dict]:
    return [row_to_document(r) for r in df.to_dict(orient="records")]
