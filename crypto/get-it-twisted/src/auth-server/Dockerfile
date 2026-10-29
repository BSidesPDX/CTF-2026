ARG PYTHON_VERSION=3.15
FROM python:${PYTHON_VERSION}-alpine AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
# Use copy mode since the cache and build filesystem are on different volumes.
ENV UV_LINK_MODE=copy

# Prevent Python from writing .pyc files to disk.
ENV PYTHONDONTWRITEBYTECODE=1
# Prevent Python from buffering stdout/stderr so logs appear immediately.
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies into the uv venv using cache and bind mounts so neither
# uv nor the lock files need to be copied into the image.
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-managed-python

# ------

# Development image for local docker-compose development. Intended to be used
# with Compose Watch for dev server hot-reload.
FROM builder AS development

ENV PATH="/app/.venv/bin:$PATH"

COPY . .

# Default to bctf app but allow overriding for bctf-api via envvar.
ARG PORT=8000
ENV PORT=${PORT}

EXPOSE ${PORT}

CMD python manage.py runserver --settings "twistedauth.settings" "0.0.0.0:${PORT}"

# ------

# Production image using proper gunicorn WSGI.
FROM python:${PYTHON_VERSION}-alpine AS production

# Prevent Python from buffering stdout/stderr so logs appear immediately.
ENV PYTHONUNBUFFERED=1
# Activate the virtual environment copied from the build stage.
ENV PATH="/app/.venv/bin:$PATH"

# Run production as a non-root user
RUN addgroup -g 1000 nonroot && \
    adduser -u 1000 -G nonroot -D nonroot

# USER before WORKDIR means the directory is created with the proper non-root
# ownership.
USER nonroot
WORKDIR /app

# Copy only the pre-built venv and app source files.
COPY --from=builder /app/.venv /app/.venv
COPY . .

# Default to bctf app but allow overriding for bctf-api via envvar.
ARG PORT=8000
ENV PORT=${PORT}

EXPOSE ${PORT}

# Run Gunicorn as the production WSGI server.
CMD gunicorn "twistedauth.wsgi" --bind "0.0.0.0:${PORT}" \
    --access-logfile '-' --error-logfile '-' \
    --proxy-protocol auto --chdir /app/twistedauth