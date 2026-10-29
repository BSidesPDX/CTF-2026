#!/usr/bin/env bash
set -euo pipefail

echo "🟩 Initializing application database role and schema..."

# Run psql with vars passed as --set
psql -v ON_ERROR_STOP=1 \
  --username "$POSTGRES_USER" \
  --dbname "$POSTGRES_DB" \
  --set=APP_USER="$APP_USER" \
  --set=APP_USER_PASS="$APP_USER_PASS" \
  --set=APP_SCHEMA="$APP_SCHEMA" \
  --set=PG_DB="$PG_DB" \
  -f /docker-entrypoint-initdb.d/initialize.sql.template

echo "✅ Env-driven SQL initialization complete."
