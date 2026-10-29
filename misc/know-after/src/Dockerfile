# SocEngLLM app image: `socengllm serve` (AudioSocket server for Asterisk) and `socengllm web`
# (transcript viewer + text test chats) run from this image as two compose services.
# Cloud backends only (Deepgram Flux/Aura, Anthropic, Jev); the Apple-silicon local models are
# optional extras that are not installed here. Silero VAD (2 MB) is fetched at build time because
# the endpointer is constructed even when Flux does the turn detection.
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.9.21 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PROJECT_ENVIRONMENT=/opt/venv PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 NO_COLOR=1 TERM=dumb COLUMNS=160
WORKDIR /app
# Dependencies first (cached until pyproject/uv.lock change), then the source.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY socengllm/ socengllm/
COPY scripts/download_models.py scripts/download_models.py
RUN uv sync --frozen --no-dev && python scripts/download_models.py silero
# config.yaml, scenarios/, sounds/, bench/ are bind-mounted by docker-compose.yml so they can be
# edited without a rebuild (restart the service to pick up changes); baked-in copies as a fallback.
COPY config.yaml ./
COPY scenarios/ scenarios/
COPY sounds/ sounds/
COPY bench/ bench/
EXPOSE 9092 8090
CMD ["socengllm", "serve"]
