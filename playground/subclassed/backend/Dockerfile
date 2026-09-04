# Subclassed-host playground backend image. Same shape as
# ../../default/backend/Dockerfile — see that file's own header comment for the full "why
# context: .." reasoning. No django-dynamic-user[celery] here — this host proves the OTHER
# finalize path (manage.py process_deletion_requests, no Celery installed at all), so there is
# no `worker-subclassed` service in playground/docker-compose.yml.
FROM python:3.13-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.7 /uv /uvx /usr/local/bin/

WORKDIR /app

COPY backend/pyproject.toml backend/README.md backend/MANIFEST.in backend/LICENSE /app/backend/
COPY backend/src/ /app/backend/src/
COPY playground/subclassed/backend/ /app/playground/subclassed/backend/

ENV UV_PROJECT_ENVIRONMENT=/opt/venv

WORKDIR /app/playground/subclassed/backend

RUN uv sync --no-dev

ENV PATH="/opt/venv/bin:$PATH"

EXPOSE 8000

CMD ["sh", "-c", "python manage.py migrate --noinput && python manage.py seed_users && python manage.py collectstatic --noinput --clear && uvicorn config.asgi:application --host 0.0.0.0 --port 8000"]
