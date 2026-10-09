FROM python:3.12-slim

# Pas de fichiers .pyc, logs affichés immédiatement
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Dépendances d'abord : cette couche reste en cache tant que
# requirements.txt ne change pas
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY pytest.ini .
COPY src/ src/
COPY tests/ tests/

# Le script ne tourne pas en root
RUN useradd --create-home appuser && mkdir -p /app/exports && chown appuser /app/exports
USER appuser

CMD ["python", "-m", "src.migrate"]
