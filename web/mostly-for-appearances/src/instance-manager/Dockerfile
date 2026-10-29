# Install uv
FROM python:3.14-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Change the working directory to the `app` directory
WORKDIR /app

# Copy the project into the image
COPY . /app

# Sync the project
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked

# create sha for version reporting
RUN find . -type f -exec sha256sum {} \; | sort | sha256sum > /sha

EXPOSE 8080
CMD uv run gunicorn -b 0.0.0.0:8080 'server:app' \
    --access-logfile=- --error-logfile=- --log-level=info
