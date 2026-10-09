"""Configuration centralisée, lue depuis les variables d'environnement.

Aucun secret n'est écrit dans le code : en local, les valeurs viennent du
fichier .env (via python-dotenv) ; dans Docker, de la section `environment`
du docker-compose.yml.
"""
import os
from urllib.parse import quote_plus

from dotenv import load_dotenv

load_dotenv()  # sans effet si aucun .env n'est présent (cas du conteneur)

MONGO_HOST = os.getenv("MONGO_HOST", "localhost")
MONGO_PORT = int(os.getenv("MONGO_PORT", "27017"))
MONGO_DB = os.getenv("MONGO_DB", "healthcare")
MONGO_USER = os.getenv("MONGO_USER", "migration_user")
MONGO_PASSWORD = os.getenv("MONGO_PASSWORD", os.getenv("MIGRATION_PASSWORD", ""))

COLLECTION = os.getenv("MONGO_COLLECTION", "admissions")
CSV_PATH = os.getenv("CSV_PATH", "data/healthcare_dataset.csv")
EXPORT_DIR = os.getenv("EXPORT_DIR", "exports")
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "5000"))


def mongo_uri() -> str:
    """Construit l'URI de connexion.

    quote_plus() encode les caractères spéciaux du mot de passe (@, :, /, #...)
    qui casseraient sinon l'URI.
    """
    user = quote_plus(MONGO_USER)
    pwd = quote_plus(MONGO_PASSWORD)
    return (
        f"mongodb://{user}:{pwd}@{MONGO_HOST}:{MONGO_PORT}/{MONGO_DB}"
        f"?authSource={MONGO_DB}"
    )
