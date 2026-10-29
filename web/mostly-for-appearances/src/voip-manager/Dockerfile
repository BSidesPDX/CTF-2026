FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DB_PATH=/app/data/app.db

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential python3-dev tini \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml /app/
# No uv.lock yet, let it generate or just sync
RUN uv sync

COPY . /app

RUN uv run python /app/bootstrap_users.py

EXPOSE 8000

CMD uv run gunicorn -b 0.0.0.0:8000 "app:create_app()" \
    --access-logfile=- --error-logfile=- --log-level=info
