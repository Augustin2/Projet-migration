"""Export de l'ensemble de la collection en JSON (format natif MongoDB)
et en CSV (format à plat, comparable au fichier source).

Usage :
    python -m src.export_data
"""
import logging
import os

import pandas as pd
from bson import json_util
from pymongo import MongoClient

from . import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(message)s")
log = logging.getLogger("export")


def export_collection(col, out_dir: str) -> tuple[str, str]:
    os.makedirs(out_dir, exist_ok=True)
    docs = list(col.find({}, {"_id": 0}))

    json_path = os.path.join(out_dir, "admissions.json")
    with open(json_path, "w", encoding="utf-8") as f:
        f.write(json_util.dumps(docs, indent=1))  # conserve les types (dates...)

    csv_path = os.path.join(out_dir, "admissions.csv")
    pd.json_normalize(docs).to_csv(csv_path, index=False)  # patient.name, ...

    log.info("%d documents exportés -> %s et %s", len(docs), json_path, csv_path)
    return json_path, csv_path


def main() -> None:
    client = MongoClient(config.mongo_uri(), serverSelectionTimeoutMS=10000)
    try:
        export_collection(client[config.MONGO_DB][config.COLLECTION], config.EXPORT_DIR)
    finally:
        client.close()


if __name__ == "__main__":
    main()
