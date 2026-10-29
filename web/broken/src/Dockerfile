FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

RUN groupadd --system --gid 999 broken \
 && useradd --system --gid 999 --uid 999 --create-home broken

COPY . /opt/challenge/
WORKDIR /opt/challenge/

RUN uv sync --locked --no-dev \
 && mkdir -p data \
 && uv run setup.py \
 && chmod 777 data \
 && chmod 666 data/app.db

USER broken

EXPOSE 8000/tcp

CMD ["uv", "run", "--locked", "--no-dev", "fastapi", "run", "main.py"]
