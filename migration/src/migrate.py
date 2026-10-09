"""Script principal : migration du CSV vers MongoDB.

Étapes :
  1. Chargement du CSV et contrôle d'intégrité AVANT migration
  2. Nettoyage (casse, doublons, typage)
  3. (Re)création de la collection avec un validateur $jsonSchema
  4. Insertion par lots
  5. Création des index
  6. Contrôle d'intégrité APRÈS migration + rapport JSON

Usage :
    python -m src.migrate
"""
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone

from pymongo import MongoClient
from pymongo.errors import PyMongoError

from . import config
from .cleaning import clean_dataframe, dataframe_to_documents, load_csv
from .integrity import IntegrityError, check_after, check_before
from .schema import ADMISSION_VALIDATOR, INDEXES

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
)
log = logging.getLogger("migration")


def prepare_collection(db, name: str, use_validator: bool = True):
    """Supprime puis recrée la collection : la migration est rejouable
    sans créer de doublons (idempotente)."""
    if name in db.list_collection_names():
        log.info("Collection '%s' existante : suppression", name)
        db.drop_collection(name)
    if use_validator:
        db.create_collection(name, validator=ADMISSION_VALIDATOR,
                             validationLevel="strict", validationAction="error")
    else:
        db.create_collection(name)
    return db[name]


def insert_in_batches(collection, documents: list[dict], batch_size: int) -> int:
    inserted = 0
    for start in range(0, len(documents), batch_size):
        batch = documents[start:start + batch_size]
        result = collection.insert_many(batch, ordered=False)
        inserted += len(result.inserted_ids)
        log.info("Lot inséré : %d/%d documents", inserted, len(documents))
    return inserted


def run_migration(db, csv_path: str, collection_name: str,
                  batch_size: int = 5000, use_validator: bool = True) -> dict:
    """Exécute toute la migration sur la base `db`. Renvoie le rapport."""
    started = time.perf_counter()

    raw = load_csv(csv_path)
    before = check_before(raw)

    clean, cleaning_report = clean_dataframe(raw)
    documents = dataframe_to_documents(clean)

    collection = prepare_collection(db, collection_name, use_validator)
    inserted = insert_in_batches(collection, documents, batch_size)

    collection.create_indexes(INDEXES)
    log.info("Index créés : %s", [i.document["name"] for i in INDEXES])

    after = check_after(collection, clean)

    return {
        "date": datetime.now(timezone.utc).isoformat(),
        "source": csv_path,
        "collection": collection_name,
        "inserted": inserted,
        "duration_s": round(time.perf_counter() - started, 2),
        "before": before,
        "cleaning": cleaning_report,
        "after": after,
    }


def main() -> int:
    log.info("Connexion à MongoDB (%s:%s, base '%s', utilisateur '%s')",
             config.MONGO_HOST, config.MONGO_PORT, config.MONGO_DB, config.MONGO_USER)
    client = MongoClient(config.mongo_uri(), serverSelectionTimeoutMS=10000)
    try:
        client.admin.command("ping")
        db = client[config.MONGO_DB]
        report = run_migration(db, config.CSV_PATH, config.COLLECTION, config.BATCH_SIZE)
    except IntegrityError as exc:
        log.error("Contrôle d'intégrité en échec : %s", exc)
        return 2
    except (PyMongoError, FileNotFoundError, ValueError) as exc:
        log.error("Migration interrompue : %s", exc)
        return 1
    finally:
        client.close()

    os.makedirs(config.EXPORT_DIR, exist_ok=True)
    path = os.path.join(config.EXPORT_DIR, "migration_report.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False, default=str)
    log.info("Migration terminée : %d documents en %ss. Rapport : %s",
             report["inserted"], report["duration_s"], path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
